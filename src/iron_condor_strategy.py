"""
Iron Condor strategy implementation for ThetaGangExpanded.

The Iron Condor is a neutral options strategy that profits from low volatility
and range-bound markets. It consists of four legs:
1. Sell OTM put (collect premium)
2. Buy further OTM put (limit downside risk)
3. Sell OTM call (collect premium)
4. Buy further OTM call (limit upside risk)

Ideal for stocks trading in a range with low implied volatility.
"""

import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

from src.strategy_base import Strategy, StrategyType, Action, TradeRecommendation
from src.data_fetcher import OptionChainData, Position, AccountInfo
from src.config_loader import SymbolConfig

logger = logging.getLogger(__name__)


class IronCondorStrategy(Strategy):
    """
    Implements the Iron Condor options strategy.

    The strategy:
    1. Identify range-bound market conditions
    2. Sell OTM put spread and OTM call spread simultaneously
    3. Collect net credit from all four legs
    4. Manage based on P&L and DTE
    5. Close or roll when profit target hit or approaching expiration
    """

    def __init__(self, config: SymbolConfig):
        """
        Initialize Iron Condor strategy.

        Args:
            config: Symbol-specific configuration
        """
        super().__init__(config)

        # Iron Condor specific parameters
        # These should come from config in future iterations
        self.wing_width = 5.0  # Width of each spread (e.g., $5)
        self.min_credit = 1.0  # Minimum total credit to collect
        self.profit_target_percent = 50.0  # Close at 50% profit
        self.max_loss_percent = 200.0  # Close if loss > 200% of credit
        self.adjustment_threshold = 0.10  # Adjust if tested within 10% of strikes

    def get_strategy_type(self) -> StrategyType:
        """Return strategy type identifier."""
        return StrategyType.IRON_CONDOR

    def is_compatible_with(
        self,
        stock_price: float,
        volatility: Optional[float] = None,
        trend: Optional[str] = None
    ) -> bool:
        """
        Iron Condor works best in low volatility, range-bound markets.

        Args:
            stock_price: Current stock price
            volatility: Current implied volatility
            trend: Market trend indicator

        Returns:
            True if conditions are favorable for Iron Condor
        """
        # Prefer neutral trends
        if trend and trend != 'neutral':
            logger.debug(f"{self.symbol}: Iron Condor prefers neutral trends, got {trend}")
            return False

        # Prefer lower volatility (< 30% IV)
        if volatility and volatility > 0.30:
            logger.debug(f"{self.symbol}: Iron Condor prefers low volatility, IV={volatility:.2%}")
            return False

        return True

    def analyze(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        positions: List[Position],
        account_info: AccountInfo
    ) -> List[TradeRecommendation]:
        """
        Analyze current state and generate Iron Condor trade recommendations.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            positions: Current positions for this symbol
            account_info: Account balance and buying power

        Returns:
            List of trade recommendations
        """
        recommendations = []

        if not self.config.enabled:
            logger.debug(f"{self.symbol} is disabled, skipping")
            return recommendations

        # Identify existing iron condor positions
        ic_positions = self._identify_iron_condor_positions(positions)

        # Check existing positions for management
        for ic_pos in ic_positions:
            rec = self._check_iron_condor_position(
                ic_pos,
                stock_price,
                options_chain
            )
            if rec:
                recommendations.append(rec)

        # Check if we should open new iron condor
        if len(ic_positions) < self.config.max_positions:
            rec = self._find_new_iron_condor(
                stock_price,
                options_chain,
                account_info
            )
            if rec:
                recommendations.append(rec)

        return recommendations

    def _identify_iron_condor_positions(
        self,
        positions: List[Position]
    ) -> List[Dict]:
        """
        Identify existing iron condor positions from portfolio.

        An iron condor has 4 legs:
        - Long put (far OTM)
        - Short put (OTM)
        - Short call (OTM)
        - Long call (far OTM)

        Args:
            positions: Current positions

        Returns:
            List of iron condor position groups
        """
        iron_condors = []

        # Get option positions
        option_positions = [p for p in positions if p.position_type == 'option']

        # Group by expiration
        by_expiration = {}
        for pos in option_positions:
            if pos.expiration:
                exp_key = pos.expiration.date()
                if exp_key not in by_expiration:
                    by_expiration[exp_key] = []
                by_expiration[exp_key].append(pos)

        # Look for iron condor pattern in each expiration
        for exp_date, exp_positions in by_expiration.items():
            puts = [p for p in exp_positions if p.right == 'P']
            calls = [p for p in exp_positions if p.right == 'C']

            # Need 2 puts and 2 calls for an iron condor
            if len(puts) == 2 and len(calls) == 2:
                # Check for short put + long put spread
                puts_sorted = sorted(puts, key=lambda p: p.strike)
                short_put = puts_sorted[1] if puts_sorted[1].quantity < 0 else puts_sorted[0]
                long_put = puts_sorted[0] if puts_sorted[0].quantity > 0 else puts_sorted[1]

                # Check for short call + long call spread
                calls_sorted = sorted(calls, key=lambda p: p.strike)
                short_call = calls_sorted[0] if calls_sorted[0].quantity < 0 else calls_sorted[1]
                long_call = calls_sorted[1] if calls_sorted[1].quantity > 0 else calls_sorted[0]

                # Verify it's actually an iron condor pattern
                if (short_put.quantity < 0 and long_put.quantity > 0 and
                    short_call.quantity < 0 and long_call.quantity > 0):

                    iron_condors.append({
                        'expiration': exp_date,
                        'long_put': long_put,
                        'short_put': short_put,
                        'short_call': short_call,
                        'long_call': long_call
                    })

        logger.debug(f"Found {len(iron_condors)} iron condor positions")
        return iron_condors

    def _check_iron_condor_position(
        self,
        ic_position: Dict,
        stock_price: float,
        options_chain: List[OptionChainData]
    ) -> Optional[TradeRecommendation]:
        """
        Check if an existing iron condor should be managed.

        Args:
            ic_position: Iron condor position dict
            stock_price: Current stock price
            options_chain: Available options

        Returns:
            Trade recommendation if action needed
        """
        exp_date = ic_position['expiration']
        dte = (exp_date - datetime.now().date()).days

        # Calculate P&L
        total_credit = (
            abs(ic_position['short_put'].avg_cost) +
            abs(ic_position['short_call'].avg_cost)
        )
        total_debit = (
            abs(ic_position['long_put'].avg_cost) +
            abs(ic_position['long_call'].avg_cost)
        )
        entry_credit = total_credit - total_debit

        current_value = (
            abs(ic_position['short_put'].market_value) +
            abs(ic_position['short_call'].market_value) +
            abs(ic_position['long_put'].market_value) +
            abs(ic_position['long_call'].market_value)
        )

        profit = entry_credit - current_value
        profit_pct = (profit / entry_credit * 100) if entry_credit > 0 else 0

        logger.debug(f"{self.symbol} Iron Condor: DTE={dte}, P&L={profit_pct:.1f}%")

        # Close for profit
        if profit_pct >= self.profit_target_percent:
            return TradeRecommendation(
                action=Action.CLOSE_IRON_CONDOR,
                symbol=self.symbol,
                quantity=abs(ic_position['short_put'].quantity),
                strategy_type=StrategyType.IRON_CONDOR,
                long_put_strike=ic_position['long_put'].strike,
                short_put_strike=ic_position['short_put'].strike,
                short_call_strike=ic_position['short_call'].strike,
                long_call_strike=ic_position['long_call'].strike,
                expiration=datetime.combine(exp_date, datetime.min.time()),
                reasoning=f"Close iron condor for {profit_pct:.1f}% profit (target {self.profit_target_percent}%)"
            )

        # Close for loss
        loss_pct = abs(profit_pct) if profit_pct < 0 else 0
        if loss_pct >= self.max_loss_percent:
            return TradeRecommendation(
                action=Action.CLOSE_IRON_CONDOR,
                symbol=self.symbol,
                quantity=abs(ic_position['short_put'].quantity),
                strategy_type=StrategyType.IRON_CONDOR,
                long_put_strike=ic_position['long_put'].strike,
                short_put_strike=ic_position['short_put'].strike,
                short_call_strike=ic_position['short_call'].strike,
                long_call_strike=ic_position['long_call'].strike,
                expiration=datetime.combine(exp_date, datetime.min.time()),
                reasoning=f"Close iron condor for loss: {profit_pct:.1f}% (max loss {self.max_loss_percent}%)"
            )

        # Roll if close to expiration
        if dte <= self.config.roll_when_dte:
            return TradeRecommendation(
                action=Action.ROLL_IRON_CONDOR,
                symbol=self.symbol,
                quantity=abs(ic_position['short_put'].quantity),
                strategy_type=StrategyType.IRON_CONDOR,
                long_put_strike=ic_position['long_put'].strike,
                short_put_strike=ic_position['short_put'].strike,
                short_call_strike=ic_position['short_call'].strike,
                long_call_strike=ic_position['long_call'].strike,
                expiration=datetime.combine(exp_date, datetime.min.time()),
                reasoning=f"Roll iron condor with {dte} DTE"
            )

        # Check if price is testing strikes (needs adjustment)
        short_put_strike = ic_position['short_put'].strike
        short_call_strike = ic_position['short_call'].strike

        put_distance = abs(stock_price - short_put_strike) / stock_price
        call_distance = abs(stock_price - short_call_strike) / stock_price

        if put_distance < self.adjustment_threshold or call_distance < self.adjustment_threshold:
            return TradeRecommendation(
                action=Action.ADJUST_IRON_CONDOR,
                symbol=self.symbol,
                quantity=abs(ic_position['short_put'].quantity),
                strategy_type=StrategyType.IRON_CONDOR,
                long_put_strike=ic_position['long_put'].strike,
                short_put_strike=ic_position['short_put'].strike,
                short_call_strike=ic_position['short_call'].strike,
                long_call_strike=ic_position['long_call'].strike,
                expiration=datetime.combine(exp_date, datetime.min.time()),
                reasoning=f"Price testing strikes: ${stock_price:.2f} near ${short_put_strike:.2f} or ${short_call_strike:.2f}"
            )

        return None

    def _find_new_iron_condor(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        account_info: AccountInfo
    ) -> Optional[TradeRecommendation]:
        """
        Find a new iron condor to open.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            account_info: Account information

        Returns:
            Trade recommendation for new iron condor
        """
        # Find suitable expiration
        expirations = self._get_valid_expirations(options_chain)

        if not expirations:
            logger.debug(f"{self.symbol}: No valid expirations for iron condor")
            return None

        # Use the first expiration that meets our criteria
        target_exp = expirations[0]

        # Find the four legs
        # Short put: ~30 delta OTM put
        short_put = self._find_option_by_delta(
            options_chain, 'P', 0.30, stock_price,
            self.config.dte_min, self.config.dte_max
        )

        if not short_put or short_put.expiration.date() != target_exp.date():
            logger.debug(f"{self.symbol}: Could not find suitable short put")
            return None

        # Long put: wing_width below short put
        long_put_strike = short_put.strike - self.wing_width
        long_put = self._find_option_at_strike(
            options_chain, 'P', long_put_strike, target_exp
        )

        if not long_put:
            logger.debug(f"{self.symbol}: Could not find suitable long put")
            return None

        # Short call: ~30 delta OTM call
        short_call = self._find_option_by_delta(
            options_chain, 'C', 0.30, stock_price,
            self.config.dte_min, self.config.dte_max
        )

        if not short_call or short_call.expiration.date() != target_exp.date():
            logger.debug(f"{self.symbol}: Could not find suitable short call")
            return None

        # Long call: wing_width above short call
        long_call_strike = short_call.strike + self.wing_width
        long_call = self._find_option_at_strike(
            options_chain, 'C', long_call_strike, target_exp
        )

        if not long_call:
            logger.debug(f"{self.symbol}: Could not find suitable long call")
            return None

        # Calculate net credit
        total_credit = (
            (short_put.bid + short_put.ask) / 2 +
            (short_call.bid + short_call.ask) / 2
        )
        total_debit = (
            (long_put.bid + long_put.ask) / 2 +
            (long_call.bid + long_call.ask) / 2
        )
        net_credit = total_credit - total_debit

        # Check minimum credit
        if net_credit < self.min_credit:
            logger.debug(f"{self.symbol}: Net credit ${net_credit:.2f} below minimum ${self.min_credit:.2f}")
            return None

        # Calculate max loss
        put_spread_width = short_put.strike - long_put.strike
        call_spread_width = long_call.strike - short_call.strike
        max_loss = max(put_spread_width, call_spread_width) - net_credit

        return TradeRecommendation(
            action=Action.SELL_IRON_CONDOR,
            symbol=self.symbol,
            quantity=1,
            strategy_type=StrategyType.IRON_CONDOR,
            long_put_strike=long_put.strike,
            short_put_strike=short_put.strike,
            short_call_strike=short_call.strike,
            long_call_strike=long_call.strike,
            expiration=target_exp,
            expected_credit=net_credit * 100,  # Per contract
            max_loss=max_loss * 100,
            max_profit=net_credit * 100,
            reasoning=f"Sell iron condor: ${long_put.strike:.0f}/${short_put.strike:.0f}/${short_call.strike:.0f}/${long_call.strike:.0f} for ${net_credit:.2f} credit"
        )

    def _get_valid_expirations(
        self,
        options_chain: List[OptionChainData]
    ) -> List[datetime]:
        """
        Get valid expirations within DTE range.

        Args:
            options_chain: Available options

        Returns:
            List of valid expiration dates
        """
        today = datetime.now().date()
        expirations = set()

        for option in options_chain:
            dte = (option.expiration.date() - today).days
            if self.config.dte_min <= dte <= self.config.dte_max:
                expirations.add(option.expiration)

        return sorted(list(expirations))

    def _find_option_at_strike(
        self,
        options_chain: List[OptionChainData],
        right: str,
        strike: float,
        expiration: datetime
    ) -> Optional[OptionChainData]:
        """
        Find specific option by strike and expiration.

        Args:
            options_chain: Available options
            right: 'C' or 'P'
            strike: Strike price
            expiration: Expiration date

        Returns:
            Matching option or None
        """
        for option in options_chain:
            if (option.right == right and
                option.strike == strike and
                option.expiration.date() == expiration.date() and
                option.bid > 0 and option.ask > 0):
                return option

        return None


def main():
    """Example usage of IronCondorStrategy."""

    logging.basicConfig(level=logging.DEBUG)

    from src.config_loader import SymbolConfig
    from src.data_fetcher import AccountInfo

    config = SymbolConfig(
        symbol='SPY',
        enabled=True,
        max_positions=2,
        target_delta=0.30,
        dte_min=30,
        dte_max=45,
        roll_when_dte=21
    )

    strategy = IronCondorStrategy(config)

    # Mock account
    account = AccountInfo(
        account_number='TEST',
        net_liquidation=100000.0,
        total_cash=50000.0,
        buying_power=50000.0,
        available_funds=50000.0,
        excess_liquidity=50000.0,
        margin_used=0.0,
        margin_available=50000.0
    )

    print(f"Strategy type: {strategy.get_strategy_type()}")
    print(f"Compatible with neutral trend: {strategy.is_compatible_with(450.0, 0.25, 'neutral')}")
    print(f"Compatible with high vol: {strategy.is_compatible_with(450.0, 0.50, 'neutral')}")


if __name__ == '__main__':
    main()
