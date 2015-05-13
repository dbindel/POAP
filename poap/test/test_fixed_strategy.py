"""
Test fixed sampling strategy.
"""

from poap.strategy import FixedSampleStrategy
from poap.controller import SerialController


def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    controller = SerialController(lambda x: (x-0.123)*(x-0.123))
    controller.strategy = FixedSampleStrategy(samples)
    result = controller.run()
    print(result.value, result.params)

if __name__ == '__main__':
    main()
