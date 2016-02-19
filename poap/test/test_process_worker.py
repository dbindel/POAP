"""
Test shell-out to another process.
"""

import subprocess
import logging
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import ChaosMonkeyStrategy
from poap.controller import ThreadController
from poap.controller import ProcessWorkerThread
from poap.test.monitor import add_monitor


class DummySim(ProcessWorkerThread):

    def handle_eval(self, record):
        args = ['./dummy_sim', str(*record.params)]
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE)
        data = self.process.communicate()[0]
        try:
            self.finish_success(record, float(data))
            logging.info("Success: {0}".format(record.params))
        except ValueError:
            self.finish_cancelled(record)
            logging.info("Failure: {0}".format(record.params))


def main():
    "Testing routine."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = ThreadController()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    strategy = ChaosMonkeyStrategy(controller, strategy, mtbf=3)
    controller.strategy = strategy
    add_monitor(controller, 1)

    for _ in range(5):
        controller.launch_worker(DummySim(controller))

    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    main()
