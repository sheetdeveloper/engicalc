"""Command line interface - the same engine without the window.

    python -m engicalc.cli solve "2x^2 - 5x - 3 = 0" --steps
    python -m engicalc.cli calc integral "x*sin(x)" --var x --from 0 --to pi
    python -m engicalc.cli formulas --search reynolds
    python -m engicalc.cli formula fluid_mechanics.reynolds --solve-for v \\
        Re=2300 rho=998 D=0.05 mu=0.001 --excel out.xlsx
    python -m engicalc.cli plot "x^2-4" "sin(x)" --out graph.png
    python -m engicalc.cli history --export history.xlsx
"""

from __future__ import annotations

import argparse
import sys

from .core.engine import OPERATIONS, calculate
from .export.excel import export_expression, export_formula, export_history
from .formulas.library import get_library, solve_formula
from .storage.history import History


def _pairs(items) -> dict:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"Expected name=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def cmd_solve(args) -> int:
    result = calculate(args.expression, "solve", args.var)
    print(result.result_text)
    if args.steps:
        print("\n--- steps ---")
        print(result.steps_text())
    if args.save:
        History().add_result(result)
        print("(saved to history)")
    return 0


def cmd_calc(args) -> int:
    result = calculate(args.expression, args.operation, args.var,
                       subs=_pairs(args.values), lower=args.lower,
                       upper=args.upper, point=args.point, order=args.order)
    print(result.result_text)
    for warning in result.warnings:
        print("Note:", warning)
    if args.steps:
        print("\n--- steps ---")
        print(result.steps_text())
    if args.excel:
        print("Wrote", export_expression(result, args.excel, _pairs(args.values)))
    if args.save:
        History().add_result(result)
    return 0


def cmd_formulas(args) -> int:
    library = get_library()
    if args.branches:
        for branch in library.branches():
            print(f"{branch:28s} {len(library.by_branch(branch)):3d} formulas")
        return 0
    formulas = library.search(args.search) if args.search else library.all()
    if args.branch:
        formulas = [f for f in formulas if f.branch.lower() == args.branch.lower()]
    for formula in formulas[:args.limit]:
        print(f"{formula.key:46s} {formula.name}")
        print(f"{'':46s} {formula.equation}")
    print(f"\n{len(formulas)} matching formulas ({len(library)} in the library).")
    return 0


def cmd_formula(args) -> int:
    library = get_library()
    formula = library.get(args.key)
    if formula is None:
        matches = library.search(args.key)
        if not matches:
            raise SystemExit(f"No formula matching {args.key!r}")
        formula = matches[0]
        print(f"(using {formula.key})")
    print(f"{formula.name}  [{formula.branch} / {formula.category}]")
    print(f"  {formula.equation}")
    for variable in formula.variables:
        print(f"    {variable.symbol:12s} {variable.description} "
              f"{('[' + variable.unit + ']') if variable.unit else ''}")
    if formula.assumptions:
        print("  Assumes:", formula.assumptions)
    if not args.solve_for:
        return 0

    solution = solve_formula(formula, args.solve_for, _pairs(args.values))
    print()
    print(solution)
    for warning in solution.warnings:
        print("Note:", warning)
    if args.excel:
        sweep = None
        if args.sweep:
            variable, start, stop = args.sweep
            sweep = {"variable": variable, "start": float(start),
                     "stop": float(stop), "points": args.sweep_points}
        print("Wrote", export_formula(formula, args.solve_for,
                                      _pairs(args.values), args.excel,
                                      sweep=sweep))
    if args.save:
        History().add_formula_solution(solution, project=args.project or "")
        print("(saved to history)")
    return 0


def cmd_plot(args) -> int:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    from .plotting.plot import Curve, PlotSpec, draw

    spec = PlotSpec(curves=[Curve(expression=e, kind=args.kind)
                            for e in args.expressions],
                    xmin=args.xmin, xmax=args.xmax, mark_roots=args.roots)
    figure = Figure(figsize=(8, 5), dpi=120)
    warnings = draw(spec, figure.add_subplot(111))
    figure.tight_layout()
    figure.savefig(args.out, bbox_inches="tight")
    for warning in warnings:
        print("Note:", warning)
    print("Wrote", args.out)
    return 0


def cmd_history(args) -> int:
    history = History()
    entries = history.search(args.search) if args.search else \
        history.recent(limit=args.limit, project=args.project)
    for entry in entries:
        star = "*" if entry.favourite else " "
        print(f"{star} {entry.id:5d}  {entry.short_date()}  {entry.kind:10s} "
              f"{entry.title[:44]:44s} {entry.result_text.splitlines()[0][:40]}")
    print(f"\n{len(entries)} entries. {history.stats()}")
    if args.export:
        print("Wrote", export_history(entries, args.export, library=get_library()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="engicalc", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("solve", help="solve an equation")
    p.add_argument("expression")
    p.add_argument("--var", default=None)
    p.add_argument("--steps", action="store_true")
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_solve)

    p = subs.add_parser("calc", help="any operation")
    p.add_argument("operation", choices=OPERATIONS)
    p.add_argument("expression")
    p.add_argument("--var", default=None)
    p.add_argument("--from", dest="lower", default=None)
    p.add_argument("--to", dest="upper", default=None)
    p.add_argument("--point", default="0")
    p.add_argument("--order", default="1")
    p.add_argument("--values", nargs="*", help="name=value substitutions")
    p.add_argument("--steps", action="store_true")
    p.add_argument("--excel", default=None)
    p.add_argument("--save", action="store_true")
    p.set_defaults(func=cmd_calc)

    p = subs.add_parser("formulas", help="browse the library")
    p.add_argument("--search", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--branches", action="store_true")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(func=cmd_formulas)

    p = subs.add_parser("formula", help="show or evaluate one formula")
    p.add_argument("key")
    p.add_argument("values", nargs="*", help="name=value pairs")
    p.add_argument("--solve-for", default=None)
    p.add_argument("--excel", default=None)
    p.add_argument("--sweep", nargs=3, metavar=("VAR", "START", "STOP"))
    p.add_argument("--sweep-points", type=int, default=25)
    p.add_argument("--save", action="store_true")
    p.add_argument("--project", default="")
    p.set_defaults(func=cmd_formula)

    p = subs.add_parser("plot", help="write a graph to a file")
    p.add_argument("expressions", nargs="+")
    p.add_argument("--kind", default="explicit",
                   choices=["explicit", "implicit", "polar"])
    p.add_argument("--xmin", type=float, default=-10)
    p.add_argument("--xmax", type=float, default=10)
    p.add_argument("--roots", action="store_true")
    p.add_argument("--out", default="graph.png")
    p.set_defaults(func=cmd_plot)

    p = subs.add_parser("history", help="list or export saved calculations")
    p.add_argument("--search", default="")
    p.add_argument("--project", default=None)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--export", default=None)
    p.set_defaults(func=cmd_history)
    return parser


def _use_utf8_output() -> None:
    """Let results print on a console that is not already UTF-8.

    Answers carry characters the display layer uses freely - the U+2248
    'almost equal' in front of a decimal approximation, degree signs, Greek
    letters. A Windows console defaults to cp1252, where printing one raises
    UnicodeEncodeError and the answer is lost behind an encoding error. The
    fix belongs here rather than in the display layer: the notation is right,
    it is the stream that needs telling.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):    # not a reconfigurable stream
            pass


def main(argv=None) -> int:
    _use_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI should not dump a traceback
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
