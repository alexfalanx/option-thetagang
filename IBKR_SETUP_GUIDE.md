# Interactive Brokers Setup Guide for ThetaGang

Complete guide to setting up IBKR paper trading and API access for testing the bot.

---

## Overview

To test ThetaGang, you need:
1. ✅ Interactive Brokers account (free to open)
2. ✅ Paper Trading account (completely free, no real money)
3. ✅ TWS or IB Gateway software (free download)
4. ✅ API access enabled (free)

**Total Cost: $0** for paper trading!

---

## Step 1: Create Interactive Brokers Account

### Option A: Individual Account (Recommended for Testing)

1. **Go to IBKR website:**
   - Visit: https://www.interactivebrokers.com
   - Click "Open Account" or "Get Started"

2. **Choose Account Type:**
   - Select **"Individual Account"**
   - Choose your country of residence

3. **Fill Out Application:**
   - Personal information (name, address, SSN/tax info)
   - Employment information
   - Financial information
   - Trading experience

   **Note:** Be honest but know that:
   - You need "some" options trading experience in the form
   - Paper trading doesn't require minimum balances
   - Approval usually takes 1-3 business days

4. **Fund Account (Optional for Paper Trading):**
   - For **paper trading only**: You don't need to fund
   - For **live trading**: Minimum $0 (but need money to trade obviously)
   - You can skip funding if only doing paper trading

5. **Account Approval:**
   - Wait for approval email (usually 1-3 business days)
   - You'll receive account number (e.g., U1234567)

### Option B: Just Want to Test Fast?

If you already have an IBKR account:
- Skip to Step 2 to enable paper trading
- If you don't have an account yet, follow Option A above

---

## Step 2: Enable Paper Trading Account

**THIS IS THE KEY FOR SAFE TESTING!**

1. **Log into Account Management:**
   - Go to: https://www.interactivebrokers.com
   - Click "Login" → "Account Management"
   - Use your username and password

2. **Navigate to Paper Trading:**
   - Click on your username (top right)
   - Select "Settings" or "Paper Trading Account"
   - Or go to: Settings → User Settings → Paper Trading Account

3. **Create Paper Trading Account:**
   - Click "Create Paper Trading Account" or similar
   - It will create a new account number starting with "DU" (e.g., DU1234567)
   - This is your **Paper Trading Account Number** - write it down!

4. **Set Paper Trading Balance:**
   - You can usually set the starting balance
   - Default is often $1,000,000 (fake money)
   - This is completely separate from any real account

**Important Notes:**
- Paper trading account is **completely separate** from live account
- Uses **real market data** but **fake money**
- Perfect for testing - you can't lose real money
- Resets are possible if you blow up the account
- All the same features as live trading

---

## Step 3: Download TWS or IB Gateway

You need software to connect to IBKR. Two options:

### Option A: IB Gateway (Recommended for Bots)

**Pros:**
- Lighter weight, less resource intensive
- Designed for API/bot connections
- No charts or complex UI
- Faster startup

**Download:**
1. Go to: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
2. Download for your OS (Windows/Mac/Linux)
3. Install the software

### Option B: Trader Workstation (TWS)

**Pros:**
- Full trading platform with charts
- Good if you want to manually check positions
- More features for manual trading

**Download:**
1. Go to: https://www.interactivebrokers.com/en/trading/tws.php
2. Download for your OS
3. Install the software

**Recommendation:** Start with **IB Gateway** - it's simpler for bot usage.

---

## Step 4: Configure IB Gateway/TWS for API Access

This is the most important part!

### A. Login to Paper Trading

1. **Open IB Gateway** (or TWS)

2. **Select Paper Trading:**
   - Look for a toggle or dropdown that says "Trading Mode"
   - Select **"Paper Trading"** (not "Live Trading")
   - This is CRITICAL - always verify you're in paper trading!

3. **Login:**
   - Username: Your IBKR username
   - Password: Your IBKR password
   - Trading Mode: **Paper Trading** ✓
   - Click Login

### B. Enable API Connections

**In IB Gateway:**

1. After logging in, you'll see the Gateway window

2. Click **"Configure"** → **"Settings"**

3. Go to **"API"** → **"Settings"** section

