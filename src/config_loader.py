"""
Configuration loader for ThetaGangExpanded.

Loads and validates configuration from TOML files and environment variables.
Provides a single source of truth for all configurable parameters.
"""

import os
import toml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


@dataclass
class AccountConfig:
    """IBKR account configuration."""
    account_number: str
    host: str = "127.0.0.1"
    port: int = 7497  # 7497 for paper trading, 7496 for live
    client_id: int = 1
    read_only: bool = False


@dataclass
class SymbolConfig:
    """Per-symbol trading configuration."""
    symbol: str
    enabled: bool = True

    # Position sizing
    max_positions: int = 1
    target_delta: float = 0.30

    # Premium criteria
    min_premium: float = 0.0
    min_premium_percent: float = 0.0

    # Days to expiration
    dte_min: int = 30
    dte_max: int = 45

    # Rolling criteria
    roll_when_dte: int = 21
    roll_when_pnl_percent: float = 50.0

    # Assignment handling
    write_calls_on_assignment: bool = True

    # Risk limits
    max_position_size_percent: float = 10.0  # % of portfolio


@dataclass
class RiskConfig:
    """Risk management configuration."""
    # Portfolio limits
    max_portfolio_margin_usage: float = 0.5  # 50% max margin usage
    max_concentration_per_symbol: float = 0.25  # 25% max per symbol

    # Volatility controls
    max_vix_for_new_positions: Optional[float] = None
    reduce_size_when_vix_above: Optional[float] = 30.0
    vix_size_reduction_factor: float = 0.5

    # Stop loss
    enable_stop_loss: bool = False
    stop_loss_percent: float = 50.0  # Close if loss > 50% of credit received

    # Position limits
    max_total_positions: Optional[int] = None


@dataclass
class StrategyConfig:
    """Strategy-specific configuration."""
    strategy_name: str = "wheel"

    # Wheel strategy params
    wheel_enabled: bool = True
    prefer_cash_secured_puts: bool = True

    # Future expansion for other strategies
    iron_condor_enabled: bool = False
    strangle_enabled: bool = False


@dataclass
class DataConfig:
    """Data provider configuration."""
    primary_provider: str = "ibkr"

    # Polygon.io config
    polygon_api_key: Optional[str] = None
    use_polygon_for_greeks: bool = False

    # Earnings calendar
    avoid_earnings: bool = True
    earnings_buffer_days: int = 7


@dataclass
class ScheduleConfig:
    """Scheduling configuration."""
    # Run schedule
    run_on_startup: bool = True
    run_every_minutes: int = 60

    # Trading hours (UTC)
    trading_start_hour: int = 14  # 9:30 AM ET
    trading_end_hour: int = 20    # 4:00 PM ET

    # Days of week (0 = Monday, 6 = Sunday)
    trading_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_to_file: bool = True
    log_dir: str = "logs"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Alert configuration
    enable_email_alerts: bool = False
    email_to: Optional[str] = None
    email_from: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: int = 587

    enable_slack_alerts: bool = False
    slack_webhook_url: Optional[str] = None


@dataclass
class Config:
    """Main configuration object."""
    account: AccountConfig
    symbols: Dict[str, SymbolConfig]
    risk: RiskConfig
    strategy: StrategyConfig
    data: DataConfig
    schedule: ScheduleConfig
    logging: LoggingConfig

    # Global settings
    dry_run: bool = True


