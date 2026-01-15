"""
Risk manager for ThetaGangExpanded.

Implements risk controls and position sizing calculations.
Validates proposed trades against risk parameters and can reject unsafe trades.
Monitors overall portfolio health.
"""

import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

from src.data_fetcher import Position, AccountInfo
from src.strategy_base import TradeRecommendation, Action
from src.config_loader import RiskConfig, SymbolConfig

logger = logging.getLogger(__name__)


class RiskViolation(Enum):
    """Types of risk violations."""
    MARGIN_EXCEEDED = "margin_exceeded"
    CONCENTRATION_EXCEEDED = "concentration_exceeded"
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    VIX_TOO_HIGH = "vix_too_high"
    BUYING_POWER_INSUFFICIENT = "buying_power_insufficient"
    PORTFOLIO_OVEREXPOSED = "portfolio_overexposed"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"


@dataclass
class RiskCheckResult:
    """Result of a risk check."""
    approved: bool
    violations: List[RiskViolation]
    reasons: List[str]
    adjusted_quantity: Optional[int] = None  # Adjusted quantity if position size should be reduced


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics."""
    total_positions: int
    total_margin_used: float
    margin_usage_percent: float
    concentration_by_symbol: Dict[str, float]  # Symbol -> % of portfolio
    max_concentration: float
    total_delta: float
    total_theta: float


class RiskManager:
    """
    Manages risk controls and validates trades.

    Checks proposed trades against:
    - Margin limits
    - Position size limits
    - Concentration limits
    - Volatility constraints
    - Stop loss triggers
    """

    def __init__(self, risk_config: RiskConfig, symbol_configs: Dict[str, SymbolConfig]):
        """
        Initialize risk manager.

        Args:
            risk_config: Risk management configuration
            symbol_configs: Per-symbol configurations
        """
        self.config = risk_config
        self.symbol_configs = symbol_configs

    def validate_trade(
        self,
        recommendation: TradeRecommendation,
        positions: List[Position],
        account_info: AccountInfo,
        current_vix: Optional[float] = None
    ) -> RiskCheckResult:
        """
        Validate a proposed trade against risk limits.

        Args:
            recommendation: Proposed trade
            positions: Current portfolio positions
            account_info: Account balance and buying power
            current_vix: Current VIX value (optional)

        Returns:
            Risk check result indicating approval status and any violations
        """
        violations = []
        reasons = []
        adjusted_quantity = None

        # Check VIX limits
        if current_vix is not None:
            vix_check = self._check_vix_limits(current_vix, recommendation)
            if not vix_check.approved:
                violations.extend(vix_check.violations)
                reasons.extend(vix_check.reasons)
                if vix_check.adjusted_quantity is not None:
                    adjusted_quantity = vix_check.adjusted_quantity

        # Check margin usage
        margin_check = self._check_margin_usage(recommendation, positions, account_info)
        if not margin_check.approved:
            violations.extend(margin_check.violations)
            reasons.extend(margin_check.reasons)

        # Check position limits
        position_check = self._check_position_limits(recommendation, positions)
        if not position_check.approved:
            violations.extend(position_check.violations)
            reasons.extend(position_check.reasons)

        # Check concentration limits
        concentration_check = self._check_concentration(recommendation, positions, account_info)
        if not concentration_check.approved:
            violations.extend(concentration_check.violations)
            reasons.extend(concentration_check.reasons)

        # Check buying power
        bp_check = self._check_buying_power(recommendation, account_info)
        if not bp_check.approved:
            violations.extend(bp_check.violations)
            reasons.extend(bp_check.reasons)

        # Overall approval
        approved = len(violations) == 0

        if approved:
            logger.info(f"Trade approved: {recommendation.action.value} {recommendation.quantity}x {recommendation.symbol}")
        else:
            logger.warning(f"Trade REJECTED: {recommendation.action.value} {recommendation.quantity}x {recommendation.symbol}")
            for reason in reasons:
                logger.warning(f"  - {reason}")

        return RiskCheckResult(
            approved=approved,
            violations=violations,
            reasons=reasons,
            adjusted_quantity=adjusted_quantity
        )

    def _check_vix_limits(
        self,
        vix: float,
        recommendation: TradeRecommendation
    ) -> RiskCheckResult:
        """
        Check if trade should be blocked or reduced based on VIX.

        Args:
            vix: Current VIX value
            recommendation: Proposed trade

        Returns:
            Risk check result
        """
        violations = []
        reasons = []
        adjusted_quantity = None

        # Block new positions if VIX too high
        if self.config.max_vix_for_new_positions is not None:
            if vix > self.config.max_vix_for_new_positions:
                if recommendation.action in [Action.SELL_PUT, Action.SELL_CALL]:
                    violations.append(RiskViolation.VIX_TOO_HIGH)
                    reasons.append(f"VIX {vix:.1f} exceeds maximum {self.config.max_vix_for_new_positions} for new positions")

        # Reduce position size if VIX elevated
        if self.config.reduce_size_when_vix_above is not None:
            if vix > self.config.reduce_size_when_vix_above:
                if recommendation.action in [Action.SELL_PUT, Action.SELL_CALL]:
                    reduced_qty = int(recommendation.quantity * self.config.vix_size_reduction_factor)
                    if reduced_qty < recommendation.quantity:
                        adjusted_quantity = max(1, reduced_qty)
                        reasons.append(f"VIX {vix:.1f} above {self.config.reduce_size_when_vix_above}: "
                                     f"Reducing position size from {recommendation.quantity} to {adjusted_quantity}")

        return RiskCheckResult(
            approved=len(violations) == 0,
            violations=violations,
            reasons=reasons,
            adjusted_quantity=adjusted_quantity
        )

    def _check_margin_usage(
        self,
        recommendation: TradeRecommendation,
        positions: List[Position],
        account_info: AccountInfo
    ) -> RiskCheckResult:
        """
        Check if trade would exceed margin usage limits.

        Args:
            recommendation: Proposed trade
            positions: Current positions
            account_info: Account information

        Returns:
            Risk check result
        """
        violations = []
        reasons = []

        # Calculate current margin usage
        current_margin = account_info.margin_used
        total_equity = account_info.net_liquidation

        if total_equity <= 0:
            violations.append(RiskViolation.MARGIN_EXCEEDED)
            reasons.append("Total equity is zero or negative")
            return RiskCheckResult(approved=False, violations=violations, reasons=reasons)

        current_usage_pct = current_margin / total_equity

        # Estimate additional margin for proposed trade
        additional_margin = self._estimate_margin_requirement(recommendation)

        # Calculate new margin usage
        new_margin = current_margin + additional_margin
        new_usage_pct = new_margin / total_equity

        logger.debug(f"Margin usage: current={current_usage_pct:.1%}, "
                    f"after trade={new_usage_pct:.1%}, "
                    f"limit={self.config.max_portfolio_margin_usage:.1%}")

        # Check against limit
        if new_usage_pct > self.config.max_portfolio_margin_usage:
            violations.append(RiskViolation.MARGIN_EXCEEDED)
            reasons.append(f"Trade would increase margin usage to {new_usage_pct:.1%} "
                         f"(limit: {self.config.max_portfolio_margin_usage:.1%})")

        return RiskCheckResult(
            approved=len(violations) == 0,
            violations=violations,
            reasons=reasons
        )

    def _check_position_limits(
        self,
        recommendation: TradeRecommendation,
        positions: List[Position]
    ) -> RiskCheckResult:
        """
        Check if trade would exceed position count limits.

        Args:
            recommendation: Proposed trade
            positions: Current positions

        Returns:
            Risk check result
        """
        violations = []
        reasons = []

        # Check total position limit
        if self.config.max_total_positions is not None:
            current_positions = len([p for p in positions if p.quantity != 0])

            # Count this as new position if opening
            is_new_position = recommendation.action in [Action.SELL_PUT, Action.SELL_CALL]

            if is_new_position and current_positions >= self.config.max_total_positions:
                violations.append(RiskViolation.POSITION_LIMIT_EXCEEDED)
                reasons.append(f"Already at maximum total positions ({self.config.max_total_positions})")

        # Check per-symbol limits
        symbol_config = self.symbol_configs.get(recommendation.symbol)
        if symbol_config:
            symbol_positions = [p for p in positions
                              if p.symbol == recommendation.symbol and p.quantity != 0]
            current_count = len(symbol_positions)

            is_new_position = recommendation.action in [Action.SELL_PUT, Action.SELL_CALL]

            if is_new_position and current_count >= symbol_config.max_positions:
                violations.append(RiskViolation.POSITION_LIMIT_EXCEEDED)
                reasons.append(f"Already at maximum positions for {recommendation.symbol} "
                             f"({symbol_config.max_positions})")

        return RiskCheckResult(
            approved=len(violations) == 0,
            violations=violations,
            reasons=reasons
        )

    def _check_concentration(
        self,
        recommendation: TradeRecommendation,
        positions: List[Position],
        account_info: AccountInfo
    ) -> RiskCheckResult:
        """
        Check if trade would exceed concentration limits.

        Args:
            recommendation: Proposed trade
            positions: Current positions
            account_info: Account information

        Returns:
            Risk check result
        """
        violations = []
        reasons = []

        total_equity = account_info.net_liquidation

        if total_equity <= 0:
            violations.append(RiskViolation.CONCENTRATION_EXCEEDED)
            reasons.append("Cannot calculate concentration: total equity is zero")
            return RiskCheckResult(approved=False, violations=violations, reasons=reasons)

        # Calculate current exposure to this symbol
        symbol_positions = [p for p in positions if p.symbol == recommendation.symbol]
        current_exposure = sum(abs(p.market_value) for p in symbol_positions)

        # Estimate additional exposure from this trade
        additional_exposure = self._estimate_position_value(recommendation)

        new_exposure = current_exposure + additional_exposure
        concentration_pct = new_exposure / total_equity

        logger.debug(f"{recommendation.symbol} concentration: "
                    f"current={current_exposure/total_equity:.1%}, "
                    f"after trade={concentration_pct:.1%}, "
                    f"limit={self.config.max_concentration_per_symbol:.1%}")

        # Check against limit
        if concentration_pct > self.config.max_concentration_per_symbol:
            violations.append(RiskViolation.CONCENTRATION_EXCEEDED)
            reasons.append(f"Trade would increase {recommendation.symbol} concentration to {concentration_pct:.1%} "
                         f"(limit: {self.config.max_concentration_per_symbol:.1%})")

        # Check symbol-specific limit
        symbol_config = self.symbol_configs.get(recommendation.symbol)
        if symbol_config and symbol_config.max_position_size_percent:
            limit_pct = symbol_config.max_position_size_percent / 100.0
            if concentration_pct > limit_pct:
                violations.append(RiskViolation.CONCENTRATION_EXCEEDED)
                reasons.append(f"Trade would increase {recommendation.symbol} concentration to {concentration_pct:.1%} "
                             f"(symbol limit: {limit_pct:.1%})")

        return RiskCheckResult(
            approved=len(violations) == 0,
            violations=violations,
            reasons=reasons
        )

    def _check_buying_power(
        self,
        recommendation: TradeRecommendation,
        account_info: AccountInfo
    ) -> RiskCheckResult:
        """
        Check if sufficient buying power exists for the trade.

        Args:
            recommendation: Proposed trade
            account_info: Account information

        Returns:
            Risk check result
        """
        violations = []
        reasons = []

        # Calculate required buying power
        required_bp = self._estimate_buying_power_requirement(recommendation)

        available_bp = account_info.buying_power

        logger.debug(f"Buying power: required=${required_bp:,.2f}, "
                    f"available=${available_bp:,.2f}")

        if required_bp > available_bp:
            violations.append(RiskViolation.BUYING_POWER_INSUFFICIENT)
            reasons.append(f"Insufficient buying power: need ${required_bp:,.2f}, "
                         f"have ${available_bp:,.2f}")

        return RiskCheckResult(
            approved=len(violations) == 0,
            violations=violations,
            reasons=reasons
        )

    def check_stop_loss(
        self,
        position: Position,
        current_market_value: float
    ) -> bool:
        """
        Check if a position has triggered stop loss.

        Args:
            position: Current position
            current_market_value: Current market value of position

        Returns:
            True if stop loss triggered
        """
        if not self.config.enable_stop_loss:
            return False

        # For short options, we received a credit and now it has a cost
        # Loss occurs when current value > entry credit
        if position.position_type == 'option' and position.quantity < 0:
            entry_credit = abs(position.avg_cost)
            current_cost = abs(current_market_value)

            loss = current_cost - entry_credit
            loss_pct = (loss / entry_credit * 100) if entry_credit > 0 else 0

            if loss_pct > self.config.stop_loss_percent:
                logger.warning(f"Stop loss triggered for {position.symbol}: "
                             f"loss={loss_pct:.1f}% exceeds {self.config.stop_loss_percent}%")
                return True

        return False

    def calculate_portfolio_risk(
        self,
        positions: List[Position],
        account_info: AccountInfo
    ) -> PortfolioRisk:
        """
        Calculate portfolio-level risk metrics.

        Args:
            positions: Current positions
            account_info: Account information

        Returns:
            Portfolio risk metrics
        """
        total_positions = len([p for p in positions if p.quantity != 0])

        total_margin = account_info.margin_used
        margin_usage_pct = (total_margin / account_info.net_liquidation
                           if account_info.net_liquidation > 0 else 0)

        # Calculate concentration by symbol
        concentration_by_symbol = {}
        for symbol in set(p.symbol for p in positions):
            symbol_positions = [p for p in positions if p.symbol == symbol]
            symbol_exposure = sum(abs(p.market_value) for p in symbol_positions)
            if account_info.net_liquidation > 0:
                concentration_by_symbol[symbol] = symbol_exposure / account_info.net_liquidation

        max_concentration = max(concentration_by_symbol.values()) if concentration_by_symbol else 0.0

        # Aggregate Greeks (would need Greeks from positions - simplified here)
        total_delta = 0.0
        total_theta = 0.0

        risk = PortfolioRisk(
            total_positions=total_positions,
            total_margin_used=total_margin,
            margin_usage_percent=margin_usage_pct,
            concentration_by_symbol=concentration_by_symbol,
            max_concentration=max_concentration,
            total_delta=total_delta,
            total_theta=total_theta
        )

        logger.info(f"Portfolio risk: {total_positions} positions, "
                   f"margin={margin_usage_pct:.1%}, "
                   f"max concentration={max_concentration:.1%}")

        return risk

    def _estimate_margin_requirement(self, recommendation: TradeRecommendation) -> float:
        """Estimate margin requirement for a trade."""
        if recommendation.action in [Action.SELL_PUT]:
            # Cash-secured put: 100% of strike value
            if recommendation.strike:
                return recommendation.strike * 100 * recommendation.quantity
        elif recommendation.action in [Action.SELL_CALL]:
            # Covered call: no additional margin (covered by stock)
            return 0.0

        return 0.0

    def _estimate_position_value(self, recommendation: TradeRecommendation) -> float:
        """Estimate market value of position."""
        if recommendation.strike:
            return recommendation.strike * 100 * recommendation.quantity
        return 0.0

    def _estimate_buying_power_requirement(self, recommendation: TradeRecommendation) -> float:
        """Estimate buying power requirement for a trade."""
        return self._estimate_margin_requirement(recommendation)


def main():
    """Example usage of RiskManager."""

    logging.basicConfig(level=logging.INFO)

    # Create configurations
    from src.config_loader import RiskConfig, SymbolConfig
    from src.data_fetcher import AccountInfo
    from src.core_strategy import TradeRecommendation, Action

    risk_config = RiskConfig(
        max_portfolio_margin_usage=0.5,
        max_concentration_per_symbol=0.25,
        reduce_size_when_vix_above=30.0,
        vix_size_reduction_factor=0.5
    )

    symbol_configs = {
        'SPY': SymbolConfig(
            symbol='SPY',
            max_positions=2,
            max_position_size_percent=20.0
        )
    }

    risk_manager = RiskManager(risk_config, symbol_configs)

    # Mock account
    account = AccountInfo(
        account_number='TEST',
        net_liquidation=100000.0,
        total_cash=50000.0,
        buying_power=50000.0,
        available_funds=50000.0,
        excess_liquidity=50000.0,
        margin_used=10000.0,
        margin_available=40000.0
    )

    # Mock trade
    trade = TradeRecommendation(
        action=Action.SELL_PUT,
        symbol='SPY',
        quantity=1,
        strike=450.0,
        premium=2.50,
        reasoning="Test trade"
    )

    # Validate
    result = risk_manager.validate_trade(trade, [], account, current_vix=25.0)

    print(f"Trade approved: {result.approved}")
    if not result.approved:
        print("Violations:")
        for reason in result.reasons:
            print(f"  - {reason}")


if __name__ == '__main__':
    main()
