"""
Main orchestrator for ThetaGangExpanded.

Coordinates all modules to run the automated trading bot:
- Loads configuration
- Connects to IBKR
- Fetches market data
- Runs strategy analysis
- Validates trades with risk manager
- Executes approved trades
- Handles scheduling
"""

import logging
import asyncio
import sys
from datetime import datetime, time as dt_time
from typing import List
import schedule

from ib_async import IB, util

from src.config_loader import load_config, Config
from src.data_fetcher import DataFetcher
from src.strategy_base import TradeRecommendation
from src.strategy_selector import StrategySelector
from src.risk_manager import RiskManager
from src.order_executor import OrderExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/thetagang.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class ThetaGangBot:
    """
    Main bot orchestrator.

    Coordinates all components to execute trading strategies:
    1. Fetch market data and positions
    2. Select appropriate strategy per symbol
    3. Run strategy analysis
    4. Validate trades against risk limits
    5. Execute approved trades
    6. Monitor positions for rolling/closing
    """

    def __init__(self, config: Config):
        """
        Initialize the bot with configuration.

        Args:
            config: Loaded configuration object
        """
        self.config = config
        self.data_fetcher: Optional[DataFetcher] = None
        self.risk_manager: Optional[RiskManager] = None
        self.order_executor: Optional[OrderExecutor] = None
        self.strategy_selector: Optional[StrategySelector] = None
        self.ib: Optional[IB] = None

        self._setup_logging()
        self._initialize_strategy_selector()

    def _setup_logging(self):
        """Configure logging based on config."""
        log_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)

        logger.info("ThetaGangExpanded Bot Initialized")
        logger.info(f"Dry run mode: {self.config.dry_run}")
        logger.info(f"Number of symbols: {len(self.config.symbols)}")

    def _initialize_strategy_selector(self):
        """Initialize strategy selector for dynamic strategy selection."""
        self.strategy_selector = StrategySelector(
            strategy_config=self.config.strategy,
            symbol_configs=self.config.symbols
        )

        enabled_strategies = []
        if self.config.strategy.wheel_enabled:
            enabled_strategies.append("Wheel")
        if self.config.strategy.iron_condor_enabled:
            enabled_strategies.append("IronCondor")
        if self.config.strategy.strangle_enabled:
            enabled_strategies.append("Strangle")

        logger.info(f"Enabled strategies: {', '.join(enabled_strategies)}")

    async def connect(self):
        """Connect to IBKR and initialize components."""
        logger.info("Connecting to IBKR...")

        # Initialize IB connection
        self.ib = IB()

        try:
            await self.ib.connectAsync(
                host=self.config.account.host,
                port=self.config.account.port,
                clientId=self.config.account.client_id,
                timeout=30
            )

            logger.info(f"Connected to IBKR at {self.config.account.host}:{self.config.account.port}")

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            raise

        # Initialize data fetcher
        self.data_fetcher = DataFetcher(
            host=self.config.account.host,
            port=self.config.account.port,
            client_id=self.config.account.client_id
        )
        self.data_fetcher.ib = self.ib
        self.data_fetcher._connected = True

        # Initialize risk manager
        self.risk_manager = RiskManager(
            risk_config=self.config.risk,
            symbol_configs=self.config.symbols
        )

        # Initialize order executor
        self.order_executor = OrderExecutor(
            ib=self.ib,
            dry_run=self.config.dry_run
        )

        logger.info("All components initialized")

    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")

    async def run_once(self):
        """
        Run one iteration of the trading logic.

        This is the main trading loop that:
        1. Fetches current market data
        2. Gets current positions
        3. Runs strategy for each symbol
        4. Validates trades with risk manager
        5. Executes approved trades
        """
        logger.info("=" * 60)
        logger.info("Starting trading cycle")
        logger.info("=" * 60)

        try:
            # Get account info
            account_info = await self.data_fetcher.get_account_info(
                self.config.account.account_number
            )

            logger.info(f"Account: {account_info.account_number}")
            logger.info(f"Net Liquidation: ${account_info.net_liquidation:,.2f}")
            logger.info(f"Buying Power: ${account_info.buying_power:,.2f}")

            # Get all current positions
            all_positions = await self.data_fetcher.get_positions()
            logger.info(f"Current positions: {len(all_positions)}")

            # Get VIX for risk checks
            vix = await self.data_fetcher.get_vix()
            if vix:
                logger.info(f"VIX: {vix:.2f}")

            # Calculate portfolio risk
            portfolio_risk = self.risk_manager.calculate_portfolio_risk(
                all_positions,
                account_info
            )

            logger.info(f"Portfolio: {portfolio_risk.total_positions} positions, "
                       f"margin usage: {portfolio_risk.margin_usage_percent:.1%}")

            # Process each enabled symbol
            all_recommendations = []

            for symbol, symbol_config in self.config.symbols.items():
                if not symbol_config.enabled:
                    continue

                logger.info(f"\nAnalyzing {symbol}...")

                try:
                    # Get current stock price
                    stock_price = await self.data_fetcher.get_stock_price(symbol)
                    logger.info(f"{symbol} price: ${stock_price:.2f}")

                    # Get historical volatility for strategy selection
                    volatility = await self.data_fetcher.get_historical_volatility(symbol, days=30)

                    # Get options chain
                    options_chain = await self.data_fetcher.get_options_chain(
                        symbol,
                        min_dte=symbol_config.dte_min,
                        max_dte=symbol_config.dte_max
                    )

                    logger.info(f"Retrieved {len(options_chain)} options for {symbol}")

                    # Get positions for this symbol
                    symbol_positions = [p for p in all_positions if p.symbol == symbol]

                    # Select best strategy for current market conditions
                    strategy = self.strategy_selector.select_best_strategy(
                        symbol,
                        stock_price,
                        volatility,
                        trend='neutral',  # Could be enhanced with trend detection
                        existing_positions=symbol_positions
                    )

                    if not strategy:
                        logger.warning(f"{symbol}: No suitable strategy selected")
                        continue

                    logger.info(f"{symbol}: Using {strategy.get_strategy_type().value} strategy")

                    # Run strategy analysis
                    recommendations = strategy.analyze(
                        stock_price,
                        options_chain,
                        symbol_positions,
                        account_info
                    )

                    logger.info(f"{symbol}: {len(recommendations)} recommendations")

                    for rec in recommendations:
                        logger.info(f"  - {rec.action.value} ({rec.strategy_type.value}): {rec.reasoning}")

                    all_recommendations.extend(recommendations)

                except Exception as e:
                    logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
                    continue

            # Validate and execute trades
            logger.info(f"\nValidating {len(all_recommendations)} total recommendations")

            for rec in all_recommendations:
                # Validate with risk manager
                risk_result = self.risk_manager.validate_trade(
                    rec,
                    all_positions,
                    account_info,
                    vix
                )

                if risk_result.approved:
                    logger.info(f"✓ Trade approved: {rec.action.value} {rec.symbol}")

                    # Adjust quantity if needed
                    if risk_result.adjusted_quantity:
                        logger.info(f"  Adjusting quantity: {rec.quantity} -> {risk_result.adjusted_quantity}")
                        rec.quantity = risk_result.adjusted_quantity

                    # Execute trade
                    order = await self.order_executor.execute_recommendation(rec)

                    if order:
                        logger.info(f"  Order submitted: ID={order.order_id}")
                    else:
                        logger.warning(f"  Failed to execute trade")

                else:
                    logger.warning(f"✗ Trade rejected: {rec.action.value} {rec.symbol}")
                    for reason in risk_result.reasons:
                        logger.warning(f"  - {reason}")

            # Get order statistics
            stats = self.order_executor.get_order_statistics()
            logger.info(f"\nOrder statistics: {stats}")

            logger.info("=" * 60)
            logger.info("Trading cycle complete")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)

    def should_trade_now(self) -> bool:
        """
        Check if we should trade based on current time and schedule.

        Returns:
            True if within trading hours and on trading day
        """
        now = datetime.now()

        # Check day of week
        if now.weekday() not in self.config.schedule.trading_days:
            logger.debug(f"Not a trading day (day {now.weekday()})")
            return False

        # Check time of day (UTC)
        current_hour = now.hour

        if current_hour < self.config.schedule.trading_start_hour:
            logger.debug(f"Before trading hours (current: {current_hour}, start: {self.config.schedule.trading_start_hour})")
            return False

        if current_hour >= self.config.schedule.trading_end_hour:
            logger.debug(f"After trading hours (current: {current_hour}, end: {self.config.schedule.trading_end_hour})")
            return False

        return True

    async def run_scheduled(self):
        """Run the bot on a schedule."""
        logger.info("Starting scheduled mode")
        logger.info(f"Run every: {self.config.schedule.run_every_minutes} minutes")
        logger.info(f"Trading hours: {self.config.schedule.trading_start_hour}:00 - {self.config.schedule.trading_end_hour}:00 UTC")
        logger.info(f"Trading days: {self.config.schedule.trading_days}")

        # Run immediately if configured
        if self.config.schedule.run_on_startup and self.should_trade_now():
            logger.info("Running on startup")
            await self.run_once()

        # Schedule periodic runs
        while True:
            if self.should_trade_now():
                await self.run_once()

            # Sleep until next scheduled run
            await asyncio.sleep(self.config.schedule.run_every_minutes * 60)


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("ThetaGangExpanded - Automated Options Trading Bot")
    logger.info("=" * 60)

    # Load configuration
    try:
        config = load_config(
            config_path="configs/thetagang.toml",
            env_path=".env"
        )
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Create bot
    bot = ThetaGangBot(config)

    # Connect to IBKR
    try:
        await bot.connect()
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        sys.exit(1)

    try:
        # Run scheduled or once
        if len(sys.argv) > 1 and sys.argv[1] == '--once':
            logger.info("Running in single-shot mode")
            await bot.run_once()
        else:
            logger.info("Running in scheduled mode")
            await bot.run_scheduled()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    finally:
        await bot.disconnect()
        logger.info("Shutdown complete")


if __name__ == '__main__':
    # Use ib_async's event loop
    util.startLoop()
    asyncio.run(main())
