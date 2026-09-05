"""Export calculations to a *live* Excel workbook.

The point of this module is that the exported sheet is not a snapshot: every
input lands in its own labelled cell and the result cell holds a real Excel
formula built from the SymPy expression. Change an input, Excel recalculates.

Conventions follow normal spreadsheet practice: blue text for cells you are
meant to edit, black for calculated cells, and a legend on every sheet.
"""

from __future__ import annotations

import os
from datetime import datetime

import sympy as sp
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

from ..core.excel_printer import ExcelFormulaError, excel_name, to_excel_formula

FONT = "Arial"
TITLE_FONT = Font(name=FONT, size=14, bold=True)
H1 = Font(name=FONT, size=11, bold=True, color="FFFFFF")
LABEL = Font(name=FONT, size=10, bold=True)
BODY = Font(name=FONT, size=10)
INPUT_FONT = Font(name=FONT, size=10, color="0000FF")
RESULT_FONT = Font(name=FONT, size=12, bold=True)
MUTED = Font(name=FONT, size=9, italic=True, color="666666")

HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
RESULT_FILL = PatternFill("solid", fgColor="E2EFDA")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


class ExportError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Shared sheet builders
# --------------------------------------------------------------------------
def _header(ws, row: int, headings: list[str], start_col: int = 1) -> None:
    for offset, text in enumerate(headings):
        cell = ws.cell(row=row, column=start_col + offset, value=text)
        cell.font = H1
        cell.fill = HEADER_FILL
        cell.border = BOX
        cell.alignment = Alignment(horizontal="center")


def _widths(ws, widths: dict) -> None:
    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def _legend(ws, row: int) -> int:
    ws.cell(row=row, column=1, value="Legend").font = LABEL
    ws.cell(row=row + 1, column=1, value="Blue, shaded cells are inputs - edit these"
            ).font = INPUT_FONT
    ws.cell(row=row + 2, column=1,
            value="Black cells are live formulas - they recalculate automatically"
            ).font = BODY
    return row + 3


def _write_inputs_block(ws, start_row: int, variables, values: dict,
                        target: str, sheet_name: str,
                        defined: dict | None = None) -> tuple[int, dict]:
    """Write the input table and return (next_row, symbol -> cell reference)."""
    _header(ws, start_row, ["Symbol", "Quantity", "Value", "Unit"])
    refs: dict[str, str] = {}
    row = start_row + 1
    for var in variables:
        if var.symbol == target:
            continue
        raw = values.get(var.symbol, var.typical)
        ws.cell(row=row, column=1, value=var.symbol).font = LABEL
        ws.cell(row=row, column=2, value=var.description).font = BODY
        cell = ws.cell(row=row, column=3, value=_as_number(raw))
        cell.font = INPUT_FONT
        cell.fill = INPUT_FILL
        cell.border = BOX
        cell.number_format = "General"
        ws.cell(row=row, column=4, value=var.unit).font = BODY
        refs[var.symbol] = f"'{sheet_name}'!$C${row}"
        if defined is not None:
            defined[var.symbol] = f"'{sheet_name}'!$C${row}"
        row += 1
    return row, refs


