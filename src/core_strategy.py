"""
Core strategy module for ThetaGangExpanded.

Implements the Wheel strategy logic:
1. Sell cash-secured puts when not holding stock
2. Handle assignment and acquire stock
3. Sell covered calls when holding stock
4. Handle call assignment and sell stock
5. Roll positions based on DTE and P&L criteria

Returns recommended trades without executing them directly.
"""

import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta

from src.strategy_base import Strategy, StrategyType, Action, TradeRecommendation
from src.data_fetcher import OptionChainData, Position, AccountInfo
from src.config_loader import SymbolConfig

logger = logging.getLogger(__name__)


class WheelStrategy(Strategy):
    """
    Implements the Wheel options strategy.

    The Wheel strategy:
    1. Sell cash-secured puts at target delta
    2. If assigned, hold stock and sell covered calls
    3. If called away, return to step 1
    4. Roll positions when approaching expiration or profit target
    """

    def __init__(self, config: SymbolConfig):
        """
        Initialize Wheel strategy for a symbol.

        Args:
            config: Symbol-specific configuration
        """
        super().__init__(config)

    def get_strategy_type(self) -> StrategyType:
        """Return strategy type identifier."""
        return StrategyType.WHEEL

    def analyze(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        positions: List[Position],
        account_info: AccountInfo
    ) -> List[TradeRecommendation]:
        """
        Analyze current state and generate trade recommendations.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            positions: Current positions for this symbol
            account_info: Account balance and buying power

        Returns:
            List of trade recommendations
        """
        recommendations = []

        # Skip if symbol is disabled
        if not self.config.enabled:
            logger.debug(f"{self.symbol} is disabled, skipping")
            return recommendations

        # Separate stock and option positions
        stock_positions = [p for p in positions if p.position_type == 'stock']
        put_positions = [p for p in positions if p.position_type == 'option' and p.right == 'P']
        call_positions = [p for p in positions if p.position_type == 'option' and p.right == 'C']

        logger.info(f"{self.symbol}: Stock={len(stock_positions)}, Puts={len(put_positions)}, Calls={len(call_positions)}")

        # Check existing positions for rolling/closing opportunities
        for put_pos in put_positions:
            recommendation = self._check_put_position(put_pos, stock_price, options_chain)
            if recommendation:
                recommendations.append(recommendation)

        for call_pos in call_positions:
            recommendation = self._check_call_position(call_pos, stock_price, options_chain)
            if recommendation:
                recommendations.append(recommendation)

        # Determine if we should open new positions
        has_stock = any(p.quantity > 0 for p in stock_positions)
        has_short_puts = any(p.quantity < 0 for p in put_positions)
        has_short_calls = any(p.quantity < 0 for p in call_positions)

        # Count current option positions
        total_short_puts = sum(abs(p.quantity) for p in put_positions if p.quantity < 0)
        total_short_calls = sum(abs(p.quantity) for p in call_positions if p.quantity < 0)

        if has_stock and not has_short_calls:
            # We have stock but no covered calls - sell calls
            stock_qty = sum(p.quantity for p in stock_positions)
            contracts_to_sell = (stock_qty // 100) - total_short_calls

            if contracts_to_sell > 0:
                recommendation = self._find_covered_call(
                    stock_price,
                    options_chain,
                    contracts_to_sell
                )
                if recommendation:
                    recommendations.append(recommendation)

        elif not has_stock and not has_short_puts:
            # No stock and no short puts - sell cash-secured puts
            if total_short_puts < self.config.max_positions:
                contracts_to_sell = self.config.max_positions - total_short_puts
                recommendation = self._find_cash_secured_put(
                    stock_price,
                    options_chain,
                    account_info,
                    contracts_to_sell
                )
                if recommendation:
                    recommendations.append(recommendation)

        return recommendations

    def _check_put_position(
        self,
        position: Position,
        stock_price: float,
        options_chain: List[OptionChainData]
    ) -> Optional[TradeRecommendation]:
        """
        Check if an existing put position should be rolled or closed.

        Args:
            position: Current put position
            stock_price: Current stock price
            options_chain: Available options

        Returns:
            Trade recommendation if action needed, None otherwise
        """
        if not position.expiration:
            return None

        # Calculate DTE
        dte = (position.expiration.date() - datetime.now().date()).days

        # Calculate P&L percentage
        entry_credit = abs(position.avg_cost)
        current_value = abs(position.market_value)
        pnl_percent = ((entry_credit - current_value) / entry_credit * 100) if entry_credit > 0 else 0

        logger.debug(f"{self.symbol} put at ${position.strike}: DTE={dte}, P&L={pnl_percent:.1f}%")

        # Check if we should close for profit
        if pnl_percent >= self.config.roll_when_pnl_percent:
            return TradeRecommendation(
                action=Action.CLOSE_PUT,
                symbol=self.symbol,
                quantity=abs(position.quantity),
                strategy_type=StrategyType.WHEEL,
                existing_position=position,
                reasoning=f"Close put for {pnl_percent:.1f}% profit (target {self.config.roll_when_pnl_percent}%)"
            )

        # Check if we should roll based on DTE
        if dte <= self.config.roll_when_dte:
            # Find new put to roll to
            new_option = self._find_option_by_delta(
                options_chain,
                'P',
                self.config.target_delta,
                stock_price,
                self.config.dte_min,
                self.config.dte_max
            )

            if new_option:
                return TradeRecommendation(
                    action=Action.ROLL_PUT,
                    symbol=self.symbol,
                    quantity=abs(position.quantity),
                    strategy_type=StrategyType.WHEEL,
                    existing_position=position,
                    new_strike=new_option.strike,
                    new_expiration=new_option.expiration,
                    premium=(new_option.bid + new_option.ask) / 2,
                    delta=new_option.delta,
                    reasoning=f"Roll put with {dte} DTE (threshold {self.config.roll_when_dte})"
                )

        return None

    def _check_call_position(
        self,
        position: Position,
        stock_price: float,
        options_chain: List[OptionChainData]
    ) -> Optional[TradeRecommendation]:
        """
        Check if an existing call position should be rolled or closed.

        Args:
            position: Current call position
            stock_price: Current stock price
            options_chain: Available options

        Returns:
            Trade recommendation if action needed, None otherwise
        """
        if not position.expiration:
            return None

        # Calculate DTE
        dte = (position.expiration.date() - datetime.now().date()).days

        # Calculate P&L percentage
        entry_credit = abs(position.avg_cost)
        current_value = abs(position.market_value)
        pnl_percent = ((entry_credit - current_value) / entry_credit * 100) if entry_credit > 0 else 0

        logger.debug(f"{self.symbol} call at ${position.strike}: DTE={dte}, P&L={pnl_percent:.1f}%")

        # Check if we should close for profit
        if pnl_percent >= self.config.roll_when_pnl_percent:
            return TradeRecommendation(
                action=Action.CLOSE_CALL,
                symbol=self.symbol,
                quantity=abs(position.quantity),
                strategy_type=StrategyType.WHEEL,
                existing_position=position,
                reasoning=f"Close call for {pnl_percent:.1f}% profit (target {self.config.roll_when_pnl_percent}%)"
            )

        # Check if we should roll based on DTE
        if dte <= self.config.roll_when_dte:
            # Find new call to roll to
            new_option = self._find_option_by_delta(
                options_chain,
                'C',
                self.config.target_delta,
                stock_price,
                self.config.dte_min,
                self.config.dte_max
            )

            if new_option:
                return TradeRecommendation(
                    action=Action.ROLL_CALL,
                    symbol=self.symbol,
                    quantity=abs(position.quantity),
                    strategy_type=StrategyType.WHEEL,
                    existing_position=position,
                    new_strike=new_option.strike,
                    new_expiration=new_option.expiration,
                    premium=(new_option.bid + new_option.ask) / 2,
                    delta=new_option.delta,
                    reasoning=f"Roll call with {dte} DTE (threshold {self.config.roll_when_dte})"
                )

        return None

    def _find_cash_secured_put(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        account_info: AccountInfo,
        quantity: int
    ) -> Optional[TradeRecommendation]:
        """
        Find a suitable cash-secured put to sell.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            account_info: Account information
            quantity: Number of contracts to sell

        Returns:
            Trade recommendation if suitable option found
        """
        # Find put option near target delta
        option = self._find_option_by_delta(
            options_chain,
            'P',
            self.config.target_delta,
            stock_price,
            self.config.dte_min,
            self.config.dte_max
        )

        if not option:
            logger.debug(f"{self.symbol}: No suitable put found")
            return None

        # Calculate premium
        mid_price = (option.bid + option.ask) / 2

        # Check minimum premium requirements
        if self.config.min_premium > 0 and mid_price < self.config.min_premium:
            logger.debug(f"{self.symbol}: Premium ${mid_price:.2f} below minimum ${self.config.min_premium:.2f}")
            return None

        if self.config.min_premium_percent > 0:
            premium_percent = (mid_price / stock_price) * 100
            if premium_percent < self.config.min_premium_percent:
                logger.debug(f"{self.symbol}: Premium {premium_percent:.2f}% below minimum {self.config.min_premium_percent}%")
                return None

        # Check if we have enough buying power
        buying_power_required = option.strike * 100 * quantity
        if buying_power_required > account_info.buying_power:
            logger.warning(f"{self.symbol}: Insufficient buying power for cash-secured put")
            return None

        return TradeRecommendation(
            action=Action.SELL_PUT,
            symbol=self.symbol,
            quantity=quantity,
            strategy_type=StrategyType.WHEEL,
            strike=option.strike,
            expiration=option.expiration,
            right='P',
            premium=mid_price,
            delta=option.delta,
            reasoning=f"Sell cash-secured put: ${option.strike} {option.expiration.strftime('%Y-%m-%d')} @ ${mid_price:.2f} (delta {option.delta:.2f})"
        )

    def _find_covered_call(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        quantity: int
    ) -> Optional[TradeRecommendation]:
        """
        Find a suitable covered call to sell.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            quantity: Number of contracts to sell

        Returns:
            Trade recommendation if suitable option found
        """
        # Find call option near target delta
        option = self._find_option_by_delta(
            options_chain,
            'C',
            self.config.target_delta,
            stock_price,
            self.config.dte_min,
            self.config.dte_max
        )

        if not option:
            logger.debug(f"{self.symbol}: No suitable call found")
            return None

        # Calculate premium
        mid_price = (option.bid + option.ask) / 2

        # Check minimum premium requirements
        if self.config.min_premium > 0 and mid_price < self.config.min_premium:
            logger.debug(f"{self.symbol}: Premium ${mid_price:.2f} below minimum ${self.config.min_premium:.2f}")
            return None

        if self.config.min_premium_percent > 0:
            premium_percent = (mid_price / stock_price) * 100
            if premium_percent < self.config.min_premium_percent:
                logger.debug(f"{self.symbol}: Premium {premium_percent:.2f}% below minimum {self.config.min_premium_percent}%")
                return None

        return TradeRecommendation(
            action=Action.SELL_CALL,
            symbol=self.symbol,
            quantity=quantity,
            strategy_type=StrategyType.WHEEL,
            strike=option.strike,
            expiration=option.expiration,
            right='C',
            premium=mid_price,
            delta=option.delta,
            reasoning=f"Sell covered call: ${option.strike} {option.expiration.strftime('%Y-%m-%d')} @ ${mid_price:.2f} (delta {option.delta:.2f})"
        )

def main():
    """Example usage of WheelStrategy."""

    logging.basicConfig(level=logging.DEBUG)

    # Create mock configuration
    from src.config_loader import SymbolConfig

    config = SymbolConfig(
        symbol='SPY',
        enabled=True,
        max_positions=1,
        target_delta=0.30,
        min_premium=50.0,
        dte_min=30,
        dte_max=45,
        roll_when_dte=21,
        roll_when_pnl_percent=50.0
    )

    strategy = WheelStrategy(config)

    # Create mock data
    stock_price = 450.0

    # Mock account info
    from src.data_fetcher import AccountInfo
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

    # Analyze (with empty positions and options for this example)
    recommendations = strategy.analyze(stock_price, [], [], account)

    print(f"Generated {len(recommendations)} recommendations")
    for rec in recommendations:
        print(f"  {rec.action.value}: {rec.reasoning}")


if __name__ == '__main__':
    main()
