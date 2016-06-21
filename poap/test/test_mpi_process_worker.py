"""
Test shell-out to another process.
"""

import subprocess
import logging
import time

from mpi4py import MPI
from poap.strategy import FixedSampleStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import ChaosMonkeyStrategy
from poap.controller import ThreadController
from poap.mpiserve import MPIMasterHub
from poap.mpiserve import MPIProcessWorker
from poap.test.monitor import add_monitor


class DummySim(MPIProcessWorker):

    def eval(self, record_id, params):
        args = ['./dummy_sim', str(*params)]
        t0 = time.clock()
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE)
        data = self.process.communicate()[0]
        try:
            self.hub.update(record_id, time=time.clock()-t0)
            self.hub.finish_success(record_id, float(data))
            logging.info("Success: {0}".format(params))
        except ValueError:
            self.hub.update(record_id, time=time.clock()-t0)
            self.hub.finish_cancelled(record_id)
            logging.info("Failure: {0}".format(params))


def main():
    "Testing routine."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    hub = MPIMasterHub()
    strategy = FixedSampleStrategy(samples)
    strategy = CheckWorkerStrategy(hub.controller, strategy)
    strategy = ChaosMonkeyStrategy(hub.controller, strategy, mtbf=3)
    hub.controller.strategy = strategy
    add_monitor(hub.controller, 1)
    result = hub.optimize()
    print("Final: {0:.3e} @ {1} time {2}".format(result.value, result.params, result.time))


if __name__ == '__main__':
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    if rank == 0:
        main()
    else:
        DummySim().run()
