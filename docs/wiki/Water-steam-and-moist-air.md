# Fluid properties

Water and steam, moist air, and four refrigerants.

**Fluid properties**, in the top row of tabs.

Everything here is computed from the international standards rather than
looked up in a table. There is no row to interpolate between and no edge to
read off, and there are no hand-typed numbers to get a digit wrong in. How
much to trust that is covered in
[How the answers are checked](How-the-answers-are-checked).

## Water and steam

Three ways of asking, because those are the three ways a question is put:

* **On the boil** - give a temperature or a pressure, and get the saturated
  liquid and the saturated vapour side by side.
* **Wet steam** - the same, plus a dryness fraction, and it works out the
  mixture. `h = hf + x·hfg`, done once and correctly.
* **At a pressure and a temperature** - which fixes the state outright,
  anywhere in the compressed liquid or superheated regions.

Temperature and pressure are not independent on the saturation line, so the
first two modes ask for one of them. A form that took both would be lying
about that.

`h_fg` is shown beside the saturated pair. It is what most questions are
after and it is the one number a printed table makes you work out yourself.

The chart is beside the numbers, and you can switch it between T-s, P-v, P-h
and T-v. The dome is not a stored outline - it is the saturation line
computed from the same equations the table uses, so the point on the chart
and the figure beside it cannot disagree.

## Moist air

The dry bulb never fixes the state on its own, so give it one measure of the
moisture as well - relative humidity, humidity ratio, wet bulb or dew point,
whichever you have. Everything else follows.

It will not take two. Any two would have to agree with each other, and a
chart is easier to read than an argument about which one was right.

The pressure is a field because it matters: thinner air holds more vapour
per kilogram of dry air at the same relative humidity, which is why a
psychrometric chart is drawn for an altitude.

Below freezing the vapour deposits as frost rather than condensing. That is
the sublimation curve, which this does not have, so the dew point and wet
bulb are left out with the reason on screen. Everything that does not depend
on that curve - humidity ratio, enthalpy, volume, relative humidity - is
still exactly right.

## The symbols

Each property is shown with the letter it goes by, because that is the one
that turns up in the equation you are about to put the number into. `h` in
the steady flow energy equation, `s` across an isentropic process, `W` on a
psychrometric chart.

# Refrigerants

R134a, ammonia, propane and carbon dioxide, under **Properties**, beside
water and moist air. Pick one at the top of the tab and everything below it
follows.

Each comes from its own published reference equation of state - Tillner-Roth
and Baehr for R134a, Gao and others for ammonia, Lemmon and others for
propane, Span and Wagner for CO2 - rather than from a table of one and a
correlation for the rest.

Three ways of asking, the same three as steam: on the saturation line, inside
the dome at a known dryness, or at a pressure and a temperature that fix the
state outright. Beside the numbers is a pressure-enthalpy diagram with a
logarithmic pressure axis - the one a refrigeration cycle is drawn on,
because on it the throttle is a vertical line and the two heat exchangers
are horizontal ones, so the shape of the cycle is the shape of the drawing.

## Where the R134a numbers come from

Tillner-Roth and Baehr's international standard formulation: a Helmholtz
free energy in reduced density and reduced temperature, from which every
other property follows by differentiating it. Pressure, enthalpy, entropy
and both specific heats are one function differentiated in different
directions, so they cannot disagree with each other. Nothing is
interpolated and there is no table to read between.

The saturation line is not an ancillary curve either. At each temperature
the two densities are found where the pressures match and the Gibbs energies
match, which is what actually defines saturation - so the liquid and the
vapour come out of the same equation as everything else.

Valid from 170 K to 455 K and up to 70 MPa. Outside that it says so rather
than extrapolating, and within about a twentieth of a kelvin of the critical
point it says so too, because there the two phases have become the same
thing and there is nothing to find.

## The reference state

Refrigerant tables measure enthalpy and entropy from saturated liquid at
0 C, called 200 kJ/kg and 1 kJ/kg K. The ideal-gas part of the equation
carries two arbitrary constants which fix nothing else, and rather than
copying them from somewhere they are **solved for** from that condition.
They separate cleanly - entropy carries one and enthalpy the other - so it
is two one-line solves, and the reference state becomes something this
guarantees rather than something it hopes was typed in correctly.

## How R134a was checked

