"""
Unit tests for core_strategy module.
"""

import pytest
from datetime import datetime, timedelta
from src.core_strategy import WheelStrategy, Action
from src.config_loader import SymbolConfig
from src.data_fetcher import OptionChainData, Position, AccountInfo


@pytest.fixture
def symbol_config():
    """Create a test symbol configuration."""
    return SymbolConfig(
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


@pytest.fixture
def mock_options_chain():
    """Create a mock options chain."""
    exp_date = datetime.now() + timedelta(days=35)

    options = []

    # Create put options at various deltas
    for strike_offset in [-20, -15, -10, -5, 0]:
        strike = 450.0 + strike_offset

        option = OptionChainData(
            symbol='SPY',
            strike=strike,
            expiration=exp_date,
            right='P',
            bid=2.40,
            ask=2.60,
            last=2.50,
            volume=100,
            open_interest=500,
            delta=-0.30 if strike_offset == -10 else -0.20,
            gamma=0.01,
            theta=-0.05,
            vega=0.10,
            iv=0.15
        )

        options.append(option)

    # Create call options
    for strike_offset in [0, 5, 10, 15, 20]:
        strike = 450.0 + strike_offset

        option = OptionChainData(
            symbol='SPY',
            strike=strike,
            expiration=exp_date,
            right='C',
            bid=2.40,
            ask=2.60,
            last=2.50,
            volume=100,
            open_interest=500,
            delta=0.30 if strike_offset == 10 else 0.20,
            gamma=0.01,
            theta=-0.05,
            vega=0.10,
            iv=0.15
        )

        options.append(option)

    return options


def test_strategy_initialization(symbol_config):
    """Test strategy initialization."""
    strategy = WheelStrategy(symbol_config)

    assert strategy.symbol == 'SPY'
    assert strategy.config.target_delta == 0.30


def test_find_cash_secured_put(symbol_config, account_info, mock_options_chain):
    """Test finding a cash-secured put."""
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    recommendation = strategy._find_cash_secured_put(
        stock_price,
        mock_options_chain,
        account_info,
        quantity=1
    )

    assert recommendation is not None
    assert recommendation.action == Action.SELL_PUT
    assert recommendation.symbol == 'SPY'
    assert recommendation.quantity == 1
    assert recommendation.strike is not None
    assert recommendation.right == 'P'


def test_find_covered_call(symbol_config, mock_options_chain):
    """Test finding a covered call."""
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    recommendation = strategy._find_covered_call(
        stock_price,
        mock_options_chain,
        quantity=1
    )

    assert recommendation is not None
    assert recommendation.action == Action.SELL_CALL
    assert recommendation.symbol == 'SPY'
    assert recommendation.quantity == 1
    assert recommendation.strike is not None
    assert recommendation.right == 'C'


def test_analyze_no_positions(symbol_config, account_info, mock_options_chain):
    """Test analyze with no existing positions."""
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    recommendations = strategy.analyze(
        stock_price,
        mock_options_chain,
        positions=[],
        account_info=account_info
    )

    # Should recommend selling a cash-secured put
    assert len(recommendations) > 0
    assert recommendations[0].action == Action.SELL_PUT


def test_analyze_with_stock_no_calls(symbol_config, account_info, mock_options_chain):
    """Test analyze when holding stock but no calls."""
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    # Create a stock position
    stock_position = Position(
        symbol='SPY',
        position_type='stock',
        quantity=100,
        avg_cost=445.0,
        market_value=45000.0,
        unrealized_pnl=500.0,
        realized_pnl=0.0
    )

    recommendations = strategy.analyze(
        stock_price,
        mock_options_chain,
        positions=[stock_position],
        account_info=account_info
    )

    # Should recommend selling a covered call
    assert len(recommendations) > 0
    assert any(rec.action == Action.SELL_CALL for rec in recommendations)


def test_disabled_symbol_returns_empty(symbol_config, account_info, mock_options_chain):
    """Test that disabled symbol returns no recommendations."""
    symbol_config.enabled = False
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    recommendations = strategy.analyze(
        stock_price,
        mock_options_chain,
        positions=[],
        account_info=account_info
    )

    assert len(recommendations) == 0


def test_minimum_premium_filtering(symbol_config, account_info, mock_options_chain):
    """Test that minimum premium requirement filters options."""
    # Set a very high minimum premium
    symbol_config.min_premium = 1000.0
    strategy = WheelStrategy(symbol_config)
    stock_price = 450.0

    recommendations = strategy.analyze(
        stock_price,
        mock_options_chain,
        positions=[],
        account_info=account_info
    )

    # Should return empty because no options meet minimum premium
    assert len(recommendations) == 0
