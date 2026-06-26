"""CLI interface — click-based command line."""

import os
import random
from datetime import date
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .db import BILLING_CYCLES, CATEGORIES, CURRENCIES, Database, Subscription
from .services import (
    BILLING_LABELS,
    CATEGORY_ICONS,
    format_price,
    subscriptions_to_csv,
    subscriptions_to_json,
)
from .banner import get_banner, BANNERS
from .utils import make_stats_panel, make_welcome_text

console = Console()


def _db(ctx):
    return ctx.obj["db"]


def _print_banner(style="default"):
    """Print colorful ASCII banner."""
    banner, color = get_banner(style)
    console.print(banner, style=color, highlight=False)


@click.group(invoke_without_command=True)
@click.option("--db-path", envvar="SUBTRACK_DB", type=click.Path(), default=None, help="Path to database file")
@click.option("--banner", "-B", type=click.Choice(list(BANNERS.keys())), default=None, help="Banner style")
@click.pass_context
def cli(ctx, db_path, banner):
    """SubTrack — track all your subscriptions in the terminal."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = Database(db_path)
    ctx.obj["banner"] = banner

    if ctx.invoked_subcommand is None:
        # No subcommand — show welcome + stats
        _print_banner(banner or "default")
        console.print(make_welcome_text())
        subs = ctx.obj["db"].list_all(active_only=True)
        console.print(make_stats_panel(subs))


@cli.command()
@click.argument("name")
@click.option("--price", "-p", type=float, required=True, help="Subscription price")
@click.option("--currency", "-c", type=click.Choice(CURRENCIES), default="RUB", help="Currency")
@click.option("--billing", "-b", type=click.Choice(BILLING_CYCLES), default="monthly", help="Billing cycle")
@click.option("--category", "-cat", type=click.Choice(CATEGORIES), default="other", help="Category")
@click.option("--next-renewal", "-r", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="Next renewal date (YYYY-MM-DD)")
@click.option("--notes", "-n", default="", help="Notes")
@click.pass_context
def add(ctx, name, price, currency, billing, category, next_renewal, notes):
    """Add a new subscription."""
    sub = Subscription(
        name=name,
        price=price,
        currency=currency,
        billing=billing,
        category=category,
        next_renewal=next_renewal.date() if next_renewal else None,
        notes=notes,
    )
    created = _db(ctx).add(sub)
    icon = CATEGORY_ICONS.get(category, "📦")

    # Colorful add confirmation
    t = Text()
    t.append("  ")
    t.append(icon)
    t.append(" ")
    t.append("Added: ", style="bold green")
    t.append(name, style="bold")
    t.append(" — ")
    t.append(format_price(price, currency), style="bold #7c6cf0")
    t.append(BILLING_LABELS[billing], style="dim")
    console.print(t)


@cli.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show inactive subscriptions too")
@click.option("--category", "-cat", type=click.Choice(CATEGORIES), default=None, help="Filter by category")
@click.pass_context
def list_subs(ctx, show_all, category):
    """List all subscriptions."""
    db = _db(ctx)
    subs = db.list_all(active_only=not show_all)
    if category:
        subs = [s for s in subs if s.category == category]

    if not subs:
        console.print("\n  [dim]No subscriptions yet. Use [bold]subtrack add[/] to add one.[/]\n")
        return

    banner_style = ctx.obj.get("banner") or "minimal"
    _print_banner(banner_style)

    # Colorful gradient table
    gradient = ["#7c6cf0", "#6d72f3", "#5e78f6", "#4f7ef9", "#4084fc", "#318aff", "#2290ff"]

    table = Table(title="Subscriptions", show_lines=True, border_style="#7c6cf0")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Price")
    table.add_column("Monthly")
    table.add_column("Category")
    table.add_column("Billing")
    table.add_column("Renewal")
    table.add_column("Status")

    for i, s in enumerate(subs):
        icon = CATEGORY_ICONS.get(s.category, "📦")
        color = gradient[i % len(gradient)]
        status = "[green]active[/]" if s.active else "[dim]inactive[/]"
        renewal = s.next_renewal.isoformat() if s.next_renewal else "—"
        table.add_row(
            str(s.id),
            "{} {}".format(icon, s.name),
            "{}{}".format(format_price(s.price, s.currency), BILLING_LABELS[s.billing]),
            "[{}]{}[/]".format(color, format_price(s.monthly_cost, s.currency)),
            "[{}]{}[/]".format(color, s.category),
            s.billing,
            renewal,
            status,
        )

    console.print(table)

    # Colorful totals
    by_currency = {}
    for s in subs:
        if s.active:
            by_currency[s.currency] = by_currency.get(s.currency, 0) + s.monthly_cost

    t = Text("\n  Monthly total: ")
    for i, (cur, amt) in enumerate(sorted(by_currency.items())):
        if i > 0:
            t.append("  ")
        t.append(format_price(amt, cur), style="bold {}".format(gradient[i % len(gradient)]))
    console.print(t)


@cli.command()
@click.argument("sub_id", type=int)
@click.pass_context
def remove(ctx, sub_id):
    """Remove a subscription by ID."""
    db = _db(ctx)
    sub = db.get(sub_id)
    if not sub:
        console.print("\n  [red]Subscription #{} not found.[/]\n".format(sub_id))
        return
    if db.remove(sub_id):
        t = Text()
        t.append("  ")
        t.append("Removed: ", style="bold red")
        t.append(sub.name, style="bold")
        console.print(t)


@cli.command()
@click.argument("sub_id", type=int)
@click.option("--name", default=None, help="New name")
@click.option("--price", "-p", type=float, default=None, help="New price")
@click.option("--currency", "-c", type=click.Choice(CURRENCIES), default=None, help="New currency")
@click.option("--billing", "-b", type=click.Choice(BILLING_CYCLES), default=None, help="New billing cycle")
@click.option("--category", "-cat", type=click.Choice(CATEGORIES), default=None, help="New category")
@click.option("--next-renewal", "-r", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="New renewal date")
@click.option("--notes", "-n", default=None, help="New notes")
@click.option("--deactivate", is_flag=True, help="Deactivate subscription")
@click.option("--activate", is_flag=True, help="Activate subscription")
@click.pass_context
def edit(ctx, sub_id, name, price, currency, billing, category, next_renewal, notes, deactivate, activate):
    """Edit a subscription."""
    db = _db(ctx)
    updates = {}
    if name is not None:
        updates["name"] = name
    if price is not None:
        updates["price"] = price
    if currency is not None:
        updates["currency"] = currency
    if billing is not None:
        updates["billing"] = billing
    if category is not None:
        updates["category"] = category
    if next_renewal is not None:
        updates["next_renewal"] = next_renewal.date() if hasattr(next_renewal, "date") else next_renewal
    if notes is not None:
        updates["notes"] = notes
    if activate:
        updates["active"] = True
    if deactivate:
        updates["active"] = False

    if not updates:
        console.print("\n  [dim]Nothing to update. Use flags to specify changes.[/]\n")
        return

    result = db.update(sub_id, **updates)
    if result:
        t = Text()
        t.append("  ")
        t.append("Updated: ", style="bold green")
        t.append(result.name, style="bold")
        console.print(t)
    else:
        console.print("\n  [red]Subscription #{} not found.[/]\n".format(sub_id))


@cli.command()
@click.option("--all", "show_all", is_flag=True, help="Include inactive")
@click.pass_context
def summary(ctx, show_all):
    """Show cost breakdown by category."""
    db = _db(ctx)
    data = db.summary(active_only=not show_all)

    if not data:
        console.print("\n  [dim]No subscriptions yet.[/]\n")
        return

    _print_banner(ctx.obj.get("banner") or "minimal")

    gradient = ["#7c6cf0", "#6d72f3", "#5e78f6", "#4f7ef9", "#4084fc", "#318aff", "#2290ff"]

    table = Table(title="Cost Summary", show_lines=True, border_style="#7c6cf0")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Monthly", justify="right")
    table.add_column("Yearly", justify="right")

    grand_monthly = {}
    grand_yearly = {}

    for i, (cat, info) in enumerate(data.items()):
        icon = CATEGORY_ICONS.get(cat, "📦")
        color = gradient[i % len(gradient)]
        monthly_str = "  ".join(format_price(v, c) for c, v in info["monthly"].items())
        yearly_str = "  ".join(format_price(v, c) for c, v in info["yearly"].items())

        for c, v in info["monthly"].items():
            grand_monthly[c] = grand_monthly.get(c, 0) + v
        for c, v in info["yearly"].items():
            grand_yearly[c] = grand_yearly.get(c, 0) + v

        table.add_row(
            "[{}]{} {}[/]".format(color, icon, cat),
            str(info["count"]),
            "[{}]{}[/]".format(color, monthly_str),
            "[{}]{}[/]".format(color, yearly_str),
        )

    table.add_section()
    gm = "  ".join(format_price(v, c) for c, v in sorted(grand_monthly.items()))
    gy = "  ".join(format_price(v, c) for c, v in sorted(grand_yearly.items()))
    table.add_row("[bold]TOTAL[/]", "", "[bold]{}[/]".format(gm), "[bold]{}[/]".format(gy))

    console.print(table)

    # Upcoming renewals
    upcoming = db.upcoming_renewals(days=7)
    if upcoming:
        console.print("\n  [bold yellow]Upcoming renewals (7 days):[/]")
        for s in upcoming:
            days_left = (s.next_renewal - date.today()).days if s.next_renewal else 0
            console.print("    [yellow]•[/] {} — {} ({}d) — {}".format(
                s.name, s.next_renewal, days_left, format_price(s.price, s.currency)
            ))


@cli.command()
@click.pass_context
def stats(ctx):
    """Show colorful stats dashboard."""
    _print_banner(ctx.obj.get("banner") or "default")
    console.print(make_welcome_text())
    subs = _db(ctx).list_all(active_only=True)
    console.print(make_stats_panel(subs))


@cli.command()
@click.option("--style", "-s", type=click.Choice(list(BANNERS.keys())), default=None, help="Banner style to preview")
@click.pass_context
def banner(ctx, style):
    """Preview available ASCII banners."""
    if style:
        _print_banner(style)
    else:
        for name in BANNERS:
            console.print("\n  [bold #7c6cf0]--- {} ---[/]\n".format(name))
            _print_banner(name)


@cli.command()
@click.option("--format", "-f", "fmt", type=click.Choice(["csv", "json"]), default="csv", help="Export format")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
@click.option("--all", "show_all", is_flag=True, help="Include inactive")
@click.pass_context
def export(ctx, fmt, output, show_all):
    """Export subscriptions to CSV or JSON."""
    db = _db(ctx)
    subs = db.list_all(active_only=not show_all)

    if not subs:
        console.print("\n  [dim]No subscriptions to export.[/]\n")
        return

    if fmt == "csv":
        content = subscriptions_to_csv(subs)
    else:
        content = subscriptions_to_json(subs)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print("\n  [green]Exported to[/] {}\n".format(output))
    else:
        console.print(content)


@cli.command()
@click.pass_context
def tui(ctx):
    """Launch interactive TUI dashboard."""
    from .tui import SubTrackApp

    app = SubTrackApp(db_path=ctx.obj["db"].db_path)
    app.run()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
