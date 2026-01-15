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

This project is currently in the **planning phase**. All architecture, documentation, and blueprints are complete. Implementation of actual trading code is the next phase.

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

**Note**: Implementation is not yet complete. The following commands are planned functionality.

Run the bot manually:
```bash
python -m src.main
```

Run backtests:
```bash
python -m src.backtest --start-date 2023-01-01 --end-date 2024-01-01
```

Run tests:
```bash
pytest tests/
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
