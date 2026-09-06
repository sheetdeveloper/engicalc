"""Fluid properties, grouped.

Steam and moist air are the same kind of question - what is this fluid doing
at this state - so they share a tab rather than taking two places in a bar
that is already long. Anything else with a property table belongs here too.

The pane holds the tabs and does none of the work; anything wanting one asks
for it by name, so the rest of the app does not need to know they are
grouped.
"""

from __future__ import annotations

from tkinter import ttk

from .moistair_tab import MoistAirTab
from .r134a_tab import R134aTab
from .steam_tab import SteamTab


class PropertiesPane(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.steam = SteamTab(self.tabs, app)
        self.moist_air = MoistAirTab(self.tabs, app)
        self.r134a = R134aTab(self.tabs, app)

        self.tabs.add(self.steam, text="  Water and steam  ")
        self.tabs.add(self.moist_air, text="  Moist air  ")
        self.tabs.add(self.r134a, text="  R134a  ")

    def show_steam(self) -> None:
        self.tabs.select(self.steam)

    def show_moist_air(self) -> None:
        self.tabs.select(self.moist_air)

    def show_r134a(self) -> None:
        self.tabs.select(self.r134a)
