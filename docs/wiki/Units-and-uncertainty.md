# Units and uncertainty

Two things a number off an instrument carries that a bare number does not:
what it measures, and how well it was measured. Both of them change the
answer, and leaving either at the door is how a calculation goes wrong
without looking wrong.

## Units, carried rather than labelled

A unit used to be a label. The formula library declared one per variable,
the worksheet declared one per row, and a value typed with its own unit was
converted into the declared one. What nothing did was work out what an
*expression* comes out in.

    F = 5000 N
    A = 20 mm^2
    sigma = F/A            ->   250 N/mm^2

Divide the same force by 20 m^2 instead and the answer is 250 N/m^2, which
is 250 000 times smaller. Nothing in a bare 250 says which of those
happened, and mixing millimetres with metres is the commonest real mistake
in engineering arithmetic.

So the unit goes through the arithmetic:

    adding and subtracting   the two have to measure the same kind of
                             thing, and the right one is converted to the
                             left one's unit. 5 m + 3 mm is 5.003 m.
    multiplying, dividing    the units multiply and divide with them, so
                             N over mm^2 comes out N/mm^2 without anybody
                             saying so
    powers                   the exponent has to be a plain number, and
                             the unit goes up with it. The square root of
                             an area is a length.
    functions                sin, log and exp want a plain number. An
                             angle counts, because an angle is one - and
                             so does anything else that measures nothing,
                             however it is written.

### It is kept as it was written

Not reduced to SI. An answer in kg/(m s^2) where N/mm^2 was meant is a
worse answer, and a unit-aware calculator that hands back 250000000 has
taken something away rather than added it.

The price of that is that two names for one thing do not cancel by
themselves. A Reynolds number worked out as rho v d / mu comes out in
kg/(mm s^2 Pa), which is dimensionless and does not look it, because Pa
and kg/(m s^2) are one thing under two names. So the dimension is asked
for at the end, and a unit that cancels is seen to cancel - with the
factor the units were carrying folded into the number, which for
millimetres against metres is a thousand and is exactly the error this
exists to catch.

### What it refuses

    5 m + 3 kg          a length and a mass. There is no answer to give:
                        the expression is wrong, not the numbers
    2 m + 5             a length and a bare number. Assuming the 5 meant
                        millimetres is what goes wrong
    log(2 m)            would depend on whether it was measured in metres
                        or in feet
    x ^ (3 m)           there is no such thing as x to the power of a
                        length

A sum that will not go together says **which two terms**, not only which
two units. On an expression of any length that is the only question worth
answering.

### A unit inside an expression

`T - 5 K`, `2 m + 300 mm`, `9.81 m/s^2`. Each is lifted out and given a
name of its own, so what is left is ordinary algebra.

**A variable always wins over a unit of the same spelling.** Somebody with
a row called `m` for a mass who writes `2*m` means twice their mass, and no
cleverness about it would be an improvement.

### Degrees Celsius

Held as kelvin from the door and shown back in degrees where a row asks for
it. It is an offset rather than a scale, so there is nothing sensible to
multiply or divide it by, and every row below wants the kelvin.

A value typed as `20 degC` is a temperature, not a rise: 293.15 K. A rise
of twenty is written `20 K`, and that ambiguity is why the two are written
differently rather than guessed at.

### It found two bugs in the formula library

Every variable in the library declares a unit and nothing had ever asked
whether the equation they sit in balances - whether the left side measures
what the right side does. Asking, over all 229:

- **Antoine's temperature was declared C.** C is a coulomb. It had been a
  charge in a vapour pressure equation for as long as the entry existed,
  and nothing could see it because a unit was a label.
- **The integral of the error in the PID law was declared dimensionless.**
  Integrating a dimensionless error over time gives it a second, which is
  what makes the integral gain's 1/s cancel so the three terms add up.

Two formulas genuinely do not balance and now say why. Manning's n is
quoted as a bare number and is not one - it carries s/m^(1/3), which is
why the same n gives a different answer in feet. And the 3.45 in tensile
strength from Brinell hardness carries MPa. A formula can record that, and
the test asserts the reason is a reason rather than a label: an exemption
with nothing beside it is where a mistake goes to hide.

## On a worksheet

The worksheet is where both of these earn their keep, because it is where
one number is worked out from another and then from that.

    Name   Is                Unit     Answer
    d      50 +/- 0.5 mm     mm       50 +/- 0.5 mm
    A      pi*d^2/4                   1963.5 +/- 39.27 mm^2
    Q      2 +/- 0.05 L/s    m^3/s    0.002 +/- 5e-05 m^3/s
    v      Q/A                        1.0186 +/- 0.03261 m/s
    rho    998 kg/m^3        kg/m^3   998 kg/m^3
    mu     0.001 Pa*s        Pa*s     0.001 Pa*s
    Re     rho*v*d/mu                 50828 +/- 1369

Three things there are worth pointing at.

**A row that declares no unit is given one.** The area comes out in mm^2
because the diameter was in millimetres, and nothing had to say so. A row
that *does* declare one has to be able to hold what the expression makes:
declare m^2 for that area and it converts, declare mm and it is refused,
because an area is not a length.

**A given typed as a bare number takes the unit its row declares.** That is
what declaring one is for, and it is how nearly every measurement on a
sheet is written.

**The tolerance converts with the value.** `2 +/- 0.05 L/s` in a row
declared m^3/s is `0.002 +/- 5e-05`, and nobody moved a decimal point by
hand.

**Stages get subscripts.** `T[1]`, `T[2]`, `h[3]`. `T1` will not do,
because the parser reads it as T times 1 and quietly works out something
else, and `T_1` works but reads like a filename. `T[1]` and `T_1` are the
*same name*, the way `rho` and its Greek letter are, and the typeset
display draws it as T with a subscript.

