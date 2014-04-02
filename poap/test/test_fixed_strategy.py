"""
Test fixed sampling strategy.
"""

import math
from poap.strategy import FixedSampleStrategy
from poap.controller import SerialController

def main():
    "Testing routine."
    x0 = 0.1234
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    strategy = FixedSampleStrategy(samples)
    controller = SerialController(strategy, lambda x: (x-x0)*(x-x0))
    result = controller.run()
    print(result.value, result.params)

if __name__ == '__main__':
    main()
