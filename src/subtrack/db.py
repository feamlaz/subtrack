"""Database layer — SQLite storage for subscriptions."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional, Sequence

DEFAULT_DB_PATH = Path.home() / ".subtrack" / "subscriptions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    price       REAL    NOT NULL,
    currency    TEXT    NOT NULL DEFAULT 'RUB',
    billing     TEXT    NOT NULL DEFAULT 'monthly',
    category    TEXT    NOT NULL DEFAULT 'other',
    next_renewal TEXT,
    notes       TEXT    DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CATEGORIES = [
    "streaming",
    "music",
    "vpn",
    "cloud",
    "gaming",
    "productivity",
    "education",
    "news",
    "fitness",
    "other",
]

CURRENCIES = ["RUB", "USD", "EUR", "GBP", "KZT", "UAH", "BYN"]

BILLING_CYCLES = ["weekly", "monthly", "quarterly", "yearly"]


@dataclass
class Subscription:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0
    currency: str = "RUB"
    billing: str = "monthly"
    category: str = "other"
    next_renewal: Optional[date] = None
    notes: str = ""
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def monthly_cost(self) -> float:
        """Convert price to monthly equivalent."""
        multipliers = {"weekly": 4.33, "monthly": 1, "quarterly": 1 / 3, "yearly": 1 / 12}
        return round(self.price * multipliers.get(self.billing, 1), 2)

    @property
    def yearly_cost(self) -> float:
        return round(self.monthly_cost * 12, 2)


def _row_to_sub(row: sqlite3.Row) -> Subscription:
    return Subscription(
        id=row["id"],
        name=row["name"],
        price=row["price"],
        currency=row["currency"],
        billing=row["billing"],
        category=row["category"],
        next_renewal=date.fromisoformat(row["next_renewal"]) if row["next_renewal"] else None,
        notes=row["notes"] or "",
        active=bool(row["active"]),
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
    )


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def add(self, sub: Subscription) -> Subscription:
        cur = self.conn.execute(
            """INSERT INTO subscriptions (name, price, currency, billing, category, next_renewal, notes, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sub.name,
                sub.price,
                sub.currency,
                sub.billing,
                sub.category,
                sub.next_renewal.isoformat() if sub.next_renewal else None,
                sub.notes,
                int(sub.active),
            ),
        )
        self.conn.commit()
        sub.id = cur.lastrowid
        return sub

    def get(self, sub_id: int) -> Optional[Subscription]:
        row = self.conn.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
        return _row_to_sub(row) if row else None

    def list_all(self, active_only: bool = True) -> List[Subscription]:
        q = "SELECT * FROM subscriptions"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY category, name"
        return [_row_to_sub(r) for r in self.conn.execute(q).fetchall()]

    def update(self, sub_id: int, **kwargs) -> Optional[Subscription]:
        existing = self.get(sub_id)
        if not existing:
            return None

        fields = []
        values = []
        for key, val in kwargs.items():
            if key == "next_renewal" and isinstance(val, date):
                val = val.isoformat()
            if key == "active" and isinstance(val, bool):
                val = int(val)
            fields.append(f"{key} = ?")
            values.append(val)

        if not fields:
            return existing

        fields.append("updated_at = datetime('now')")
        values.append(sub_id)

        self.conn.execute(
            "UPDATE subscriptions SET {} WHERE id = ?".format(", ".join(fields)), values
        )
        self.conn.commit()
        return self.get(sub_id)

    def remove(self, sub_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def summary(self, active_only: bool = True) -> Dict[str, dict]:
        subs = self.list_all(active_only=active_only)
        by_category: Dict[str, List[Subscription]] = {}
        for s in subs:
            by_category.setdefault(s.category, []).append(s)

        result = {}
        for cat, cat_subs in sorted(by_category.items()):
            by_currency: Dict[str, List[Subscription]] = {}
            for s in cat_subs:
                by_currency.setdefault(s.currency, []).append(s)

            cat_monthly = {}
            cat_yearly = {}
            cat_count = len(cat_subs)
            for cur, cur_subs in by_currency.items():
                cat_monthly[cur] = round(sum(s.monthly_cost for s in cur_subs), 2)
                cat_yearly[cur] = round(sum(s.yearly_cost for s in cur_subs), 2)

            result[cat] = {
                "count": cat_count,
                "monthly": cat_monthly,
                "yearly": cat_yearly,
                "subscriptions": cat_subs,
            }
        return result

    def upcoming_renewals(self, days: int = 7) -> List[Subscription]:
        """Subscriptions renewing within `days` days from today."""
        subs = self.list_all(active_only=True)
        today = date.today()
        result = []
        for s in subs:
            if s.next_renewal:
                delta = (s.next_renewal - today).days
                if 0 <= delta <= days:
                    result.append(s)
        result.sort(key=lambda s: s.next_renewal or date.max)
        return result
