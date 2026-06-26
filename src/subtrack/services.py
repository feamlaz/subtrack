"""Business logic — exports, formatting helpers."""

import csv
import io
import json
from dataclasses import asdict
from datetime import date
from typing import Sequence

from .db import Subscription


def subscriptions_to_csv(subs: Sequence[Subscription]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "name", "price", "currency", "billing", "category",
        "next_renewal", "notes", "active", "monthly_cost", "yearly_cost",
    ])
    for s in subs:
        writer.writerow([
            s.id, s.name, s.price, s.currency, s.billing, s.category,
            s.next_renewal.isoformat() if s.next_renewal else "",
            s.notes, s.active, s.monthly_cost, s.yearly_cost,
        ])
    return buf.getvalue()


def subscriptions_to_json(subs: Sequence[Subscription]) -> str:
    data = []
    for s in subs:
        d = asdict(s)
        d["monthly_cost"] = s.monthly_cost
        d["yearly_cost"] = s.yearly_cost
        d["next_renewal"] = s.next_renewal.isoformat() if s.next_renewal else None
        d["created_at"] = s.created_at.isoformat() if s.created_at else None
        d["updated_at"] = s.updated_at.isoformat() if s.updated_at else None
        data.append(d)
    return json.dumps(data, indent=2, ensure_ascii=False)


CATEGORY_ICONS = {
    "streaming": "🎬",
    "music": "🎵",
    "vpn": "🔒",
    "cloud": "☁️",
    "gaming": "🎮",
    "productivity": "⚡",
    "education": "📚",
    "news": "📰",
    "fitness": "💪",
    "other": "📦",
}

BILLING_LABELS = {
    "weekly": "/week",
    "monthly": "/mo",
    "quarterly": "/qtr",
    "yearly": "/yr",
}


def format_price(price: float, currency: str) -> str:
    symbols = {"RUB": "₽", "USD": "$", "EUR": "€", "GBP": "£", "KZT": "₸", "UAH": "₴", "BYN": "Br"}
    sym = symbols.get(currency, currency)
    if currency in ("USD", "EUR", "GBP"):
        return "{}{:,.2f}".format(sym, price)
    return "{:,.2f} {}".format(price, sym)