def _as_number(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(sp.N(sp.sympify(str(raw))))
    except Exception:  # noqa: BLE001
        return str(raw)


# --------------------------------------------------------------------------
# Single formula export
# --------------------------------------------------------------------------
def export_formula(formula, target: str, values: dict, path: str,
                   expression=None, sweep: dict | None = None,
                   project: str = "") -> str:
    """Write a workbook for one library formula.

    ``sweep`` is optional: ``{"variable": "T2", "start": 20, "stop": 90,
    "points": 25}`` adds a live sensitivity table and a chart.
    """
    from ..core.engine import rearrange

    expr = expression if expression is not None else rearrange(formula.eq,
                                                               sp.Symbol(target))
    if expr is None:
        raise ExportError(
            f"{formula.name} has no closed-form rearrangement for {target}, "
            "so it cannot be written as an Excel formula.")
    if isinstance(expr, list):
        expr = expr[0]

    wb = Workbook()
    ws = wb.active
    ws.title = "Calculation"
    ws.sheet_view.showGridLines = False
    _widths(ws, {"A": 14, "B": 42, "C": 18, "D": 16, "E": 30})

    ws["A1"] = formula.name
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"{formula.branch} / {formula.category}"
    ws["A2"].font = MUTED

    ws["A4"] = "Formula"
    ws["A4"].font = LABEL
    ws["B4"] = formula.equation
    ws["B4"].font = BODY
    ws["A5"] = "Solved for"
    ws["A5"].font = LABEL
    ws["B5"] = f"{target}  [{formula.unit_of(target)}]"
    ws["B5"].font = BODY
    ws["A6"] = "Rearranged"
    ws["A6"].font = LABEL
    ws["B6"] = f"{target} = {sp.sstr(expr)}"
    ws["B6"].font = BODY

    defined: dict[str, str] = {}
    next_row, _ = _write_inputs_block(ws, 8, formula.variables, values, target,
                                      "Calculation", defined)

    # Workbook-level names so the result formula reads like the algebra.
    name_map = {}
    for symbol, ref in defined.items():
        name = excel_name(symbol)
        name_map[symbol] = name
        wb.defined_names.add(DefinedName(name, attr_text=ref))

    try:
        formula_text = to_excel_formula(expr, symbol_map=name_map)
    except ExcelFormulaError as exc:
        raise ExportError(str(exc)) from exc

    result_row = next_row + 1
    ws.cell(row=result_row, column=1, value="RESULT").font = LABEL
    ws.cell(row=result_row, column=2, value=target).font = LABEL
    cell = ws.cell(row=result_row, column=3, value=formula_text)
    cell.font = RESULT_FONT
    cell.fill = RESULT_FILL
    cell.border = BOX
    cell.number_format = "0.000000"
    ws.cell(row=result_row, column=4, value=formula.unit_of(target)).font = BODY
    ws.cell(row=result_row + 1, column=2, value="Excel formula used:").font = MUTED
    ws.cell(row=result_row + 1, column=3, value="'" + formula_text).font = MUTED

    row = result_row + 3
    if formula.assumptions:
        ws.cell(row=row, column=1, value="Assumptions").font = LABEL
        ws.cell(row=row, column=2, value=formula.assumptions).font = BODY
        row += 1
    if formula.notes:
        ws.cell(row=row, column=1, value="Notes").font = LABEL
        ws.cell(row=row, column=2, value=formula.notes).font = BODY
        row += 1
    if formula.reference:
        ws.cell(row=row, column=1, value="Reference").font = LABEL
        ws.cell(row=row, column=2, value=formula.reference).font = BODY
        row += 1
    ws.cell(row=row, column=1,
            value=f"Generated by EngiCalc on "
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                  + (f" - project: {project}" if project else "")).font = MUTED
    _legend(ws, row + 2)

    if sweep:
        _add_sweep_sheet(wb, formula, target, expr, name_map, sweep)

    _save(wb, path)
    return path


def _add_sweep_sheet(wb, formula, target, expr, name_map: dict, sweep: dict) -> None:
    variable = sweep["variable"]
    start = float(sweep.get("start", 0))
    stop = float(sweep.get("stop", 1))
    points = max(2, min(int(sweep.get("points", 25)), 500))

    ws = wb.create_sheet("Sensitivity")
    ws.sheet_view.showGridLines = False
    _widths(ws, {"A": 18, "B": 22, "C": 40})
    ws["A1"] = f"Sensitivity of {target} to {variable}"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Every row is a live formula - edit the left column and the "
                "result follows.")
    ws["A2"].font = MUTED

    unit_in = formula.unit_of(variable)
    unit_out = formula.unit_of(target)
    _header(ws, 4, [f"{variable} [{unit_in}]".strip(),
                    f"{target} [{unit_out}]".strip()])

    step = (stop - start) / (points - 1)
    for index in range(points):
        row = 5 + index
        cell = ws.cell(row=row, column=1, value=start + step * index)
        cell.font = INPUT_FONT
        cell.fill = INPUT_FILL
        cell.border = BOX
        # The swept variable points at this row; everything else keeps its name.
        local_map = dict(name_map)
        local_map[variable] = f"$A{row}"
        out = ws.cell(row=row, column=2, value=to_excel_formula(expr, symbol_map=local_map))
        out.font = BODY
        out.border = BOX
        out.number_format = "0.000000"

    chart = LineChart()
    chart.title = f"{target} vs {variable}"
    chart.y_axis.title = f"{target} [{unit_out}]".strip()
    chart.x_axis.title = f"{variable} [{unit_in}]".strip()
    chart.height, chart.width = 9, 16
    data = Reference(ws, min_col=2, min_row=4, max_row=4 + points)
    cats = Reference(ws, min_col=1, min_row=5, max_row=4 + points)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    ws.add_chart(chart, "E4")


