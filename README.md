# EngiCalc

A desktop equation solver, grapher and engineering formula library. Symbolab's
solving and graphing, minus the AI and the subscription, plus the two things it
doesn't do: a searchable library of engineering formulas that rearrange for any
variable, and export to a **live, formula-driven** Excel workbook.

Everything runs locally. No account, nothing uploaded.

The one thing that can reach the internet is the update check, and it is
**off unless you ask for it**: *Help → Check for updates* asks GitHub whether
a newer release exists, and *Options → Check for updates at startup* does the
same each time the app opens. Either way it only ever **tells** you - it
never downloads or installs anything, it opens the release page and you
decide. Leave both alone and the app makes no network calls at all.

New to this codebase? Read **HANDOVER.md** first - it covers what is built, what
was verified and how, what was not, and what to do next. **CLAUDE.md** covers how
to work on the code.

**[Download the installer](https://github.com/sheetdeveloper/engicalc/releases/latest)**
for Windows - no Python needed.

---

![The calculator](docs/screenshots/calculator.png)

*A definite integral, typed into the equation bar as a real integral sign, with
the area it measures shaded underneath and the working beside it.*

| | |
|---|---|
| ![Matrices](docs/screenshots/matrices.png) | ![Interpolation](docs/screenshots/interpolate.png) |
| **Matrices** - several equations solved at once | **Interpolation** - reading between the rows of a table |
| ![Formula library](docs/screenshots/formula_library.png) | ![Graphing](docs/screenshots/graph.png) |
| **229 formulas**, each rearranging for any variable | **Graphing** - explicit, implicit, parametric and polar |
| ![Solved together](docs/screenshots/simultaneous.png) | ![Units](docs/screenshots/units.png) |
| **Equations solved together** - in any order, with the count before the answer | **Units** - and the same value in everything else that measures it |
| ![All working](docs/screenshots/working.png) | ![Trendlines](docs/screenshots/statistics.png) |
| **All working** - the rule stated, then applied | **Trendlines** - six shapes, scored so they compare |
| ![Steam](docs/screenshots/steam.png) | ![Moist air](docs/screenshots/moistair.png) |
| **Steam tables** computed from IAPWS-IF97, with the chart beside them | **Moist air** - the psychrometric chart, read off exactly |
| ![A study](docs/screenshots/study.png) | ![Complex numbers](docs/screenshots/complex.png) |
| **Parametric studies** - the same set solved down a column of values | **Complex numbers** - rectangular, polar and the Argand diagram |
| ![Stress and strain](docs/screenshots/tensile.png) | ![Beam](docs/screenshots/beam.png) |
| **Stress and strain** - modulus, proof stress and UTS read off a test | **Beam diagrams** - free body, shear, moment and deflection |
| ![Stress state](docs/screenshots/mohr.png) | ![Moody](docs/screenshots/moody.png) |
| **Stress state** - Mohr's circle, then whether the material stands it | **Moody chart** - Colebrook solved, not approximated |
| ![Section properties](docs/screenshots/section.png) | ![Motion](docs/screenshots/motion.png) |
| **Section properties** - centroid and second moment, from the dimensions | **Motion** - distance, velocity and acceleration on one time axis |
| ![R134a](docs/screenshots/r134a.png) | ![Refrigeration cycle](docs/screenshots/cycle.png) |
| **Refrigerants** - R134a, ammonia and propane, each from its own reference equation | **The refrigeration cycle** - four states, the COP, the duty |
| ![Torsion](docs/screenshots/torsion.png) | ![Columns](docs/screenshots/columns.png) |
| **Torsion** - shear stress and twist, from the power at a speed | **Columns** - Euler, Rankine and Perry-Robertson on one chart |
| ![Truss](docs/screenshots/truss.png) | ![Pressure vessel](docs/screenshots/vessel.png) |
| **Trusses** - every joint solved at once, ties red and struts blue | **Pressure vessels** - thin walled and thick, and where the two part |
| ![Geometry](docs/screenshots/geometry.png) | ![Material chart](docs/screenshots/materials.png) |
| **Geometry** - triangles, arcs and crossings, with both answers where there are two | **Material charts** - 52 of them, with family envelopes and a selection line |
| ![Curved beam](docs/screenshots/curved.png) | ![Axial](docs/screenshots/axial.png) |
| **Curved beams** - a hook or a clamp, where M y / I is not conservative | **Axial members** - stepped and composite bars, held at both ends and heated |
| ![Worksheet](docs/screenshots/sheet.png) | ![Formula cards](docs/screenshots/formula_cards.png) |
| **Worksheets** - named steps down the page, each using the ones above it | **Formula cards** - the library to browse rather than to solve |
| ![Differential equations](docs/screenshots/ode.png) | ![Inequalities](docs/screenshots/inequality.png) |
| **Differential equations** - solved symbolically, with the initial conditions applied | **Inequalities** - solved, and the range shaded on the number line |

---

## Running it

**Windows** - double-click `run_engicalc.bat`.

The first run creates a private Python environment in `.venv` and installs the
four dependencies (two or three minutes). Every run after that opens straight
away. If Python isn't installed the script tells you where to get it.

    run_engicalc.bat              start the app
    run_engicalc.bat test         run the self-tests
    run_engicalc.bat reinstall    rebuild the environment from scratch

To get a desktop icon: right-click `run_engicalc.bat` → Send to → Desktop
(create shortcut). Right-click the shortcut → Properties → Change Icon if you
want to give it one.

**macOS / Linux** - `./run_engicalc.sh` (same three commands).

Requires Python 3.10 or newer with Tkinter, which the standard python.org
installer includes on Windows and macOS. On Debian/Ubuntu: `sudo apt install
python3-tk`.

---

## How numbers are written

**Options -> Numbers** sets the decimal places and the notation for the whole
app at once - plain decimal, scientific or engineering, where engineering
keeps the exponent a multiple of three because that is what makes it kilo or
micro. A preference that applied to only some tabs would not be one.

Plain decimal counts places after the point, which is what "decimal places"
means; the others count significant figures, because a fixed number of
places after the point does not go with an exponent. In the typeset panels an
exponent is drawn as one - 565.884 x 10^3 rather than 565.884e3.


## The tabs

### Calculator

Type an equation and press Go. Everything on screen is typeset properly -
including the equation bar itself. Press the definite integral button and you
get a real integral sign with empty boxes at the limits; Tab moves between them
and you type the values straight in. Fractions, powers, roots, logs and limits
all behave the same way, and they nest, so the denominator of a fraction can
hold a square root. Answers and working appear as fractions, radicals,
integrals and Greek letters rather than ASCII.

Underneath sits a plain-text box for anyone who would rather type
`2x^2 - 5x - 3 = 0` and be done with it. The two are kept in step - edit either
one and the other follows, and typed text becomes real structure, so typing
`sqrt(x)` there gives you a radical upstairs with an editable box under it.
**Show all working** on the steps panel expands the working. Instead of the
integral of 2x becoming x squared with nothing in between, it names the rule
and states it as notation - constant multiple, then the power rule - and then
applies it. A transposition goes one move at a time, each carrying the
equation it leaves behind, described the way it would be said out loud: add
fifteen to both sides, rather than take away minus fifteen.

There is also a plain-text toggle on the steps panel if you want something
copyable, and a Copy LaTeX button for pasting into a report.

**Plot it** draws the answer beside it. For a definite integral that means the
integrand with the area shaded between the limits - which is what the answer
actually measures - with area below the axis hatched in red, since it counts as
negative in the total. For a solve, the curve with its roots marked. The
checkbox turns it off, and anything with no sensible picture (a system of
equations, say) simply doesn't show one.

Under the entry boxes sits the **symbol pad**: the common symbols on one row,
with **Full pad** expanding the rest grouped by kind. Every button is drawn in
real notation and tells you what it types when you hover. The ones with a shape
to them - fractions, powers, roots, logs, and the calculus buttons - draw that
shape in the equation bar with the caret already in the first box.

**Help -> Symbols and syntax reference** opens a searchable table of every
symbol: what it looks like, what to type to get it, and a worked example.
Double-click a row to type it straight into the calculator. Handles linear, quadratic, polynomial, rational,
radical, exponential, logarithmic, absolute-value and trigonometric equations,
and falls back to numerical root-finding when no closed form exists.

The **Steps** panel shows the working: terms moved to one side, denominators
cleared (with the domain restriction noted), the equation classified, the
discriminant, the factorisation or quadratic formula, then each answer
substituted back in to verify it.

Operations: solve, roots, simplify, expand, factor, evaluate, derivative,
integral (indefinite or definite), limit, series, simultaneous systems
(separate the equations with `;`), and differential equations.

**Differential equations** are written in prime notation, as they are on
paper: `y' = -(y - 20)/5` for a cooling curve, `y'' + 4y = 0` for a vibrating
mass, `y'' = -w*x/(E*I)` for a beam. Initial conditions go in the conditions
box as `y(0) = 90, y'(0) = 0`. Without them the answer keeps its arbitrary
constants and is a family of curves rather than the one your apparatus
actually followed, and it says so.

Inequalities work too - `x^2 <= 9`, `1/x < 1`, `abs(x - 3) <= 5`, `x != 0` -
and answer with the range that satisfies them (`x in [-3, 3]`) rather than a
list of points, showing the boundary points and the interval test as working.

### Graph

Up to six curves at once, in four flavours:

| Type | What you type | Example |
|---|---|---|
| explicit | y as a function of x | `x^2 - 4` or `y = sin(x)` |
| implicit | any relation in x and y | `x^2 + y^2 = 9` |
| parametric | x(t) and y(t) in the two boxes | `cos(t)` and `sin(t)` |
| polar | r as a function of theta | `1 + cos(theta)` |

Roots are marked and labelled. Full matplotlib pan/zoom toolbar underneath, and
Save PNG (or PDF/SVG) for reports.

### Formula cards

The whole library as typeset cards - name, formula in proper notation, branch.
Filter by branch, search by anything, click a card to open it ready to solve.
Recognising a formula by its notation is much faster than reading ASCII.

### Formula library

**229 formulas across 12 branches**: Mechanics, Strength of Materials,
Thermodynamics, Fluid Mechanics, Heat Transfer, Electrical, Civil & Structural,
Materials & Manufacturing, Chemical & Process, Control & Signals,
Geometry & Maths, and **HVAC & Sheet Metal**.

The HVAC branch covers duct sizing and airflow, velocity pressure, duct
friction, air changes, sensible load, fan power and the fan laws; and on the
sheet-metal side bend allowance, setback, bend deduction, K-factor, sheet
weight and rolled blank length. The bend maths is the K-factor method a
flat-pattern generator uses, and is checked against fixed values that any
reader can verify by hand - because a blank cut from a number worked out
here has to fold to the size the drawing says. Nothing here reaches into
another program to check that; the numbers are written down.

Every formula carries its variables, units, descriptions, typical values and
assumptions. Pick what to solve for, fill in what you know, press Calculate.
The formula is rearranged symbolically first, then evaluated - so you see the
rearrangement and the answer, both typeset.

Formulas are drawn in the order they are conventionally written: F = ma, not
F = am. SymPy reorders terms as it evaluates, so anything shown to the user is
parsed without evaluation and printed with the ordering left alone.

800 of the 804 possible rearrangements (every variable of every formula) resolve
symbolically; the four that can't - fin efficiency, Heron for the semi-perimeter,
annuity interest rate - are solved numerically instead, and say so.

**Made of** appears on the formulas that have somewhere to put a material,
and fills those slots from the material database - a modulus into `E`, a
yield strength into `sigma_y`, a conductivity into `k` - converted into
whatever unit that formula is written in, so a database that quotes 210 GPa
puts 2.1e11 into a slot asking for pascals.

Which slots take a material is declared on the formula rather than worked
out from the words, and that is the point of it. "Density" appears
twenty-one times in the library and only six of those want a solid: the
rest are air in a duct or water in a pipe. Nothing in the description tells
those apart, so a picker that guessed would offer steel to a drag force.
The ones that do not take a material do not show the picker at all.

Only grades are offered, never classes, for the same reason the beam tab
only offers grades. A property the chosen material does not record is left
alone and said so, rather than filled from the materials that do record it.
Every filled field stays editable and says where its number came from.

**Sensitivity plot** sweeps one input across a range and plots the result.

**Add my own formula** stores your own equations in
`~/.engicalc/user_formulas.json`, and they behave exactly like the built-in ones.

### Interpolate

Reading a value between the rows of a table - a steam table, a pump curve, a
materials chart. Paste two columns straight out of Excel, say which x you
want, and it gives you the answer with the working: which two rows it used,
the straight-line formula, the numbers substituted in, and the gradient over
that interval. That working is the part that gets marked.

Also does the reverse (given y, find x), a least-squares polynomial fit when
a straight line will not do, and nearest-row lookup.

**Extrapolation is called out.** Ask for a value beyond the ends of the data
and you still get an answer, with a warning saying it is a guess from outside
where the numbers came from. Reading past the end of a steam table silently
is how people get hurt.

### Calculator -> Solved together

A calculation is rarely a chain that runs one way. Sizing a duct, the friction
factor depends on the Reynolds number, which depends on the velocity, which
depends on the area - and the pressure drop depends on all three. Untangling
that by hand before you can start is where the mistakes come from.

Write the equations in any order and they are solved as a set. A known value
is an equation too, so fixing something means writing `d = 0.15` on a line of
its own.

**The count is shown before anything is solved, and updates as you type.**
Three equations and four unknowns has no single answer, and being told so
while you are still writing is more use than any number would be - so it says
what to do about the shortfall rather than only naming it.

Every answer is substituted back into the original equations and checked. A
numerical solve that converged on the wrong branch looks exactly like one that
worked until you do that. The check is relative: an absolute tolerance against
a Reynolds number of half a million would be asking for more significant
figures than double precision carries.

Leave a set one equation short and the name nothing pins down becomes an
input. The **Study** page beside the answer then solves the whole set once
for each value of it and tabulates and plots the results - what the pressure
drop does across every duct size, rather than at the one you were given.

Each value is solved from the equations as written rather than from the
previous answer. That is slower, and it is right: a set with more than one
solution can jump between them as the swept value moves, and carrying the
last answer forward would smooth over exactly that.


### Calculator -> Units

Converts a quantity, and then shows it in every unit that measures the same
thing - 2.5 bar is also 250 kPa and 36.26 psi - because the number you need is
often not the one you thought to ask for.

Temperature is the one case it asks about rather than guessing: 20 °C is
293.15 K as a temperature and 20 K as a difference, and picking wrong is a 273
degree error that looks perfectly plausible on the page. The choice appears
only where it changes the answer.

### Data

The numbers a lab report needs. Paste one column of readings and it gives the
count, mean, median, standard deviation, standard error and range. Paste two
and it fits **six trendline shapes** - linear, quadratic, cubic, exponential,
logarithmic and power - lists them ranked, and draws the one you pick.

**R squared is measured on the readings for every shape, which is deliberately
not what a spreadsheet does.** An exponential is fitted by taking logs of y and
fitting a line to those, and Excel reports how well that line fits the logs.
That number flatters - taking logs squashes the large residuals that matter
most - and two shapes scored that way cannot be compared at all, because they
are measured against different things. Since the whole point of offering six
shapes is to choose between them, each is scored by how far its curve actually
lands from the readings. On noisy exponential data the difference is enough to
change which shape wins.

A shape that cannot be fitted is still listed, saying why: "needs every y above
zero" is more use than the shape quietly not appearing. A fit that misses badly
scores below zero, which means the curve describes the readings worse than a
flat line through their mean - worth being told.

Both the sample and population standard deviations are shown, sample first,
because measurements are a sample and quoting the wrong one is an invisible
error. The residuals are drawn because R squared says how much of the
variation the curve accounts for, not whether it was the right shape to
fit - a pattern in the residuals means it was not.

### Properties

Fluid properties, computed rather than looked up.

**Water and steam** comes from IAPWS-IF97 - the international standard, the
same formulation used industrially. Nothing is tabulated, so there is no row
to interpolate between and no edge to read off. Three ways of asking, because
those are the three ways a question is put: on the saturation line, inside
the dome at a known dryness, or at a pressure and temperature that fix the
state outright. `h_fg` is shown beside the saturated pair, since it is what
most questions are after and the one number a printed table makes you work
out yourself.

The basis for trusting it is in the tests: **all twenty-four verification
values published with the standard match to better than one part in 10^8**.
Two further checks do not depend on the coefficients at all - the saturation
equation lands on the triple point and the critical point, which are defined
rather than fitted values, and the internal energy and entropy of saturated
liquid at the triple point come out as zero without anything setting them to
zero. Regions 3 and 5 are not implemented, and a state in either raises
rather than being answered from the wrong equations.

**Moist air** is the psychrometric chart. The dry bulb never fixes the state
on its own, so it asks for one measure of the moisture as well - relative
humidity, humidity ratio, wet bulb or dew point, whichever you have - and
everything else follows. It shares one saturation pressure with the steam
tables rather than carrying a correlation of its own, so the two cannot
disagree in the fourth figure.

Below freezing the vapour deposits as frost rather than condensing, which is
a different curve and not one this has. Where that happens the dew point and
wet bulb are left out with the reason on screen; everything that does not
depend on that curve is still exactly right.

**Refrigerants** - R134a, ammonia (R717) and propane (R290), each from its
own published reference equation of state rather than from a table of one
and a correlation for the others:

| | |
| --- | --- |
| R134a | Tillner-Roth and Baehr (1994) |
| Ammonia | Gao and others (2023), with the associating term |
| Propane | Lemmon, McLinden and Wagner (2009) |

The saturation line is found by Maxwell construction - the pressure at
which the liquid and the vapour sit at the same pressure with the same
Gibbs energy - and not from a fitted curve. Nothing sets the saturation
pressure directly, so agreeing with the ancillary equation published
alongside each formulation is a **result** rather than an arrangement, and
all three agree with theirs to within the accuracy the ancillary is itself
quoted to: 0.009% for R134a, 0.016% for propane, 0.05% for ammonia.

The boiling points come out at -26.074, -33.316 and -42.114 C against
published values of -26.07, -33.327 and -42.114. The critical pressure is
not set either - the equation is evaluated at the critical temperature and
density and the published pressure comes back.

Ammonia's molecules hydrogen bond, and that is why its formulation needed a
term shape the other two do not have. All three are measured from the same
reference state - saturated liquid at 0 C, h = 200 kJ/kg, s = 1 kJ/(kg K) -
so their enthalpies can be put side by side.

**The refrigeration cycle** puts four states on that diagram - compressor in
and out, condenser out, evaporator in - and gives the COP, the work, and the
mass flow needed for a duty, on any of the three refrigerants. Isentropic
efficiency, superheat and subcooling are all optional and left out rather
than assumed. The same four states run as a heat pump, since a heat pump is
this cycle read for what it rejects instead of what it absorbs.

Running the same machine on all three shows what the choice of refrigerant
actually buys. Between -10 and 40 C the COP is 2.88 to 3.00 whichever one
is in it - the coefficient of performance is set by the two temperatures
and barely at all by the fluid. What changes is everything else: ammonia
carries seven times the heat per kilogram, so it moves a seventh of the
mass for the same cooling and the pipework and the compressor are smaller;
and it leaves the compressor at 162 C rather than 65, which is why an
ammonia plant needs desuperheating that a halocarbon one does not.


### Charts

Eleven engineering calculations that are better looked at than listed. Each
one draws, states its numbers beside the drawing, and exports the figure as
PNG, SVG or PDF or copies it straight to the clipboard.

**Beam diagrams.** Any number of point loads, couples, spread loads and ramps,
at angles, on supports you put where you want them - pinned, roller or built
in. It draws the free body, then the axial force, shear force, bending moment
and deflection under each other on one length axis. Two supports are solved by
statics; three or more, or a built-in end, are **statically indeterminate** and
solved by the force method, releasing the extra restraints and putting back
whatever forces close the gaps they open. The five textbook deflection cases
come out to within five parts in a million, and the indeterminate ones to
better than 0.01%.

**Section properties.** Area, centroid, second moment about both axes, the
product moment, the principal axes and the section moduli, from rectangles,
circles, polygons and fillets added together - or from a **section table** of
48 rolled profiles: universal beams and columns, channels, angles, hollow
sections and pipe. Every row in that table is checked against the geometry it
claims, which is a check on the data rather than on the arithmetic: the
published area and second moment have to fall out of the published dimensions.
The median disagreement is 0.12%, and two rows whose published dimensions did
not reproduce their published properties were removed rather than fudged.

The shear stress through the depth is drawn too - VQ/It, worked from the
actual shape rather than from a formula for a rectangle. It gives 3V/2A for a
rectangle and 4V/3A for a circle exactly, because those are what the general
method reduces to.

The section feeds the beam tab, and the beam tab feeds the stress state tab.

**Torsion.** Shear stress and angle of twist in a shaft, from a torque or
from the power at a speed. It will size a shaft for an allowable stress or an
allowable twist, and split a torque between shafts in parallel. It refuses
non-circular sections rather than applying a circular formula to them.

**Columns.** Euler, Rankine-Gordon and Perry-Robertson drawn together against
slenderness, with the yield cut-off, so you can see where Euler stops meaning
anything. Eight end conditions.

**Motion.** Distance, velocity and acceleration on one time axis, built out of
phases - accelerate, hold, decelerate - with the SUVAT equations solved for
whatever was left out.

**Stress state.** Mohr's circle drawn exactly, with the construction on it,
from stresses or from a **strain gauge rosette** - 45, 60 or 120 degree. Then
whether the material stands it: Tresca and von Mises worked from all three
principal stresses rather than the plane-stress shortcut, with both loci drawn
and the state plotted on them.

**Pressure vessels.** Thin-walled and thick-walled (Lame) side by side, so the
error in the thin-wall assumption is visible rather than assumed away, with
the stress distribution through the wall drawn. Cylinders and spheres, and it
will size a wall for an allowable stress.

**Trusses.** The whole frame solved at once - two equilibrium equations per
joint as one linear system - rather than joint by joint in an order you have
to find. Ties red, struts blue, thickness by force. It states whether the
frame is determinate before it solves it, and every joint balances to within
a hundred-billionth of a newton.

**Material charts.** **52 materials** on logarithmic axes, each drawn as
the range it actually covers rather than as a point, with an envelope round
each family and a performance index laid across as a straight edge with
everything above it better. The method is Ashby's; the data is assembled
here from standards and manufacturers' figures, and each row says where it
came from.

Fifty-two is more than one screen can name at once, so the chart has the
controls that make a crowded one usable: a tick per family, so you can
narrow it to the two you are actually choosing between; a material picked
out with a heavy edge; naming that falls back to only the ones above the
line when there are too many, and says that it has; and an option to draw
only what beats the line at all.

They span what a selection chart has to span - three decades of density
from a flexible foam to tungsten, nearly seven of modulus from a silicone
to a carbide - and wood is on it **both ways round**, because along the
grain it looks extraordinary and across it looks like a soft polymer, and
putting only the first on is putting the half that flatters it.

It is held at two levels because two different questions get asked. A class -
"carbon steel" - carries wide ranges, because the class is that wide, and
those ranges are what the chart is drawn from. A grade - S275, 6082-T6, 316L -
carries tight values with the condition they apply at, and is what gets pulled
into a calculation. Only grades are offered to the beam and column tabs,
because handing over the middle of 250 to 1500 N/mm2 would look like an
answer.

The data checks itself: G = E/2(1+v) - which is a formula in this program, so
the data is checked against the app's own algebra - yield below tensile
strength, service temperature below melting point, and volumetric heat
capacity and thermal diffusivity inside the bands every solid falls in.
Thirty-six materials, zero failures.

**Curved beams.** A crane hook, a C-clamp, a chain link, the frame of a
punch press. Bend a straight beam and the stress goes linearly across the
depth with nothing at the centroid; bend a bar that was curved to start
with and neither is true. The fibres on the inside of the curve were
shorter to begin with, so the same rotation strains them more, and the
stress comes out as a hyperbola in the radius rather than a straight line
in the depth.

Two things follow, and they are what the tab is for. **The neutral axis is
not at the centroid** - it moves in toward the centre of curvature. And
**the inside stress can be far higher than a straight-beam calculation
gives**: on a hook whose radius is about the depth of its section it is
half as much again, and the inside is the fibre a hook is judged on. Using
M y / I there is not conservative, it is optimistic, which is the wrong
direction to be wrong in. Both answers are drawn on the same axes so the
gap between them is visible, and it closes as the radius grows - past about
eight times the depth there is a couple of per cent in it and the tab says
so.

**Axial members.** Bars held at both ends, and what heating them does. Heat
a steel bar lying on a bench and it gets longer and carries nothing; heat
the same bar between two walls and it gets no longer at all and carries a
force that **does not depend on how long it is** - a metre or a kilometre,
the strain that was prevented is the same and so is the stress.

In series, a stepped bar or several bars end to end with loads where they
meet; in parallel, a bolt through a sleeve or a column with steel in it,
sharing the load in proportion to their stiffnesses. Held at both ends it
is statically indeterminate and solved by the force method, the same as the
beams.

Three kinds of support, because conflating any two of them gives a wrong
answer that looks reasonable. **Fixed** is attached: it can pull as well as
push. **Free** is nothing there. **A wall** can only push - it carries
nothing until the bar has grown far enough to touch it, and nothing again
if the load pulls the bar away from it. A bar left a millimetre short of
the wall is genuinely one problem or the other, and which is not decided by
whoever set it.

**Geometry.** The other half of geometry from the section tab: not what a
shape's properties are, but what the shape *is*. Three parts of a triangle
and the other three follow; two facts about an arc and the rest of it
follows; two lines, or a line and a circle, or two circles, and where they
cross; the tangents from a point; the circle through three points.

Its whole character is that some of these questions have two answers, and
it says so instead of picking one. Two sides and an angle that is not
between them describe **two** different triangles and both are correct -
returning whichever one the arcsine happened to give is the classic wrong
answer in every trigonometry course there is. Both are drawn, one over the
other, which shows exactly how the loose side swings to meet the base in
two places. A radius and a chord describe two arcs for a similar reason:
the chord cuts the circle in two and both pieces are arcs of it, so both
are drawn on the same chord. And three angles are refused outright,
because they fix the shape and say nothing whatever about the size.

**Moody chart.** Colebrook solved rather than approximated, with the operating
point marked.

**Stress and strain.** Modulus, proof stress and UTS read off a tensile test.

### Worksheet

Real work is never one calculation. It is a diameter, then an area from that
diameter, then a velocity, then a Reynolds number - and if the diameter
changes, everything after it should follow.

A sheet is a list of named steps worked down the page. Each step can use any
name defined above it, and nothing may use a name defined below it. Change
the bore from 50 mm to 100 mm, press Calculate, and every line beneath moves.
Worksheets save and reopen as files.

A step that fails is reported and the ones after it carry on, because one
broken line in the middle should not blank the page.

### Matrices

Built around **A x = b** - solving several equations at once, which is what
matrices are for in engineering. A frame with a dozen joints gives a dozen
equations that all have to hold, and this solves them in one step.

The coefficients go into a **grid of cells**, because that is what a matrix
is - Tab across, Enter down, and buttons to add or remove a row or a column.
Pasting a block copied out of Excel fills the grid and resizes it to fit.

Also determinant, inverse, transpose, rank, eigenvalues (natural frequencies,
buckling loads, principal stresses) and multiplication. Entries can be
symbols, not just numbers.

Two things it refuses to do quietly:

- **A singular matrix has no unique solution**, so it says so instead of
  returning whatever dividing by nearly-zero produced. The equations are
  either contradictory or say the same thing twice.
- **An ill-conditioned matrix is flagged.** If small changes in the inputs
  would swing the answer wildly, the figures are arithmetic rather than
  engineering, and you are told.

### History

Every calculation you save goes into a SQLite database at
`~/.engicalc/history.db`. Assign a project, add notes, star the important ones,
search across everything, reopen any entry back into the tab it came from, or
export a selection.

Turn on Options → Auto-save every result if you'd rather it kept everything.

---

## Excel export

This is the part worth knowing about. The exported workbook is **not** a
snapshot of numbers - each input gets its own labelled cell and a defined name,
and the result cell holds a real Excel formula:

    Q = m*c*(T2 - T1)      becomes      =v_c*v_m*(-v_T1+v_T2)

Change an input, Excel recalculates. Blue shaded cells are inputs, black cells
are formulas, and every sheet carries a legend saying so.

A SymPy-to-Excel printer handles `SQRT`, `LN`/`LOG`, all the trig and hyperbolic
functions, `ATAN2` (whose argument order Excel reverses), `FLOOR`/`CEILING` with
their step argument, `Piecewise` as nested `IF`, and rational powers. It sticks
to Excel-2007-era functions, so the workbooks open and recalculate correctly in
LibreOffice and Google Sheets too - verified by recalculating the generated
files in LibreOffice and checking for formula errors.

Three exports:

- **From the library** - one calculation, plus an optional Sensitivity sheet
  with a live formula per row and a line chart.
- **From the calculator** - any expression, with a cell per free symbol.
- **From History** - a log sheet of everything shown, *plus a rebuilt live sheet
  per saved formula calculation*. Exporting your past work gives you a workbook
  you can keep using.

---

## Input syntax

    Powers            x^2   or   x**2   (or press the pad button)
    Multiplication    2x, 3sin(x) and 2*x all work
    Roots             sqrt(x), cbrt(x), root(x, 3), x^(1/3)
    Logs              log(x) is natural; log(x, 10), log10(x), log2(x)
    Exponential       exp(x), e^x
    Absolute value    abs(x) or |x|
    Trig              sin cos tan asin acos atan atan2, plus hyperbolics
    Constants         pi, e, oo (infinity), I (imaginary unit)
    Greek             type rho, mu, sigma... or paste ρ, μ, σ
    Equations         one '=' per line
    Systems           separate with ';'   ->   x + y = 10; x - y = 2
    Numbers           2/3 stays exact, 0.667 is decimal, 1.5e-3 works

---

## Layout

    engicalc/
      core/
        parsing.py         text -> SymPy, whitelisted names only
        engine.py          solve / calculus / systems, returns CalcResult
        steps.py           the worked solution
        display.py         SymPy -> readable notation
        excel_printer.py   SymPy -> Excel formula strings
      formulas/
        model.py           Formula and Variable
        library.py         load, search, rearrange, user formulas
        data/              one module per branch - this is where to add formulas
      plotting/plot.py     all four curve types, root marking, sweeps
      core/interpolate.py  reading between the rows of a table
      core/matrices.py     A x = b, determinant, eigenvalues and the rest
      core/sheet.py        chained steps, each using the ones above
      core/statistics.py   describing readings, and the line through them
      core/odes.py         differential equations in prime notation
      formulas/data/hvac.py  ductwork, fans and sheet metal
      core/updates.py      is there a newer release - telling, never installing
      core/units.py        mm and m cannot be quietly mixed
      core/system.py       equations solved together, in any order
      core/fitting.py      six trendline shapes, scored so they compare
      core/steam.py        water and steam, from IAPWS-IF97
      core/psychrometrics.py  moist air, on top of that saturation pressure
      plotting/property_plot.py  the saturation dome, T-s, P-v, P-h, T-v
      storage/history.py   SQLite history
      export/excel.py      the workbook builders
      ui/
        app.py             window shell and cross-tab plumbing
        mathrender.py      LaTeX -> PNG -> Tk, with a plain-text fallback
        pad.py             the symbol list: buttons, help and syntax in one place
        mathfield.py       the editable typeset equation bar
        clipboard.py       put a picture on the clipboard, for Word
        matrixview.py      draws a matrix, which mathtext cannot
        symbol_pad.py      the pad widget
        reference_window.py  searchable symbol and syntax reference
        calculator_pane.py the Calculator's sub-tabs
        properties_pane.py steam and moist air together
        steam_tab.py       moistair_tab.py
        simultaneous_tab.py  units_tab.py
        calculator_tab.py  graph_tab.py  library_tab.py  cards_tab.py
        history_tab.py     widgets.py
    tests/test_engicalc.py 332 tests
    main.py                entry point
    run_engicalc.bat       Windows launcher

### Adding formulas in bulk

Open the relevant file in `engicalc/formulas/data/` and add an entry:

```python
f("bolt_preload", "Bolt preload from torque", "Fasteners",
  "T = K*F*d",
  {"T": ("Tightening torque", "N*m"),
   "K": ("Nut factor", "-", "0.2"),
   "F": ("Preload", "N"),
   "d": ("Nominal diameter", "m")},
  notes="K is 0.2 for plain steel, ~0.15 lubricated.",
  assumptions="Elastic tightening, no thread damage.")
```

The third element of a variable tuple is an optional typical value used by
"Use defaults". Two rules the test suite enforces: the symbols in the equation
must exactly match the declared variables, and the formula must rearrange for
each of them. Run `run_engicalc.bat test` after adding any.

---

## Building a standalone .exe

For handing the app to someone who has no Python and should not have to
install any.

    build_exe.bat              build dist\EngiCalc.exe
    build_exe.bat clean        throw away the build folders first
    build_exe.bat debug        build a console version instead
    build_installer.bat        wrap it in Output\EngiCalc_Setup.exe

`build_exe.bat` makes its own environment in `.venv-build` (separate from the
`.venv` the app runs from, so installing PyInstaller cannot disturb a working
install), runs the test suite, and refuses to build if it fails. The result is
a single ~56 MB file that runs on a machine with nothing installed. The
installer needs [Inno Setup](https://jrsoftware.org/isdl.php), which is free;
the script looks in the usual places for it.

The version comes from `engicalc/__init__.py` and is stamped into
`installer.iss` automatically - don't edit it in two places.

**If a frozen build misbehaves**, use `build_exe.bat debug` and run
`dist\EngiCalc-debug.exe` from a command prompt. A windowed build that fails at
startup does so silently: the process sits there with no window and no error.
The console build prints the traceback. This is not hypothetical - the first
build of this app failed exactly that way, because the formula library imports
its eleven branch modules by name and PyInstaller's import scan could not see
them.

---

## Tests

198 tests covering the parser (including that it refuses `__import__`), the
engine, the formula library (every formula parses, declares its variables, and
rearranges), the history store, the Excel export, plotting, the typeset
rendering layer (every library formula, every pad symbol and every calculator
step is checked to render), the equation field (every shape renders, every box is
locatable, every one compiles back to input the parser accepts, and typed text
round-trips through the structure unchanged), and the answer plots.

The Excel printer tests are the interesting ones: they generate random values,
evaluate the printed Excel string in Python, and compare against SymPy to eight
decimal places - so the translation is proven faithful rather than
eyeballed.

---

## How the notation is drawn

Matplotlib's mathtext engine renders a LaTeX subset to a PNG and Tk loads the
PNG - so there is no TeX installation to manage and no extra dependency. Every
one of the 212 library formulas, and every calculator result and step, was
checked to render; anything mathtext cannot draw (matrices, piecewise braces)
falls back to monospace text rather than showing an error.

## Known limits

- Roots of periodic functions are reported as SymPy's principal solutions
  (`sin(x) = 0` gives 0 and pi, not the whole family).
- Units are carried through a worksheet and through the formula library, but
  the calculator itself is still unitless. Keep one system per calculation
  there.
- Complex results and infinities can't be written to Excel; the export says so
  rather than writing something wrong.
- Library formulas are the standard textbook forms. Check the assumption line
  before using any of them for design work - and none of the civil or structural
  entries include code factors.
