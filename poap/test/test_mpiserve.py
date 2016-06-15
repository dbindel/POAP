import sys
import time
import logging
import threading

from mpi4py import MPI
from poap.strategy import FixedSampleStrategy
from poap.mpiserve import MPIMasterHub
from poap.mpiserve import MPISimpleWorker


# Set up default host, port, and time
TIMEOUT=0


def f(x):
    logging.info("Request for {0}".format(x))
    if TIMEOUT > 0:
        time.sleep(TIMEOUT)
    logging.info("OK, done")
    return (x-1.23)*(x-1.23)


def worker_main():
    MPISimpleWorker(f).run()


def main():
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)
    strategy = FixedSampleStrategy([1, 2, 3, 4, 5])
    server = MPIMasterHub(strategy=strategy)
    result = server.optimize()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    if len(sys.argv) > 1:
        TIMEOUT=float(sys.argv[1])
    if rank == 0:
        main()
    else:
        worker_main()