# --------------------------------------------------------------------------
# History export
# --------------------------------------------------------------------------
def export_history(entries, path: str, library=None, rebuild: bool = True,
                   max_sheets: int = 25) -> str:
    """Write the calculation log, plus a live sheet per stored formula result."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Log"
    ws.sheet_view.showGridLines = False
    _widths(ws, {"A": 18, "B": 12, "C": 34, "D": 34, "E": 10, "F": 26,
                 "G": 10, "H": 16, "I": 30})
    ws["A1"] = "EngiCalc - calculation history"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"Exported {datetime.now().strftime('%Y-%m-%d %H:%M')} - " \
               f"{len(entries)} entries"
    ws["A2"].font = MUTED

    _header(ws, 4, ["Date", "Kind", "Title", "Input", "Solved for", "Result",
                    "Unit", "Project", "Note"])
    for offset, entry in enumerate(entries):
        row = 5 + offset
        cells = [entry.short_date(), entry.kind, entry.title, entry.input_text,
                 entry.variable, entry.result_text.replace("\n", " | "),
                 entry.unit, entry.project, entry.note]
        for column, value in enumerate(cells, start=1):
            cell = ws.cell(row=row, column=column, value=value)
            cell.font = BODY
            cell.alignment = Alignment(vertical="top", wrap_text=column in (3, 4, 6, 9))
    ws.freeze_panes = "A5"

    if rebuild and library is not None:
        made = 0
        used_names = set()
        for entry in entries:
            if made >= max_sheets or entry.kind != "formula":
                continue
            formula = library.get(entry.operation)
            if formula is None or not entry.inputs:
                continue
            title = _unique_sheet_name(entry.title or formula.name, used_names)
            try:
                _rebuild_sheet(wb, title, formula, entry, library)
                made += 1
            except Exception:  # noqa: BLE001 - skip anything that will not translate
                if title in wb.sheetnames:
                    del wb[title]

    _save(wb, path)
    return path


def _unique_sheet_name(base: str, used: set) -> str:
    clean = "".join(c for c in base if c not in "[]:*?/\\")[:28].strip() or "Calc"
    name, index = clean, 2
    while name.lower() in used:
        name = f"{clean[:26]}_{index}"
        index += 1
    used.add(name.lower())
    return name


def _rebuild_sheet(wb, title: str, formula, entry, library) -> None:
    from ..core.engine import rearrange

    target = entry.variable
    expr = rearrange(formula.eq, sp.Symbol(target))
    if expr is None:
        raise ExportError("no closed form")
    if isinstance(expr, list):
        expr = expr[0]

    ws = wb.create_sheet(title)
    ws.sheet_view.showGridLines = False
    _widths(ws, {"A": 14, "B": 42, "C": 18, "D": 16})
    ws["A1"] = formula.name
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"{entry.short_date()} - solved for {target}"
    ws["A2"].font = MUTED
    ws["A4"] = "Formula"
    ws["A4"].font = LABEL
    ws["B4"] = formula.equation
    ws["B4"].font = BODY

    next_row, refs = _write_inputs_block(ws, 6, formula.variables, entry.inputs,
                                         target, title)
    # Same-sheet references keep each rebuilt sheet independent.
    cell_map = {sym: ref.split("!")[-1] for sym, ref in refs.items()}
    text = to_excel_formula(expr, symbol_map=cell_map)

    row = next_row + 1
    ws.cell(row=row, column=1, value="RESULT").font = LABEL
    ws.cell(row=row, column=2, value=target).font = LABEL
    cell = ws.cell(row=row, column=3, value=text)
    cell.font = RESULT_FONT
    cell.fill = RESULT_FILL
    cell.border = BOX
    cell.number_format = "0.000000"
    ws.cell(row=row, column=4, value=formula.unit_of(target)).font = BODY
    _legend(ws, row + 2)


# --------------------------------------------------------------------------
# Free-form expression export
# --------------------------------------------------------------------------
def export_expression(result, path: str, values: dict | None = None) -> str:
    """Export a calculator result (expression or solved equation)."""
    expr = result.results[0] if result.results else result.expression
    if expr is None:
        raise ExportError("Nothing to export.")
    if isinstance(expr, sp.Eq):
        expr = expr.rhs

    wb = Workbook()
    ws = wb.active
    ws.title = "Calculation"
    ws.sheet_view.showGridLines = False
    _widths(ws, {"A": 16, "B": 46, "C": 18, "D": 14})
    ws["A1"] = "EngiCalc export"
    ws["A1"].font = TITLE_FONT
    ws["A3"] = "Input"
    ws["A3"].font = LABEL
    ws["B3"] = result.input_text
    ws["B3"].font = BODY
    ws["A4"] = "Operation"
    ws["A4"].font = LABEL
    ws["B4"] = result.operation
    ws["B4"].font = BODY
    ws["A5"] = "Result"
    ws["A5"].font = LABEL
    ws["B5"] = sp.sstr(expr)
    ws["B5"].font = BODY

    symbols = sorted(expr.free_symbols, key=lambda s: s.name)
    values = values or {}
    name_map = {}
    _header(ws, 7, ["Symbol", "Description", "Value", "Unit"])
    row = 8
    for symbol in symbols:
        ws.cell(row=row, column=1, value=symbol.name).font = LABEL
        ws.cell(row=row, column=2, value="").font = BODY
        cell = ws.cell(row=row, column=3, value=_as_number(values.get(symbol.name)))
        cell.font = INPUT_FONT
        cell.fill = INPUT_FILL
        cell.border = BOX
        name = excel_name(symbol.name)
        wb.defined_names.add(DefinedName(name, attr_text=f"'Calculation'!$C${row}"))
        name_map[symbol.name] = name
        row += 1

    try:
        text = to_excel_formula(expr, symbol_map=name_map)
    except ExcelFormulaError as exc:
        raise ExportError(str(exc)) from exc

    ws.cell(row=row + 1, column=1, value="VALUE").font = LABEL
    cell = ws.cell(row=row + 1, column=3, value=text)
    cell.font = RESULT_FONT
    cell.fill = RESULT_FILL
    cell.border = BOX
    cell.number_format = "0.000000"
    ws.cell(row=row + 2, column=3, value="'" + text).font = MUTED
    _legend(ws, row + 4)
    _save(wb, path)
    return path


def export_table(headings, rows, path: str, title: str = "Data",
                 sheet: str = "Data") -> str:
    """Plain table export (used for sweeps computed in Python)."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws["A1"] = title
    ws["A1"].font = TITLE_FONT
    _header(ws, 3, list(headings))
    for r, values in enumerate(rows, start=4):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font = BODY
    for index in range(1, len(headings) + 1):
        ws.column_dimensions[get_column_letter(index)].width = 18
    _save(wb, path)
    return path


def _save(wb, path: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    wb.save(path)
