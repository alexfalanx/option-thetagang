"""
Strategy selector for ThetaGangExpanded.

Dynamically selects the best strategy based on market conditions.
Supports multi-strategy portfolios with allocation management.
"""

import logging
from typing import List, Optional, Dict
from enum import Enum

from src.strategy_base import Strategy, StrategyType
from src.core_strategy import WheelStrategy
from src.iron_condor_strategy import IronCondorStrategy
from src.config_loader import SymbolConfig, StrategyConfig
from src.data_fetcher import Position

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


class StrategySelector:
    """
    Selects appropriate trading strategies based on market conditions.

    Supports:
    - Single strategy mode (use one strategy exclusively)
    - Multi-strategy mode (allocate portfolio across strategies)
    - Dynamic switching based on market regime
    - Manual override for specific symbols
    """

    def __init__(
        self,
        strategy_config: StrategyConfig,
        symbol_configs: Dict[str, SymbolConfig]
    ):
        """
        Initialize strategy selector.

        Args:
            strategy_config: Global strategy configuration
            symbol_configs: Per-symbol configurations
        """
        self.config = strategy_config
        self.symbol_configs = symbol_configs

    def get_strategies_for_symbol(
        self,
        symbol: str,
        stock_price: float,
        volatility: Optional[float] = None,
        trend: Optional[str] = None
    ) -> List[Strategy]:
        """
        Get list of strategies to use for a symbol.

        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            volatility: Current implied volatility
            trend: Market trend indicator

        Returns:
            List of strategy instances to use
        """
        if symbol not in self.symbol_configs:
            logger.warning(f"No configuration for {symbol}")
            return []

        symbol_config = self.symbol_configs[symbol]
        strategies = []

        # Check which strategies are enabled
        if self.config.wheel_enabled:
            wheel = WheelStrategy(symbol_config)
            if wheel.is_compatible_with(stock_price, volatility, trend):
                strategies.append(wheel)
                logger.debug(f"{symbol}: Wheel strategy is compatible")

        if self.config.iron_condor_enabled:
            iron_condor = IronCondorStrategy(symbol_config)
            if iron_condor.is_compatible_with(stock_price, volatility, trend):
                strategies.append(iron_condor)
                logger.debug(f"{symbol}: Iron Condor strategy is compatible")

        # Future strategies
        if self.config.strangle_enabled:
            logger.debug(f"{symbol}: Strangle strategy not yet implemented")

        if not strategies:
            logger.warning(f"{symbol}: No compatible strategies found")

        return strategies

    def select_best_strategy(
        self,
        symbol: str,
        stock_price: float,
        volatility: Optional[float] = None,
        trend: Optional[str] = None,
        existing_positions: Optional[List[Position]] = None
    ) -> Optional[Strategy]:
        """
        Select the single best strategy for current conditions.

        Uses a decision tree based on market regime:
        - Bullish trend + low vol → Wheel (sell puts)
        - Neutral trend + low vol → Iron Condor
        - High volatility → Prefer premium collection (Wheel)
        - Existing positions → Continue with same strategy

        Args:
            symbol: Stock symbol
            stock_price: Current stock price
            volatility: Current implied volatility
            trend: Market trend indicator
            existing_positions: Current positions for continuity

        Returns:
            Best strategy instance
        """
        if symbol not in self.symbol_configs:
            return None

        symbol_config = self.symbol_configs[symbol]

        # Check for existing positions to maintain strategy continuity
        if existing_positions:
            existing_strategy = self._detect_current_strategy(existing_positions)
            if existing_strategy:
                logger.info(f"{symbol}: Continuing with {existing_strategy.value} strategy")

                if existing_strategy == StrategyType.WHEEL and self.config.wheel_enabled:
                    return WheelStrategy(symbol_config)
                elif existing_strategy == StrategyType.IRON_CONDOR and self.config.iron_condor_enabled:
                    return IronCondorStrategy(symbol_config)

        # Determine market regime
        regime = self._classify_market_regime(volatility, trend)
        logger.debug(f"{symbol}: Market regime = {regime.value if regime else 'unknown'}")

        # Select strategy based on regime
        if regime == MarketRegime.NEUTRAL and volatility and volatility < 0.25:
            # Neutral + low vol → Iron Condor
            if self.config.iron_condor_enabled:
                logger.info(f"{symbol}: Selected Iron Condor (neutral, low vol)")
                return IronCondorStrategy(symbol_config)

        if regime in [MarketRegime.BULLISH, MarketRegime.BEARISH]:
            # Directional trend → Wheel
            if self.config.wheel_enabled:
                logger.info(f"{symbol}: Selected Wheel ({regime.value} trend)")
                return WheelStrategy(symbol_config)

        if regime == MarketRegime.HIGH_VOLATILITY:
            # High vol → Wheel for premium collection
            if self.config.wheel_enabled:
                logger.info(f"{symbol}: Selected Wheel (high volatility)")
                return WheelStrategy(symbol_config)

        # Default to Wheel if enabled
        if self.config.wheel_enabled:
            logger.info(f"{symbol}: Defaulting to Wheel strategy")
            return WheelStrategy(symbol_config)

        logger.warning(f"{symbol}: No strategy selected")
        return None

    def allocate_strategies(
        self,
        symbols: List[str],
        market_data: Dict[str, Dict]
    ) -> Dict[str, List[Strategy]]:
        """
        Allocate strategies across multiple symbols for portfolio diversification.

        Example allocation:
        - 60% in Wheel strategies (directional/premium collection)
        - 40% in Iron Condors (neutral/range-bound)

        Args:
            symbols: List of symbols to trade
            market_data: Dictionary of market data per symbol
                        {symbol: {'price': float, 'volatility': float, 'trend': str}}

        Returns:
            Dictionary mapping symbols to list of strategies
        """
        allocation = {}

        for symbol in symbols:
            if symbol not in market_data:
                continue

            data = market_data[symbol]
            strategies = self.get_strategies_for_symbol(
                symbol,
                data.get('price', 0.0),
                data.get('volatility'),
                data.get('trend')
            )

            if strategies:
                allocation[symbol] = strategies

        return allocation

    def _detect_current_strategy(
        self,
        positions: List[Position]
    ) -> Optional[StrategyType]:
        """
        Detect which strategy is currently being used based on positions.

        Args:
            positions: Current positions for a symbol

        Returns:
            Detected strategy type or None
        """
        # Check for stock position (indicates Wheel)
        has_stock = any(p.position_type == 'stock' for p in positions)
        if has_stock:
            return StrategyType.WHEEL

        # Check for single short put or call (Wheel)
        option_positions = [p for p in positions if p.position_type == 'option']
        if len(option_positions) == 1:
            return StrategyType.WHEEL

        # Check for Iron Condor pattern (4 legs)
        if len(option_positions) == 4:
            puts = [p for p in option_positions if p.right == 'P']
            calls = [p for p in option_positions if p.right == 'C']

            if len(puts) == 2 and len(calls) == 2:
                # Likely an iron condor
                return StrategyType.IRON_CONDOR

        return None

    def _classify_market_regime(
        self,
        volatility: Optional[float],
        trend: Optional[str]
    ) -> Optional[MarketRegime]:
        """
        Classify market regime based on volatility and trend.

        Args:
            volatility: Implied volatility (e.g., 0.25 = 25%)
            trend: Trend indicator ('bullish', 'bearish', 'neutral')

        Returns:
            Market regime classification
        """
        # Volatility-based classification
        if volatility:
            if volatility > 0.35:
                return MarketRegime.HIGH_VOLATILITY
            elif volatility < 0.20:
                return MarketRegime.LOW_VOLATILITY

        # Trend-based classification
        if trend:
            if trend.lower() == 'bullish':
                return MarketRegime.BULLISH
            elif trend.lower() == 'bearish':
                return MarketRegime.BEARISH
            elif trend.lower() == 'neutral':
                return MarketRegime.NEUTRAL

        # Default to neutral if insufficient data
        return MarketRegime.NEUTRAL

    def get_strategy_statistics(
        self,
        positions: List[Position]
    ) -> Dict[str, int]:
        """
        Get statistics on which strategies are currently active.

        Args:
            positions: All positions across portfolio

        Returns:
            Dictionary of strategy counts
        """
        stats = {
            'wheel': 0,
            'iron_condor': 0,
            'other': 0
        }

        # Group positions by symbol
        by_symbol = {}
        for pos in positions:
            if pos.symbol not in by_symbol:
                by_symbol[pos.symbol] = []
            by_symbol[pos.symbol].append(pos)

        # Detect strategy for each symbol
        for symbol, symbol_positions in by_symbol.items():
            strategy_type = self._detect_current_strategy(symbol_positions)

            if strategy_type == StrategyType.WHEEL:
                stats['wheel'] += 1
            elif strategy_type == StrategyType.IRON_CONDOR:
                stats['iron_condor'] += 1
            else:
                stats['other'] += 1

        return stats


