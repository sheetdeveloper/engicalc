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

## Curved beam

A crane hook, a C-clamp, a chain link, the frame of a punch press.

Bend a straight beam and the stress goes linearly across the depth with
nothing at the centroid. Bend a bar that was curved to start with and
neither is true.

The reason is short. When the bar rotates through a small angle, every
fibre changes length by the same amount - but the fibres on the inside of
the curve were shorter to begin with, so the same change is a bigger
strain. Stress follows strain, so the stress is higher on the inside than
the linear answer says and lower on the outside, and it is a hyperbola in
the radius rather than a straight line in the depth.

### Two things follow

**The neutral axis is not at the centroid.** It moves in toward the centre
of curvature, to the radius where the area divided by the radius averages
out. On a rectangle 100 deep at a radius of 150 it moves 5.73 mm, and that
small shift is the whole of the difference.

**The inside stress can be far higher than a straight-beam sum gives.** On
a hook whose radius is about the depth of its own section it is half as
much again - and the inside is the fibre a hook is judged on. Using M y / I
there is not conservative. It is optimistic, which is the wrong direction
to be wrong in.

Both answers are drawn on the same axes, so the gap is visible rather than
described. It closes as the radius grows:

    R / depth      inside      outside
      0.6          2.89 x       0.57 x
      1.0          1.52 x       0.73 x
      2.0          1.20 x       0.85 x
      4.0          1.09 x       0.92 x
      8.0          1.04 x       0.96 x
     50            1.007 x      0.993 x

Past about eight times the depth there is a couple of per cent in it and
the straight-beam formula is what anybody would use. The tab says which
side of that you are on.

### The one integral it needs

Everything above comes out of the area divided by the radius, added up over
the section. That is closed form for the two shapes nearly every section is
built from:

    rectangle    b ln(r_outer / r_inner)
    circle       2 pi (d - sqrt(d^2 - a^2))

and integrated off the shape itself for anything else, split at every level
where the outline turns a corner - because between two corners the width is
a straight line, which eight-point Gauss handles exactly. A hole takes its
own share away, the same way it does everywhere else in the section work.

Checked against a four-hundred-thousand strip integration on a built-up I
section: agreement to thirteen figures.

### How it is checked

Three ways, none of which would survive a sign error.

**The stresses have to carry what was applied.** Integrate them over the
real section and the net force has to be exactly the direct force put in,
and the moment exactly the moment. Neither is set by hand. Both come out
to within a millionth of the scale of what is flowing through the section -
and that residual is the strip integration, not the formula, which is
exact.

**It has to become the straight-beam answer.** Curve a bar to a thousand
times its own depth and it is a straight bar; the two answers agree to a
tenth of a per cent, and to three per cent by eight times the depth.

**The neutral axis always moves toward the centre**, and by less and less
as the bar straightens. Both are asserted rather than assumed.

The moment sign is worth stating: **positive opens the curve**, which is
what a load on a crane hook does, and which puts the inside into tension.

A direct force through the centroid can be given as well as a moment,
because a hook carries both. On its own it spreads evenly over the area,
with no hyperbola in it at all.

## Axial

Bars held at both ends, and what heating them does.

Heat a steel bar lying on a bench and it gets longer and carries no force.
Heat the same bar between two walls and it gets no longer at all and
carries a force that **does not depend on how long it is**. A metre or a
kilometre, the stress is E alpha dT and there is no length in it anywhere,
because the strain that was prevented is the same either way.

Two arrangements, which are the two ways bars get put together.

**In series** - a stepped bar, or several bars end to end, each with its
own size and material, with loads applied where they meet. One redundant if
both ends are held, none if one end is free.

**In parallel** - a bolt through a sleeve, a concrete column with steel in
it, three hangers under one beam. They share the load in proportion to
their stiffnesses and all end the same length, which is the condition that
makes it solvable.

### Three kinds of support, and why it matters

    fixed   attached to it. It can pull as well as push, so the end goes
            nowhere whatever happens.
    free    nothing there. The bar moves as much as it likes and heating
            it puts no force in it at all.
    wall    something it can only push against. It carries nothing until
            the bar has grown far enough to touch, and nothing again if
            the load pulls the bar away from it.

