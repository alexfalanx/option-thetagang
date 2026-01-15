# Development Roadmap

This document outlines the phased implementation plan for ThetaGangExpanded, from core replication through advanced features.

## Phase 1: Core Replication (Replicate Wheel Strategy)

### Objectives
Implement the fundamental Wheel strategy with IBKR integration, matching the capabilities of the original ThetaGang project.

### Deliverables

**Configuration System**
- TOML configuration parser (`config_loader.py`)
- Environment variable loading for credentials
- Schema validation for all configuration fields
- Per-symbol and global parameter support

**IBKR Integration**
- Asynchronous connection to TWS/IB Gateway via ib-async
- Market data fetching (options chains, Greeks, current prices)
- Portfolio and position monitoring
- Account balance and buying power tracking
- Order submission, modification, and cancellation
- Error handling and reconnection logic

**Core Wheel Strategy**
- Put selling logic based on delta and premium criteria
- Assignment detection and stock position handling
- Covered call selling against stock positions
- Position rolling when approaching expiration or profit targets
- Complete cycle management from put sale through call assignment

**Basic Risk Management**
- Margin limit enforcement
- Maximum positions per symbol
- Buying power calculations
- Simple position sizing

**Testing**
- Unit tests for strategy logic with 80%+ coverage
- Integration tests with IBKR paper account
- Basic validation of order placement and position tracking

**Deployment**
- Simple local execution script
- Basic logging to files
- Manual run capability

### Acceptance Criteria
- Bot successfully executes full Wheel cycles in paper trading
- All tests passing
- Matches original ThetaGang core functionality
- No critical bugs in week-long paper trading run

## Phase 2: Strategy Expansion (Add Iron Condor)

### Objectives
Expand beyond the Wheel to support additional options strategies, starting with iron condors for range-bound markets.

### Deliverables

**Strategy Framework**
- Abstract `Strategy` base class defining common interface
- Refactor Wheel strategy to implement the base class
- Strategy selection and configuration system

**Iron Condor Strategy**
- Identify range-bound market conditions
- Sell OTM call spread and put spread simultaneously
- Manage both sides independently
- Roll or close based on profit targets and expiration
- Handle early assignment on short legs

**Multi-Strategy Management**
- Portfolio-level strategy allocation (X% Wheel, Y% Iron Condor)
- Strategy performance tracking and comparison
- Dynamic strategy selection based on market regime (optional advanced feature)

**Enhanced Risk Management**
- Volatility-based position sizing (reduce size when VIX spikes)
- Portfolio-level delta and theta limits
- Correlation-based concentration limits
- Stop-loss triggers for individual positions

**Testing**
- Unit tests for iron condor logic
- Backtests comparing Wheel vs Iron Condor performance
- Multi-strategy portfolio backtests

### Acceptance Criteria
- Iron condor strategy executes successfully in paper trading
- Strategy switching works correctly based on configuration
- Risk controls prevent over-concentration and excessive volatility exposure
- Backtest results show improved risk-adjusted returns in range-bound periods

## Phase 3: Advanced Features (Integrations, Testing, Monitoring)

### Objectives
Add production-grade features including advanced monitoring, comprehensive backtesting, external data integration, and deployment automation.

### Deliverables

**Data Integration**
- Polygon.io API integration for real-time quotes and historical data
- `DataProvider` interface for pluggable data sources
- Earnings calendar integration to avoid positions during earnings
- Alternative data sources (volatility surfaces, sentiment)

**Backtesting Framework**
- Historical data replay engine
- Realistic fill simulation (bid-ask spread, slippage)
- Comprehensive performance metrics (Sharpe, Calmar, max drawdown)
- Parameter optimization (grid search, Bayesian optimization)
- Monte Carlo simulation for stress testing

**Advanced Monitoring**
- Structured logging with JSON format
- Prometheus metrics export
- Grafana dashboard templates
- Email and Slack alerting
- Daily performance reports with P&L summaries

**Analytics and Reporting**
- Greeks aggregation across portfolio
- Risk exposure visualization
- Trade attribution analysis (which strategies contributed to P&L)
- Comparison vs benchmarks (SPY buy-and-hold)

**Deployment Automation**
- Dockerfile and Docker Compose configuration
- CI/CD pipeline (GitHub Actions) for automated testing
- Cloud deployment templates (AWS, GCP)
- Systemd service files for Linux servers
- Automated scheduling with market hours awareness

**UI Enhancements**
- CLI dashboard showing current positions and P&L
- Simple web interface for monitoring (optional)
- Configuration editor with validation

**Documentation**
- Complete API documentation
- Strategy tuning guides
- Troubleshooting playbook
- Video tutorials for setup and usage

### Acceptance Criteria
- Backtesting framework produces accurate, reproducible results
- Monitoring dashboard shows real-time portfolio state
- Alerts trigger correctly for error conditions
- Docker deployment works seamlessly
- System runs reliably for one month in paper trading with zero unplanned downtime
- Documentation enables a new user to set up and run the bot

## Future Enhancements (Beyond Phase 3)

Potential future additions based on user feedback and market needs:

- Additional strategies: strangles, butterflies, calendar spreads
- Machine learning for volatility prediction and strategy selection
- Multi-account support for managing multiple IBKR accounts
- Advanced portfolio optimization using Modern Portfolio Theory
- Options flow analysis for sentiment signals
- Integration with additional brokers (Tastytrade, Schwab)
- Mobile app for monitoring on the go

## Timeline Considerations

This roadmap is flexible and designed for iterative development:
- Each phase builds on the previous, ensuring a stable foundation
- Phases can be adjusted based on actual implementation challenges
- Testing and validation occur continuously, not just at phase end
- User feedback incorporated between phases

The goal is production-ready software at each phase, not a rush to features. Quality and reliability are prioritized over speed.
