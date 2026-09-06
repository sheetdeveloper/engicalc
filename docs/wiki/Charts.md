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

Add as many loads as the beam carries: point loads, loads spread over any
part of the span, and applied couples, in any mixture. Each row is one load
and there is an Add button for each kind.

A spread load can ramp. Give it a second intensity and it runs straight from
one to the other, which covers the triangle liquid pressure puts on a wall
and the trapezoid a sloping roof puts on a purlin. Leave it blank and the
load is uniform.

A point load can lean. The angle is measured from the beam, so ninety
degrees is straight down and anything else has a component along the beam as
well - which is held by the pinned support and drawn as an axial force
diagram underneath the other two. Past ninety it leans back towards the near
end, so one number covers every direction.

Put the supports where they actually are. A beam held in from its ends
overhangs, and the moment over the support is hogging - which the fixed pair
at the ends this tab used to have could never show.

Say what kind each support is:

| Kind | Holds it up | Holds it back | Stops it turning |
| --- | --- | --- | --- |
| roller | yes | | |
| pin | yes | yes | |
| fixed | yes | yes | yes |
| none | | | |

A cantilever is a fixed end with none at the other. Which support is the pin
is worth thinking about rather than accepting: under an inclined load it
decides which part of the beam is pulled and which is pushed, and the two
answers are not the same drawing.

Above the diagrams the beam is drawn twice - as you described it, and again
as a free body with the supports taken away and their reactions standing in
their place. The second is the step the whole method turns on and the one
people skip. Turn it off with the checkbox if you only want the beam.

Everything is worked from the loads by summing along the beam, so the
diagrams and the numbers beside them cannot disagree. Three checks come
free: the shear, the moment and the axial force all have to return to zero
at the far end of a beam in equilibrium, and if they do not you are told the
reactions are wrong rather than shown a plausible drawing.

### What it will not do

All of this comes out of equilibrium, and equilibrium settles a beam with
two simple supports, or one built-in end, and nothing more. These are real
beams and it cannot do them:

- a propped cantilever - built in at one end, resting on something at the
  other
- a beam continuous over three or more supports
- two pinned supports with a load leaning against them, which share the
  thrust in a proportion equilibrium cannot work out

Each is refused by name and by reason. They need the deflections as well as
the forces, and this does not have them.

Sign convention: upward loads positive, sagging moment positive,
anticlockwise couples positive, tension positive, distances from the
left-hand end.

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

## Getting a chart out

Every chart has four buttons under it.

**Save chart** writes the picture. PNG for a report, and PDF or SVG sit
beside it because a bending moment diagram that has to go on a drawing at A3
should not be a photograph of one - the vector formats stay sharp at any
size.

**Copy chart** puts it on the clipboard, ready to paste straight into Word.

**Copy numbers** puts the table underneath it on the clipboard as text.

**Export** writes an Excel workbook with the numbers in it, and the chart
alongside them. The picture is a picture - it does not recalculate - but a
workbook of peak values with no diagram is rarely what anybody opens the
file to see.

The parametric study on the Simultaneous page has the same buttons.
