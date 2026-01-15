# ThetaGangExpanded

An enhanced options trading bot that replicates and extends the ThetaGang Wheel strategy with advanced risk management, multi-strategy support, and comprehensive monitoring capabilities.

## Overview

ThetaGangExpanded builds upon the foundation of the original ThetaGang project, implementing the proven "Wheel" options strategy while adding significant enhancements:

- **Core Wheel Strategy**: Automated selling of cash-secured puts, covered calls, and position rolling
- **Advanced Risk Management**: Volatility-based position sizing, portfolio concentration limits, and stop-loss triggers
- **Multi-Strategy Framework**: Extensible architecture supporting additional strategies like iron condors and strangles
- **Enhanced Data Integration**: Multiple data sources including IBKR and Polygon.io for robust market data
- **Comprehensive Monitoring**: Detailed logging, performance metrics, and alerting via email/Slack
- **Production-Ready Deployment**: Docker support, cloud deployment options, and automated scheduling

## Project Status

**Phase 2 - Strategy Expansion: COMPLETE!** ✓

### Phase 1 - Core Implementation ✓
- ✓ Configuration system (TOML + environment variables)
- ✓ IBKR data fetcher (async connection, options chains, positions, account info)
- ✓ Wheel strategy logic (cash-secured puts, covered calls, position rolling)
- ✓ Risk management (margin limits, concentration checks, VIX-based sizing)
- ✓ Order execution (dry-run mode, order tracking, status monitoring)
- ✓ Main orchestrator with scheduling
- ✓ Unit tests for core functionality

### Phase 2 - Multi-Strategy Support ✓
- ✓ Abstract Strategy base class for pluggable strategies
- ✓ Iron Condor strategy implementation (4-leg neutral strategy)
- ✓ Strategy Selector for dynamic strategy selection
- ✓ Market regime detection (bullish/bearish/neutral, high/low volatility)
- ✓ Multi-strategy portfolio management
- ✓ Enhanced configuration with Iron Condor parameters
- ✓ Comprehensive Iron Condor tests

**The bot now supports:**
- **Wheel Strategy** - For directional/premium collection
- **Iron Condor** - For range-bound, low-volatility markets
- **Dynamic Selection** - Auto-select best strategy per market conditions

Ready for multi-strategy paper trading! See Usage section below.

## Documentation

See `/docs` for comprehensive documentation including architecture, replication analysis, testing plans, and deployment guides.

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- Interactive Brokers account with TWS or IB Gateway
- (Optional) Polygon.io API key for enhanced market data

### Installation

1. Clone this repository:
```bash
git clone https://github.com/alexfalanx/ThetaGangExpanded.git
cd ThetaGangExpanded
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure credentials:
   - Copy `.env.example` to `.env` and fill in your IBKR credentials
   - Edit `configs/thetagang.toml` with your trading parameters

### Configuration

Edit `configs/thetagang.toml` to configure account settings, trading symbols, risk parameters, and position sizing.

## Usage

### Before First Run

1. **Start IB Gateway or TWS**
   - For paper trading: Configure to use port 7497
   - For live trading: Use port 7496 (NOT RECOMMENDED until thoroughly tested)
   - Enable API connections in TWS/Gateway settings

2. **Configure your .env file**
   ```bash
   cp .env.example .env
   # Edit .env and add your IBKR account number
   ```

3. **Review and customize configs/thetagang.toml**
   - Set symbols to trade
   - Adjust risk parameters
   - Verify dry_run = true for safety

### Running the Bot

**Run once (single iteration):**
```bash
python -m src.main --once
```

**Run continuously (scheduled mode):**
```bash
python -m src.main
```

The bot will:
- Run every 60 minutes during trading hours (9:30 AM - 4:00 PM ET)
- Analyze positions and market data
- Generate trade recommendations
- Validate trades against risk limits
- Execute approved trades (or log in dry-run mode)

### Run Tests

```bash
pytest tests/
```

### Testing Individual Modules

Each module has a `main()` function for standalone testing:

```bash
# Test data fetcher
python -m src.data_fetcher

# Test strategy logic
python -m src.core_strategy

# Test risk manager
python -m src.risk_manager
```

## Safety and Risk Disclaimer

**IMPORTANT**: This software is for educational purposes. Options trading carries significant risk. Always start with paper trading and never trade with money you cannot afford to lose. The authors are not responsible for any financial losses.

## Roadmap

Development is planned in three phases:

1. **Phase 1 - Core Replication**: Implement the Wheel strategy with IBKR integration
2. **Phase 2 - Strategy Expansion**: Add iron condor and additional strategies
3. **Phase 3 - Advanced Features**: Enhanced monitoring, backtesting, and optimizations

See `docs/roadmap.md` for detailed phase breakdown.

## Contributing

This is a personal project forked from the original ThetaGang. Contributions, suggestions, and feedback are welcome through GitHub issues and pull requests.

## License

This project builds upon ThetaGang, which is licensed under AGPL-3.0. This expanded version maintains the same license.

## Acknowledgments

- Original ThetaGang project by Brenden Matthews: https://github.com/brndnmtthws/thetagang
- Interactive Brokers for API access
- The options trading community for strategy insights
