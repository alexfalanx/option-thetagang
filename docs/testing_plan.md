# Testing and Backtesting Plan

This document outlines the comprehensive testing strategy for ThetaGangExpanded, covering unit tests, integration tests, and backtesting framework.

## Unit Tests

Unit tests validate individual components in isolation with mocked dependencies.

### Strategy Logic Tests

Test the core Wheel strategy decision-making:

- Verify put selection logic chooses contracts matching delta and premium criteria
- Confirm call selection follows configuration parameters after assignment
- Test rolling logic correctly identifies positions ready to roll based on profit targets and expiration
- Validate assignment detection and position state transitions
- Ensure edge cases are handled (no suitable contracts available, extreme market conditions)

### Risk Manager Tests

Validate risk control calculations:

- Test margin limit enforcement rejects trades exceeding available buying power
- Verify position sizing calculations based on volatility metrics
- Confirm portfolio concentration limits prevent over-allocation to single symbols
- Test stop-loss triggers activate at correct thresholds
- Validate multiple risk rules can be composed and all must pass

### Configuration Tests

Ensure configuration loading and validation works correctly:

- Test valid TOML files parse successfully with all expected fields
- Verify invalid configurations are rejected with clear error messages
- Confirm environment variable overrides work properly
- Test default values are applied when optional fields are missing
- Validate symbol-specific configurations override global settings correctly

### Data Normalization Tests

Verify data from different sources is normalized consistently:

- Test options chain data from IBKR matches expected format
- Confirm Polygon data converts to internal data structures correctly
- Validate Greeks calculations match expected values
- Test handling of missing or incomplete data

## Integration Tests

Integration tests validate interactions with external systems using paper trading accounts and test APIs.

### IBKR Connectivity Tests

Test real interactions with Interactive Brokers:

- Verify connection to TWS/Gateway succeeds with valid credentials
- Test market data subscription and retrieval for options chains
- Confirm portfolio position fetching returns accurate data
- Validate order submission succeeds and returns order IDs
- Test order cancellation and modification operations
- Verify graceful handling of disconnections and reconnections
- Ensure rate limiting respects IBKR API constraints

All IBKR integration tests run against paper trading accounts to avoid real financial impact.

### Polygon API Tests

Validate external data provider integration:

- Test quote retrieval for configured symbols
- Verify historical data fetching for backtesting
- Confirm API key authentication works
- Test error handling for rate limits and API failures
- Validate data format matches expectations

### End-to-End Trading Flow Tests

Test complete trading cycles:

- Verify full Wheel cycle: sell put, handle assignment, sell call, exit on call assignment
- Test multiple positions managed simultaneously across different symbols
- Confirm risk checks prevent excessive position sizes
- Validate orders are placed correctly based on strategy signals
- Test scheduling runs at appropriate intervals during market hours
- Verify state persistence across restarts

## Backtesting Framework

Backtesting validates strategy performance on historical data before live deployment.

### Historical Data Replay

Build a backtesting engine that simulates trading:

- Load historical options chain data from Polygon or stored snapshots
- Replay market conditions day-by-day or intraday
- Simulate strategy decisions using historical prices and Greeks
- Model order fills with realistic assumptions about bid-ask spreads and slippage
- Track simulated portfolio over time including cash, positions, and margin usage

### Performance Metrics

Calculate comprehensive statistics on backtest results:

- **Sharpe Ratio**: Risk-adjusted return measure (target > 1.0)
- **Maximum Drawdown**: Largest peak-to-trough decline (monitor for risk)
- **Win Rate**: Percentage of profitable trades
- **Average P&L per Trade**: Mean profit or loss across all trades
- **Total Return**: Overall portfolio appreciation over backtest period
- **Calmar Ratio**: Return divided by maximum drawdown
- **Volatility**: Standard deviation of returns

Compare metrics against buy-and-hold benchmarks (SPY, QQQ) to assess alpha generation.

### Scenario Testing

Run backtests across different market conditions:

- Bull markets (2019, 2020-2021)
- Bear markets (2022, COVID crash March 2020)
- High volatility periods (VIX > 30)
- Low volatility periods (VIX < 15)
- Different underlying symbols (tech stocks, indexes, dividend stocks)

Analyze which conditions favor the Wheel strategy and where it struggles.

### Parameter Optimization

Test different configuration parameters to find optimal settings:

- Delta targets (0.10 to 0.40 for puts/calls)
- Days to expiration preferences (7 DTE vs 21 DTE vs 45 DTE)
- Profit-taking thresholds (50% of max profit vs 75%)
- Minimum premium requirements
- Position sizing rules

Use grid search or Bayesian optimization to explore parameter space efficiently.

## Test Acceptance Criteria

All tests must meet the following standards before code is considered production-ready:

### Coverage Requirements

- Minimum 80% code coverage across all modules
- 100% coverage for core strategy logic and risk management
- Critical paths (order execution, position tracking) fully tested

### Quality Standards

- No test failures in continuous integration (CI) environment
- All integration tests pass against paper trading account
- No flaky tests (intermittent failures due to timing or randomness)
- Tests run in under 5 minutes for rapid feedback

### Backtesting Standards

- Backtests cover at least 2 years of historical data
- Test against at least 3 different underlying symbols
- Include at least one high volatility period and one low volatility period
- Sharpe ratio > 1.0 on backtest data (aspirational, not guaranteed)
- Maximum drawdown < 30% in worst-case scenarios

### Documentation

- Each test includes docstring explaining what it validates
- Integration tests document required setup (API keys, paper account configuration)
- Backtest results documented with charts and metrics summary

## Testing Workflow

Recommended testing process:

1. Write unit tests alongside new feature development
2. Run unit tests locally before committing code
3. CI system runs full unit test suite on every commit
4. Integration tests run nightly or on-demand before releases
5. Backtests run when strategy logic or parameters change
6. Review backtest results before deploying new strategy versions

This multi-layered testing approach ensures reliability, validates strategy effectiveness, and prevents costly errors in live trading environments.
