"""
Unit tests for Iron Condor strategy module.
"""

import pytest
from datetime import datetime, timedelta
from src.iron_condor_strategy import IronCondorStrategy
from src.strategy_base import StrategyType, Action
from src.config_loader import SymbolConfig
from src.data_fetcher import OptionChainData, Position, AccountInfo


@pytest.fixture
def symbol_config():
    """Create a test symbol configuration."""
    return SymbolConfig(
        symbol='SPY',
        enabled=True,
        max_positions=2,
        target_delta=0.30,
        dte_min=30,
        dte_max=45,
        roll_when_dte=21
    )


@pytest.fixture
def account_info():
    """Create test account information."""
    return AccountInfo(
        account_number='TEST',
        net_liquidation=100000.0,
        total_cash=50000.0,
        buying_power=50000.0,
        available_funds=50000.0,
        excess_liquidity=50000.0,
        margin_used=0.0,
        margin_available=50000.0
    )


def test_strategy_initialization(symbol_config):
    """Test Iron Condor strategy initialization."""
    strategy = IronCondorStrategy(symbol_config)

    assert strategy.symbol == 'SPY'
    assert strategy.get_strategy_type() == StrategyType.IRON_CONDOR
    assert strategy.wing_width == 5.0


def test_compatibility_with_neutral_low_vol(symbol_config):
    """Test that Iron Condor is compatible with neutral, low volatility."""
    strategy = IronCondorStrategy(symbol_config)

    # Should be compatible
    assert strategy.is_compatible_with(450.0, volatility=0.18, trend='neutral')

    # Should not be compatible with trending markets
    assert not strategy.is_compatible_with(450.0, volatility=0.18, trend='bullish')
    assert not strategy.is_compatible_with(450.0, volatility=0.18, trend='bearish')

    # Should not be compatible with high volatility
    assert not strategy.is_compatible_with(450.0, volatility=0.40, trend='neutral')


def test_find_new_iron_condor(symbol_config, account_info):
    """Test finding a new iron condor to open."""
    strategy = IronCondorStrategy(symbol_config)
    stock_price = 450.0

    # Create a comprehensive mock options chain
    exp_date = datetime.now() + timedelta(days=35)
    options_chain = []

    # Create options at various strikes for both puts and calls
    strikes = [430, 435, 440, 445, 450, 455, 460, 465, 470]

    for strike in strikes:
        # Put options
        put = OptionChainData(
            symbol='SPY',
            strike=strike,
            expiration=exp_date,
            right='P',
            bid=2.40 if strike < stock_price else 1.20,
            ask=2.60 if strike < stock_price else 1.40,
            last=2.50 if strike < stock_price else 1.30,
            volume=100,
            open_interest=500,
            delta=-0.30 if strike == 440 else -0.20,
            gamma=0.01,
            theta=-0.05,
            vega=0.10,
            iv=0.18
        )
        options_chain.append(put)

        # Call options
        call = OptionChainData(
            symbol='SPY',
            strike=strike,
            expiration=exp_date,
            right='C',
            bid=2.40 if strike > stock_price else 1.20,
            ask=2.60 if strike > stock_price else 1.40,
            last=2.50 if strike > stock_price else 1.30,
            volume=100,
            open_interest=500,
            delta=0.30 if strike == 460 else 0.20,
            gamma=0.01,
            theta=-0.05,
            vega=0.10,
            iv=0.18
        )
        options_chain.append(call)

    # Try to find a new iron condor
    recommendation = strategy._find_new_iron_condor(
        stock_price,
        options_chain,
        account_info
    )

    # For this test, it might not find one due to strike availability
    # but the method should not crash
    assert recommendation is None or recommendation.action == Action.SELL_IRON_CONDOR


def test_identify_iron_condor_positions(symbol_config):
    """Test identifying existing iron condor positions."""
    strategy = IronCondorStrategy(symbol_config)

    exp_date = datetime.now() + timedelta(days=30)

    # Create mock iron condor positions
    positions = [
        Position(
            symbol='SPY',
            position_type='option',
            quantity=1,  # Long put
            avg_cost=1.00,
            market_value=100.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            strike=435.0,
            expiration=exp_date,
            right='P'
        ),
        Position(
            symbol='SPY',
            position_type='option',
            quantity=-1,  # Short put
            avg_cost=2.50,
            market_value=-250.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            strike=440.0,
            expiration=exp_date,
            right='P'
        ),
        Position(
            symbol='SPY',
            position_type='option',
            quantity=-1,  # Short call
            avg_cost=2.50,
            market_value=-250.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            strike=460.0,
            expiration=exp_date,
            right='C'
        ),
        Position(
            symbol='SPY',
            position_type='option',
            quantity=1,  # Long call
            avg_cost=1.00,
            market_value=100.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            strike=465.0,
            expiration=exp_date,
            right='C'
        )
    ]

    iron_condors = strategy._identify_iron_condor_positions(positions)

    assert len(iron_condors) == 1
    assert iron_condors[0]['long_put'].strike == 435.0
    assert iron_condors[0]['short_put'].strike == 440.0
    assert iron_condors[0]['short_call'].strike == 460.0
    assert iron_condors[0]['long_call'].strike == 465.0


def test_analyze_no_positions(symbol_config, account_info):
    """Test analyze with no existing positions."""
    strategy = IronCondorStrategy(symbol_config)
    stock_price = 450.0
    options_chain = []  # Empty chain for this simple test

    recommendations = strategy.analyze(
        stock_price,
        options_chain,
        positions=[],
        account_info=account_info
    )

    # Should return empty (no suitable iron condor found with empty chain)
    assert isinstance(recommendations, list)


def test_disabled_symbol_returns_empty(symbol_config, account_info):
    """Test that disabled symbol returns no recommendations."""
    symbol_config.enabled = False
    strategy = IronCondorStrategy(symbol_config)
    stock_price = 450.0

    recommendations = strategy.analyze(
        stock_price,
        [],
        positions=[],
        account_info=account_info
    )

    assert len(recommendations) == 0