4. **Enable the following:**
   ```
   ✓ Enable ActiveX and Socket Clients
   ✓ Socket port: 7497 (for paper trading)
   ✓ Trusted IP addresses: 127.0.0.1 (localhost)
   ✓ Master API client ID: (leave blank or set to 0)
   □ Read-Only API: UNCHECKED (we need to submit orders)
   ✓ Download open orders on connection: CHECKED
   ✓ Create API message log file: CHECKED (helpful for debugging)
   ```

5. **Click "OK"** and restart Gateway if needed

**In TWS (if using TWS instead):**

1. Click **File** → **Global Configuration**

2. Go to **API** → **Settings**

3. Same settings as above

4. Click "OK" and restart TWS

### C. Important Port Numbers

- **Paper Trading:** Port **7497**
- **Live Trading:** Port **7496**

Our bot is configured for port 7497 (paper trading) by default.

**Never confuse these!** 7497 = paper, 7496 = live

---

## Step 5: Verify API Connection

Test that everything is working:

### Quick Test with Python

1. **Make sure IB Gateway is running** (logged into paper trading)

2. **In your terminal:**
   ```bash
   cd option-thetagang
   source venv/bin/activate  # Activate your virtual environment
   python -m src.data_fetcher
   ```

3. **You should see:**
   ```
   INFO - Connecting to IBKR at 127.0.0.1:7497 (client_id=1)
   INFO - Successfully connected to IBKR
   SPY Price: $XXX.XX
   Net Liquidation: $1,000,000.00
   Found X options
   ```

4. **If you see connection errors:**
   - Verify IB Gateway is running
   - Check API is enabled in settings
   - Confirm port is 7497
   - Make sure you're logged into paper trading mode

---

## Step 6: Configure the Bot

Now configure ThetaGang to use your paper trading account:

1. **Copy the environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env:**
   ```bash
   nano .env  # or use your favorite editor
   ```

3. **Set your paper trading account number:**
   ```
   IBKR_ACCOUNT_NUMBER=DU1234567  # Your paper trading account (starts with DU)
   ```

4. **Save and exit**

5. **Verify config:**
   - Open `configs/thetagang.toml`
   - Confirm `dry_run = true` (extra safety!)
   - Confirm port is 7497 in `[account]` section:
     ```toml
     [account]
     host = "127.0.0.1"
     port = 7497  # Paper trading port
     ```

---

## Step 7: First Test Run

Let's run the bot!

### A. Start IB Gateway

1. Open IB Gateway
2. Login to **Paper Trading** (verify the mode!)
3. Make sure API is enabled (green checkmark)

### B. Run the Bot

```bash
cd option-thetagang
source venv/bin/activate  # If not already activated

# Test connection
python -m src.data_fetcher

# Run bot once
python -m src.main --once
```

### C. What You Should See

```
============================================================
ThetaGangExpanded - Automated Options Trading Bot
============================================================
INFO - ThetaGangExpanded Bot Initialized
INFO - Dry run mode: True
INFO - Number of symbols: 4
INFO - Enabled strategies: Wheel, IronCondor
INFO - Connecting to IBKR...
INFO - Successfully connected to IBKR at 127.0.0.1:7497
INFO - All components initialized
============================================================
Starting trading cycle
============================================================
INFO - Account: DU1234567
INFO - Net Liquidation: $1,000,000.00
INFO - Buying Power: $1,000,000.00
INFO - Current positions: 0

Analyzing SPY...
SPY price: $450.25
SPY HV: 18%
SPY: Using iron_condor strategy
SPY: 1 recommendations
  - sell_iron_condor (iron_condor): Sell iron condor: $440/$435/$460/$465 for $2.50 credit

✓ Trade approved: sell_iron_condor SPY
DRY RUN MODE: Order not actually submitted

...
============================================================
Trading cycle complete
============================================================
```

---

## Troubleshooting Common Issues

### "Connection refused" Error

**Problem:** Can't connect to IBKR

**Solutions:**
1. ✅ Is IB Gateway running?
2. ✅ Are you logged into paper trading mode?
3. ✅ Is API enabled in settings?
4. ✅ Is port 7497 correct?
5. ✅ Is 127.0.0.1 in trusted IPs?

### "Not connected" Error

