"""Couche de persistance : Google Sheets en production, CSV local en mode démo.

Les deux backends exposent la même interface, ce qui permet de lancer
l'application sans aucun secret (``streamlit run app.py``) et de la tester en CI.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

import pandas as pd

from . import schema
from .config import SPREADSHEET_NAME, get_secret


class Storage(Protocol):
    label: str

    def read(self, sheet: str) -> pd.DataFrame: ...

    def append(self, sheet: str, rows: list[list]) -> None: ...

    def delete_last_session(self) -> tuple[bool, str]: ...


def _rows_to_delete(values: list[list]) -> int:
    """Nombre de lignes finales partageant la date de la dernière séance."""
    if not values:
        return 0
    last_date = values[-1][0]
    count = 0
    for row in reversed(values):
        if row and row[0] == last_date:
            count += 1
        else:
            break
    return count


# ---------------------------------------------------------------------------
# Backend local (CSV)
# ---------------------------------------------------------------------------
class LocalStorage:
    label = "Local (CSV)"

    def __init__(self, directory: str | Path = "data") -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, sheet: str) -> Path:
        return self.dir / f"{sheet}.csv"

    def _raw(self, sheet: str) -> list[list]:
        path = self._path(sheet)
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        return rows[1:]  # sans en-tête

    def _write(self, sheet: str, rows: list[list]) -> None:
        with self._path(sheet).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(schema.COLUMNS[sheet])
            writer.writerows(rows)

    def read(self, sheet: str) -> pd.DataFrame:
        return schema.normalize(sheet, self._raw(sheet))

    def append(self, sheet: str, rows: list[list]) -> None:
        existing = self._raw(sheet)
        self._write(sheet, existing + [schema.pad_row(sheet, r) for r in rows])

    def delete_last_session(self) -> tuple[bool, str]:
        values = self._raw(schema.REALISE)
        if not values:
            return False, "L'historique est déjà vide."
        count = _rows_to_delete(values)
        last_date = values[-1][0]
        self._write(schema.REALISE, values[:-count])
        return True, f"La séance du {last_date} ({count} lignes) a été annulée."

    def reset(self) -> None:
        for sheet in schema.COLUMNS:
            self._path(sheet).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Backend Google Sheets
# ---------------------------------------------------------------------------
class SheetsStorage:
    label = "Google Sheets"

    def __init__(self, service_account_info: dict, spreadsheet: str = SPREADSHEET_NAME) -> None:
        import gspread
        from google.oauth2.service_account import Credentials

        info = dict(service_account_info)
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open(spreadsheet)
        self._headers_checked: set[str] = set()

    def _ws(self, sheet: str):
        import gspread

        try:
            ws = self.spreadsheet.worksheet(sheet)
        except gspread.WorksheetNotFound:
            ws = self.spreadsheet.add_worksheet(sheet, rows=1000, cols=len(schema.COLUMNS[sheet]))
            ws.append_row(schema.COLUMNS[sheet])
        return ws

    def _ensure_headers(self, ws, sheet: str) -> None:
        """Ajoute les colonnes manquantes (ex : Activity_ID) sans toucher aux existantes."""
        if sheet in self._headers_checked:
            return
        header = ws.row_values(1)
        wanted = schema.COLUMNS[sheet]
        if len(header) < len(wanted):
            if ws.col_count < len(wanted):
                ws.add_cols(len(wanted) - ws.col_count)
            for idx in range(len(header), len(wanted)):
                ws.update_cell(1, idx + 1, wanted[idx])
        self._headers_checked.add(sheet)

    def read(self, sheet: str) -> pd.DataFrame:
        values = self._ws(sheet).get_all_values()
        return schema.normalize(sheet, values[1:])

    def append(self, sheet: str, rows: list[list]) -> None:
        if not rows:
            return
        ws = self._ws(sheet)
        self._ensure_headers(ws, sheet)
        ws.append_rows([schema.pad_row(sheet, r) for r in rows], value_input_option="USER_ENTERED")

    def delete_last_session(self) -> tuple[bool, str]:
        ws = self._ws(schema.REALISE)
        values = ws.get_all_values()
        if len(values) <= 1:
            return False, "L'historique est déjà vide."
        count = _rows_to_delete(values[1:])
        total = len(values)
        ws.delete_rows(total - count + 1, total)
        return True, f"La séance du {values[-1][0]} ({count} lignes) a été annulée."


def build_storage() -> Storage:
    """Sélectionne le backend selon les secrets disponibles."""
    sa = get_secret("gcp_service_account")
    if sa and get_secret("STORAGE", "auto") != "local":
        return SheetsStorage(dict(sa), get_secret("SPREADSHEET_NAME", SPREADSHEET_NAME))
    return LocalStorage(get_secret("LOCAL_DATA_DIR", "data"))
