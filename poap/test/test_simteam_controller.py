"""
Test fixed sampling strategy.
"""

import random
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.controller import SimTeamController


def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    def objective(x):
        "Objective function"
        return (x-0.123)*(x-0.123)

    def delay():
        "Delay term"
        return 5 + random.random()

    controller = SimTeamController(objective, delay, 5)
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    controller.strategy = strategy

    def monitor():
        "Report progress of the optimization, roughly once a second."
        record = controller.best_point()
        if record:
            print(record.value, record.params)
        else:
            print('No points yet')
        controller.add_timer(1, monitor)

    controller.add_timer(1, monitor)
    result = controller.run()
    print('Final', result.value, result.params)


if __name__ == '__main__':
    main()
