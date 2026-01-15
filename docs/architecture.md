# Project Architecture

## Modules

The ThetaGangExpanded system is organized into focused, loosely-coupled modules:

### core_strategy.py
Contains the core Wheel strategy logic including put selling rules, call selling rules, position rolling logic, and assignment handling. This module makes strategy decisions based on current portfolio state, market data, and configuration parameters. Returns recommended trades without executing them directly.

### risk_manager.py
Implements risk controls and position sizing calculations. Checks proposed trades against margin limits, maximum position sizes, portfolio concentration limits, and volatility-based constraints. Can reject trades that violate risk parameters. Monitors overall portfolio health and can trigger position reductions or trading halts.

### data_fetcher.py
Handles all external data retrieval from IBKR and Polygon.io. Fetches options chains with Greeks, current market prices, portfolio positions, account balances, historical volatility data, and earnings calendars. Normalizes data from different sources into consistent internal formats. Includes retry logic and error handling for API failures.

### order_executor.py
Manages order creation, submission, tracking, and cancellation. Translates strategy decisions into specific order objects, submits orders to IBKR via ib-async, monitors order status (filled, partially filled, rejected), handles order modifications and cancellations, and logs all order activity.

### config_loader.py
Loads and validates configuration from TOML files and environment variables. Parses symbol-specific settings, strategy parameters, risk limits, and account credentials. Validates configuration consistency and required fields. Provides a single source of truth for all configurable parameters across the system.

## Data Flow Diagram

```
┌─────────────────┐
│  Config Files   │
│  (.toml, .env)  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ config_loader   │
│                 │
└────────┬────────┘
         │
         v
    ┌────────────────────────────────┐
    │                                │
    v                                v
┌─────────────┐              ┌──────────────┐
│data_fetcher │              │ scheduler    │
│             │              │ (main loop)  │
│ IBKR API    │              └──────┬───────┘
│ Polygon API │                     │
└─────┬───────┘                     │
      │                             │
      │  Market Data                │
      │  Portfolio State            │
      └────────────┬────────────────┘
                   │
                   v
            ┌──────────────┐
            │core_strategy │
            │              │
            │ Wheel Logic  │
            └──────┬───────┘
                   │
                   │ Proposed Trades
                   │
                   v
            ┌──────────────┐
            │risk_manager  │
            │              │
            │ Validate     │
            └──────┬───────┘
                   │
                   │ Approved Trades
                   │
                   v
            ┌──────────────┐
            │order_executor│
            │              │
            │ Submit Orders│
            └──────┬───────┘
                   │
                   v
              ┌─────────┐
              │  IBKR   │
              │ Orders  │
              └─────────┘
```

## Expansion Hooks

The architecture provides clear extension points for adding new capabilities:

### Strategy Base Class
Define an abstract `Strategy` base class with methods like `analyze_market()`, `generate_signals()`, and `should_roll()`. The Wheel strategy implements this interface. New strategies like IronCondor, Strangle, or custom approaches can inherit from this base class and implement the same interface, allowing the system to work with any strategy without code changes elsewhere.

### Data Provider Interface
Create a `DataProvider` interface with methods for fetching options chains, quotes, and Greeks. The current IBKR and Polygon implementations conform to this interface. Additional providers (Yahoo Finance, TDA API, etc.) can be added by implementing the same interface, and the system can switch between providers through configuration.

### Risk Rule System
Implement risk rules as independent, composable validators. Each rule (margin check, volatility check, concentration check) implements a `validate(trade, portfolio)` method. New risk rules can be added without modifying existing code, and rules can be enabled/disabled via configuration.

### Event Hooks
Provide event hooks for pre-trade, post-trade, and end-of-day events. External modules (logging, alerting, analytics) can subscribe to these events. This allows adding monitoring, notifications, and custom logic without coupling to core trading code.

### Strategy Selector
Design a `StrategySelector` component that can choose which strategy to use based on market conditions. Implement selectors for volatility regime detection, trend identification, or manual override. This enables dynamic strategy switching as market conditions change.

The modular design ensures each component has a single responsibility, clear interfaces, and minimal coupling. This makes testing easier (mock data providers, validate strategies independently), enables parallel development of different modules, and allows incremental enhancement without disrupting working code.
