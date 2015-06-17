"""
Test external input strategy.
"""

import time
import random
import threading
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import InputStrategy
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
    strategy = InputStrategy(controller, strategy)
    controller.strategy = strategy

    def monitor():
        "Report progress of the optimization, roughly once a second."
        record = controller.best_point()
        if record:
            controller.lprint(record.value, record.params)
        else:
            controller.lprint('No points yet')
        controller.add_timer(1, monitor)

    for _ in range(5):
        controller.launch_worker(BasicWorkerThread(controller, objective))

    def shutdown():
        print("Initiating external shutdown")
        strategy.terminate()
    threading.Timer(7, shutdown).start()
    
    controller.add_timer(1, monitor)
    result = controller.run()
    print('Final', result.value, result.params)


if __name__ == '__main__':
    main()