class ConfigLoader:
    """Loads and validates configuration from TOML and environment variables."""

    def __init__(self, config_path: str = "configs/thetagang.toml", env_path: str = ".env"):
        """
        Initialize config loader.

        Args:
            config_path: Path to TOML configuration file
            env_path: Path to .env file for credentials
        """
        self.config_path = config_path
        self.env_path = env_path

    def load(self) -> Config:
        """
        Load configuration from files and environment.

        Returns:
            Config object with all settings

        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If config files don't exist
        """
        # Load environment variables
        load_dotenv(self.env_path)

        # Load TOML config
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config_data = toml.load(f)

        # Parse account config (from env + toml)
        account_config = self._load_account_config(config_data.get('account', {}))

        # Parse symbols
        symbols_config = self._load_symbols_config(config_data.get('symbols', {}))

        # Parse risk config
        risk_config = self._load_risk_config(config_data.get('risk', {}))

        # Parse strategy config
        strategy_config = self._load_strategy_config(config_data.get('strategy', {}))

        # Parse data config (from env + toml)
        data_config = self._load_data_config(config_data.get('data', {}))

        # Parse schedule config
        schedule_config = self._load_schedule_config(config_data.get('schedule', {}))

        # Parse logging config (from env + toml)
        logging_config = self._load_logging_config(config_data.get('logging', {}))

        # Global settings
        dry_run = config_data.get('dry_run', True)

        config = Config(
            account=account_config,
            symbols=symbols_config,
            risk=risk_config,
            strategy=strategy_config,
            data=data_config,
            schedule=schedule_config,
            logging=logging_config,
            dry_run=dry_run
        )

        # Validate configuration
        self._validate_config(config)

        logger.info(f"Configuration loaded successfully from {self.config_path}")
        logger.info(f"Loaded {len(config.symbols)} symbols")
        logger.info(f"Dry run mode: {config.dry_run}")

        return config

    def _load_account_config(self, account_data: Dict[str, Any]) -> AccountConfig:
        """Load account configuration from env and TOML."""
        return AccountConfig(
            account_number=os.getenv('IBKR_ACCOUNT_NUMBER', account_data.get('account_number', '')),
            host=account_data.get('host', '127.0.0.1'),
            port=int(account_data.get('port', 7497)),
            client_id=int(account_data.get('client_id', 1)),
            read_only=account_data.get('read_only', False)
        )

    def _load_symbols_config(self, symbols_data: Dict[str, Any]) -> Dict[str, SymbolConfig]:
        """Load per-symbol configuration."""
        symbols = {}

        # Get global defaults
        defaults = symbols_data.get('defaults', {})

        # Get per-symbol overrides
        tickers = symbols_data.get('tickers', {})

        for symbol, symbol_data in tickers.items():
            # Merge defaults with symbol-specific settings
            merged = {**defaults, **symbol_data}

            symbols[symbol] = SymbolConfig(
                symbol=symbol,
                enabled=merged.get('enabled', True),
                max_positions=int(merged.get('max_positions', 1)),
                target_delta=float(merged.get('target_delta', 0.30)),
                min_premium=float(merged.get('min_premium', 0.0)),
                min_premium_percent=float(merged.get('min_premium_percent', 0.0)),
                dte_min=int(merged.get('dte_min', 30)),
                dte_max=int(merged.get('dte_max', 45)),
                roll_when_dte=int(merged.get('roll_when_dte', 21)),
                roll_when_pnl_percent=float(merged.get('roll_when_pnl_percent', 50.0)),
                write_calls_on_assignment=merged.get('write_calls_on_assignment', True),
                max_position_size_percent=float(merged.get('max_position_size_percent', 10.0))
            )

        return symbols

    def _load_risk_config(self, risk_data: Dict[str, Any]) -> RiskConfig:
        """Load risk management configuration."""
        return RiskConfig(
            max_portfolio_margin_usage=float(risk_data.get('max_portfolio_margin_usage', 0.5)),
            max_concentration_per_symbol=float(risk_data.get('max_concentration_per_symbol', 0.25)),
            max_vix_for_new_positions=risk_data.get('max_vix_for_new_positions'),
            reduce_size_when_vix_above=risk_data.get('reduce_size_when_vix_above', 30.0),
            vix_size_reduction_factor=float(risk_data.get('vix_size_reduction_factor', 0.5)),
            enable_stop_loss=risk_data.get('enable_stop_loss', False),
            stop_loss_percent=float(risk_data.get('stop_loss_percent', 50.0)),
            max_total_positions=risk_data.get('max_total_positions')
        )

    def _load_strategy_config(self, strategy_data: Dict[str, Any]) -> StrategyConfig:
        """Load strategy configuration."""
        return StrategyConfig(
            strategy_name=strategy_data.get('strategy_name', 'wheel'),
            wheel_enabled=strategy_data.get('wheel_enabled', True),
            prefer_cash_secured_puts=strategy_data.get('prefer_cash_secured_puts', True),
            iron_condor_enabled=strategy_data.get('iron_condor_enabled', False),
            strangle_enabled=strategy_data.get('strangle_enabled', False)
        )

    def _load_data_config(self, data_config: Dict[str, Any]) -> DataConfig:
        """Load data provider configuration."""
        return DataConfig(
            primary_provider=data_config.get('primary_provider', 'ibkr'),
            polygon_api_key=os.getenv('POLYGON_API_KEY', data_config.get('polygon_api_key')),
            use_polygon_for_greeks=data_config.get('use_polygon_for_greeks', False),
            avoid_earnings=data_config.get('avoid_earnings', True),
            earnings_buffer_days=int(data_config.get('earnings_buffer_days', 7))
        )

    def _load_schedule_config(self, schedule_data: Dict[str, Any]) -> ScheduleConfig:
        """Load scheduling configuration."""
        return ScheduleConfig(
            run_on_startup=schedule_data.get('run_on_startup', True),
            run_every_minutes=int(schedule_data.get('run_every_minutes', 60)),
            trading_start_hour=int(schedule_data.get('trading_start_hour', 14)),
            trading_end_hour=int(schedule_data.get('trading_end_hour', 20)),
            trading_days=schedule_data.get('trading_days', [0, 1, 2, 3, 4])
        )

    def _load_logging_config(self, logging_data: Dict[str, Any]) -> LoggingConfig:
        """Load logging and alerting configuration."""
        return LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            log_to_file=logging_data.get('log_to_file', True),
            log_dir=logging_data.get('log_dir', 'logs'),
            log_format=logging_data.get('log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            enable_email_alerts=logging_data.get('enable_email_alerts', False),
            email_to=os.getenv('EMAIL_TO', logging_data.get('email_to')),
            email_from=os.getenv('EMAIL_FROM', logging_data.get('email_from')),
            smtp_server=os.getenv('SMTP_SERVER', logging_data.get('smtp_server')),
            smtp_port=int(logging_data.get('smtp_port', 587)),
            enable_slack_alerts=logging_data.get('enable_slack_alerts', False),
            slack_webhook_url=os.getenv('SLACK_WEBHOOK_URL', logging_data.get('slack_webhook_url'))
        )

    def _validate_config(self, config: Config) -> None:
        """
        Validate configuration for consistency and required fields.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate account
        if not config.account.account_number:
            raise ValueError("IBKR account number is required")

        # Validate symbols
        if not config.symbols:
            raise ValueError("At least one symbol must be configured")

        for symbol, symbol_config in config.symbols.items():
            if symbol_config.target_delta <= 0 or symbol_config.target_delta >= 1:
                raise ValueError(f"Invalid target_delta for {symbol}: must be between 0 and 1")

            if symbol_config.dte_min > symbol_config.dte_max:
                raise ValueError(f"Invalid DTE range for {symbol}: min > max")

            if symbol_config.roll_when_dte > symbol_config.dte_min:
                raise ValueError(f"Invalid roll DTE for {symbol}: roll_when_dte > dte_min")

        # Validate risk
        if config.risk.max_portfolio_margin_usage <= 0 or config.risk.max_portfolio_margin_usage > 1:
            raise ValueError("max_portfolio_margin_usage must be between 0 and 1")

        if config.risk.max_concentration_per_symbol <= 0 or config.risk.max_concentration_per_symbol > 1:
            raise ValueError("max_concentration_per_symbol must be between 0 and 1")

        # Validate strategy
        if not any([config.strategy.wheel_enabled, config.strategy.iron_condor_enabled,
                    config.strategy.strangle_enabled]):
            raise ValueError("At least one strategy must be enabled")

        logger.info("Configuration validation passed")


def load_config(config_path: str = "configs/thetagang.toml", env_path: str = ".env") -> Config:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to TOML configuration file
        env_path: Path to .env file

    Returns:
        Loaded and validated Config object
    """
    loader = ConfigLoader(config_path, env_path)
    return loader.load()
