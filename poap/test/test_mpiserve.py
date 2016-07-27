"""
Test MPI server.
"""

import logging
from mpi4py import MPI
from poap.strategy import FixedSampleStrategy
from poap.mpiserve import MPIController
from poap.mpiserve import MPISimpleWorker


def f(x):
    "Simple objective function."
    logging.info("Handle request for %s", x)
    return (x-1.23)*(x-1.23)


def worker_main():
    "Worker process main."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        filename='test_mpi_serve.log-{0}'.format(rank),
                        level=logging.DEBUG)
    MPISimpleWorker(f).run()


def main():
    "Controller process main."
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        filename='test_mpi_serve.log-{0}'.format(rank),
                        level=logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(name)-12s: %(levelname)-8s %(message)s")
    ch.setFormatter(formatter)
    logging.getLogger('').addHandler(ch)

    strategy = FixedSampleStrategy([1, 2, 3, 4, 5])
    c = MPIController(strategy)
    result = c.run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


if __name__ == '__main__':
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    if rank == 0:
        main()
    else:
        worker_main()
