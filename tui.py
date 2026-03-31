#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane

from core.config import AppConfig, load_config
from core.db import (
    add_search,
    get_active_searches,
    get_alert_count_by_search,
    get_alerts_for_search,
    init_db,
)
from core.ebay_api import search_ebay


@dataclass(frozen=True)
class SearchRow:
    id: int
    keyword: str
    min_price: Optional[float]
    max_price: Optional[float]
    category_id: Optional[str]
    buying_option: Optional[str]


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


class AlertsScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, *, search: SearchRow) -> None:
        super().__init__()
        self.search = search

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"Alerts for search #{self.search.id} — {self.search.keyword}", id="alerts_title"),
            DataTable(id="alerts_table"),
            Static("Esc to close · j/k to navigate", id="alerts_help"),
            id="alerts_root",
        )

    def on_mount(self) -> None:
        table = self.query_one("#alerts_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Time", "Title", "Price", "URL")

        rows = get_alerts_for_search(self.search.id, limit=1000)
        for r in rows:
            price = ""
            if r["price_value"] is not None:
                cur = r["price_currency"] or ""
                price = f'{r["price_value"]} {cur}'.strip()
            table.add_row(
                _fmt(r["timestamp"]),
                _fmt(r["title"]),
                price,
                _fmt(r["url"]),
            )
        if rows:
            table.focus()

    def action_cursor_down(self) -> None:
        table = self.query_one("#alerts_table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#alerts_table", DataTable)
        table.action_cursor_up()


class StatusView(Static):
    class OpenAlerts(Message):
        def __init__(self, search: SearchRow) -> None:
            super().__init__()
            self.search = search

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "open_selected", "Open alerts", show=False),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Status — searches and alert counts", id="status_title"),
            DataTable(id="searches_table"),
            id="status_root",
        )

    def on_mount(self) -> None:
        table = self.query_one("#searches_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Keyword", "Min", "Max", "Category", "Type", "Alerts")
        self.refresh_table()
        table.focus()

    def refresh_table(self) -> None:
        table = self.query_one("#searches_table", DataTable)
        table.clear()
        searches = get_active_searches()
        for s in searches:
            sr = SearchRow(
                id=int(s["id"]),
                keyword=s["keyword"],
                min_price=s["min_price"],
                max_price=s["max_price"],
                category_id=s["category_id"],
                buying_option=s["buying_option"],
            )
            alerts = get_alert_count_by_search(sr.id)
            table.add_row(
                str(sr.id),
                sr.keyword,
                _fmt(sr.min_price),
                _fmt(sr.max_price),
                _fmt(sr.category_id),
                _fmt(sr.buying_option),
                str(alerts),
                key=str(sr.id),
            )

    def _selected_search(self) -> Optional[SearchRow]:
        table = self.query_one("#searches_table", DataTable)
        if table.row_count == 0:
            return None
        row_key = table.get_row_key(table.cursor_row)
        if row_key is None:
            return None
        # Re-fetch from DB for correctness
        for s in get_active_searches():
            if str(s["id"]) == str(row_key):
                return SearchRow(
                    id=int(s["id"]),
                    keyword=s["keyword"],
                    min_price=s["min_price"],
                    max_price=s["max_price"],
                    category_id=s["category_id"],
                    buying_option=s["buying_option"],
                )
        return None

    def action_cursor_down(self) -> None:
        self.query_one("#searches_table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#searches_table", DataTable).action_cursor_up()

    def action_open_selected(self) -> None:
        sel = self._selected_search()
        if sel:
            self.post_message(self.OpenAlerts(sel))

    def action_refresh(self) -> None:
        self.refresh_table()


class AddSearchView(Static):
    BINDINGS = [
        Binding("ctrl+s", "save_search", "Save search", show=True),
        Binding("r", "refresh_preview", "Refresh preview", show=True),
    ]

    def __init__(self, *, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.current_keyword: str = ""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Add search — type a term, press Enter to preview", id="add_title"),
            Label("Lookback: (30/90/180 days) — preview uses available Browse results; true historical completed listings require a different API", id="lookback_hint"),
            DataTable(id="preview_table"),
            Input(placeholder="Search keyword… (Enter to preview)", id="keyword_input"),
            id="add_root",
        )

    def on_mount(self) -> None:
        table = self.query_one("#preview_table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Title", "Price", "URL")
        self.query_one("#keyword_input", Input).focus()

    @on(Input.Submitted, "#keyword_input")
    def preview(self, event: Input.Submitted) -> None:
        self.current_keyword = event.value.strip()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        table = self.query_one("#preview_table", DataTable)
        table.clear()
        if not self.current_keyword:
            return
        items = search_ebay(self.current_keyword, config=self.config)
        for item in items:
            title = item.get("title") or ""
            price = item.get("price") or {}
            price_str = ""
            if "value" in price and price["value"] is not None:
                cur = price.get("currency") or ""
                price_str = f'{price["value"]} {cur}'.strip()
            url = item.get("itemWebUrl") or ""
            table.add_row(title, price_str, url)

    def action_refresh_preview(self) -> None:
        self.refresh_preview()

    def action_save_search(self) -> None:
        keyword = self.current_keyword.strip()
        if not keyword:
            return
        add_search(keyword, None, None, None, None)
        # Clear input and preview
        self.current_keyword = ""
        self.query_one("#keyword_input", Input).value = ""
        self.query_one("#preview_table", DataTable).clear()


class EbayBotTUI(App[None]):
    CSS = """
    #status_root, #add_root, #alerts_root { padding: 1; }
    #keyword_input { dock: bottom; }
    #alerts_help { dock: bottom; opacity: 0.7; }
    #lookback_hint { opacity: 0.7; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Status", id="tab_status"):
                yield StatusView()
            with TabPane("Add Search", id="tab_add"):
                yield AddSearchView(config=self.config)
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"ebaybot ({self.config.ebay.mode})"

    def on_status_view_open_alerts(self, message: StatusView.OpenAlerts) -> None:
        self.push_screen(AlertsScreen(search=message.search))


def main() -> None:
    init_db()
    cfg = load_config()
    app = EbayBotTUI(cfg)
    app.run()


if __name__ == "__main__":
    main()