Conflating any two of these gives a wrong answer that looks perfectly
reasonable, which is why they are three settings and not two. A bar left a
millimetre short of a wall carries nothing until it has grown that
millimetre and then behaves as if it were held, so the answer is genuinely
one thing or the other - and which one is not decided by whoever set the
problem. Take a bar with 0.6 mm of free growth in it:

    gap 0.0 mm     -63.0 kN, and the end goes nowhere
    gap 0.3 mm     -31.5 kN, and the end moves exactly 0.3
    gap 0.9 mm       0    , and the end moves its full 0.6

### The one nobody expects

A steel bolt through an aluminium sleeve, both heated 60 K, with no load on
the assembly at all. The aluminium wants to grow twice as much as the steel
and cannot, so the bolt ends up in tension and the sleeve in compression -
and the two add to exactly nothing, which is what "no load on it" means.

No load, and forces in it anyway. That is the whole of why a composite bar
is not a straight-line problem.

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

## Geometry

The other half of geometry from the Section tab. That one answers what a
shape's properties are; this one answers what the shape *is* - the
setting-out question. Three parts of a triangle and the other three follow.
Two facts about an arc and the rest of it follows. Two lines, and where
they cross.

Seven problems: a triangle, an arc, two lines, a line and a circle, two
circles, the tangents from a point, and the circle through three points.

### It says when there are two answers

That is most of what this tab is for. Three of these questions have two
correct answers, and a calculator that returns one of them is not being
concise, it is being wrong.

**Two sides and an angle that is not between them.** Give a = 7, b = 10 and
A = 30 degrees, and side b can swing to meet the far line in two places:
B comes out at 45.58 degrees or at 134.42, and both are triangles with
exactly the parts you gave. The sine of an angle and the sine of its
supplement are the same number, so an arcsine cannot tell them apart, and
returning whichever one it happened to give is the classic wrong answer in
every trigonometry course there is.

Both are drawn, one over the other on the same base, which shows the thing
the numbers do not: the two triangles share side b and angle A, and differ
only in where the swinging side lands.

The ambiguity is not always there, and the tab does not claim it is. Once
the side facing the given angle is the longer of the two, the swing can
only reach once, and one triangle comes back.

**A radius and a chord.** A chord cuts a circle in two, and both pieces are
arcs of that chord. A radius of 100 with a chord of 100 is a 60 degree arc
and it is also a 300 degree arc. Both are returned, drawn on the same
chord - the centre mark ends up below the chord for one and above it for
the other, which is the whole difference between them.

**An arc length with a rise.** This one is not obvious at all, and it took
finding. The ratio of an arc to its rise starts unbounded on a shallow arc,
*falls* to a minimum of 2.7601, and climbs back to pi at a full circle. So
any ratio between those two belongs to two different arcs, and below 2.7601
there is no arc at all.

The turning point is where tan(theta/4) = theta/2, which comes from
differentiating the ratio, and it is solved in the code rather than written
down as 267.1 degrees. A constant with no derivation beside it is a
constant nobody can check.

### And when there are none

    three angles          fix the shape and say nothing about the size,
                          so every triangle with them is a valid answer
                          and none is given
    sides that cannot     the longest as long as the other two together
    close                 will not make a triangle
    a side too short      it never reaches the far line, and the message
                          says how long it would have to be
    an arc shallower      no arc is 2.2 times as long as its rise
    than the turn
    three points in       no circle passes through them, and the
    a line                perpendicular bisectors are parallel

### Touching is one point, not two

Two circles that just touch have one intersection. Floating point will
never land exactly on that case, so it is admitted with a tolerance rather
than pretended away: inside the tolerance the answer is one point, and two
roots that differ in the fifteenth decimal are not reported as two
crossings. The same goes for a line tangent to a circle.

### Small things that keep it honest

