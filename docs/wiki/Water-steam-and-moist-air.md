# Water, steam and moist air

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

# R134a

The refrigerant every fridge, car and heat pump course is taught on, under
**Properties**, beside water and moist air.

Three ways of asking, the same three as steam: on the saturation line, inside
the dome at a known dryness, or at a pressure and a temperature that fix the
state outright. Beside the numbers is a pressure-enthalpy diagram with a
logarithmic pressure axis - the one a refrigeration cycle is drawn on,
because on it the throttle is a vertical line and the two heat exchangers
are horizontal ones, so the shape of the cycle is the shape of the drawing.

## Where the numbers come from

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

## How it was checked

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
