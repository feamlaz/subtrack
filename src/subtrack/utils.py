"""Utilities — colorful output, tips, stats display."""

from datetime import date
from typing import Dict, List, Optional

from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from .db import Subscription
from .services import CATEGORY_ICONS, format_price

# ── Inspirational tips ─────────────────────────────────────────────────

TIPS = [
    "Cancel what you haven't used in 30 days.",
    "Annual plans save ~15% on average.",
    "Share family plans when possible.",
    "Set renewal reminders — avoid surprise charges.",
    "Review your subscriptions quarterly.",
    "Free trials are the #1 source of forgotten charges.",
    "The cheapest subscription is the one you cancel.",
    "If you use it daily — it's worth it.",
    "Check if your bank offers cashback on subscriptions.",
    "Some services offer student discounts — use them!",
]

# ── Stats display ──────────────────────────────────────────────────────

GRADIENT_COLORS = [
    "#7c6cf0", "#6d72f3", "#5e78f6", "#4f7ef9", "#4084fc",
    "#318aff", "#2290ff", "#1396ff", "#049cff", "#00a5f7",
]


def make_stats_panel(subs: List[Subscription]) -> Panel:
    """Build a colorful stats summary panel."""
    if not subs:
        return Panel(
            Align.center(Text("No subscriptions yet", style="dim"), vertical="middle"),
            border_style="#7c6cf0",
            title="SubTrack",
        )

    # Calculate totals
    by_currency: Dict[str, float] = {}
    by_category: Dict[str, int] = {}
    for s in subs:
        by_currency[s.currency] = by_currency.get(s.currency, 0) + s.monthly_cost
        by_category[s.category] = by_category.get(s.category, 0) + 1

    lines = Text()

    # Monthly totals with color
    lines.append("Monthly burn: ", style="dim")
    total_parts = []
    for i, (cur, amount) in enumerate(sorted(by_currency.items())):
        color = GRADIENT_COLORS[i % len(GRADIENT_COLORS)]
        total_parts.append(Text(format_price(amount, cur), style=f"bold {color}"))

    for i, part in enumerate(total_parts):
        if i > 0:
            lines.append("  ")
        lines.append(part)

    lines.append("\n")

    # Yearly
    lines.append("Yearly burn:  ", style="dim")
    yearly_parts = []
    for i, (cur, amount) in enumerate(sorted(by_currency.items())):
        color = GRADIENT_COLORS[(i + 3) % len(GRADIENT_COLORS)]
        yearly_parts.append(Text(format_price(amount * 12, cur), style=f"bold {color}"))

    for i, part in enumerate(yearly_parts):
        if i > 0:
            lines.append("  ")
        lines.append(part)

    lines.append("\n\n")

    # Category breakdown with gradient bar
    max_count = max(by_category.values()) if by_category else 1
    for i, (cat, count) in enumerate(sorted(by_category.items())):
        icon = CATEGORY_ICONS.get(cat, "📦")
        color = GRADIENT_COLORS[i % len(GRADIENT_COLORS)]
        bar_len = int((count / max_count) * 15)
        bar = "█" * bar_len + "░" * (15 - bar_len)

        cat_subs = [s for s in subs if s.category == cat]
        cat_total = {}
        for s in cat_subs:
            cat_total[s.currency] = cat_total.get(s.currency, 0) + s.monthly_cost

        cat_str = "  ".join(format_price(v, c) for c, v in sorted(cat_total.items()))

        lines.append(f"  {icon} ", style="")
        lines.append(f"{cat:<14}", style=f"bold {color}")
        lines.append(bar, style=color)
        lines.append(f"  {count} sub{'s' if count > 1 else ''}  ", style="dim")
        lines.append(cat_str, style=color)
        lines.append("\n")

    lines.append("\n")

    # Upcoming renewals warning
    today = date.today()
    upcoming = [s for s in subs if s.next_renewal and 0 <= (s.next_renewal - today).days <= 7]
    if upcoming:
        lines.append("Renewing soon: ", style="bold yellow")
        names = ", ".join(s.name for s in upcoming[:5])
        lines.append(names, style="yellow")
        lines.append("\n\n")

    # Tip
    import random
    tip = random.choice(TIPS)
    lines.append("Tip: ", style="bold #7c6cf0")
    lines.append(tip, style="dim italic")

    return Panel(lines, border_style="#7c6cf0", title="[bold #7c6cf0]SubTrack[/]", padding=(1, 2))


def make_welcome_text() -> Text:
    """Colorful welcome line for CLI."""
    t = Text()
    t.append("  Sub", style="bold #7c6cf0")
    t.append("Track", style="bold #22c55e")
    t.append(" — ", style="dim")
    t.append("track your subscriptions\n", style="dim italic")
    return t