**And a row can be a table.** Engineering runs on tabulated data, and the
alternative to putting it on the sheet is fitting a polynomial to it and
then pretending that is the data:

    Name   Is                                                  Unit
    k      table in deg: 15, 0.35; 30, 0.60; 45, 0.95           -
    theta  38                                                   deg
    dp     k(theta)*rho*v^2/2                                   Pa

The argument is an ordinary expression, so `k(theta)` and `k(2*d + 5 mm)`
both mean what they look like, and `table in mm` lets a table tabulated in
millimetres be asked about a length in metres. Between the rows it
interpolates linearly; past the ends it **refuses**, because a straight
line between two measurements is a defensible guess and a reading taken
off the end of a manufacturer's curve is how a number nobody can defend
gets into a calculation.

Under the table the sheet says what the tolerances came to and which
measurement to improve:

    Re = 50828 +/- 1369, which is 2.7%.
    Q accounts for 86% of that - measuring anything else better would buy
    almost nothing.

## Uncertainty

Every number that came off an instrument has a tolerance, and an answer
worked out from three of them has one too. Write it as `5000 +/- 50 N`, or
`5000 +/- 1% N`, or with the sign if that is easier to type.

    F = 5000 +/- 50 N
    A = 20 +/- 0.5 mm^2
    sigma = F/A            ->   250 +/- 6.73 N/mm^2   (2.7%)

The useful part is not the 6.73. It is that **the area contributes 86% of
it**, so measuring the force better would buy almost nothing and measuring
the area better is the whole of what is left. That is the question an
uncertainty calculation is actually asked, and the tab answers it.

### Differentiated, not propagated

The standard method: the uncertainty is the square root of the sum of the
squares of each input's tolerance times how far the answer moves when that
input moves. The derivatives are taken **symbolically, of the whole
expression at once**, rather than by carrying an error term through the
arithmetic operation by operation.

That distinction is the one thing worth getting right. Propagating
operation by operation treats every appearance of a name as a separate
measurement:

    x * x    propagated   root two times the relative error of x
             differentiated   two times it

The second is correct. The same x cannot be high on one side and low on
the other. Differentiating handles it exactly and needs no special case,
because d(x^2)/dx is 2x and nothing had to notice that x appeared twice.

### And down a whole sheet

This is where it matters most, and where it is easiest to get wrong. Take
a pipe:

    d   = 50 +/- 0.5 mm
    A   = pi*d^2/4
    Q   = 2 L/s
    v   = Q/A
    Re  = rho*v*d/mu

The diameter is in the answer **twice**, by two different routes - once
directly and once through the area. Giving each row an uncertainty and
treating it as a fresh measurement for the row below gets that wrong,
because the same diameter cannot be high on one route and low on the
other. Which way it is wrong depends on the signs, so it is not even
conservative.

So each row keeps its expression written out in terms of the **givens** -
the rows that were typed in rather than worked out - and the derivatives
are taken of that. The diameter appears once, as itself, however many
routes it took.

    a 1% diameter  ->  a 2% area, a 2% velocity, and a 1% Reynolds number

One per cent, because Re goes as rho Q d / (mu A) and A goes as d squared,
so Re goes as 1/d. Row by row it would have come out as the root of one
plus four.

**The proof that it works**: writing the same calculation as one line
instead of five gives the identical answer, to every figure. There is a
test that asserts exactly that.

### What it assumes

That the inputs are independent of each other, and that the answer is
close enough to straight over the range of the tolerances for the first
derivative to describe it. Both hold for ordinary engineering arithmetic
with tolerances of a few per cent.

Neither holds for two measurements taken off the same badly calibrated
instrument, and nothing here can tell. Correlation *within a sheet* is
handled exactly, because the sheet knows where each number came from.
Correlation between two things you measured yourself is not, because it
cannot be.

## In the formula library

The same thing, in the tab where most single calculations get done. Every
variable there already declares a unit and a typed value is already
converted into it, so a typed tolerance rides along:

    E  = 210 +/- 5 GPa
    I  = 8503 +/- 20 cm^4
    K  = 1
    L  = 3.5 +/- 0.01 m
    Pcr = pi^2 E I / (K L)^2    ->  14.39 +/- 0.35 MN   (2.5%)

        E   +/- 5e9 Pa      moves it 3.43e5 N   -  94% of the total
        L   +/- 0.01 m      moves it 8.2e4 N    -   5%
        I   +/- 2e-7 m^4    moves it 3.4e4 N    -   1%

The tolerance converts with its value - 5 GPa becomes 5e9 Pa and 20 cm^4
becomes 2e-7 m^4, with nobody moving a decimal point - and the expression
differentiated is the **rearrangement**, which is the one the answer
actually came from.

Because every variable declares a unit, the whole calculation is
dimensionally checked on the way through for nothing extra: each
contribution is a derivative times a tolerance, and if those did not come
to the answer's own unit something would be wrong.

A formula that carries a constant with units hidden in it - Manning's, and
the Brinell rule of thumb - gets no uncertainty rather than a wrong one.
There is no dimensionally consistent derivative to take, and saying nothing
is better than saying something that cannot be right.

### A difference of two close numbers

    a = 100.0 +/- 0.5 mm
    b =  99.0 +/- 0.5 mm
    a - b   ->   1 +/- 0.71 mm   (71%)

Right, and nearly useless, and saying so is the point. Two measurements
good to half a per cent, subtracted, give an answer good to seventy. That
is not a fault in the arithmetic; it is what subtracting close numbers
does, and the only way to fix it is to measure the difference directly.
