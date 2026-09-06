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

## Columns

What a strut carries before it bends sideways, and the diagram the whole
subject is taught on: failure stress against slenderness, with this column
marked on it.

A short column fails by squashing. A long one bends sideways long before it
squashes, at a load the material could carry twice over, and it does it
suddenly. Euler settles the long case exactly:

    P = pi^2 E I / Le^2

and the whole subject is knowing where that stops applying.

### Three curves, not one

Euler is derived for a perfectly straight column of perfectly uniform
material loaded perfectly down its axis. Below a slenderness of about
`pi root(E/sigma_y)` it predicts a stress the material cannot reach at all -
which is not a conservative error but a meaningless one, describing a
failure that could not happen because the column would have squashed first.
The tab draws the line where that crossover is and says so when a column is
below it.

So it gives three:

- **Euler**, right at the slender end and nonsense at the stocky end
- **the material's yield**, right at the stocky end and nonsense at the
  slender end
- **Perry-Robertson**, which is the shape every steel code uses. It comes
  from assuming the column starts slightly bent, so bending and squashing
  happen together from the first newton rather than the column staying
  straight until it suddenly does not. Real columns follow this one.

**Rankine-Gordon** is given too - the two failures added as though they were
resistances in series, `1/P = 1/P_squash + 1/P_Euler`. Older and cruder, and
still what a lot of courses teach first.

None of these is a code check. A real design goes to the code, which uses
the same shape of curve with an imperfection factor chosen for the section
and the axis.

### The axis it buckles about

Whichever is easiest, which is the **smaller principal** second moment - not
the smaller of Ixx and Iyy. On an angle those are not the same thing: the
weak axis runs diagonally across it and using Iyy would overstate what the
column carries. The tab says which axis it used and how far round it is.

### Holding the ends

| held | K |
| --- | --- |
| pinned both ends | 1.0 |
| fixed both ends | 0.5 |
| fixed one end, pinned the other | 0.699 |
| fixed one end, free at the other | 2.0 |

These are the theoretical values. Codes use higher ones for real
construction, because a joint drawn as fixed is never quite fixed - a
fixed-fixed column is usually designed at 0.65 rather than 0.5.

A column free at one end is twice as slender as its length suggests, which
makes a free-standing post the worst of the four by a factor of sixteen on
the Euler load.

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

## Stress state

Give σx, σy and τxy and it draws Mohr's circle, marks the principal
stresses, and gives the angles to them. Turn the axes and it shows where
that pair of points sits, with the diameter joining them - which is the
construction itself.

All of that is exact. Nothing is fitted and nothing iterated: the centre is
the average direct stress, the radius follows from Pythagoras, and the
angles come out of an arctangent. The two-argument kind, so it knows which
quadrant it is in - `atan(y/x)` cannot tell 1+1j from -1-1j.

### Does it yield?

Mohr's circle says what the stresses are and nothing about whether they
matter, and the answer is not obvious: a state with no direct stress at all
can be worse than one with a large direct stress, because in a ductile metal
it is the **difference** between the principal stresses that does the damage
rather than their size.

Two criteria, drawn beside the circle in principal stress space:

- **Tresca** - the largest shear reaches half the yield stress. A hexagon.
- **von Mises** - the energy of changing shape reaches a limit. The ellipse
  through the hexagon's corners.

The hexagon is inside, which is what makes Tresca the safe one and is not
visible in either formula. They differ by at most 15.5%, at pure shear,
which is exactly where it matters most.

One trap the tab does not fall into: with both in-plane stresses the same
sign, Tresca is the larger of them **against zero**, not the gap between the
two. The third principal stress is zero, not absent.

Neither criterion says anything about brittle materials. A ductile metal
yields when it is sheared and a brittle one breaks when it is pulled, so
cast iron and concrete need a different criterion - and an answer here for
one of those would be worse than none.

### From a strain gauge rosette

A gauge measures how much the metal stretched under it and nothing else, so
three at known angles are needed to fix a state. Switch the tab to a rosette
and give the three readings in microstrain, plus E and Poisson's ratio.

Solved as a three-by-three system rather than by the two special formulae
for the two common rosettes - those formulae are this with those angles
substituted - so a rosette at any angles at all works the same way.

Turning strain into stress needs Hooke's law in **two** dimensions: pulling
a plate along x makes it thinner along y, so the stress along x depends on
the strain along y too. Using E on its own instead of `E/(1-ν²)` gives an
answer about ten per cent light and entirely plausible.

## Pressure vessel

A cylinder or a sphere, thin walled and thick, with the stress through the
wall drawn.

    cylinder    hoop = pr/t     along = pr/2t
    sphere      both  = pr/2t

A cylinder is twice as stressed round as along, which is why a sausage
splits lengthways and why the seam that runs the length of a boiler drum is
the one that matters. A sphere at the same pressure and wall carries half
what a cylinder does, which is why gas is stored in spheres.

Those hold while the stress does not vary much through the wall. When it
does, **Lamé** gives it properly - and the tab gives both answers and the
gap between them, because the interesting question is not what the thick
answer is but at what thickness the thin one stops being good enough. A wall
a third of the mean radius understates the hoop stress at the bore by 4%.

