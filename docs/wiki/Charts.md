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

### Giving it a section

Pick a section - one off the list, or whatever the Section tab currently
has - and give it a modulus, and two more things follow.

**The stress**, at the hardest-worked fibre, worked out on the section
itself. On a shape with no axis of symmetry that is not `M y / I` and not at
the top or bottom fibre either; see the Section notes above.

**The deflection**, drawn as a fourth diagram underneath the others.
`EI y'' = M`, so it is the moment diagram integrated twice, and the two
constants that fall out of integrating twice are exactly what the supports
say: held down in two places, or held down and held level in one. Doing it
numerically along the diagram already drawn means it works for any beam this
can draw rather than for the six with formulae in the back of a book - an
overhang, a triangular load, three loads at once.

It is checked against those six all the same. `5wL^4/384EI`, `PL^3/48EI`,
`Pa^2b^2/3EIL`, `PL^3/3EI` and `wL^4/8EI` all come back to within five parts
in a million.

Beside the deflection is the span over it - span/360 and so on - because
that is the number a floor is actually checked against, and the span it uses
is the distance between the supports rather than the length of the beam.

Two things get said out loud rather than left in the table: a stress past
the yield of ordinary structural steel, since the deflection below it
assumes the beam springs back, and a movement worse than span/360, which is
what a floor is commonly held to.

### Beams equilibrium cannot settle on its own

A propped cantilever, a beam built in at both ends, a beam continuous over
three supports - all ordinary, and all with more unknown reactions than
statics has equations. These were refused for a long time, and the refusal
was honest while there was nothing else to go on.

The deflection is the missing equation. A support is a place where the beam
cannot move, and a built-in end is a place where it cannot turn either. So
the extra supports are taken away, the sag where they were is worked out,
and the forces that put it back are solved for - the force method, and the
same idea as the compatibility condition that splits a torque between two
fixed ends.

Two things worth knowing. **The reactions do not depend on what the beam is
made of.** For one section throughout, the stiffness cancels between the sag
and the force that undoes it, so a steel beam and an aluminium one of the
same shape share their load identically; only the movement differs. And the
method is entirely general - it applies to any beam these diagrams can draw,
so a propped cantilever with a triangular load on an overhang is no harder
than the one in the book.

It is checked against the cases that are in the book:

| | | |
| --- | --- | --- |
| propped cantilever, spread load | R at the prop | 3wL/8 |
| propped cantilever, load at midspan | R at the prop | 5P/16 |
| built in both ends, spread load | moment at the ends | wL²/12 |
| built in both ends, load at midspan | moment at the ends | PL/8 |
| two equal spans, spread load | middle reaction | 10wL/8 |

The tab takes three supports, which is what a continuous beam needs. The
third starts as "none".

### What it still will not do

Two pinned supports with a load leaning against them. They share the thrust
along the beam in a proportion equilibrium cannot settle, and the deflection
worked out here says nothing about that direction - so that one is still
refused rather than guessed.

Sign convention: upward loads positive, sagging moment positive,
anticlockwise couples positive, tension positive, distances from the
left-hand end.

## Section

Area, centroid, second moment of area, section modulus and radius of
gyration, for the shape a beam is actually made of. Give it a bending moment
and it gives the stress as well.

Two ways in. Pick a designation from the table - universal beams and
columns, channels, equal and unequal angles, circular hollow sections - and
it fills the dimension boxes in. Or ignore the table and type the dimensions
of whatever you have. Either way the properties are worked out from the
geometry, so the two routes cannot disagree with each other, and a section
that is not in the list is served exactly as well as one that is.

Shapes: I section, channel, tee, angle, rectangular hollow, circular hollow,
round bar and flat bar. Anything else can be built from rectangles, circles
and holes in the core module.

### About the table

A table of numbers in a program is a liability - nobody can see where it
came from and a transposed digit reads like an answer forever. So this one
carries its own check. Each row holds the dimensions *and* the published
area and second moments, and the test suite works the properties out from
the dimensions and compares. Five dimensions producing three published
quantities at once is tight: a wrong web thickness moves the area, a wrong
flange moves Ixx and Iyy by different amounts.

Forty-eight rows agree, most of them to better than a fifth of a percent.
Two more were removed rather than shipped, because they did not.

What the check cannot tell you is whether the right name is on the row. It
says the geometry is self-consistent, not that anyone looked the designation
up correctly - so check the designation against your own tables before it
goes into something that matters.

### Radii

The root radii are in, and so are the toe radii on angles. This is not
fussiness. Square corners read a universal beam about 2% stiff and an angle
2 to 3% stiff, and 2% of a second moment is 2% of every deflection worked
from it. Putting the toe radii in at half the root radius took eleven angles
from 2-3% out to under a third of a percent - which is the argument for
having them.

Rectangular hollow sections are rounded outside and inside too. Square
corners read those about 3% stiff.

### Shear stress

Give the section a shear force as well as a moment and it works out the
other stress:

    tau = V Q / (I t)

`Q` is the first moment about the neutral axis of everything beyond the
level being asked about, and `t` is how much metal is there to carry it.
Both are questions about the **level** rather than about the section, which
is why the section answers them one level at a time rather than once at the
start.

It is drawn beside the shape, sharing the vertical axis, so the step lines
up with the flange it steps at.

**The two stresses never peak in the same place.** Bending is largest at the
top and bottom and nothing at the neutral axis; shear is exactly the other
way round. A section checked for one has not been checked for the other, and
the tab says so.

Two results fall out that are worth knowing:

