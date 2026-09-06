# Solving a set of equations

A calculation is rarely a chain that runs one way. Sizing a duct, the
friction factor depends on the Reynolds number, which depends on the
velocity, which depends on the area - and the pressure drop depends on all
three. Working out which to do first, by hand, before you can start, is
where the mistakes come from.

**Calculator -> Simultaneous** takes them in any order.

## Writing them

One equation per bar. It opens with two and there is an **Add equation**
button for more; the text box underneath takes a paste if you already have
them written down somewhere.

A known value is an equation too. There is no separate box for inputs -
`d = 0.15` goes on a line of its own, which is also how it reads.

Lines starting with `#` are notes and are ignored, so a set can carry its
own explanation.

## The count comes before the answer

Under the equations it says how many you have and how many unknowns, and it
updates as you type:

    5 equations, 5 unknowns: A, Re, dp, f, v
    Enough to solve.

or

    4 equations, 5 unknowns: A, Re, d, dp, f, v
    Give 1 more equation, or fix 1 of them to a value.

This is the most useful thing on the screen. Three equations and four
unknowns has no single answer, and being told so while you are still writing
is worth more than any number would be.

## How it solves

Exactly where it can, numerically where it cannot, and it says which.

One case is decided in advance: if an unknown is raised to a fractional
power - `f = 0.3164/Re^0.25` - it goes straight to iteration. Asking for an
exact answer there means a Gröbner basis, which can take unbounded time and
cannot be interrupted once started. That used to hang the app on its own
duct example.

Every answer is substituted back into the original equations and the
residual reported, relative to the size of the terms it came from.

## Studies

The **Study** page solves the whole set once for each value of one name, and
tabulates and plots the results. Pick the name, give it a range and a number
of steps, and press Run.

Two kinds of name can be swept. One the set leaves free - written
`A = pi*d^2/4` with nothing saying what `d` is - and one it fixes with a
plain line like `d = 0.15`. In the second case each value of the sweep goes
in place of that line rather than beside it, so the set stays solvable at
every step instead of over-determined at every step. You get the pressure
drop at every duct size rather than at one of them, without touching the
equations.

A name the equations *work out* is never offered. Fixing a velocity or a
pressure drop is not sweeping an input; it is over-determining the set in a
roundabout way.

Picking a name also fills the range in around whatever it currently is, so
Run does something sensible on the first press. It is a guess - half the
value either side - and it can be typed over.

Each value is solved from the equations as written rather than from the
previous answer. That is slower, and it is right: a set with two solutions
can jump between them as the swept value moves, and carrying the last answer
forward would smooth over exactly that.