The radial stress is not zero either: it is minus the pressure at the bore.
On a thick vessel that is a large fraction of the hoop stress, so the
equivalent stresses are worked out from all three principal stresses rather
than from a plane state.

## Truss

Member forces in a pin-jointed frame. A truss is a drawing, and no
arrangement of boxes lets you describe an arbitrary one, so it is written
down as text - one line per thing:

    node 0 0 pin
    node 4000 0 roller
    node 2000 3000
    member 1 3
    load 3 0 -10000

Joints are numbered from one in the order they are written. There is a
button that puts a Warren girder in the box, since a blank one is a hard
place to start.

Solved as one system of 2n equations rather than joint by joint, so there is
no order to find and nothing to get stuck on. **Tension is positive**
throughout.

The count comes before the answer and is more use than any number: too few
members and the frame is a mechanism that will fold; too many and it cannot
be settled by statics at all, because it is then held by how much each bar
stretches. Both are refused by name.

**Zero-force members are found rather than spotted** - the other classic
question, and the other thing people miss. They are not useless: they hold
the rest straight and take load the moment the loading changes.

In the drawing, red pulls and blue pushes and the thickness is how hard, so
the way the frame carries its load is visible before any of the numbers are
read.

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

## Material chart

Two properties on logarithmic axes, every material drawn as the range it
actually covers, coloured by family - and a performance index laid across it
as a straight edge, with everything above the edge better.

The method is Ashby's. The data is not: it is assembled here from material
standards and manufacturers' figures, nothing is taken from a commercial
materials database, and every row says where it came from.

### Two levels, because two questions get asked

A **class** - "carbon steel", "aluminium alloy" - carries wide ranges,
because the class is that wide. Steel yields anywhere from 250 to
1500 N/mm² depending entirely on what was done to it. Those ranges are what
the chart is drawn from, and there the width is the information rather than
a compromise: a chart spanning five orders of magnitude is not troubled by a
factor of two, and a long box tells you the grade has to be pinned down
before the number is used.

A **grade** - S275, 6082-T6, 316L - carries tight values with the condition
they apply at, and is what gets pulled into a calculation. Only grades are
offered to the Beam and Column tabs, because a class is a range and handing
over the middle of 250 to 1500 would look like an answer.

### Two kinds of property

    structure-insensitive   density, modulus, specific heat, expansion,
                            melting point - set by bonding and crystal
                            structure, so a plain carbon steel is
                            205-215 GPa whatever was done to it
    structure-sensitive     yield, tensile strength, hardness, toughness -
                            set by microstructure, which is what processing
                            exists to change

The first are quoted as values and the second as ranges. Quoting the second
as values would be fiction, and there is a test asserting the data actually
behaves this way.

### How the data checks itself

A yield strength is not derivable from anything, so this cannot be checked
the way the section table can. But several relations have to hold, and each
catches a transcription error in two or three properties at once:

- **G = E/2(1+ν)** - which is a formula in the library, so the data is
  checked against this program's own algebra. It holds to within 3% on every
  row that records all three, and under 1.5% on most.
- Yield below tensile strength.
- Service temperature below melting point.
- Volumetric heat capacity ρc between 1 and 4.5 MJ/m³K, and thermal
  diffusivity k/ρc between 1e-8 and 3e-4 m²/s - the bands every solid falls
  in, which catches a density and a specific heat that disagree.

Porous families are exempt from the ρc band, and the reason is written down
rather than the tolerance widened until nothing fails. Softwood is about a
third cellulose and two thirds air and lands at 0.82 - a third of the way
into the band rather than outside it. Widening the band would have removed
the check.

Thirty-six materials, zero failures.

### Performance indices

An index comes out of the mechanics, not out of the chart. The lightest beam
of a given stiffness: stiffness goes as `Et³` and mass as `ρt`, so
eliminating the thickness leaves mass proportional to `ρ/E^½` - and the
material to pick is whichever maximises `E^½/ρ`. On log axes that is
constant along a line of **slope 2**, so the whole selection is one straight
edge on one chart.

| for | maximise | slope |
| --- | --- | --- |
| light stiff tie | E/ρ | 1 |
| light stiff beam | E^½/ρ | 2 |
| light stiff panel | E^⅓/ρ | 3 |
| light strong beam | σy^⅔/ρ | 3/2 |
| springs | σy²/E | ½ |
| damage tolerance | K_IC/σy | 1 |

The slope is nothing more than the ratio of the two exponents, and there is
a test that derives it that way rather than writing it down.

It gives the answers these charts are famous for: **wood and carbon fibre
beat steel for a light stiff beam** - which is why aircraft spars were made
of spruce - and magnesium tops a light strong beam.

### What it is not

Indicative data for choosing between materials and for teaching the method.
For anything that matters, the certificate for the actual batch is the
authority and this is not.

Fracture toughness is on the chart at class level, where the spread is the
message. It is deliberately not offered as a single grade value, because
K_IC without a temperature and a thickness is close to meaningless and is
the one entry that would read authoritative and not be.

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
