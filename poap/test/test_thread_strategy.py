"""
Test thread strategy.
"""

import math
from poap.strategy import ThreadStrategy
from poap.controller import SerialController


def golden_section(objective, a, b, maxiter):
    """Golden section search routine.

    Arguments:
        objective: Function of one variable to be optimized.
        a: Left endpoint of a bracketing interval
        b: Right endpoint of a bracketing interval
        maxiter: Maximum number of iterations allowed.
    """
    tau = (math.sqrt(5)-1)/2
    x1 = a + (1-tau)*(b-a)
    x2 = a + tau*(b-a)
    f1 = objective(x1)
    f2 = objective(x2)
    for _ in range(maxiter):
        if f1 > f2:
            a = x1
            x1 = x2
            f1 = f2
            x2 = a + tau*(b-a)
            f2 = objective(x2)
        else:
            b = x2
            x2 = x1
            f2 = f1
            x1 = a + (1-tau)*(b-a)
            f1 = objective(x1)


def main():
    "Testing routine."
    controller = SerialController(lambda x: (x-0.123)*(x-0.123), skip=True)
    strategy = ThreadStrategy(controller,
                              lambda f: golden_section(f.blocking_eval,
                                                       0.0, 1.0, 20))
    controller.strategy = strategy
    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
