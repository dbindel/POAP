"""
Test thread strategy.
"""

import math
from poap.strategy import ThreadStrategy
from poap.controller import SerialController

def golden_section(f, a, b, maxiter):
    "Golden section search routine."
    tau = (math.sqrt(5)-1)/2
    x1 = a + (1-tau)*(b-a)
    x2 = a + tau*(b-a)
    f1 = f(x1)
    f2 = f(x2)
    for i in range(maxiter):
        if f1 > f2:
            a = x1
            x1 = x2
            f1 = f2
            x2 = a + tau*(b-a)
            f2 = f(x2)
        else:
            b = x2
            x2 = x1
            f2 = f1
            x1 = a + (1-tau)*(b-a)
            f1 = f(x1)

def main():
    "Testing routine."
    x0 = 0.1234
    strategy = ThreadStrategy(lambda f: golden_section(f, 0.0, 1.0, 20))
    controller = SerialController(strategy, lambda x: (x-x0)*(x-x0))
    result = controller.run()
    print(result.value, result.params)

if __name__ == '__main__':
    main()
