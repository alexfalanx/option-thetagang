# Dependencies Documentation

## Core Dependencies

### python-dotenv
Loads environment variables from .env files into the application environment. This enables secure storage of sensitive configuration like API keys, account credentials, and broker connection details without hardcoding them in source files or configuration files that might be committed to version control.

### ib-async
An asynchronous Python wrapper for the Interactive Brokers TWS (Trader Workstation) and IB Gateway APIs. This library enables non-blocking interactions with IBKR for real-time market data retrieval, options chain fetching, portfolio monitoring, and order execution. The async nature allows the bot to handle multiple concurrent operations efficiently without blocking on network calls.

### toml
TOML (Tom's Obvious, Minimal Language) file parser for Python. Used to load and parse the main configuration file where trading parameters, symbol lists, delta targets, premium thresholds, and account settings are defined. TOML provides a human-readable configuration format that's easy to edit and validate.

### pandas
Powerful data manipulation and analysis library. Used for handling time series data, portfolio calculations, performance metrics tracking, historical data processing for backtesting, and generating reports. Pandas DataFrames provide an efficient way to work with tabular data like options chains and trade history.

### schedule
Simple, human-friendly job scheduling library for Python. Enables automated execution of the trading strategy at specified intervals (e.g., every hour during market hours, at market open/close). Handles recurring tasks without requiring complex cron syntax or external schedulers.

### requests
HTTP library for making API calls to external data providers. Used to integrate with services like Polygon.io for real-time quotes, historical data, market news, and alternative data sources. Provides a simple interface for RESTful API interactions with proper error handling and timeout management.

## Development Tools

### pytest
Comprehensive testing framework for Python. Used to write and run unit tests for strategy logic, integration tests for IBKR connectivity with paper trading accounts, and validation tests for configuration parsing. Supports fixtures, parametrized tests, and test discovery.

### black
Opinionated code formatter that enforces consistent Python code style. Automatically formats code to follow PEP 8 guidelines with minimal configuration, ensuring codebase consistency and reducing formatting debates in code reviews.

### mypy
Static type checker for Python. Analyzes type hints in the code to catch type-related errors before runtime. Improves code reliability, enables better IDE support with autocomplete and refactoring tools, and serves as living documentation of function signatures and data structures.
