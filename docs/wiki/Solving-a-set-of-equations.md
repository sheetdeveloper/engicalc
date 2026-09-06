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

Leave the set one equation short and the name nothing pins down becomes an
input. The **Study** page then solves the whole set once for each value of
it, and tabulates and plots the results.

So instead of `A = pi*0.15^2/4`, write `A = pi*d^2/4` and leave `d` free.
The picker offers `d`; give it a range and a number of steps, and you get
the pressure drop at every duct size rather than at one of them.

Each value is solved from the equations as written rather than from the
previous answer. That is slower, and it is right: a set with two solutions
can jump between them as the swept value moves, and carrying the last answer
forward would smooth over exactly that.