This one is worth reading even if the fluid is not the one you want,
because of how the first attempt at it failed.

An earlier attempt at R134a was written and thrown away rather than shipped.
It used a correlation reconstructed from memory, agreed with the saturation
line to a fiftieth of a percent, and had the saturated vapour density wrong
by a factor of fifty - giving a latent heat of 9726 kJ/kg where the answer
is 199. It passed every check anybody would think to write first.

So this one is checked against things that failure would not have survived:

- the saturation pressure against the ancillary curve published with the
  equation, at thirteen temperatures from -40 C to 100 C, agreeing to
  **0.003%**
- the saturated densities at 0 C, 1294.8 and 14.428 kg/m3, to **0.002%**
- the latent heat at 0 C: **198.60 kJ/kg** against a table value of 198.6
- the normal boiling point: **-26.074 C** at one atmosphere against -26.07
- the critical pressure out of the critical point, to 0.004%
- the reference state, which is exact by construction
- the analytic density derivative against a numerical one, since the
  pressure is that derivative and nothing else

One thing worth recording, because it cost an afternoon. Taken from a
secondary source the reducing density is quoted as 507.6 kg/m3; the standard
gives it as 4978.830171 mol/m3, which is 508.0. That twelfth of a percent
came out as a twelfth of a percent in every saturation pressure the equation
produced - dead flat across ninety kelvin, which is what made it look like a
constant of nature rather than a mistake.

## Three refrigerants, three published equations

R134a, ammonia (R717) and propane (R290). Each from its own reference
formulation, and not one of them from a correlation fitted to the others:

| | | |
| --- | --- | --- |
| R134a | Tillner-Roth and Baehr, 1994 | the halocarbon that replaced R12 |
| Ammonia | Gao and others, 2023 | the industrial one, and the oldest |
| Propane | Lemmon, McLinden and Wagner, 2009 | R290, a hydrocarbon |

### Why three equations rather than one with three sets of numbers

Because they are not the same shape. Every one of these is the Helmholtz
free energy in reduced density and reduced temperature, split into an
ideal-gas part and a residual part, and every property falls out of its
derivatives - so the *solving* is shared, and there is one copy of the
Maxwell construction, one safeguarded Newton, one reference-state solve.

But the residual part is a sum of terms, and the terms come in shapes:

    n delta^d tau^t                      the plain ones
      ... times exp(-delta^c)            the exponential ones
      ... times exp(-eta(delta-eps)^2
                   -beta(tau-gamma)^2)   the Gaussian bell
      ... times exp(+eta(delta-eps)^2
                   + 1/(b+beta(tau-gamma)^2))   the associating term

R134a's equation, from 1994, uses only the first two. Propane's, from 2009,
adds the Gaussian bell that the newer formulations use to shape the
critical region. Ammonia's, from 2023, needed the fourth: its molecules
hydrogen bond, and an associating term is what that takes. Note the signs
in the last one - eta enters with a plus and is published negative, and the
temperature part is a reciprocal rather than a Gaussian. Getting that wrong
leaves the pressure looking plausible and the heat capacities nonsense.

A fluid whose published equation needs a shape not on that list has to have
it added rather than approximated by one of these.

### How they are checked

Each formulation is published with an **ancillary equation** - a fitted
curve giving the saturation pressure directly. Nothing here uses one. The
saturation line is found from the equation itself by the condition that
defines it: the two phases at one pressure with the same Gibbs energy.

That is much slower than evaluating a curve, and it is the whole point:
the ancillary becomes something to check the answer against rather than
something that produced it.

    R134a       0.009%   against a curve quoted good to 0.009%
    Propane     0.016%   against one quoted good to 0.016%
    Ammonia     0.047%   against one quoted good to 0.052%

Every one of them is inside the accuracy the published curve is itself
quoted to, which is as close as this comparison can mean anything.

Three more checks that do not depend on the ancillary at all:

- **The boiling points.** -26.074, -33.316 and -42.114 C against measured
  values of -26.07, -33.327 and -42.114. These are laboratory numbers, not
  outputs of any of these equations.
- **The critical pressure.** Nothing sets it. Evaluate the equation at the
  critical temperature and density and the published pressure comes back,
  within a thousandth of a percent.
