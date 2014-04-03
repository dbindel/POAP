"""
Test combined sampling strategy with max eval termination strategy.
"""

import math
import random
from poap.strategy import FixedSampleStrategy
from poap.strategy import MaxEvalStrategy
from poap.strategy import SimpleMergedStrategy
from poap.controller import SerialController

def random_generator():
    while True:
        yield random.random()

def main():
    "Testing routine."
    x0 = 0.1234
    controller = SerialController(None, lambda x: (x-x0)*(x-x0))
    strategies = [MaxEvalStrategy(controller, 100),
                  FixedSampleStrategy(random_generator())]
    controller.strategy = SimpleMergedStrategy(controller, strategies)
    result = controller.run()
    print(result.value, result.params)

if __name__ == '__main__':
    main()
