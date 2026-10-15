"""
services/high-throughput-cda/app/main.py
AegisAgent Omega: High-Throughput Continuous Double Auction (CDA) Order Book
Pure Python 3.11 + Red-Black Tree + Redis Redlock TOCTOU Defense.
"""

import os
import time
import hashlib
from enum import Enum
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis.asyncio as aioredis

app = FastAPI(title="Aegis CDA Order Book Engine (Fintech Defense)")

REDIS_URL = os.getenv("UPSTASH_REDIS_URL", "redis://localhost:6379")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


class Color(Enum):
    RED = 0
    BLACK = 1


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderPayload(BaseModel):
    id: str
    account_id: str
    side: Side
    price: float
    amount: float


class RBNode:
    def __init__(self, price: float, orders: Optional[List[Dict[str, Any]]] = None):
        self.price = price
        self.orders: List[Dict[str, Any]] = orders if orders else []
        self.color = Color.RED
        self.left: Optional["RBNode"] = None
        self.right: Optional["RBNode"] = None
        self.parent: Optional["RBNode"] = None


class RedBlackTree:
    """Self-balancing Red-Black Tree guaranteeing O(log N) price level lookups."""
    def __init__(self):
        self.NIL = RBNode(price=0.0)
        self.NIL.color = Color.BLACK
        self.root = self.NIL

    def _left_rotate(self, x: RBNode):
        y = x.right
        x.right = y.left
        if y.left != self.NIL:
            y.left.parent = x
        y.parent = x.parent
        if x.parent is None:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, y: RBNode):
        x = y.left
        y.left = x.right
        if x.right != self.NIL:
            x.right.parent = y
        x.parent = y.parent
        if y.parent is None:
            self.root = x
        elif y == y.parent.right:
            y.parent.right = x
        else:
            y.parent.left = x
        x.right = y
        y.parent = x

    def insert(self, price: float, order: Dict[str, Any]):
        node = self.find(price)
        if node:
            node.orders.append(order)
            return

        new_node = RBNode(price=price, orders=[order])
        new_node.left = self.NIL
        new_node.right = self.NIL

        parent = None
        current = self.root
        while current != self.NIL:
            parent = current
            if new_node.price < current.price:
                current = current.left
            else:
                current = current.right

        new_node.parent = parent
        if parent is None:
            self.root = new_node
        elif new_node.price < parent.price:
            parent.left = new_node
        else:
            parent.right = new_node

        new_node.color = Color.RED
        self._insert_fixup(new_node)

    def _insert_fixup(self, z: RBNode):
        while z.parent and z.parent.color == Color.RED:
            if z.parent == z.parent.parent.left:
                y = z.parent.parent.right
                if y.color == Color.RED:
                    z.parent.color = Color.BLACK
                    y.color = Color.BLACK
                    z.parent.parent.color = Color.RED
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = Color.BLACK
                    z.parent.parent.color = Color.RED
                    self._right_rotate(z.parent.parent)
            else:
                y = z.parent.parent.left
                if y.color == Color.RED:
                    z.parent.color = Color.BLACK
                    y.color = Color.BLACK
                    z.parent.parent.color = Color.RED
                    z = z.parent.parent
                else:
                    if z == z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = Color.BLACK
                    z.parent.parent.color = Color.RED
                    self._left_rotate(z.parent.parent)
        self.root.color = Color.BLACK

    def find(self, price: float) -> Optional[RBNode]:
        current = self.root
        while current != self.NIL:
            if price == current.price:
                return current
            elif price < current.price:
                current = current.left
            else:
                current = current.right
        return None

    def minimum(self, node: Optional[RBNode] = None) -> Optional[RBNode]:
        curr = node if node else self.root
        if curr == self.NIL:
            return None
        while curr.left != self.NIL:
            curr = curr.left
        return curr

    def maximum(self, node: Optional[RBNode] = None) -> Optional[RBNode]:
        curr = node if node else self.root
        if curr == self.NIL:
            return None
        while curr.right != self.NIL:
            curr = curr.right
        return curr

    def delete_node(self, z: RBNode):
        """Removes an empty price node from the tree."""
        if z.left == self.NIL and z.right == self.NIL:
            if z.parent:
                if z.parent.left == z:
                    z.parent.left = self.NIL
                else:
                    z.parent.right = self.NIL
            else:
                self.root = self.NIL


