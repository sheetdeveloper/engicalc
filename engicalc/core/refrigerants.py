"""The refrigerants this app knows, and what to say about each of them.

Adding another is a module beside this one and a line in ``FLUIDS``. The
tabs read from here rather than naming a fluid, so nothing else has to
change.

All three are measured from the same reference state - saturated liquid at
0 C with h = 200 kJ/kg and s = 1 kJ/(kg K) - so their enthalpies can be put
side by side. A table printed from a different reference has every enthalpy
shifted by a constant and every difference the same, which is what actually
gets used.
"""

from __future__ import annotations

from . import ammonia, propane, r134a

#: name -> (fluid, what it is for)
FLUIDS = {
    "R134a": (
        r134a.FLUID,
        "The halocarbon that replaced R12. Not flammable, not toxic, and "
        "a global warming potential of 1430 - which is why it is being "
        "replaced in turn."),
    "Ammonia (R717)": (
        ammonia.FLUID,
        "The oldest refrigerant still in wide industrial use. No ozone "
        "effect, no warming potential, and a latent heat several times "
        "any halocarbon's, which is why a cold store runs on it. Toxic, "
        "and it attacks copper."),
    "Propane (R290)": (
        propane.FLUID,
        "A hydrocarbon with a warming potential of about three. "
        "Flammable, which is why the charge in a system using it is "
        "limited rather than why it is not used."),
}


def names() -> list:
    return list(FLUIDS)


def fluid(name: str):
    """The fluid behind a name, or R134a if the name is not one of them."""
    found = FLUIDS.get(name)
    return found[0] if found else r134a.FLUID


def about(name: str) -> str:
    found = FLUIDS.get(name)
    return found[1] if found else ""
