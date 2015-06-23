"""
Test combined sampling strategy with max eval termination strategy.
"""

import random
from poap.strategy import FixedSampleStrategy
from poap.strategy import MaxEvalStrategy
from poap.strategy import SimpleMergedStrategy
from poap.controller import SerialController


def random_generator():
    "Generate a stream of [0,1) uniform random samples."
    while True:
        yield random.random()


def main():
    "Testing routine."
    controller = SerialController(lambda x: (x-0.123)*(x-0.123))
    strategies = [MaxEvalStrategy(controller, 100),
                  FixedSampleStrategy(random_generator())]
    controller.strategy = SimpleMergedStrategy(controller, strategies)
    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
