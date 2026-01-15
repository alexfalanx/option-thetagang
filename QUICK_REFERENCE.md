# Quick Reference Card

## TL;DR - Get Started in 10 Minutes

### What You Need (All Free!)

1. ✅ **IBKR Account** - Sign up at https://www.interactivebrokers.com
2. ✅ **Paper Trading** - Enable in Account Management (DU account number)
3. ✅ **IB Gateway** - Download from IBKR website
4. ✅ **API Access** - Enable in Gateway settings

**Total Cost: $0** for paper trading!

---

## Quick Setup Steps

### 1. IBKR Account (5 minutes)
```
1. Go to https://www.interactivebrokers.com
2. Click "Open Account"
3. Fill out application (1-3 days approval)
4. Enable Paper Trading in Account Management
5. Note your paper account number (DU######)
```

### 2. IB Gateway (2 minutes)
```
1. Download: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
2. Install and run
3. Login with: Paper Trading Mode
```

### 3. Enable API (2 minutes)
```
In IB Gateway → Configure → Settings → API:
✓ Enable ActiveX and Socket Clients
✓ Socket port: 7497
✓ Trusted IPs: 127.0.0.1
□ Read-Only API: UNCHECKED
```

### 4. Configure Bot (1 minute)
```bash
cp .env.example .env
# Edit .env:
IBKR_ACCOUNT_NUMBER=DU1234567  # Your paper account
```

### 5. Test (1 minute)
```bash
python -m src.data_fetcher  # Should connect and show data
python -m src.main --once   # Run bot once
```

---

## Port Numbers (IMPORTANT!)

| Mode | Port | Account Type | Risk |
|------|------|--------------|------|
| Paper Trading | **7497** | DU###### | ✅ Safe (fake money) |
| Live Trading | **7496** | U####### | ⚠️ REAL MONEY |

**Always use 7497 for testing!**

---

## Safety Modes

### Level 1: Dry Run (Safest)
```toml
# configs/thetagang.toml
dry_run = true        # Just logs, no orders
port = 7497           # Paper trading
```
**Bot logs what it would do, but doesn't actually submit orders**

### Level 2: Paper Trading
```toml
# configs/thetagang.toml
dry_run = false       # Submits orders
port = 7497           # Paper trading (fake money)
```
**Bot submits real orders, but with fake money**

### Level 3: Live Trading (DANGER!)
```toml
# configs/thetagang.toml
dry_run = false       # Submits orders
port = 7496           # LIVE TRADING (real money!)
```
**Bot trades with REAL MONEY - only use after extensive testing!**

---

## Common Commands

```bash
# Test connection
python -m src.data_fetcher

# Run bot once (single cycle)
python -m src.main --once

# Run bot continuously (scheduled)
python -m src.main

# Run tests
pytest tests/ -v

# Check logs
tail -f logs/thetagang.log
```

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection refused | IB Gateway running? API enabled? |
| Wrong account | Use DU###### (paper), not U###### (live) |
| No market data | Normal in paper trading, might need subscriptions |
| Orders not executing | Check `dry_run` setting in config |
| Can't find .env | Run `cp .env.example .env` first |

---

## Configuration Quick Changes

### Only Run Wheel Strategy
```toml
[strategy]
wheel_enabled = true
iron_condor_enabled = false
```

### Only Run Iron Condor
```toml
[strategy]
wheel_enabled = false
iron_condor_enabled = true
```

### Auto-Select Strategy (Default)
```toml
[strategy]
wheel_enabled = true
iron_condor_enabled = true
# Bot picks best strategy per symbol
```

### Trade Only SPY
```toml
[symbols.tickers.SPY]
enabled = true

[symbols.tickers.QQQ]
enabled = false

[symbols.tickers.AAPL]
enabled = false
```

---

## File Locations

```
option-thetagang/
├── .env                      # Your secrets (account number)
├── configs/thetagang.toml    # Main configuration
├── logs/thetagang.log        # Execution logs
├── src/main.py              # Main bot entry point
└── tests/                    # Unit tests
```

---

## Safety Checklist (Every Time!)

Before running the bot:

- [ ] IB Gateway shows **"Paper Trading"** mode
- [ ] Port is **7497** (paper)
- [ ] Account starts with **DU** (paper)
- [ ] Config has `dry_run = true` (for first tests)
- [ ] You understand what the bot will do
- [ ] You've reviewed the symbols in config

---

## Getting Help

1. **Setup Issues:** See `IBKR_SETUP_GUIDE.md`
2. **Usage Questions:** See `QUICKSTART.md`
3. **Technical Details:** See `IMPLEMENTATION_SUMMARY.md` (Phase 1) and `PHASE2_SUMMARY.md`
4. **Strategy Info:** See `README.md`

---

## Next Steps After Setup

1. ✅ Run in **dry-run mode** for a day (just logs)
2. ✅ Set `dry_run = false` and run in **paper trading** for 1-2 weeks
3. ✅ Monitor positions, P&L, and bot behavior
4. ✅ Adjust configuration based on results
5. ✅ Only go live after you're completely comfortable

---

**Remember:** There's no rush! Paper trading is free and unlimited. Take your time to understand how everything works.

Happy trading! 🚀 (But safely!)
