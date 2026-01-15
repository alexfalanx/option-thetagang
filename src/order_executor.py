"""
Order executor for ThetaGangExpanded.

Manages order creation, submission, tracking, and cancellation.
Translates strategy decisions into specific order objects and submits to IBKR.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import asyncio

from ib_async import IB, Order, Trade, Stock, Option, Contract
from ib_async import LimitOrder, MarketOrder

from src.strategy_base import TradeRecommendation, Action
from src.data_fetcher import Position

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status types."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class OrderRecord:
    """Record of an order submission."""
    order_id: int
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    order_type: str  # 'LIMIT', 'MARKET'
    limit_price: Optional[float]
    status: OrderStatus
    filled_quantity: int
    avg_fill_price: Optional[float]
    submitted_at: datetime
    filled_at: Optional[datetime]
    commission: Optional[float]

    # Original recommendation
    recommendation: TradeRecommendation

    # IBKR trade object
    trade: Optional[Trade] = None


class OrderExecutor:
    """
    Handles order creation and execution via IBKR.

    Supports:
    - Opening new positions (sell puts/calls)
    - Closing positions (buy to close)
    - Rolling positions (close + open)
    - Dry-run mode for testing
    """

    def __init__(self, ib: IB, dry_run: bool = True):
        """
        Initialize order executor.

        Args:
            ib: Connected IB instance
            dry_run: If True, log orders but don't actually submit
        """
        self.ib = ib
        self.dry_run = dry_run
        self.order_history: List[OrderRecord] = []

    async def execute_recommendation(
        self,
        recommendation: TradeRecommendation
    ) -> Optional[OrderRecord]:
        """
        Execute a trade recommendation.

        Args:
            recommendation: Trade recommendation from strategy

        Returns:
            Order record if executed, None if skipped
        """
        logger.info(f"Executing: {recommendation.action.value} {recommendation.quantity}x {recommendation.symbol}")
        logger.info(f"  Reasoning: {recommendation.reasoning}")

        if recommendation.action == Action.SELL_PUT:
            return await self._sell_option(recommendation, 'P')

        elif recommendation.action == Action.SELL_CALL:
            return await self._sell_option(recommendation, 'C')

        elif recommendation.action == Action.CLOSE_PUT:
            return await self._close_option(recommendation, 'P')

        elif recommendation.action == Action.CLOSE_CALL:
            return await self._close_option(recommendation, 'C')

        elif recommendation.action == Action.ROLL_PUT:
            return await self._roll_option(recommendation, 'P')

        elif recommendation.action == Action.ROLL_CALL:
            return await self._roll_option(recommendation, 'C')

        elif recommendation.action == Action.DO_NOTHING:
            logger.info("Action is DO_NOTHING, skipping")
            return None

        else:
            logger.warning(f"Unknown action: {recommendation.action}")
            return None

    async def _sell_option(
        self,
        recommendation: TradeRecommendation,
        right: str
    ) -> Optional[OrderRecord]:
        """
        Sell an option (open position).

        Args:
            recommendation: Trade recommendation
            right: 'C' for call, 'P' for put

        Returns:
            Order record
        """
        if not recommendation.strike or not recommendation.expiration:
            logger.error("Missing strike or expiration for sell option order")
            return None

        # Create option contract
        exp_str = recommendation.expiration.strftime('%Y%m%d')
        contract = Option(
            symbol=recommendation.symbol,
            lastTradeDateOrContractMonth=exp_str,
            strike=recommendation.strike,
            right=right,
            exchange='SMART'
        )

        # Qualify contract
        self.ib.qualifyContracts(contract)

        # Create limit order to sell
        # Use mid-price from recommendation, or calculate
        limit_price = recommendation.premium if recommendation.premium else 0.0

        order = LimitOrder(
            action='SELL',
            totalQuantity=recommendation.quantity,
            lmtPrice=limit_price
        )

        # Submit order
        return await self._submit_order(contract, order, recommendation)

    async def _close_option(
        self,
        recommendation: TradeRecommendation,
        right: str
    ) -> Optional[OrderRecord]:
        """
        Buy to close an option position.

        Args:
            recommendation: Trade recommendation
            right: 'C' for call, 'P' for put

        Returns:
            Order record
        """
        if not recommendation.existing_position:
            logger.error("Missing existing position for close option order")
            return None

        position = recommendation.existing_position

        # Use contract from existing position
        contract = position.contract

        if not contract:
            logger.error("No contract found in existing position")
            return None

        # Create market order to buy to close (fast exit)
        order = MarketOrder(
            action='BUY',
            totalQuantity=abs(position.quantity)
        )

        # Submit order
        return await self._submit_order(contract, order, recommendation)

    async def _roll_option(
        self,
        recommendation: TradeRecommendation,
        right: str
    ) -> Optional[OrderRecord]:
        """
        Roll an option position (close old, open new).

        Args:
            recommendation: Trade recommendation
            right: 'C' for call, 'P' for put

        Returns:
            Order record for the new position
        """
        logger.info(f"Rolling {right} option for {recommendation.symbol}")

        # Step 1: Close existing position
        if recommendation.existing_position:
            close_rec = TradeRecommendation(
                action=Action.CLOSE_PUT if right == 'P' else Action.CLOSE_CALL,
                symbol=recommendation.symbol,
                quantity=recommendation.quantity,
                existing_position=recommendation.existing_position,
                reasoning=f"Closing as part of roll"
            )

            close_result = await self._close_option(close_rec, right)

            if not close_result:
                logger.error("Failed to close position during roll, aborting")
                return None

            # Wait for fill
            await self._wait_for_fill(close_result, timeout=30)

        # Step 2: Open new position
        if not recommendation.new_strike or not recommendation.new_expiration:
            logger.error("Missing new strike or expiration for roll")
            return None

        open_rec = TradeRecommendation(
            action=Action.SELL_PUT if right == 'P' else Action.SELL_CALL,
            symbol=recommendation.symbol,
            quantity=recommendation.quantity,
            strike=recommendation.new_strike,
            expiration=recommendation.new_expiration,
            right=right,
            premium=recommendation.premium,
            reasoning=f"Opening new position as part of roll"
        )

        return await self._sell_option(open_rec, right)

    async def _submit_order(
        self,
        contract: Contract,
        order: Order,
        recommendation: TradeRecommendation
    ) -> Optional[OrderRecord]:
        """
        Submit an order to IBKR.

        Args:
            contract: Contract to trade
            order: Order object
            recommendation: Original recommendation

        Returns:
            Order record
        """
        # Log order details
        logger.info(f"Order: {order.action} {order.totalQuantity}x {contract.symbol}")
        if hasattr(order, 'lmtPrice'):
            logger.info(f"  Limit price: ${order.lmtPrice:.2f}")

        # Dry-run mode: log but don't submit
        if self.dry_run:
            logger.warning("DRY RUN MODE: Order not actually submitted")

            order_record = OrderRecord(
                order_id=0,
                symbol=contract.symbol,
                action=order.action,
                quantity=order.totalQuantity,
                order_type='LIMIT' if hasattr(order, 'lmtPrice') else 'MARKET',
                limit_price=getattr(order, 'lmtPrice', None),
                status=OrderStatus.PENDING,
                filled_quantity=0,
                avg_fill_price=None,
                submitted_at=datetime.now(),
                filled_at=None,
                commission=None,
                recommendation=recommendation
            )

            self.order_history.append(order_record)
            return order_record

        # Submit order to IBKR
        try:
            trade = self.ib.placeOrder(contract, order)

            logger.info(f"Order submitted: ID={trade.order.orderId}")

            order_record = OrderRecord(
                order_id=trade.order.orderId,
                symbol=contract.symbol,
                action=order.action,
                quantity=order.totalQuantity,
                order_type='LIMIT' if hasattr(order, 'lmtPrice') else 'MARKET',
                limit_price=getattr(order, 'lmtPrice', None),
                status=OrderStatus.SUBMITTED,
                filled_quantity=0,
                avg_fill_price=None,
                submitted_at=datetime.now(),
                filled_at=None,
                commission=None,
                recommendation=recommendation,
                trade=trade
            )

            self.order_history.append(order_record)

            # Set up callbacks for status updates
            trade.filledEvent += lambda t: self._on_order_filled(order_record, t)
            trade.cancelledEvent += lambda t: self._on_order_cancelled(order_record, t)

            return order_record

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            return None

    async def _wait_for_fill(
        self,
        order_record: OrderRecord,
        timeout: int = 60
    ) -> bool:
        """
        Wait for an order to be filled.

        Args:
            order_record: Order to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if filled, False if timeout or cancelled
        """
        if self.dry_run:
            logger.info("DRY RUN: Simulating immediate fill")
            order_record.status = OrderStatus.FILLED
            order_record.filled_quantity = order_record.quantity
            order_record.filled_at = datetime.now()
            return True

        elapsed = 0
        while elapsed < timeout:
            if order_record.status == OrderStatus.FILLED:
                logger.info(f"Order {order_record.order_id} filled")
                return True

            if order_record.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                logger.warning(f"Order {order_record.order_id} {order_record.status.value}")
                return False

            await asyncio.sleep(1)
            elapsed += 1

        logger.warning(f"Order {order_record.order_id} timeout after {timeout}s")
        return False

    def _on_order_filled(self, order_record: OrderRecord, trade: Trade):
        """Callback when order is filled."""
        order_record.status = OrderStatus.FILLED
        order_record.filled_quantity = trade.orderStatus.filled
        order_record.avg_fill_price = trade.orderStatus.avgFillPrice
        order_record.filled_at = datetime.now()

        logger.info(f"Order {order_record.order_id} FILLED: "
                   f"{order_record.filled_quantity}x @ ${order_record.avg_fill_price:.2f}")

    def _on_order_cancelled(self, order_record: OrderRecord, trade: Trade):
        """Callback when order is cancelled."""
        order_record.status = OrderStatus.CANCELLED
        logger.warning(f"Order {order_record.order_id} CANCELLED")

    async def cancel_order(self, order_record: OrderRecord) -> bool:
        """
        Cancel an open order.

        Args:
            order_record: Order to cancel

        Returns:
            True if cancelled successfully
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Cancelling order {order_record.order_id}")
            order_record.status = OrderStatus.CANCELLED
            return True

        if not order_record.trade:
            logger.error("No trade object to cancel")
            return False

        try:
            self.ib.cancelOrder(order_record.trade.order)
            logger.info(f"Cancelled order {order_record.order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order {order_record.order_id}: {e}")
            return False

    def get_order_status(self, order_id: int) -> Optional[OrderRecord]:
        """
        Get status of an order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order record if found
        """
        for record in self.order_history:
            if record.order_id == order_id:
                return record
        return None

    def get_recent_orders(self, count: int = 10) -> List[OrderRecord]:
        """
        Get recent order history.

        Args:
            count: Number of recent orders to return

        Returns:
            List of order records
        """
        return self.order_history[-count:] if self.order_history else []

    def get_order_statistics(self) -> Dict[str, int]:
        """
        Get statistics about order execution.

        Returns:
            Dictionary of statistics
        """
        total = len(self.order_history)
        filled = len([o for o in self.order_history if o.status == OrderStatus.FILLED])
        cancelled = len([o for o in self.order_history if o.status == OrderStatus.CANCELLED])
        rejected = len([o for o in self.order_history if o.status == OrderStatus.REJECTED])
        pending = len([o for o in self.order_history if o.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]])

        return {
            'total': total,
            'filled': filled,
            'cancelled': cancelled,
            'rejected': rejected,
            'pending': pending
        }


async def main():
    """Example usage of OrderExecutor."""

    logging.basicConfig(level=logging.INFO)

    # Create mock IB connection
    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=1)

    # Create executor in dry-run mode
    executor = OrderExecutor(ib, dry_run=True)

    # Create mock recommendation
    from src.core_strategy import TradeRecommendation, Action
    from datetime import datetime, timedelta

    rec = TradeRecommendation(
        action=Action.SELL_PUT,
        symbol='SPY',
        quantity=1,
        strike=450.0,
        expiration=datetime.now() + timedelta(days=40),
        right='P',
        premium=2.50,
        delta=-0.30,
        reasoning="Test put sale"
    )

    # Execute
    order = await executor.execute_recommendation(rec)

    if order:
        print(f"Order created: {order.order_id}")
        print(f"Status: {order.status.value}")

    # Get statistics
    stats = executor.get_order_statistics()
    print(f"Order statistics: {stats}")

    await ib.disconnectAsync()


if __name__ == '__main__':
    asyncio.run(main())