Lines are held as `Ax + By = C` rather than `y = mx + c`, because a vertical
line has no gradient and would otherwise be a special case in every
function that touched one.

The area of a triangle comes from two sides and the angle between them,
not from Heron's formula. Heron subtracts the longest side from the
semi-perimeter, and on a sliver - two sides of a million and one across -
those two agree to almost every figure they have, and the answer that comes
out is mostly rounding error.

The rise of an arc is written as `2 sin^2(theta/4)` rather than
`R(1 - cos(theta/2))`. They are the same identity; on a shallow arc the
second subtracts two numbers that agree to fifteen figures and keeps almost
none of them, and at a quarter of a nanoradian it returns exactly zero -
which the solver that divides by it does not survive.

The tangents from a point are found by crossing two circles, because the
touch points and the centre and the point all lie on one circle - a tangent
meets the radius square, so that angle is a right angle in a semicircle. It
needs no arithmetic of its own, which is one fewer place to be wrong.


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

### Fifty-two of them, and how to read that many

A selection chart is only worth drawing if the answer might be somewhere
you did not expect, which means the unexpected has to be on it. So the
materials here run from a flexible foam at 16 kg/m3 to tungsten at 19300,
and from a silicone at a thousandth of a gigapascal to tungsten carbide at
650 - three decades of density and nearly seven of stiffness.

Each one is chosen because it sits somewhere the others do not. Splitting
"copper alloy" into brass and bronze would put two more boxes on top of one
that is already there; adding lead and tungsten puts one at each end of the
density axis.

Wood is on it **both ways round**. Along the grain it is one of the best
things on a light stiff beam chart; across the grain it is a soft polymer.
Both are the same material and the difference is a factor of fifteen in
stiffness, so putting only the first on the chart is putting the half that
flatters it.

That many boxes is more than one screen can name, so the chart has the
controls a crowded one needs:

    family ticks         narrow it to the two families the job is
                         actually choosing between
    label                every one, only the ones above the line, none -
                         or left to decide, which names them all while
                         they can be read and falls back when they cannot
    pick out             one material drawn with a heavy edge, wherever
                         it is
    only what beats      throw away everything below the line and redraw
    the line             on what is left
    family outlines      an envelope round each family

The envelope is a hull round the corners of the boxes rather than a box
round the family. A box round the polymers reaches from silicone to
phenolic and from a thousandth of a gigapascal to five, which covers half
the chart and says nothing; the hull follows the family and leaves the
corners it does not occupy alone. Taken in log space, because the axes are
logarithmic and a hull of the raw numbers would bulge in the wrong places.

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

Sixty-three materials, zero failures - and the check earns its keep. It
caught two of these on the way in: zinc and lead both went down with a
shear modulus that did not agree with the E and the Poisson's ratio beside
it, by nine per cent and fifteen.

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

### Into a calculation

The beam and column tabs take a modulus and a yield stress from a grade,
and so does the formula library: formulas that have somewhere to put a
material grow a **Made of** box, and picking one fills those slots.

The value arrives in whatever unit the formula is written in. The database
quotes a modulus in GPa because that is how a modulus is quoted; the
library writes its formulas in pascals; a slot asking for `g/cm^3` gets
0.905 where the database holds 905. Converting at the point of use rather
than storing a second copy means the two can never drift apart, and there
is a test that every declared slot can actually be converted into - a slot
nobody could convert into would fill with a number a thousand million
times wrong and look perfectly fine.

**Which slots take a material is declared on the formula, not worked out
from the words**, and that is the whole of it. The word "density" appears
twenty-one times in the library and six of those want a solid out of the
database. The rest are air in a duct or water in a pipe. `rho` in the drag
force equation and `rho` in the sheet weight equation have the same symbol,
the same unit and the same description, and only one of them should ever
be offered steel. No amount of reading the description separates them, so
the formula says. Formulas with nothing to fill do not show the box.

A property the chosen material does not record is left alone, and the box
says which one - softwood has a density and no yield strength, so it fills
one field of the specific-strength formula and tells you about the other.
Every filled field stays editable, and says where its number came from.

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