**Problem:** Connection drops during operation

**Solutions:**
1. Check IB Gateway didn't auto-logout
2. Restart IB Gateway
3. Check your internet connection
4. Try increasing timeout in bot config

### "Invalid account number" Error

**Problem:** Account number not recognized

**Solutions:**
1. Use paper trading account (DU######), not live account (U######)
2. Copy account number from IBKR Account Management exactly
3. Remove any spaces or extra characters

### "No market data permissions" Error

**Problem:** Can't get options data

**Solutions:**
1. In paper trading, you usually have all data
2. Check you're logged in correctly
3. Try subscribing to options data in Account Management
4. For paper trading, this is usually free

### API Settings Keep Resetting

**Problem:** Settings don't save

**Solutions:**
1. Make sure to click "OK" not "Cancel"
2. Restart IB Gateway after changing settings
3. Check you have write permissions to IBKR config folder

---

## Safety Checklist Before Running

Every time before running the bot:

- [ ] IB Gateway is in **Paper Trading mode** (not Live!)
- [ ] Bot config has `dry_run = true`
- [ ] Port is **7497** (paper trading)
- [ ] Account number starts with **DU** (paper account)
- [ ] You've tested connection with `python -m src.data_fetcher`
- [ ] You understand what the bot will do
- [ ] You're ready to monitor the first run

---

## Going from Dry-Run to Paper Trading Orders

Once you're comfortable with dry-run mode:

1. **In `configs/thetagang.toml`:**
   ```toml
   dry_run = false  # Enable actual order submission
   ```

2. **Keep using paper trading!**
   - Still port 7497
   - Still DU account number
   - Still IB Gateway in paper mode

3. **The bot will now submit actual (paper) orders**
   - You can see them in IB Gateway
   - They execute with real market data
   - But using fake money

4. **Monitor closely:**
   - Watch positions open and close
   - Check P&L tracking
   - Verify orders execute as expected

---

## Going from Paper to Live (DANGER ZONE)

**⚠️ WARNING: Only do this after extensive paper trading!**

When you're absolutely ready for live trading:

1. **In IB Gateway:**
   - Change mode to **"Live Trading"** (not Paper)
   - Port becomes **7496** (live port)

2. **In `configs/thetagang.toml`:**
   ```toml
   [account]
   port = 7496  # Live trading port
   ```

3. **In `.env`:**
   ```
   IBKR_ACCOUNT_NUMBER=U1234567  # Live account (starts with U)
   ```

4. **Start with tiny positions:**
   - Set `max_positions = 1`
   - Use small, safe symbols
   - Monitor constantly

5. **Have real money in account:**
   - Ensure sufficient buying power
   - Understand margin requirements

**Recommended:** Run in paper trading for at least 2-4 weeks first!

---

## Helpful Resources

### IBKR Documentation
- **API Guide:** https://interactivebrokers.github.io/tws-api/
- **Account Management:** https://www.interactivebrokers.com/portal
- **Paper Trading:** Search "paper trading" in IBKR help

### ThetaGang Bot
- **Quick Start:** See `QUICKSTART.md`
- **Phase 1 Summary:** See `IMPLEMENTATION_SUMMARY.md`
- **Phase 2 Summary:** See `PHASE2_SUMMARY.md`

### Community
- **IBKR Forums:** https://www.interactivebrokers.com/en/community.php
- **TWS API Forums:** https://groups.io/g/twsapi

---

## Summary Checklist

Setup checklist:

- [ ] Create IBKR account
- [ ] Enable paper trading account (DU number)
- [ ] Download & install IB Gateway
- [ ] Configure API settings (port 7497, enable API)
- [ ] Copy .env.example to .env
- [ ] Set IBKR_ACCOUNT_NUMBER in .env
- [ ] Verify dry_run = true in config
- [ ] Test connection with data_fetcher
- [ ] Run bot with --once flag
- [ ] Monitor logs for successful execution
- [ ] Review paper trades in IB Gateway

**You're ready to test!** 🚀

Start with dry-run mode, then move to paper trading, and only go live after extensive testing.

---

**Questions?** Check the troubleshooting section above or open an issue on GitHub.

**Remember:** Paper trading is completely free and risk-free. Take your time learning!
