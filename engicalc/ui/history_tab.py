"""History tab: browse, search, reopen and export past calculations."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import sympy as sp

from ..core.parsing import ParseError, parse_for_display
from ..export.excel import export_history
from . import mathrender
from .widgets import MONO, ReadOnlyText

COLUMNS = [("date", "Date", 130), ("kind", "Kind", 80),
           ("title", "Title", 260), ("result", "Result", 300),
           ("project", "Project", 110)]


class HistoryTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.entries = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Saved calculations", style="Title.TLabel").pack(
            side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        entry.pack(side="left", padx=10)
        entry.bind("<KeyRelease>", lambda e: self.refresh())
        self.favourites_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="favourites only",
                        variable=self.favourites_only,
                        command=self.refresh).pack(side="left")
        ttk.Label(bar, text="project").pack(side="left", padx=(10, 2))
        self.project_var = tk.StringVar(value="(all)")
        self.project_box = ttk.Combobox(bar, textvariable=self.project_var,
                                        width=16, state="readonly")
        self.project_box.pack(side="left")
        self.project_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        table = ttk.Frame(self)
        table.pack(side="top", fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in COLUMNS],
                                 show="headings", selectmode="browse")
        for key, heading, width in COLUMNS:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda e: self.reopen())

        detail_frame = ttk.Frame(self)
        detail_frame.pack(fill="x")
        self.detail_math = mathrender.MathLabel(detail_frame, fontsize=17,
                                                height=54)
        self.detail_math.pack(fill="x", pady=(0, 2))
        self.detail = ReadOnlyText(detail_frame, height=6, font=MONO)
        self.detail.pack(fill="x")

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="Reopen", command=self.reopen).pack(side="left")
        ttk.Button(actions, text="Toggle favourite",
                   command=self.toggle_favourite).pack(side="left", padx=6)
        ttk.Button(actions, text="Set project",
                   command=self.set_project).pack(side="left")
        ttk.Button(actions, text="Add note", command=self.add_note).pack(
            side="left", padx=6)
        ttk.Button(actions, text="Delete", command=self.delete).pack(side="left")
        ttk.Button(actions, text="Export shown to Excel",
                   command=self.export).pack(side="right")
        ttk.Button(actions, text="Export JSON",
                   command=self.export_json).pack(side="right", padx=6)

    # -- data -------------------------------------------------------------
    def refresh(self) -> None:
        query = self.search_var.get().strip()
        project = self.project_var.get()
        project = None if project in ("", "(all)") else project
        if query:
            entries = self.app.history.search(query)
            if project:
                entries = [e for e in entries if e.project == project]
            if self.favourites_only.get():
                entries = [e for e in entries if e.favourite]
        else:
            entries = self.app.history.recent(
                project=project, favourites_only=self.favourites_only.get())
        self.entries = entries
        keep = self.tree.selection()[0] if self.tree.selection() else None
        self.tree.delete(*self.tree.get_children())
        for entry in entries:
            star = "* " if entry.favourite else ""
            self.tree.insert("", "end", iid=str(entry.id), values=(
                entry.short_date(), entry.kind, star + entry.title,
                entry.result_text.replace("\n", " | ")[:120], entry.project))
        # Keep the row selected across a refresh, so favouriting or noting a
        # calculation does not make the next button press a no-op.
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
            self.tree.see(keep)
        self.project_box.configure(
            values=["(all)"] + self.app.history.projects())

    def _selected(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.app.history.get(int(selection[0]))

    def _on_select(self, _event=None) -> None:
        entry = self._selected()
        if entry is None:
            return
        lines = [f"{entry.short_date()}   [{entry.kind}]  {entry.operation}",
                 f"Input:  {entry.input_text}",
                 f"Result: {entry.result_text}"]
        if entry.inputs:
            lines.append("Values: " + ", ".join(f"{k}={v}"
                                                for k, v in entry.inputs.items()))
        if entry.note:
            lines.append("Note:   " + entry.note)
        self.detail.set("\n".join(lines))
        self._show_math(entry)

    def _show_math(self, entry) -> None:
        """Typeset whatever the entry is about: the formula, or the input."""
        try:
            if entry.kind == "formula":
                formula = self.app.library.get(entry.operation)
                if formula is not None:
                    self.detail_math.show(formula.display_latex,
                                          formula.equation)
                    return
            expr = parse_for_display(entry.input_text.split(";")[0])
            self.detail_math.show(sp.latex(expr, order="none"), entry.input_text)
        except (ParseError, Exception):  # noqa: BLE001
            self.detail_math.show(None)

    # -- actions ----------------------------------------------------------
    def reopen(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        self.app.reopen_entry(entry)

    def toggle_favourite(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        self.app.history.update(entry.id, favourite=not entry.favourite)
        self.refresh()

    def set_project(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        value = _ask(self, "Project", "Assign this calculation to a project:",
                     entry.project)
        if value is not None:
            self.app.history.update(entry.id, project=value)
            self.refresh()

    def add_note(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        value = _ask(self, "Note", "Note for this calculation:", entry.note)
        if value is not None:
            self.app.history.update(entry.id, note=value)
            self.refresh()

    def delete(self) -> None:
        entry = self._selected()
        if entry is None:
            return
        if messagebox.askyesno("Delete", "Delete this calculation permanently?"):
            self.app.history.delete(entry.id)
            self.refresh()

    def export(self) -> None:
        if not self.entries:
            messagebox.showinfo("Nothing to export", "No calculations shown.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx")],
            initialfile="engicalc_history.xlsx")
        if not path:
            return
        try:
            export_history(self.entries, path, library=self.app.library)
            self.app.set_status(f"Exported {len(self.entries)} entries to {path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Export failed", str(exc))

    def export_json(self) -> None:
        if not self.entries:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON", "*.json")],
            initialfile="engicalc_history.json")
        if path:
            self.app.history.export_json(path, self.entries)
            self.app.set_status(f"Exported to {path}")


def _ask(parent, title: str, prompt: str, initial: str = "") -> str | None:
    """Small modal text prompt (simpledialog is not styled consistently)."""
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    ttk.Label(dialog, text=prompt).pack(padx=12, pady=(12, 4))
    var = tk.StringVar(value=initial)
    entry = ttk.Entry(dialog, textvariable=var, width=40)
    entry.pack(padx=12)
    entry.focus_set()
    result = {"value": None}

    def ok():
        result["value"] = var.get()
        dialog.destroy()

    buttons = ttk.Frame(dialog)
    buttons.pack(pady=10)
    ttk.Button(buttons, text="OK", command=ok).pack(side="left", padx=4)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left")
    entry.bind("<Return>", lambda e: ok())
    parent.wait_window(dialog)
    return result["value"]
