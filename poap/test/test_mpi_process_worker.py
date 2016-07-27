"""
Test shell-out to another process.
"""

import subprocess
import logging
import time

from mpi4py import MPI
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import AddArgStrategy
from poap.strategy import ChaosMonkeyStrategy
from poap.mpiserve import MPIController
from poap.mpiserve import MPIProcessWorker


class DummySim(MPIProcessWorker):
    "Dummy simulation class."

    def eval(self, record_id, params, extra_args=None):
        """Handle dummy simulation function evaluation.

        Args:
            record_id: Identifier for feval record_id
            params: Parameters to function
            extra_args: Used to pass the name of the simulator
        """
        try:
            logging.debug("In eval")
            args = [extra_args, str(*params)]
            t0 = time.clock()
            self.process = subprocess.Popen(args, stdout=subprocess.PIPE)
            data = self.process.communicate()[0]
            self.update(record_id, time=time.clock()-t0)
            self.finish_success(record_id, float(data))
            logging.info("Success: %s", params)
        except ValueError:
            logging.debug("Caught ValueError")
            self.update(record_id, time=time.clock()-t0)
            if self._eval_killed:
                self.finish_killed(record_id)
                logging.info("Killed: %s", params)
            else:
                self.finish_cancel(record_id)
                logging.info("Failure: %s", params)


def worker_main():
    "Worker main routine (run DummySim)."
    logging.basicConfig(filename='test_mpi_pw.log-{0}'.format(rank),
                        format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.DEBUG)
    DummySim().run()


def main():
    "Testing routine."
    # Log at DEBUG level to file, higher level to console
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        filename='test_mpi_pw.log-{0}'.format(rank),
                        level=logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    ch.setFormatter(formatter)
    logging.getLogger('').addHandler(ch)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = MPIController()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(controller, strategy)
    strategy = AddArgStrategy(strategy, extra_args='./dummy_sim')
    strategy = ChaosMonkeyStrategy(controller, strategy, mtbf=3)
    controller.strategy = strategy
    result = controller.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    if rank == 0:
        main()
    else:
        worker_main()
