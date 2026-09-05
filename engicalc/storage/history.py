"""Persistent calculation history, in a local SQLite file.

Nothing leaves the machine: the database lives in ``~/.engicalc/history.db``
unless another path is passed in.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime

DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".engicalc", "history.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS calculations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    kind        TEXT    NOT NULL,   -- 'calculator' | 'formula' | 'plot'
    operation   TEXT,               -- solve / integral / formula key ...
    title       TEXT,
    input_text  TEXT    NOT NULL,
    variable    TEXT,
    result_text TEXT,
    expression  TEXT,               -- SymPy srepr-free string form
    inputs_json TEXT,               -- {"m": "2.5", ...}
    unit        TEXT,
    numeric     REAL,
    project     TEXT DEFAULT '',
    tags        TEXT DEFAULT '',
    note        TEXT DEFAULT '',
    favourite   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_created ON calculations(created_at);
CREATE INDEX IF NOT EXISTS idx_project ON calculations(project);
"""


@dataclass
class Entry:
    id: int | None = None
    created_at: str = ""
    kind: str = "calculator"
    operation: str = ""
    title: str = ""
    input_text: str = ""
    variable: str = ""
    result_text: str = ""
    expression: str = ""
    inputs: dict = field(default_factory=dict)
    unit: str = ""
    numeric: float | None = None
    project: str = ""
    tags: str = ""
    note: str = ""
    favourite: bool = False

    def as_row(self) -> tuple:
        return (self.created_at or datetime.now().isoformat(timespec="seconds"),
                self.kind, self.operation, self.title, self.input_text,
                self.variable, self.result_text, self.expression,
                json.dumps(self.inputs), self.unit, self.numeric,
                self.project, self.tags, self.note, int(self.favourite))

    def short_date(self) -> str:
        return self.created_at.replace("T", " ")[:16]


class History:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- writing ----------------------------------------------------------
    def add(self, entry: Entry) -> int:
        cur = self.conn.execute(
            """INSERT INTO calculations
               (created_at, kind, operation, title, input_text, variable,
                result_text, expression, inputs_json, unit, numeric, project,
                tags, note, favourite)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", entry.as_row())
        self.conn.commit()
        return cur.lastrowid

    def add_result(self, result, project: str = "", note: str = "",
                   source: dict | None = None) -> int:
        """Store a :class:`engicalc.core.engine.CalcResult`.

        ``source`` is whatever the tab needs to rebuild itself - the rows of
        a sheet, the readings behind a summary. Kept apart from
        ``input_text`` because what restores a tab and what reads well in the
        history list are rarely the same thing.
        """
        numeric = None
        if result.numeric:
            first = result.numeric[0]
            numeric = first if isinstance(first, (int, float)) else None
        return self.add(Entry(
            kind="calculator", operation=result.operation,
            title=result.input_text[:80], input_text=result.input_text,
            variable=result.variable or "", result_text=result.result_text,
            expression=str(result.expression) if result.expression is not None else "",
            inputs=dict(source or {}),
            numeric=numeric, project=project, note=note))

    def add_formula_solution(self, solution, project: str = "",
                             note: str = "") -> int:
        """Store a :class:`engicalc.formulas.library.FormulaSolution`."""
        f = solution.formula
        return self.add(Entry(
            kind="formula", operation=f.key, title=f"{f.name} -> {solution.target}",
            input_text=f.equation, variable=solution.target,
            result_text=str(solution), expression=str(solution.expression),
            inputs=dict(solution.substitutions), unit=solution.unit,
            numeric=solution.value if isinstance(solution.value, float) else None,
            project=project, note=note))

    def update(self, entry_id: int, **fields) -> None:
        allowed = {"project", "tags", "note", "favourite", "title"}
        sets, params = [], []
        for key, value in fields.items():
            if key in allowed:
                sets.append(f"{key} = ?")
                params.append(int(value) if key == "favourite" else value)
        if not sets:
            return
        params.append(entry_id)
        self.conn.execute(
            f"UPDATE calculations SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()

    def delete(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM calculations WHERE id = ?", (entry_id,))
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM calculations")
        self.conn.commit()

    # -- reading ----------------------------------------------------------
    def _to_entry(self, row: sqlite3.Row) -> Entry:
        return Entry(
            id=row["id"], created_at=row["created_at"], kind=row["kind"],
            operation=row["operation"] or "", title=row["title"] or "",
            input_text=row["input_text"], variable=row["variable"] or "",
            result_text=row["result_text"] or "", expression=row["expression"] or "",
            inputs=json.loads(row["inputs_json"] or "{}"), unit=row["unit"] or "",
            numeric=row["numeric"], project=row["project"] or "",
            tags=row["tags"] or "", note=row["note"] or "",
            favourite=bool(row["favourite"]))

    def recent(self, limit: int = 200, project: str | None = None,
               favourites_only: bool = False) -> list[Entry]:
        sql = "SELECT * FROM calculations WHERE 1=1"
        params: list = []
        if project:
            sql += " AND project = ?"
            params.append(project)
        if favourites_only:
            sql += " AND favourite = 1"
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [self._to_entry(r) for r in self.conn.execute(sql, params)]

    def search(self, query: str, limit: int = 200) -> list[Entry]:
        like = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM calculations
               WHERE input_text LIKE ? OR result_text LIKE ? OR title LIKE ?
                  OR note LIKE ? OR tags LIKE ? OR project LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (like, like, like, like, like, like, limit))
        return [self._to_entry(r) for r in rows]

    def get(self, entry_id: int) -> Entry | None:
        row = self.conn.execute(
            "SELECT * FROM calculations WHERE id = ?", (entry_id,)).fetchone()
        return self._to_entry(row) if row else None

    def projects(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT project FROM calculations WHERE project <> '' "
            "ORDER BY project")
        return [r[0] for r in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) n, SUM(favourite) f FROM calculations").fetchone()
        return {"count": row["n"], "favourites": row["f"] or 0,
                "projects": len(self.projects())}

    def export_json(self, path: str, entries: list[Entry] | None = None) -> str:
        entries = entries if entries is not None else self.recent(limit=100000)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([asdict(e) for e in entries], fh, indent=2)
        return path

    def close(self) -> None:
        self.conn.close()
