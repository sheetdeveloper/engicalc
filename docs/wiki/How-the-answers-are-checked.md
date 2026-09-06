# How the answers are checked

A wrong answer that looks wrong is a nuisance. A wrong answer that looks
right gets copied into a report. Most of the work in this project has gone
into the second kind, and this page is what came of it - partly so you can
judge how much to trust it, and partly because the reasoning is worth
having written down somewhere.

## Steam and moist air

The steam tables are computed from IAPWS-IF97, the same formulation used
industrially, rather than transcribed from a book. That removes two whole
classes of error at once: there is no row to interpolate between, and there
are no two hundred hand-typed numbers to put a digit wrong in.

The standard publishes verification values so an implementation can be
checked. **All twenty-four of them match to better than one part in 10^8** -
specific volume, enthalpy, internal energy and entropy, at three states in
each of the two regions covered.

Two further checks do not depend on the coefficients at all, which is what
makes them worth having:

* The saturation equation lands on the **triple point** and the **critical
  point**. Those are defined values, not fitted ones, so hitting them is a
  real test rather than a restatement.
* The internal energy and entropy of saturated liquid at the triple point
  come out as **zero without anything setting them to zero**. That is
  IF-97's own reference state falling out of the equations.

Moist air is built on the same saturation pressure rather than carrying a
correlation of its own, so the two cannot disagree in the fourth figure.

## What it refuses to answer

Regions 3 and 5 of IF-97 - around the critical point, and above 1073 K -
are not implemented. Asking for a state in either **raises an error rather
than returning a number**. A region 3 property computed with region 1's
equations looks entirely plausible and is simply wrong, and a plausible
wrong number is the thing this whole page is about.

The same applies below freezing in moist air. The vapour deposits as frost
rather than condensing, which is a different curve; the dew point and wet
bulb are withheld with the reason on screen, and everything that does not
depend on that curve is still exactly right.

## R134a

It is here now, and the story of getting it here is the best argument on
this page for checking things.

The first attempt used a correlation reconstructed from memory. It agreed
with the published saturation line to a fiftieth of a percent - the one
number anybody looks up - and had the saturated vapour density wrong by a
factor of fifty, giving a latent heat of 9726 kJ/kg where the answer is 199.
It was thrown away rather than shipped.

The version that shipped is Tillner-Roth and Baehr's standard equation of
state, and it is checked against things the first attempt would not have
survived: the published ancillary saturation curve at thirteen temperatures
from -40 C to 100 C (0.003%), the saturated densities at 0 C (0.002%), the
latent heat at 0 C (198.60 against 198.6), the normal boiling point (-26.074
against -26.07), and the analytic density derivative against a numerical
one, since the pressure is that derivative and nothing else.

It also caught a mistake in itself. Every saturation pressure came out
0.080% low, and *flat* across ninety kelvin - which is a scale factor rather
than a coefficient error, and pointed straight at the reducing density. A
secondary source quotes it as 507.6 kg/m3; the standard gives
4978.830171 mol/m3, which is 508.0.

## Rearranging a formula

Solving a formula for one of its variables goes through SymPy, and SymPy
will hand back a closed form that does not solve the equation it came from.
So the answer is put back into the original equation and the two sides have
to agree; when they do not, the closed form is dropped and the formula is
solved by iteration instead.

The check is made against **the values actually given**, not against trial
numbers, and that distinction is the whole of why it works. A rearrangement
can be right for the numbers in front of it and wrong for others. Solving
`x = (-b + sqrt(b^2 - 4ac)) / 2a` for `a` gives an `a` that makes x *a* root
of the quadratic, which is the *plus* root only for some b and c. Judged on
invented numbers it looks broken; judged on a real quadratic it is exactly
right.

864 answers - every formula solved for every variable it contains, with
numbers put in and taken back out - satisfy the equations they came from.

## Sets of equations

Every answer is substituted back into the equations it came from and the
residual reported. A numerical solve that converged on the wrong branch
looks exactly like one that worked until you check.

The residual is judged **relative to the size of the terms**, not against a
fixed tolerance. A Reynolds number comes out around 500,000, and asking that
equation to balance to an absolute 1e-6 is asking for twelve significant
figures - more than double precision carries - so the check would have
called perfectly good answers wrong.

## Trendlines

Six shapes are fitted and ranked, and **R squared is measured on your
readings for every one of them**. This is deliberately not what a
spreadsheet does.

An exponential is fitted by taking logs of y and fitting a line to those,
and Excel reports how well that line fits the logs. That number flatters,
because taking logs squashes the large residuals that matter most, and two
shapes scored that way cannot be compared at all - they are measured against
different things. On noisy exponential data the difference is enough to
change which shape wins, which is the entire point of ranking them.

## The beam diagrams

Both the shear and the moment have to return to zero at the far end of a
beam in equilibrium. They are checked, and if they do not, you are told the
reactions are wrong rather than shown a plausible drawing.

## Things that were caught this way

For flavour, some of the bugs these checks or their equivalents turned up,
all of which produced answers that looked entirely reasonable:

* A fraction placed next to a root compiled to `1/nsqrt(S)`, where `nsqrt`
  reads as one name, and Manning's formula came back as `S*q*r*s*t/n`.
* `Re` parsed as R times Euler's number and `dp` as d times p, so a duct
  calculation had six unknowns where it had five.
* `T2 - T1` did not parse at all - and fixing that alone would have been
  worse, because `T1` would have quietly become T times 1, which is T.
* A solve could hang for ever on its own worked example, because a
  fractional power sent SymPy into a Gröbner basis computation that cannot
  be interrupted.
* A numerical answer carried an imaginary crumb - a pressure drop of
  `738.821919 - 4.9e-18i` went to the answer panel looking like that.
* Air at 0 °C and 60% relative humidity came back with a wet bulb of exactly
  0.000, which reads as saturated air. The search could not go below
  freezing and was returning its own lower bound.

None of these announced themselves. That is the argument for the checking.

- **A closed form that did not solve its own equation.** Compound interest
  rearranged for the number of compounding periods came back as a Lambert W
  expression. A thousand pounds at five percent for ten years compounded
  monthly comes to 1647.01, and asking which frequency does that gave
  1.2 x 10^12 instead of 12.

  What makes this one worth recording is that it survived its own check
  first. Substituting ordinary floating-point numbers and then asking for
  thirty digits recovers nothing - the rounding has already happened - and
  `(1 + 0.05/1.2e12)` has three significant digits left in double precision.
  Raised to the power 1.2e13 that turned a wrong answer of 1648.72 into
  1647.0094976903, which is the right answer to fourteen digits. The numbers
  now go into the check at thirty digits, and it fails as it should.
