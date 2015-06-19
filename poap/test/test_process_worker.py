"""
Test shell-out to another process.
"""

import time
import random
import subprocess
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import ChaosMonkeyStrategy
from poap.controller import ThreadController
from poap.controller import ProcessWorkerThread


class DummySim(ProcessWorkerThread):

    def handle_eval(self, record):
        args = ['./dummy_sim', str(*record.params)]
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE)
        data = self.process.communicate()[0]
        try:
            self.finish_success(record, float(data))
            self.lprint("Success: {0}".format(record.params))
        except ValueError:
            self.finish_failure(record)
            self.lprint("Failure: {0}".format(record.params))


def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = ThreadController()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    strategy = ChaosMonkeyStrategy(controller, strategy,
                                   logger=controller.lprint, mtbf=3)
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
        controller.launch_worker(DummySim(controller))

    controller.add_timer(1, monitor)
    result = controller.run()
    print('Final', result.value, result.params)


if __name__ == '__main__':
    main()
