# Writing equations

## The two ways in

The equation bar is typeset: press the fraction key and you get a real
fraction with two boxes, and Tab moves between them. Underneath it is a
plain text box for anyone who would rather type `2x^2 - 5x - 3 = 0` and be
done with it.

The two are kept in step. Edit either and the other follows, and typed text
becomes real structure - type `sqrt(x)` and a radical appears above with an
editable box under it.

## Syntax

| You write | It means |
|---|---|
| `2x`, `3sin(x)`, `2(x+1)` | the `*` is optional between a number and a symbol |
| `x^2` or `x**2` | a power |
| `sqrt(x)`, `cbrt(x)`, `root(x, 3)` | roots |
| `ln(x)`, `log(x)`, `log10(x)`, `log(x, b)` | logs - `log` is natural |
| `pi`, `e`, `oo` | pi, Euler's number, infinity |
| `abs(x)` or `\|x\|` | absolute value |
| `<=`, `>=`, `!=` | inequalities |
| `;` or a new line | separates equations in a set |

Greek names become letters as you type them: `rho` shows as ρ, `sigma_max`
as σ_max. A difference is written `dT` and shows as ∆T.

## A run of letters is multiplied

`xy` means x times y, not a variable called xy. That is what makes `2x`
work, and it is the right behaviour for free-form algebra, but it catches
people out: **`Re` is R times e**, and `T1` is T times 1, which is T.

If you want a multi-letter name, use a subscript: `R_e`, `T_1`, `c_p`. Those
hold together everywhere, and they draw properly too.

The app tells you when it has done this. Solve something containing `Re` and
a note appears beside the answer saying it was read as a product and
suggesting the subscript spelling.

The Worksheet and the simultaneous solver are different: there the names are
declared, so `Re` and `T1` are single variables. The note only appears where
the splitting actually happens.

## Exact or decimal

`2/3` stays exact and prints as a fraction. `0.667` is a decimal. Mixing
them is fine, and the answer keeps whichever form carries the most
information.

## The pad

The compact row has the keys most often wanted. **Full pad** opens the rest,
grouped, with a topic selector - pick Calculus and the trigonometry and
relations go away, leaving the calculus, the functions and the basics.

The presets are on one pad rather than on separate tabs on purpose: the
solver underneath does not change between algebra and calculus. It is the
same box; what differs is which keys are worth having in front of you.

## Showing the working

**All working**, on the steps panel, expands what is shown. Instead of the
integral of 2x becoming x squared with nothing in between, it names the rule
and states it as notation - constant multiple, then the power rule - and
then applies it.

A transposition goes one move at a time, each step carrying the equation it
leaves behind, and described the way you would say it: *add fifteen to both
sides*, rather than *take away minus fifteen*.
