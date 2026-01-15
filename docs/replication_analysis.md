# Replication Analysis

## Core Components

The ThetaGang project consists of the following key files and modules:

- **thetagang.py**: Main entry point that orchestrates the bot execution
- **entry.py**: CLI interface using Click framework
- **main.py**: Core application loop and initialization
- **portfolio_manager.py**: The largest module (129KB), handles portfolio management, position tracking, and strategy execution
- **config.py**: Configuration loading and validation from TOML files (35KB)
- **ibkr.py**: Integration layer with Interactive Brokers API using ib-async library
- **trades.py**: Trade execution and order management logic
- **orders.py**: Order creation and submission
- **options.py**: Options contract data structures
- **util.py**: Utility functions for calculations and helpers
- **exchange_hours.py**: Market hours and trading schedule management
- **log.py**: Logging configuration and formatting
- **fmt.py**: Formatting utilities for display

Configuration is managed through **thetagang.toml**, which defines account settings, margin usage, symbol configurations, and strategy parameters.

## Strategy Flow

The Wheel strategy implemented in ThetaGang follows these steps:

1. **Sell Cash-Secured Puts**: When not holding the underlying stock, the bot sells out-of-the-money put options to collect premium. Puts are selected based on delta thresholds and minimum premium requirements configured per symbol.

2. **Handle Assignment**: If puts are exercised (assigned), the bot acquires shares of the underlying stock at the strike price. This converts the position from short puts to long stock.

3. **Sell Covered Calls**: Once holding stock, the bot sells out-of-the-money call options against the shares to generate additional premium income. Calls are selected using similar delta and premium criteria.

4. **Roll Positions**: When options approach expiration or reach profit targets (based on configured thresholds), the bot can roll positions forward to later expiration dates to extend the trade and capture additional premium.

5. **Exit on Assignment**: If covered calls are exercised, shares are called away at the strike price, completing the wheel cycle. The bot then returns to step 1.

The bot continuously monitors positions, manages multiple symbols simultaneously, and respects configured margin limits and buying power constraints.

## Dependencies

The project relies on the following core dependencies (from pyproject.toml):

- **ib-async** (v2.0.1+): Asynchronous Python wrapper for Interactive Brokers TWS/Gateway API, enabling non-blocking market data retrieval and order execution
- **toml** (v0.10.2): TOML file parsing for configuration management
- **click** (v8.1.3+): Command-line interface framework for the entry point
- **click-log**: Logging integration with Click CLI
- **pydantic** (v2.10.2+): Data validation and settings management
- **numpy** (v1.26+): Numerical computations for portfolio calculations
- **python-dateutil**: Date and time parsing utilities
- **pytimeparse**: Time duration parsing
- **rich** (v13.7.0+): Terminal formatting and rich text output
- **schema**: Data validation schemas
- **exchange-calendars** (v4.8+): Market calendar and trading hours information
- **more-itertools**: Extended iteration utilities

Development dependencies include pytest for testing, ruff for linting, and pyright for type checking.

## Limitations

While ThetaGang effectively implements the Wheel strategy, it has several limitations:

1. **Single Strategy Focus**: The bot is designed exclusively for the Wheel strategy. It does not support other options strategies like iron condors, strangles, spreads, or butterflies.

2. **Basic Hedging**: Limited hedging capabilities beyond the inherent structure of the Wheel. No support for protective puts, collars, or portfolio-level hedging.

3. **No Multi-Strategy Support**: Cannot run different strategies simultaneously or switch between strategies based on market conditions (trending vs. range-bound markets).

4. **Simple Position Sizing**: Position sizing is based on margin usage and buying power but doesn't incorporate volatility-based dynamic sizing or risk parity approaches.

5. **Limited Risk Management**: Basic risk controls (margin limits, delta targets) but lacks advanced features like maximum drawdown limits, volatility-adjusted position sizing, or correlation-based portfolio constraints.

6. **Single Data Source**: Relies entirely on IBKR for market data; no integration with alternative data providers for enhanced analysis or redundancy.

7. **No Backtesting Framework**: While tests exist for logic validation, there's no comprehensive backtesting system for evaluating strategy performance on historical data.

8. **Limited Analytics**: Basic logging and position tracking, but no built-in performance metrics, risk analytics, or detailed reporting beyond what IBKR provides.
