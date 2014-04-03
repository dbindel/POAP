"""
Test fixed sampling strategy.
"""

import random
import threading
import Queue
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.controller import SimThreadController
from poap.controller import BasicWorkerThread

def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = SimThreadController()
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

    def objective(x):
        "Objective function -- run for about five seconds before returning."
        controller.worker_wait(5 + random.random())
        return (x-0.123)*(x-0.123)

    for _ in range(5):
        t = BasicWorkerThread(controller, objective)
        controller.add_worker(t)
        t.setDaemon(True)
        t.start()

    controller.add_timer(1, monitor)
    result = controller.run()
    print('Final', result.value, result.params)

if __name__ == '__main__':
    main()
