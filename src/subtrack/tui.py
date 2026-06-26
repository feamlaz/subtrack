"""TUI — Textual-based interactive dashboard."""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.validation import Number
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from .db import BILLING_CYCLES, CATEGORIES, CURRENCIES, Database, Subscription
from .services import BILLING_LABELS, CATEGORY_ICONS, format_price

# Color palette
ACCENT = "#7c6cf0"
BG = "#07080d"
BG_CARD = "#0f1018"
FG = "#e0e0e0"
FG_DIM = "#6b7280"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#eab308"


class SubscriptionForm(ModalScreen):
    """Modal form for adding/editing a subscription."""

    CSS = """
    SubscriptionForm {
        align: center middle;
    }
    SubscriptionForm > Container {
        width: 70;
        height: auto;
        max-height: 30;
        background: """ + BG_CARD + """;
        border: thick """ + ACCENT + """;
        padding: 1 2;
    }
    SubscriptionForm .form-title {
        text-align: center;
        margin-bottom: 1;
        color: """ + ACCENT + """;
    }
    SubscriptionForm Input, SubscriptionForm Select {
        margin-bottom: 1;
    }
    SubscriptionForm .row {
        height: auto;
    }
    SubscriptionForm .btn-row {
        margin-top: 1;
        height: auto;
    }
    SubscriptionForm Button {
        margin-right: 1;
    }
    """

    def __init__(self, sub=None, **kwargs):
        super().__init__(**kwargs)
        self.sub = sub
        self.editing = sub is not None

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(
                "Edit Subscription" if self.editing else "Add Subscription",
                classes="form-title",
            )
            yield Input(
                placeholder="Name (e.g. Netflix)",
                id="name",
                value=self.sub.name if self.sub else "",
            )
            with Horizontal(classes="row"):
                yield Input(
                    placeholder="Price",
                    id="price",
                    value=str(self.sub.price) if self.sub and self.sub.price else "",
                    validators=[Number(minimum=0)],
                )
                yield Select(
                    [(c, c) for c in CURRENCIES],
                    id="currency",
                    value=self.sub.currency if self.sub else "RUB",
                )
            with Horizontal(classes="row"):
                yield Select(
                    [(b, b) for b in BILLING_CYCLES],
                    id="billing",
                    value=self.sub.billing if self.sub else "monthly",
                )
                yield Select(
                    [(c, c) for c in CATEGORIES],
                    id="category",
                    value=self.sub.category if self.sub else "other",
                )
            yield Input(
                placeholder="Next renewal (YYYY-MM-DD)",
                id="next_renewal",
                value=self.sub.next_renewal.isoformat() if self.sub and self.sub.next_renewal else "",
            )
            yield Input(
                placeholder="Notes (optional)",
                id="notes",
                value=self.sub.notes if self.sub else "",
            )
            with Horizontal(classes="btn-row"):
                yield Button("Save", variant="success", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    @on(Button.Pressed, "#save")
    def save(self):
        name = self.query_one("#name", Input).value.strip()
        if not name:
            return

        try:
            price = float(self.query_one("#price", Input).value)
        except ValueError:
            return

        currency = self.query_one("#currency", Select).value or "RUB"
        billing = self.query_one("#billing", Select).value or "monthly"
        category = self.query_one("#category", Select).value or "other"
        renewal_str = self.query_one("#next_renewal", Input).value.strip()
        notes = self.query_one("#notes", Input).value.strip()

        next_renewal = None
        if renewal_str:
            try:
                next_renewal = date.fromisoformat(renewal_str)
            except ValueError:
                pass

        sub = Subscription(
            id=self.sub.id if self.sub else None,
            name=name,
            price=price,
            currency=currency,
            billing=billing,
            category=category,
            next_renewal=next_renewal,
            notes=notes,
        )
        self.dismiss(sub)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class ConfirmDelete(ModalScreen):
    CSS = """
    ConfirmDelete {
        align: center middle;
    }
    ConfirmDelete > Container {
        width: 50;
        height: auto;
        background: """ + BG_CARD + """;
        border: thick """ + ERROR + """;
        padding: 1 2;
    }
    ConfirmDelete .msg {
        text-align: center;
        margin-bottom: 1;
        color: """ + FG + """;
    }
    """

    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self.sub_name = name

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Delete {}?".format(self.sub_name), classes="msg")
            with Horizontal():
                yield Button("Delete", variant="error", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")

    @on(Button.Pressed, "#confirm")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(False)

    def key_escape(self):
        self.dismiss(False)


class SubTrackApp(App):
    """SubTrack — subscription tracker TUI."""

    CSS = """
    Screen {
        background: """ + BG + """;
    }
    #main-container {
        layout: vertical;
        height: 100%;
    }
    #summary-bar {
        dock: top;
        height: auto;
        background: """ + BG_CARD + """;
        border-bottom: solid """ + ACCENT + """;
        padding: 0 1;
        margin-bottom: 0;
    }
    #summary-bar .stat-label {
        color: """ + FG_DIM + """;
    }
    #summary-bar .stat-value {
        color: """ + ACCENT + """;
        text-style: bold;
    }
    #table-container {
        height: 1fr;
    }
    DataTable {
        height: 100%;
        background: """ + BG + """;
    }
    DataTable > .datatable--header {
        background: """ + BG_CARD + """;
        color: """ + ACCENT + """;
    }
    """

    TITLE = "SubTrack"
    SUB_TITLE = "Subscription Tracker"

    BINDINGS = [
        Binding("a", "add", "Add", show=True),
        Binding("e", "edit", "Edit", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, db_path=None, **kwargs):
        super().__init__(**kwargs)
        self.db = Database(db_path)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            with Horizontal(id="summary-bar"):
                yield Label("Loading...", id="stats-label")
            with Vertical(id="table-container"):
                yield DataTable(id="subs-table")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#subs-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Name", "Price", "Monthly", "Category", "Billing", "Renewal")
        self.refresh_data()

    def refresh_data(self):
        subs = self.db.list_all(active_only=True)
        table = self.query_one("#subs-table", DataTable)
        table.clear()

        for s in subs:
            icon = CATEGORY_ICONS.get(s.category, "📦")
            price_str = "{}{}".format(format_price(s.price, s.currency), BILLING_LABELS[s.billing])
            monthly_str = format_price(s.monthly_cost, s.currency)
            renewal = s.next_renewal.isoformat() if s.next_renewal else "—"
            table.add_row(str(s.id), "{} {}".format(icon, s.name), price_str, monthly_str, s.category, s.billing, renewal)

        by_currency = {}
        for s in subs:
            by_currency[s.currency] = by_currency.get(s.currency, 0) + s.monthly_cost

        parts = "  ".join("{}/mo".format(format_price(m, c)) for c, m in sorted(by_currency.items()))
        count = len(subs)

        label = self.query_one("#stats-label", Label)
        text = "  [bold]{}[/] subscription{}  •  [bold]{}[/]".format(
            count, "s" if count != 1 else "", parts
        )

        # Check upcoming
        upcoming = self.db.upcoming_renewals(days=7)
        if upcoming:
            names = ", ".join(s.name for s in upcoming[:3])
            text += "  •  [yellow]Soon: {}[/]".format(names)

        label.update(text)

    def action_add(self):
        def handle(result):
            if result:
                self.db.add(result)
                self.refresh_data()

        self.push_screen(SubscriptionForm(), handle)

    def action_edit(self):
        table = self.query_one("#subs-table", DataTable)
        if table.cursor_row is None:
            return
        row = table.get_row_at(table.cursor_row)
        sub_id = int(row[0])
        sub = self.db.get(sub_id)
        if not sub:
            return

        def handle(result):
            if result and result.id:
                self.db.update(
                    result.id,
                    name=result.name,
                    price=result.price,
                    currency=result.currency,
                    billing=result.billing,
                    category=result.category,
                    next_renewal=result.next_renewal,
                    notes=result.notes,
                )
                self.refresh_data()

        self.push_screen(SubscriptionForm(sub=sub), handle)

    def action_delete(self):
        table = self.query_one("#subs-table", DataTable)
        if table.cursor_row is None:
            return
        row = table.get_row_at(table.cursor_row)
        sub_id = int(row[0])
        sub = self.db.get(sub_id)
        if not sub:
            return

        def handle(confirmed):
            if confirmed:
                self.db.remove(sub_id)
                self.refresh_data()

        self.push_screen(ConfirmDelete(sub.name), handle)

    def action_refresh(self):
        self.refresh_data()

    def on_unmount(self):
        self.db.close()
