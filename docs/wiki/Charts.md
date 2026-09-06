# Charts

Under **Graph**, beside the general plotter. The plotter draws whatever
expression you write; these each take the handful of numbers that define
them, work the whole thing out, and put the figures worth quoting in a table
next to the drawing.

## Stress and strain

Paste a tensile test - strain in the first column, stress in the second -
and it reads off the modulus, the proof stress, the ultimate and the
elongation.

Two parts of that are judgement rather than arithmetic, and both are done
the way a ruler does them:

**Where the straight part ends is found, not assumed.** The modulus is the
slope of the initial straight run, and how much of the curve counts as
straight is the whole question - take too little and the slope is noise,
take too much and the yield rounds it off. It grows the window from the
start while a straight line still fits properly, and stops when it does not.
The chart shows which points it used.

**The proof stress is where the curve crosses a line**, not where it bends,
because on most curves there is no corner to find. A line of the elastic
slope, shifted along by 0.2% strain, and where the data first crosses it is
the answer. The crossing is interpolated between the two readings either
side rather than rounded to the nearer one.

It also gives resilience and toughness, as the areas under the elastic part
and under the whole curve.

## Beam

Shear force and bending moment for a simply supported beam or a cantilever,
with a point load, a spread load, or both.

Everything is worked from the loads by summing along the beam, so the
diagrams and the numbers beside them cannot disagree. Two checks come free:
the shear and the moment both have to return to zero at the far end of a
beam in equilibrium, and if they do not you are told the reactions are wrong
rather than shown a plausible drawing.

Sign convention: upward loads positive, sagging moment positive, distances
from the left-hand end.

## Mohr's circle

Give σx, σy and τxy and it draws the circle, marks the principal stresses,
and gives the angles to them. Turn the axes and it shows where that pair of
points sits, with the diameter joining them - which is the construction
itself.

All of it is exact. There is nothing fitted and nothing iterated: the centre
is the average direct stress, the radius follows from Pythagoras, and the
angles come out of an arctangent. The two-argument kind, so it knows which
quadrant it is in - `atan(y/x)` cannot tell 1+1j from -1-1j.

## Moody

Friction factor against Reynolds number, with your flow marked on it. Pick a
surface and a bore and it works out the relative roughness for you.

Colebrook is solved rather than approximated. The Swamee-Jain and Haaland
forms are within about 2% and are what a spreadsheet usually uses, but
iterating costs nothing and 2% of a pressure drop is not nothing when it is
the number a fan is picked from.

The three regimes are treated as three regimes. Below about 2300 the flow is
laminar and the factor is 64/Re exactly, with no roughness in it at all.
Above 4000 it is turbulent. Between them the transition is shaded and the
answer is flagged as an estimate, because there the result depends on the
pipe's history rather than on the numbers, and a chart that draws a
confident line through it is drawing something nobody can predict.
