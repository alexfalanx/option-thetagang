"""
Unit tests for config_loader module.
"""

import pytest
import tempfile
import os
from src.config_loader import ConfigLoader, SymbolConfig, RiskConfig


def test_symbol_config_defaults():
    """Test SymbolConfig default values."""
    config = SymbolConfig(symbol='SPY')

    assert config.symbol == 'SPY'
    assert config.enabled == True
    assert config.max_positions == 1
    assert config.target_delta == 0.30
    assert config.dte_min == 30
    assert config.dte_max == 45


def test_symbol_config_custom():
    """Test SymbolConfig with custom values."""
    config = SymbolConfig(
        symbol='TSLA',
        enabled=False,
        target_delta=0.20,
        max_positions=2
    )

    assert config.symbol == 'TSLA'
    assert config.enabled == False
    assert config.target_delta == 0.20
    assert config.max_positions == 2


def test_risk_config_defaults():
    """Test RiskConfig default values."""
    config = RiskConfig()

    assert config.max_portfolio_margin_usage == 0.5
    assert config.max_concentration_per_symbol == 0.25
    assert config.enable_stop_loss == False


def test_config_validation_invalid_delta():
    """Test configuration validation catches invalid delta."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[account]
account_number = "TEST123"

[symbols.defaults]
target_delta = 1.5

[symbols.tickers.SPY]
enabled = true

[risk]
[strategy]
[data]
[schedule]
[logging]
        """)
        config_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("IBKR_ACCOUNT_NUMBER=TEST123")
        env_path = f.name

    try:
        loader = ConfigLoader(config_path, env_path)
        with pytest.raises(ValueError, match="Invalid target_delta"):
            loader.load()
    finally:
        os.unlink(config_path)
        os.unlink(env_path)


def test_config_validation_missing_account():
    """Test configuration validation catches missing account."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[account]

[symbols.defaults]

[symbols.tickers.SPY]
enabled = true

[risk]
[strategy]
[data]
[schedule]
[logging]
        """)
        config_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("")
        env_path = f.name

    try:
        loader = ConfigLoader(config_path, env_path)
        with pytest.raises(ValueError, match="account number is required"):
            loader.load()
    finally:
        os.unlink(config_path)
        os.unlink(env_path)


def test_config_loader_env_override():
    """Test that environment variables override TOML values."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[account]
account_number = "WRONG"

[symbols.defaults]

[symbols.tickers.SPY]
enabled = true

[risk]
[strategy]
[data]
[schedule]
[logging]
        """)
        config_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("IBKR_ACCOUNT_NUMBER=CORRECT123")
        env_path = f.name

    try:
        loader = ConfigLoader(config_path, env_path)
        config = loader.load()

        assert config.account.account_number == "CORRECT123"
    finally:
        os.unlink(config_path)
        os.unlink(env_path)
