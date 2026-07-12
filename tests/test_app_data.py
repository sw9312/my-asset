import app_data
from app_data import SHEETS, init_sheets, migrate_missing_ids


class FakeWorksheet:
    def __init__(self, title, values):
        self.title = title
        self.values = values

    def get_all_values(self):
        return self.values

    def clear(self):
        self.values = []

    def update(self, _range, values):
        self.values = values


class FakeBook:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}

    def worksheets(self):
        return list(self.sheets.values())

    def add_worksheet(self, title, rows, cols):
        sheet = FakeWorksheet(title, [])
        self.sheets[title] = sheet
        return sheet


def test_init_sheets_migrates_legacy_cash_without_losing_values():
    cash = FakeWorksheet("cash_list", [["owner", "label", "amount", "currency"], ["지영", "현금", "100", "KRW(원)"]])
    book = FakeBook([cash])
    init_sheets(book)
    assert cash.values[0] == SHEETS["cash_list"]
    migrated = dict(zip(cash.values[0], cash.values[1]))
    assert migrated["owner"] == "지영"
    assert migrated["amount"] == "100"
    assert migrated["id"]


def test_init_sheets_repairs_blank_duplicate_headers():
    history = FakeWorksheet("history", [["date", "total", "stock", "cash", "", ""], ["2026-01-01", "100", "80", "20", "50", "50"]])
    book = FakeBook([history])
    init_sheets(book)
    assert history.values[0] == SHEETS["history"]
    assert history.values[1][2:5] == ["100", "80", "20"]


def test_migration_with_existing_ids_does_not_read_google_sheets(monkeypatch):
    def fail_if_called():
        raise AssertionError("Google Sheets should not be opened during a slider rerun")

    monkeypatch.setattr(app_data, "_initialized_book", fail_if_called)
    data = {
        "cash_list": [{"id": "cash-1"}],
        "stocks": [{"id": "stock-1"}],
        "watchlist": [{"id": "watch-1"}],
    }
    assert migrate_missing_ids(data) is False
