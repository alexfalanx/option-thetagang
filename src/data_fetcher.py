"""
Data fetcher for ThetaGangExpanded.

Handles all external data retrieval from IBKR and optional Polygon.io.
Provides normalized data structures for use by strategy and risk modules.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

from ib_async import IB, Stock, Option, Contract, PortfolioItem, AccountValue
from ib_async import util

logger = logging.getLogger(__name__)


@dataclass
class OptionChainData:
    """Normalized options chain data."""
    symbol: str
    strike: float
    expiration: datetime
    right: str  # 'C' for call, 'P' for put

    # Market data
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int

    # Greeks
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None  # Implied volatility

    # Metadata
    contract: Optional[Contract] = None


@dataclass
class Position:
    """Current portfolio position."""
    symbol: str
    position_type: str  # 'stock', 'option'
    quantity: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float

    # For options
    strike: Optional[float] = None
    expiration: Optional[datetime] = None
    right: Optional[str] = None

    contract: Optional[Contract] = None


@dataclass
class AccountInfo:
    """Account balance and buying power information."""
    account_number: str
    net_liquidation: float
    total_cash: float
    buying_power: float
    available_funds: float
    excess_liquidity: float
    margin_used: float
    margin_available: float


class DataFetcher:
    """
    Handles all data fetching from IBKR and external sources.
    Provides retry logic, error handling, and data normalization.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        """
        Initialize data fetcher.

        Args:
            host: IBKR TWS/Gateway host
            port: IBKR TWS/Gateway port (7497 paper, 7496 live)
            client_id: Unique client ID for this connection
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self._connected = False

    async def connect(self, timeout: int = 30) -> bool:
        """
        Connect to IBKR TWS/Gateway.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully

        Raises:
            ConnectionError: If connection fails
        """
        try:
            logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})")
            await self.ib.connectAsync(self.host, self.port, self.client_id, timeout=timeout)
            self._connected = True
            logger.info("Successfully connected to IBKR")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self._connected = False
            raise ConnectionError(f"Could not connect to IBKR: {e}")

    async def disconnect(self):
        """Disconnect from IBKR."""
        if self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self._connected and self.ib.isConnected()

    async def _ensure_connected(self):
        """Ensure connection is active, reconnect if needed."""
        if not self.is_connected():
            logger.warning("Connection lost, attempting to reconnect...")
            await self.connect()

    async def get_stock_price(self, symbol: str) -> float:
        """
        Get current stock price.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current stock price
        """
        await self._ensure_connected()

        stock = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(stock)

        ticker = self.ib.reqMktData(stock, '', False, False)
        await asyncio.sleep(2)  # Wait for data

        self.ib.cancelMktData(stock)

        # Get the most recent price
        price = ticker.marketPrice()
        if price and price > 0:
            logger.debug(f"{symbol} price: ${price:.2f}")
            return price

        # Fallback to last or close
        if ticker.last and ticker.last > 0:
            return ticker.last
        if ticker.close and ticker.close > 0:
            return ticker.close

        raise ValueError(f"Could not get price for {symbol}")

    async def get_options_chain(
        self,
        symbol: str,
        expiration: Optional[datetime] = None,
        min_dte: int = 0,
        max_dte: int = 60,
        right: Optional[str] = None
    ) -> List[OptionChainData]:
        """
        Get options chain for a symbol.

        Args:
            symbol: Stock ticker symbol
            expiration: Specific expiration date (if None, gets all within DTE range)
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration
            right: 'C' for calls only, 'P' for puts only, None for both

        Returns:
            List of option chain data
        """
        await self._ensure_connected()

        stock = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(stock)

        # Get option chain
        chains = await self.ib.reqSecDefOptParamsAsync(
            stock.symbol, '', stock.secType, stock.conId
        )

        if not chains:
            logger.warning(f"No options chain found for {symbol}")
            return []

        chain = chains[0]
        logger.debug(f"Found options chain for {symbol} with {len(chain.expirations)} expirations")

        # Filter expirations by DTE
        today = datetime.now().date()
        valid_expirations = []

        for exp_str in chain.expirations:
            exp_date = datetime.strptime(exp_str, '%Y%m%d').date()
            dte = (exp_date - today).days

            if min_dte <= dte <= max_dte:
                if expiration is None or exp_date == expiration.date():
                    valid_expirations.append(exp_str)

        if not valid_expirations:
            logger.warning(f"No expirations found for {symbol} within DTE range {min_dte}-{max_dte}")
            return []

        logger.info(f"Found {len(valid_expirations)} valid expirations for {symbol}")

        # Get options for these expirations
        options_data = []

        for exp_str in valid_expirations:
            for strike in chain.strikes:
                rights = ['P', 'C'] if right is None else [right]

                for r in rights:
                    option = Option(symbol, exp_str, strike, r, 'SMART')
                    self.ib.qualifyContracts(option)

                    # Request market data and greeks
                    ticker = self.ib.reqMktData(option, '106', False, False)  # 106 = greeks

        # Wait for all data to arrive
        await asyncio.sleep(3)

        # Process all tickers
        for ticker in self.ib.tickers():
            if not isinstance(ticker.contract, Option):
                continue

            opt = ticker.contract

            # Skip if not our symbol
            if opt.symbol != symbol:
                continue

            # Parse expiration
            exp_date = datetime.strptime(opt.lastTradeDateOrContractMonth, '%Y%m%d')

            # Get market data
            bid = ticker.bid if ticker.bid and ticker.bid > 0 else 0.0
            ask = ticker.ask if ticker.ask and ticker.ask > 0 else 0.0
            last = ticker.last if ticker.last and ticker.last > 0 else 0.0
            volume = ticker.volume if ticker.volume else 0

            # Get Greeks
            delta = ticker.modelGreeks.delta if ticker.modelGreeks else None
            gamma = ticker.modelGreeks.gamma if ticker.modelGreeks else None
            theta = ticker.modelGreeks.theta if ticker.modelGreeks else None
            vega = ticker.modelGreeks.vega if ticker.modelGreeks else None
            iv = ticker.modelGreeks.impliedVol if ticker.modelGreeks else None

            option_data = OptionChainData(
                symbol=opt.symbol,
                strike=opt.strike,
                expiration=exp_date,
                right=opt.right,
                bid=bid,
                ask=ask,
                last=last,
                volume=volume,
                open_interest=0,  # Not readily available from ticker
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                iv=iv,
                contract=opt
            )

            options_data.append(option_data)

        # Cancel all market data
        self.ib.cancelMktData('')

        logger.info(f"Retrieved {len(options_data)} options for {symbol}")
        return options_data

    async def get_positions(self) -> List[Position]:
        """
        Get all current portfolio positions.

        Returns:
            List of current positions
        """
        await self._ensure_connected()

        positions = []

        for item in self.ib.portfolio():
            contract = item.contract

            # Determine position type
            if isinstance(contract, Stock):
                pos_type = 'stock'
                strike = None
                expiration = None
                right = None
            elif isinstance(contract, Option):
                pos_type = 'option'
                strike = contract.strike
                expiration = datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d')
                right = contract.right
            else:
                continue  # Skip other types

            position = Position(
                symbol=contract.symbol,
                position_type=pos_type,
                quantity=int(item.position),
                avg_cost=item.averageCost,
                market_value=item.marketValue,
                unrealized_pnl=item.unrealizedPNL,
                realized_pnl=item.realizedPNL,
                strike=strike,
                expiration=expiration,
                right=right,
                contract=contract
            )

            positions.append(position)

        logger.info(f"Retrieved {len(positions)} positions")
        return positions

    async def get_account_info(self, account_number: str) -> AccountInfo:
        """
        Get account balance and buying power information.

        Args:
            account_number: IBKR account number

        Returns:
            Account information
        """
        await self._ensure_connected()

        # Get account values
        account_values = {av.tag: float(av.value) for av in self.ib.accountValues(account_number)}

        account_info = AccountInfo(
            account_number=account_number,
            net_liquidation=account_values.get('NetLiquidation', 0.0),
            total_cash=account_values.get('TotalCashValue', 0.0),
            buying_power=account_values.get('BuyingPower', 0.0),
            available_funds=account_values.get('AvailableFunds', 0.0),
            excess_liquidity=account_values.get('ExcessLiquidity', 0.0),
            margin_used=account_values.get('GrossPositionValue', 0.0),
            margin_available=account_values.get('AvailableFunds', 0.0)
        )

        logger.info(f"Account {account_number}: Net Liquidation = ${account_info.net_liquidation:,.2f}")
        return account_info

    async def get_vix(self) -> Optional[float]:
        """
        Get current VIX value.

        Returns:
            Current VIX value, or None if unavailable
        """
        try:
            await self._ensure_connected()

            vix = Stock('VIX', 'CBOE', 'USD')
            self.ib.qualifyContracts(vix)

            ticker = self.ib.reqMktData(vix, '', False, False)
            await asyncio.sleep(2)

            self.ib.cancelMktData(vix)

            vix_value = ticker.last if ticker.last else ticker.close

            if vix_value:
                logger.debug(f"VIX: {vix_value:.2f}")
                return vix_value

            return None

        except Exception as e:
            logger.warning(f"Could not fetch VIX: {e}")
            return None

    async def get_historical_volatility(
        self,
        symbol: str,
        days: int = 30
    ) -> Optional[float]:
        """
        Calculate historical volatility for a symbol.

        Args:
            symbol: Stock ticker symbol
            days: Number of days of history to use

        Returns:
            Annualized historical volatility (as decimal, e.g., 0.25 = 25%)
        """
        try:
            await self._ensure_connected()

            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)

            # Request historical data
            bars = await self.ib.reqHistoricalDataAsync(
                stock,
                endDateTime='',
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )

            if not bars or len(bars) < 2:
                logger.warning(f"Insufficient historical data for {symbol}")
                return None

            # Calculate daily returns
            closes = [bar.close for bar in bars]
            returns = []
            for i in range(1, len(closes)):
                daily_return = (closes[i] - closes[i-1]) / closes[i-1]
                returns.append(daily_return)

            # Calculate volatility (standard deviation of returns)
            if not returns:
                return None

            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            daily_vol = variance ** 0.5

            # Annualize (assuming 252 trading days)
            annual_vol = daily_vol * (252 ** 0.5)

            logger.debug(f"{symbol} {days}-day HV: {annual_vol:.2%}")
            return annual_vol

        except Exception as e:
            logger.warning(f"Could not calculate historical volatility for {symbol}: {e}")
            return None


async def main():
    """Example usage of DataFetcher."""

    logging.basicConfig(level=logging.INFO)

    # Initialize data fetcher
    fetcher = DataFetcher(host="127.0.0.1", port=7497, client_id=1)

    try:
        # Connect
        await fetcher.connect()

        # Get stock price
        spy_price = await fetcher.get_stock_price('SPY')
        print(f"SPY Price: ${spy_price:.2f}")

        # Get account info
        account = await fetcher.get_account_info('DU1234567')
        print(f"Net Liquidation: ${account.net_liquidation:,.2f}")

        # Get positions
        positions = await fetcher.get_positions()
        print(f"Positions: {len(positions)}")

        # Get options chain
        options = await fetcher.get_options_chain('SPY', min_dte=30, max_dte=45, right='P')
        print(f"Found {len(options)} put options")

        if options:
            # Show first option
            opt = options[0]
            print(f"  {opt.symbol} {opt.expiration.strftime('%Y-%m-%d')} {opt.strike}{opt.right}")
            print(f"  Bid/Ask: ${opt.bid:.2f}/${opt.ask:.2f}, Delta: {opt.delta:.3f}")

        # Get VIX
        vix = await fetcher.get_vix()
        if vix:
            print(f"VIX: {vix:.2f}")

    finally:
        await fetcher.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
