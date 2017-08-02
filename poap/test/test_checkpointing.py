"""
Test fixed sampling strategy.
"""

from poap.strategy import FixedSampleStrategy
from poap.controller import SerialController
import multiprocessing
import time
import os


def fun(x):
    time.sleep(1)
    print(x)
    return (x - 0.32) * (x - 0.32)


def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = SerialController(fun)
    controller.strategy = FixedSampleStrategy(samples)

    # Remove old checkpoints before we start
    if os.path.isfile(controller.checkpoint_name):
        os.remove(controller.checkpoint_name)

    # Start foo as a process
    p = multiprocessing.Process(target=controller.run, args=(None, None, True, True))
    p.start()

    # Wait 3 seconds before killing the thread
    time.sleep(3)
    p.terminate()
    p.join()

    print("Whooops, controller crashed. Resuming...")

    result = controller.resume()
    print("Final: {0:.3e} @ {1}".format(result.value, result.params))

if __name__ == '__main__':
    main()
