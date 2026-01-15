"""
Abstract base class for trading strategies.

Defines the interface that all strategies must implement.
Enables pluggable strategy architecture and multi-strategy portfolios.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from src.data_fetcher import OptionChainData, Position, AccountInfo
from src.config_loader import SymbolConfig


class StrategyType(Enum):
    """Strategy type identifiers."""
    WHEEL = "wheel"
    IRON_CONDOR = "iron_condor"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CALENDAR = "calendar"


class Action(Enum):
    """Trade action types."""
    # Wheel actions
    SELL_PUT = "sell_put"
    SELL_CALL = "sell_call"
    ROLL_PUT = "roll_put"
    ROLL_CALL = "roll_call"
    CLOSE_PUT = "close_put"
    CLOSE_CALL = "close_call"

    # Iron Condor actions
    SELL_IRON_CONDOR = "sell_iron_condor"
    CLOSE_IRON_CONDOR = "close_iron_condor"
    ROLL_IRON_CONDOR = "roll_iron_condor"
    ADJUST_IRON_CONDOR = "adjust_iron_condor"

    # Generic
    DO_NOTHING = "do_nothing"


@dataclass
class TradeRecommendation:
    """
    Recommended trade action from a strategy.

    Universal structure that works for all strategy types.
    """
    action: Action
    symbol: str
    quantity: int
    strategy_type: StrategyType

    # For single-leg options (puts/calls)
    strike: Optional[float] = None
    expiration: Optional[datetime] = None
    right: Optional[str] = None  # 'C' or 'P'
    premium: Optional[float] = None
    delta: Optional[float] = None

    # For multi-leg strategies (iron condors, spreads)
    long_call_strike: Optional[float] = None
    short_call_strike: Optional[float] = None
    long_put_strike: Optional[float] = None
    short_put_strike: Optional[float] = None

    # For rolling or closing
    existing_position: Optional[Position] = None
    new_strike: Optional[float] = None
    new_expiration: Optional[datetime] = None

    # Metadata
    reasoning: str = ""
    expected_credit: Optional[float] = None
    max_loss: Optional[float] = None
    max_profit: Optional[float] = None


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement:
    - analyze(): Generate trade recommendations
    - get_strategy_type(): Return strategy identifier
    - is_compatible_with(): Check if compatible with market conditions
    """

    def __init__(self, config: SymbolConfig):
        """
        Initialize strategy.

        Args:
            config: Symbol-specific configuration
        """
        self.config = config
        self.symbol = config.symbol

    @abstractmethod
    def analyze(
        self,
        stock_price: float,
        options_chain: List[OptionChainData],
        positions: List[Position],
        account_info: AccountInfo
    ) -> List[TradeRecommendation]:
        """
        Analyze market conditions and generate trade recommendations.

        Args:
            stock_price: Current stock price
            options_chain: Available options
            positions: Current positions for this symbol
            account_info: Account balance and buying power

        Returns:
            List of trade recommendations
        """
        pass

    @abstractmethod
    def get_strategy_type(self) -> StrategyType:
        """
        Get the type of this strategy.

        Returns:
            Strategy type identifier
        """
        pass

    def is_compatible_with(
        self,
        stock_price: float,
        volatility: Optional[float] = None,
        trend: Optional[str] = None
    ) -> bool:
        """
        Check if this strategy is compatible with current market conditions.

        Args:
            stock_price: Current stock price
            volatility: Current implied volatility (optional)
            trend: Market trend - 'bullish', 'bearish', 'neutral' (optional)

        Returns:
            True if strategy is suitable for current conditions
        """
        # Default implementation - always compatible
        # Override in specific strategies for more sophisticated logic
        return True

    def _find_option_by_delta(
        self,
        options_chain: List[OptionChainData],
        right: str,
        target_delta: float,
        stock_price: float,
        min_dte: int,
        max_dte: int
    ) -> Optional[OptionChainData]:
        """
        Find option closest to target delta within DTE range.

        Shared utility method for all strategies.

        Args:
            options_chain: Available options
            right: 'C' for call, 'P' for put
            target_delta: Target delta value
            stock_price: Current stock price
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration

        Returns:
            Best matching option, or None if not found
        """
        from datetime import datetime

        # Filter by type and DTE
        today = datetime.now().date()
        candidates = []

        for option in options_chain:
            # Filter by right
            if option.right != right:
                continue

            # Check DTE
            dte = (option.expiration.date() - today).days
            if dte < min_dte or dte > max_dte:
                continue

            # Need delta
            if option.delta is None:
                continue

            # Need valid bid/ask
            if option.bid <= 0 or option.ask <= 0:
                continue

            candidates.append(option)

        if not candidates:
            return None

        # For puts, we want delta around -target_delta (e.g., -0.30)
        # For calls, we want delta around +target_delta (e.g., +0.30)
        if right == 'P':
            target = -abs(target_delta)
        else:
            target = abs(target_delta)

        # Find closest to target delta
        best_option = min(candidates, key=lambda o: abs(o.delta - target))

        return best_option

    def _find_options_by_strike_range(
        self,
        options_chain: List[OptionChainData],
        right: str,
        min_strike: float,
        max_strike: float,
        expiration: datetime,
        min_dte: int,
        max_dte: int
    ) -> List[OptionChainData]:
        """
        Find all options within a strike range for a specific expiration.

        Useful for building spreads and iron condors.

        Args:
            options_chain: Available options
            right: 'C' for call, 'P' for put
            min_strike: Minimum strike price
            max_strike: Maximum strike price
            expiration: Target expiration date
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration

        Returns:
            List of matching options
        """
        from datetime import datetime

        today = datetime.now().date()
        matching = []

        for option in options_chain:
            # Filter by right
            if option.right != right:
                continue

            # Check strike range
            if option.strike < min_strike or option.strike > max_strike:
                continue

            # Check expiration match (same date)
            if option.expiration.date() != expiration.date():
                continue

            # Check DTE
            dte = (option.expiration.date() - today).days
            if dte < min_dte or dte > max_dte:
                continue

            # Need valid bid/ask
            if option.bid <= 0 or option.ask <= 0:
                continue

            matching.append(option)

        return matching


# Import datetime for type hints
from datetime import datetime
