import sys
import time
import logging
import threading

from poap.strategy import FixedSampleStrategy
from poap.tcpserve import ThreadedTCPServer
from poap.tcpserve import SimpleSocketWorker


# Set up default host, port, and time
PORT=9000
TIMEOUT=0


def f(x):
    logging.info("Request for {0}".format(x))
    if TIMEOUT > 0:
        time.sleep(TIMEOUT)
    logging.info("OK, done")
    return (x-1.23)*(x-1.23)


def controller_main():
    logging.info("Launching controller")
    strategy = FixedSampleStrategy([1, 2, 3, 4, 5])
    result = ThreadedTCPServer(port=PORT, strategy=strategy).run()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))


def worker_main():
    logging.info("Launching worker")
    SimpleSocketWorker(f, port=PORT, retries=1).run()


def main():
    logging.basicConfig(format="%(name)-18s: %(levelname)-8s %(message)s",
                        level=logging.INFO)

    # Launch controller
    cthread = threading.Thread(target=controller_main)
    cthread.start()

    # Launch workers
    wthreads = []
    for k in range(2):
        wthread = threading.Thread(target=worker_main)
        wthread.start()
        wthreads.append(wthread)

    # Wait on controller and workers
    cthread.join()
    for t in wthreads:
        t.join()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        PORT=int(sys.argv[1])
    if len(sys.argv) > 2:
        TIMEOUT=float(sys.argv[2])
    main()
