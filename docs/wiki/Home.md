# EngiCalc

An equation solver, grapher and formula library for engineering coursework.
It runs on Windows as a single installer, needs nothing else installed, and
does not touch the internet unless you ask it to check for an update.

It exists because the tools a student ends up using are a calculator that
cannot show its working, a spreadsheet that cannot do algebra, and a phone
app that wants a subscription. This does the parts of all three that matter
for a degree, and shows what it did.

## What it does

**Solves and shows the working.** Type an equation and press Go. The
equation bar is typeset, so a definite integral appears as a real integral
sign with boxes for the limits. Turn on *all working* and it names the rule
it used and states it before applying it, and takes a transposition one move
at a time.

**Solves a set of equations together.** Write them in any order. It tells
you how many equations and how many unknowns you have *before* it tries,
because three equations and four unknowns has no single answer and being
told that is worth more than any number.

**Knows the properties of water, steam and moist air.** Computed from
IAPWS-IF97 rather than looked up in a table, so there is no row to
interpolate between and no edge to read off. See
[How the answers are checked](How-the-answers-are-checked) for why you can
trust that.

**Draws the charts a course is taught on.** Stress-strain, shear force and
bending moment, Mohr's circle, the Moody chart, and T-s / P-v / P-h /
T-v with the saturation dome.

**229 engineering formulas**, each of which rearranges for any variable in
it, across mechanics, thermodynamics, fluids, electrical, heat transfer,
chemical, civil, control, geometry and HVAC.

## Where to start

* [Installing](Installing) - one file, one click
* [Writing equations](Writing-equations) - the syntax, and what the pad does
* [Solving a set of equations](Solving-a-set-of-equations)
* [Water, steam and moist air](Water-steam-and-moist-air)
* [Charts](Charts)
* [How the answers are checked](How-the-answers-are-checked)
* [Building from source](Building-from-source)

## What it is not

It is not a replacement for understanding the material, and it is not
trying to be. Nothing here does a derivation you could not follow; the
working is shown precisely so it can be checked.

It is not a CAD package, a finite element solver, or a substitute for
design software. The beam diagrams are for a single span with simple
supports, which covers a statics course and not a building.

And it does not know everything about a fluid. Water is covered properly;
refrigerants are not in yet, and the reason they are not is in
[How the answers are checked](How-the-answers-are-checked).