- **The derivatives**, against numerical differentiation, at twenty
  combinations of density and temperature for each fluid. This is what
  catches a sign in one of the term shapes.

### Comparing them

All three are measured from the same reference state - saturated liquid at
0 C with h = 200 kJ/kg and s = 1 kJ/(kg K) - so the numbers can be put side
by side. A table printed from somewhere else has every enthalpy shifted by
a constant and every difference identical, and the differences are what get
used.

Run the same machine on all three, between -10 and 40 C with 5 K of
superheat, 3 K of subcooling and a compressor at 70%:

    R134a       COP 2.92    145 kJ/kg    discharge  65 C
    Ammonia     COP 3.00   1087 kJ/kg    discharge 162 C
    Propane     COP 2.88    273 kJ/kg    discharge  64 C

**The COP barely moves.** That is the thing worth taking away: how well a
refrigeration machine performs between two temperatures is set by those two
temperatures and hardly at all by what is inside it. All three land near
55% of the Carnot value for that gap.

What the choice actually decides is everything else. Ammonia carries seven
times the heat per kilogram, so it moves a seventh of the mass for the same
duty and the pipework and the swept volume come down with it - which is why
a cold store the size of a warehouse runs on it. And it leaves the
compressor at 162 C instead of 65, which is why that plant needs
desuperheating and oil cooling that a halocarbon plant does not. The same
trade, read from both ends.

Propane sits between them, with a global warming potential of about three
against R134a's fourteen hundred, and is flammable - which is why the
charge in a system using it is limited rather than why it is not used.

### What is not here

**Carbon dioxide (R744).** Its equation needs a fifth term shape - the
non-analytic terms of Span and Wagner - and a CO2 machine usually runs
transcritical, where there is no condensation at all and the high side is
above the critical point. That is a different cycle as well as a different
fluid, so it is not a matter of adding a table of numbers.

**Blends.** R410A, R404A and the rest are mixtures, and a mixture boils
across a range of temperature rather than at one. Everything on these pages
assumes a pure fluid with one saturation temperature per pressure, and a
blend would need that assumption taken out rather than worked around.

# The refrigeration cycle

Under **Properties**, beside the refrigerants, and it runs on any of the
three. Give it two temperatures and it works out
the four states the refrigerant goes round, draws them on the
pressure-enthalpy chart, and tells you what they come to.

The four corners:

1. **into the compressor** - out of the evaporator, dry saturated or
   superheated by however much you say
2. **into the condenser** - out of the compressor, at the condensing pressure
3. **into the throttle** - out of the condenser, saturated liquid or
   subcooled
4. **into the evaporator** - out of the throttle, part flashed to gas

Two of those four are not on the saturation line, and that is the part worth
having done for you. The compressor exit is found at a pressure and an
entropy, the throttle exit at a pressure and an enthalpy, and reading either
off a table means interpolating twice. Reading the four states is where the
errors in this calculation come from - not the arithmetic afterwards.

## What you give it

- The **evaporating and condensing temperatures**, which fix both pressures
- **Superheat** at the compressor inlet and **subcooling** at the condenser
  outlet, both in kelvin
- The compressor's **isentropic efficiency** as a percentage
- A **duty** in kilowatts, if you want the machine sized rather than the
  answers per kilogram - and whether that duty is the cooling wanted in or
  the heat wanted out, because a heat pump is bought for the other end of
  itself

## What comes out

Refrigerating effect, compressor work and heat rejected, per kilogram. Both
coefficients of performance. The Carnot coefficient between the same two
temperatures and what fraction of it this cycle reaches - which is the
number that says whether a disappointing COP is the machine's fault or the
temperatures'.

Then the pressure ratio, the discharge temperature and the dryness after the
throttle. With a duty: mass flow, volume flow into the compressor,
compressor power and condenser duty.

## The two checks

The heat rejected has to equal the heat taken in plus the work put in,
because energy does not go anywhere else. And the heating coefficient of
performance has to be exactly one more than the cooling one, for the same
reason.

Neither is imposed. Both are worked out from the four states independently
and compared, so if the states are wrong the sums say so rather than
agreeing with each other by construction.

It also says when the answer is right but the machine is odd: a discharge
temperature high enough to break down compressor oil, a pressure ratio past
what one stage of compression normally does, or a compressor being fed
saturated vapour - which is the textbook cycle and not what anybody builds.
