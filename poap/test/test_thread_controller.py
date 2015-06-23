"""
Test fixed sampling strategy.
"""

import time
import random
import logging
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.controller import ThreadController
from poap.controller import BasicWorkerThread
from poap.test.monitor import add_monitor


def objective(x):
    "Objective function -- run for about five seconds before returning."
    time.sleep(5 + random.random())
    return (x-0.123)*(x-0.123)


def main():
    "Testing routine."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = ThreadController()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    controller.strategy = strategy
    add_monitor(controller, 1)

    for _ in range(5):
        controller.launch_worker(BasicWorkerThread(controller, objective))

    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
