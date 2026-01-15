# ThetaGang Quick Start Guide

This guide will help you get the ThetaGang bot running in paper trading mode in under 10 minutes.

## Prerequisites

- Python 3.10 or higher installed
- Interactive Brokers account with paper trading enabled
- TWS (Trader Workstation) or IB Gateway installed

## Step 1: Set Up IBKR

1. **Open IB Gateway or TWS**
   - Log in to your **paper trading** account
   - Go to Configuration → API → Settings
   - Enable "ActiveX and Socket Clients"
   - Set Socket Port to **7497** (paper trading port)
   - Add 127.0.0.1 to Trusted IP Addresses
   - **Uncheck** "Read-Only API" (we need to submit orders)
   - Click OK and restart if needed

2. **Keep IB Gateway/TWS running** while the bot operates

## Step 2: Install Dependencies

```bash
cd option-thetagang

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

## Step 3: Configure the Bot

1. **Create .env file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env and add your paper trading account number:**
   ```
   IBKR_ACCOUNT_NUMBER=DU1234567  # Replace with YOUR paper account number
   ```

3. **Review configs/thetagang.toml:**
   - The default configuration trades SPY, QQQ, and AAPL
   - Verify `dry_run = true` (this prevents actual order submission)
   - Adjust symbols, deltas, and DTE ranges if desired

## Step 4: Test the Connection

Run the data fetcher test to verify IBKR connection:

```bash
python -m src.data_fetcher
```

You should see:
- "Successfully connected to IBKR"
- Stock prices for SPY
- Account information
- Options chain data

If you see connection errors, check:
- IB Gateway/TWS is running
- API connections are enabled
- Port is 7497
- Your account number in .env is correct

## Step 5: Run the Bot

**Option A: Single run (one iteration)**
```bash
python -m src.main --once
```

This will:
1. Connect to IBKR
2. Fetch positions and market data
3. Analyze each symbol
4. Generate trade recommendations
5. Validate against risk limits
6. Log what trades would be executed (dry-run mode)
7. Exit

**Option B: Scheduled mode (runs continuously)**
```bash
python -m src.main
```

This runs every 60 minutes during market hours (9:30 AM - 4:00 PM ET).

## Step 6: Review the Output

Check the logs:
```bash
tail -f logs/thetagang.log
```

You'll see:
- Connection status
- Current positions
- Account information
- Trade recommendations
- Risk validation results
- Order execution (DRY RUN mode)

## Step 7: Monitor in Paper Trading

1. Let the bot run for a few days in **dry_run mode**
2. Review the logs to understand what trades it would make
3. Verify the strategy aligns with your expectations
4. Check that risk limits are appropriate

## Going Live (When Ready)

**WARNING**: Only do this after extensive paper trading!

1. In `configs/thetagang.toml`, change:
   ```toml
   dry_run = false  # DANGER: This enables real trading!
   ```

2. Update .env with your **live** account number

3. Change port in config to **7496** (live trading port)

4. Start with very small position sizes

5. Monitor closely for the first few weeks

## Troubleshooting

**"Connection refused" error:**
- Check IB Gateway/TWS is running
- Verify API connections are enabled
- Confirm port is 7497

**"No options chain found":**
- Verify you have market data subscriptions in IBKR
- Check that symbols are configured correctly

**"Insufficient buying power":**
- Check account has sufficient cash
- Review position sizes in config

**"Account number is required":**
- Verify .env file has IBKR_ACCOUNT_NUMBER set
- Make sure .env is in the project root directory

## Running Tests

Verify everything works:

```bash
pytest tests/ -v
```

All tests should pass.

## Next Steps

- Read `/docs/architecture.md` to understand the system design
- Review `/docs/roadmap.md` for planned features
- Customize `configs/thetagang.toml` for your preferences
- Join the community and share feedback!

## Important Safety Notes

1. **Always start with dry_run = true**
2. **Never trade with money you can't afford to lose**
3. **Test extensively in paper trading first**
4. **Understand the Wheel strategy before using**
5. **Monitor positions regularly**
6. **Have a plan for assignment scenarios**

Happy trading! (But safely, please!)
