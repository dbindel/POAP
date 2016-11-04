"""
Test external input strategy.
"""

import random
import logging
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import InputStrategy
from poap.controller import SimTeamController
from poap.test.monitor import add_monitor


def objective(x):
    "Objective function"
    return (x-0.123)*(x-0.123)


def delay(record):
    "Run for about five seconds before returning."
    return 5 + random.random()


def main():
    "Testing routine."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = SimTeamController(objective, delay, 5)
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    strategy = InputStrategy(controller, strategy)
    controller.strategy = strategy
    add_monitor(controller, 1)

    def shutdown():
        logging.info("Initiating external shutdown")
        strategy.terminate()
    controller.add_timer(7.0, shutdown)

    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