- On a **rectangle** the distribution is parabolic and peaks at `3V/2A` -
  half again the average, not the average, which is the mistake worth not
  making.
- On a **round bar** it peaks at `4V/3A`.
- On an **I section** it jumps where the flange meets the web, because `t`
  drops from the flange width to the web thickness with nothing else
  changing. On a 305x165x40 UB the step is nearly tenfold and **the web
  carries 97% of the shear** - which is why webs are what buckle and why
  `V/(D x t_web)` is the quick check people use. That quick check is about
  10% unconservative; the real peak is higher.

The Beam tab reports it too, from its own largest shear force, once it has
been given a section.

### Bending stress

Not `M y / I`. That is the stress in a section with an axis of symmetry,
which is every shape here except the angles - and the angles are where it
matters. The general form is used throughout:

    sigma = [(Mx Iyy + My Ixy) y - (Mx Ixy + My Ixx) x] / (Ixx Iyy - Ixy^2)

which collapses back to `M y / I` the moment Ixy is zero, so there is no
need for both. On a 100x75x10 angle the term `M y / I` drops is a third of
the answer.

With that term in, the worst-stressed point is no longer the furthest fibre
from the x axis - it is the furthest corner from the neutral axis, and the
neutral axis is not horizontal. So every corner of the shape is asked and
the tab says which one won.

A section without an axis of symmetry also gets its principal axes drawn on
the picture and reported in the table, because the weak axis of an angle is
nowhere near either of its legs. That is why an unrestrained angle moves
sideways when you load it downwards.

## Torsion

Shear stress and angle of twist in a round shaft, drawn the way it is drawn
on paper: the section cut across a diameter, and underneath it the stress -
nothing at the centre, most at the surface, straight in between.

    tau = T r / J        theta = T L / (G J)        P = T omega

Give it an outside diameter, a bore, a length and a modulus of rigidity, and
either a torque or **a power at a speed** - because a torque is usually not
what anybody has. It is a motor rating, and converting it is the first step
of every one of these problems.

Out come J, the polar section modulus, the stress at the surface and at the
bore, the angle of twist over the length and per metre, and the torsional
stiffness in newton metres per radian. Give it an allowable shear stress and
it adds the factor against it and **the smallest diameter that would do** -
which is the question behind the answer.

### Why shafts are tubes

The picture makes the case better than the numbers. Stress is proportional
to radius, so the metal near the axis is carrying almost nothing - and
because J goes as the fourth power of diameter, taking that metal out costs
far less strength than weight.

Bore a 60 mm shaft out to 40 mm and it still carries 80% of the torque for
56% of the weight. The tab says so, in those terms, whenever there is a
bore.

### What it will not do

The polar second moment of area is the torsion constant **for a circular
section and nothing else**. A square bar's resistance to twist is not the
sum of its two second moments; non-circular sections warp as they twist,
which is a different theory. Using J for them overstates the stiffness by
something like forty per cent, so this covers round bars and tubes and says
nothing about anything else.

### A shaft fixed at both ends

`shared_torque` in the core splits a torque applied part way along between
two built-in ends. It is statically indeterminate - two unknowns and one
equation of equilibrium - and it is settled the same way a propped beam is:
both halves twist by the same amount where they meet, so the torque divides
inversely with the lengths. A torque a third of the way along a shaft sends
two thirds of itself to the near end.

## Motion

Distance, velocity and acceleration against time, stacked on one time axis.
They are one movement seen three ways, and the whole subject is the two
facts joining them: the slope of the velocity curve is the acceleration, and
the area under it is the distance. Drawn apart those are two more things to
remember; drawn one above the other they are hard to miss. The area under
the velocity curve is shaded for the same reason.

A movement is described as the stages it goes through, each of constant
acceleration. **Give any two of the four** - how long it lasts, what it
accelerates at, what velocity it reaches, how far it covers - and the other
two are worked out. Which two is up to you, and that is the point: the stage
a lift spends getting up to speed is naturally a rate and a speed, the stage
it spends at that speed is a distance, and converting one into the other is
work the program should be doing.

Each stage starts at the velocity the one before it finished at, which is
what makes them stages rather than separate problems.

### The five equations

One stage, plus the starting velocity, is three of the five quantities
known - which is the exercise every course sets. So it is the same tab: put
one stage in and it works the other two out.

    v = u + a t
    s = (u + v) t / 2
    s = u t + a t^2 / 2
    v^2 = u^2 + 2 a s

They are applied in turn until nothing new comes out, rather than as ten
special cases for the ten ways of choosing three from five. The equations
are the same four whichever three you know, and writing them once is the
only way they stay the same four. The test suite works one movement out all
ten ways and checks they agree.

`v^2 = u^2 + 2 a s` has two roots and only one of them happens after the
start of the problem, so the one that takes a positive time is the one
taken. And if it comes out negative there is no real answer at all - that is
braking harder than the distance allows, which is a sign error rather than a
movement, and it says so.

### Turning round

A velocity that goes negative means it has turned round, not that something
has gone wrong. Distance travelled and displacement are then different
numbers and both are reported. Something thrown up at 20 m/s and caught
again covers 40.8 m of ground and ends up where it started - the area under
the velocity curve counting the part below the axis as negative is exactly
that difference.

### Speed up, run, stop

The button fills in the trapezoidal profile a lift, a conveyor or a machine
axis actually moves on. Give it a top speed, a rate each way and a distance,
and the cruise in the middle - the fiddly one to work out by hand - falls
out. If it cannot reach that speed and still stop in the distance, it says
how much room speeding up and braking need on their own rather than
returning a negative cruise.

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
