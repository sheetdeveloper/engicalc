"""Complex numbers as phasors, with the Argand diagram."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np

from ..core import phasor
from ..core.parsing import ParseError
from .charts_pane import ChartTab


class ComplexTab(ChartTab):
    """Two complex numbers, what they do together, and where they sit."""

    title = "Complex numbers"
    hint = "rectangular and polar at once, with the Argand diagram"

    def build_form(self, parent) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x")
        self.left = self.field(row, "z1", "3+4j", "", width=16)
        self.operation = tk.StringVar(value="x")
        box = ttk.Combobox(row, state="readonly", width=3,
                           textvariable=self.operation,
                           values=list(phasor.OPERATIONS))
        box.pack(side="left", padx=(0, 8))
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.right = self.field(row, "z2", "5 angle 30", "", width=16)

        second = ttk.Frame(parent)
        second.pack(fill="x", pady=(6, 0))
        self.angle_unit = tk.StringVar(value=phasor.DEGREES)
        for label in (phasor.DEGREES, phasor.RADIANS):
            ttk.Radiobutton(second, text=label, value=label,
                            variable=self.angle_unit,
                            command=self.refresh).pack(side="left",
                                                       padx=(0, 8))
        ttk.Label(second, style="Hint.TLabel",
                  text="write either form - 3+4j, or a magnitude and an "
                       "angle like 5 angle 30").pack(side="left", padx=(10, 0))

    def draw(self) -> tuple:
        unit = self.angle_unit.get()
        try:
            first = phasor.read(self.left.get(), unit)
            second = phasor.read(self.right.get(), unit)
        except phasor.PhasorError as exc:
            raise ParseError(str(exc)) from exc
        answer = phasor.combine(first, self.operation.get(), second)

        self.figure.clear()
        axes = self.figure.add_subplot(111)
        axes.axhline(0, color="#888888", linewidth=0.8)
        axes.axvline(0, color="#888888", linewidth=0.8)
        for value, colour, name in ((first, "#1f4e79", "z1"),
                                    (second, "#0b7a3b", "z2"),
                                    (answer, "#c0392b", "answer")):
            axes.annotate("", xy=(value.real, value.imaginary), xytext=(0, 0),
                          arrowprops=dict(arrowstyle="->", color=colour,
                                          linewidth=1.6))
            axes.annotate(f"{name}  {value.as_rectangular()}",
                          (value.real, value.imaginary),
                          textcoords="offset points", xytext=(8, 6),
                          fontsize=7, color=colour)
        # The circle each one sits on, so the magnitudes can be compared by
        # eye - which is the whole point of drawing it rather than listing it.
        angles = np.linspace(0, 2 * np.pi, 200)
        for value, colour in ((first, "#1f4e79"), (answer, "#c0392b")):
            axes.plot(value.magnitude * np.cos(angles),
                      value.magnitude * np.sin(angles), ":", color=colour,
                      linewidth=0.7, alpha=0.6)
        axes.set_xlabel("real", fontsize=8)
        axes.set_ylabel("imaginary", fontsize=8)
        axes.grid(True, alpha=0.3, linestyle=":")
        axes.tick_params(labelsize=7)
        axes.set_aspect("equal", adjustable="datalim")

        mark = "deg" if unit == phasor.DEGREES else "rad"
        rows = [("z1", "first", first.as_rectangular(), first.as_polar()),
                ("z2", "second", second.as_rectangular(), second.as_polar()),
                ("", "", "", "")]
        flat = [(f"{symbol} {label}".strip(), rect, polar)
                for symbol, label, rect, polar in rows if rect]
        flat.append((f"z1 {self.operation.get()} z2",
                     answer.as_rectangular(), answer.as_polar()))
        flat.append(("", "", ""))
        flat += [(f"{symbol}  {name}", value, unit_text)
                 for symbol, name, value, unit_text in answer.rows()]
        return flat, []
