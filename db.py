from dataclasses import dataclass, field
from typing import Optional, Dict

@dataclass
class Order:
    id: int
    user_id: int
    username: str
    photo_file_id: str
    photo_kind: str  # "photo" or "document"
    ref_file_id: Optional[str] = None
    ref_kind: Optional[str] = None
    comment: str = ""
    service: str = ""
    credits_cost: int = 0
    status: str = "new"  # new/accepted/upgrade/rejected/done
    admin_note: str = ""

class InMemoryDB:
    def __init__(self):
        self._orders: Dict[int, Order] = {}
        self._seq = 100
        self._credits: Dict[int, int] = {}  # user_id -> credits

    def next_order_id(self) -> int:
        self._seq += 1
        return self._seq

    def create_order(self, order: Order) -> None:
        self._orders[order.id] = order

    def get_order(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    def set_status(self, order_id: int, status: str, note: str = "") -> None:
        if order_id in self._orders:
            self._orders[order_id].status = status
            self._orders[order_id].admin_note = note

    def add_credits(self, user_id: int, amount: int) -> int:
        self._credits[user_id] = self._credits.get(user_id, 0) + amount
        return self._credits[user_id]

    def get_credits(self, user_id: int) -> int:
        return self._credits.get(user_id, 0)

    def spend_credits(self, user_id: int, amount: int) -> bool:
        cur = self._credits.get(user_id, 0)
        if cur < amount:
            return False
        self._credits[user_id] = cur - amount
        return True
