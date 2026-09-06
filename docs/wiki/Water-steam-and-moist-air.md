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
