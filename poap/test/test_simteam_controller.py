"""
Test fixed sampling strategy.
"""

import random
import logging
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.controller import SimTeamController
from poap.test.monitor import add_monitor


def objective(x):
    "Objective function"
    return (x-0.123)*(x-0.123)


def delay(record):
    return 5 + 5 * (record.params[0] > 0.25)


def main():
    "Testing routine."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    controller = SimTeamController(objective, delay, 5)
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    controller.strategy = strategy
    add_monitor(controller, 1)
    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
