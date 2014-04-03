"""
Test fixed sampling strategy.
"""

import time
import random
import threading
import Queue
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.controller import ThreadController
from poap.controller import BasicWorkerThread

def objective(x):
    "Objective function -- run for about five seconds before returning."
    time.sleep(5 + random.random())
    return (x-0.123)*(x-0.123)

def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = ThreadController()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    controller.strategy = strategy
    def monitor():
        record = controller.best_point()
        if record:
            print(record.value, record.params)
        else:
            print('No points yet')
        controller.add_timer(1, monitor)
    for _ in range(5):
        t = BasicWorkerThread(controller, objective)
        controller.add_worker(t)
        t.setDaemon(True)
        t.start()
    controller.add_timer(0, monitor)
    result = controller.run()
    print('Final', result.value, result.params)

if __name__ == '__main__':
    main()