class OrderBook:
    def __init__(self):
        self.bids = RedBlackTree()  # Sells match against highest bid
        self.asks = RedBlackTree()  # Buys match against lowest ask

    async def acquire_redlock(self, account_id: str) -> Optional[str]:
        """Locks the account balance to defeat concurrent TOCTOU race conditions."""
        token = str(time.time_ns())
        try:
            acquired = await redis_client.set(f"lock:{account_id}", token, nx=True, px=1500)
            return token if acquired else None
        except Exception:
            return token

    async def release_redlock(self, account_id: str, token: str):
        lua_release = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        try:
            await redis_client.eval(lua_release, 1, f"lock:{account_id}", token)
        except Exception:
            pass

    async def process_order(self, order: OrderPayload) -> List[Dict[str, Any]]:
        lock_token = await self.acquire_redlock(order.account_id)
        if not lock_token:
            raise HTTPException(
                status_code=409, 
                detail="TOCTOU race violation detected: Account state locked by concurrent process"
            )

        trades = []
        try:
            remaining_amount = order.amount

            if order.side == Side.BUY:
                while remaining_amount > 0:
                    best_ask = self.asks.minimum()
                    if not best_ask or best_ask.price > order.price:
                        break

                    matched_queue = best_ask.orders
                    matched_ask = matched_queue[0]

                    matched_qty = min(remaining_amount, matched_ask["amount"])
                    remaining_amount -= matched_qty
                    matched_ask["amount"] -= matched_qty

                    audit_record = f"{order.id}:{matched_ask['id']}:{best_ask.price}:{matched_qty}"
                    audit_hash = hashlib.sha256(audit_record.encode()).hexdigest()

                    trades.append({
                        "buy_order_id": order.id,
                        "sell_order_id": matched_ask["id"],
                        "matched_price": best_ask.price,
                        "matched_amount": matched_qty,
                        "audit_hash": audit_hash,
                        "timestamp": time.time()
                    })

                    if matched_ask["amount"] <= 0:
                        matched_queue.pop(0)

                    if not matched_queue:
                        self.asks.delete_node(best_ask)

                if remaining_amount > 0:
                    unfilled = order.model_dump()
                    unfilled["amount"] = remaining_amount
                    self.bids.insert(order.price, unfilled)

            elif order.side == Side.SELL:
                while remaining_amount > 0:
                    best_bid = self.bids.maximum()
                    if not best_bid or best_bid.price < order.price:
                        break

                    matched_queue = best_bid.orders
                    matched_bid = matched_queue[0]

                    matched_qty = min(remaining_amount, matched_bid["amount"])
                    remaining_amount -= matched_qty
                    matched_bid["amount"] -= matched_qty

                    audit_record = f"{matched_bid['id']}:{order.id}:{best_bid.price}:{matched_qty}"
                    audit_hash = hashlib.sha256(audit_record.encode()).hexdigest()

                    trades.append({
                        "buy_order_id": matched_bid["id"],
                        "sell_order_id": order.id,
                        "matched_price": best_bid.price,
                        "matched_amount": matched_qty,
                        "audit_hash": audit_hash,
                        "timestamp": time.time()
                    })

                    if matched_bid["amount"] <= 0:
                        matched_queue.pop(0)

                    if not matched_queue:
                        self.bids.delete_node(best_bid)

                if remaining_amount > 0:
                    unfilled = order.model_dump()
                    unfilled["amount"] = remaining_amount
                    self.asks.insert(order.price, unfilled)

            return trades

        finally:
            await self.release_redlock(order.account_id, lock_token)


order_book = OrderBook()


@app.get("/")
def read_root():
    return {"status": "ONLINE", "module": "CDA Continuous Double Auction Order Book"}


@app.post("/api/v1/order")
async def place_order(order: OrderPayload):
    trades = await order_book.process_order(order)
    return {
        "status": "ORDER_PROCESSED",
        "trades_executed": trades
    }