def main():
    """Example usage of StrategySelector."""

    logging.basicConfig(level=logging.DEBUG)

    from src.config_loader import SymbolConfig, StrategyConfig

    # Create configurations
    strategy_config = StrategyConfig(
        wheel_enabled=True,
        iron_condor_enabled=True,
        strangle_enabled=False
    )

    symbol_configs = {
        'SPY': SymbolConfig(symbol='SPY', enabled=True, max_positions=2),
        'QQQ': SymbolConfig(symbol='QQQ', enabled=True, max_positions=1)
    }

    selector = StrategySelector(strategy_config, symbol_configs)

    # Test strategy selection
    print("Test 1: Neutral trend, low vol (should pick Iron Condor)")
    strategy = selector.select_best_strategy('SPY', 450.0, 0.18, 'neutral')
    print(f"Selected: {strategy.get_strategy_type() if strategy else 'None'}\n")

    print("Test 2: Bullish trend (should pick Wheel)")
    strategy = selector.select_best_strategy('SPY', 450.0, 0.25, 'bullish')
    print(f"Selected: {strategy.get_strategy_type() if strategy else 'None'}\n")

    print("Test 3: High volatility (should pick Wheel)")
    strategy = selector.select_best_strategy('SPY', 450.0, 0.45, 'neutral')
    print(f"Selected: {strategy.get_strategy_type() if strategy else 'None'}\n")

    print("Test 4: Get all compatible strategies for SPY")
    strategies = selector.get_strategies_for_symbol('SPY', 450.0, 0.20, 'neutral')
    print(f"Compatible strategies: {[s.get_strategy_type().value for s in strategies]}")


if __name__ == '__main__':
    main()
