"""
Test fixed sampling strategy.
"""

from poap.strategy import FixedSampleStrategy
from poap.controller import SerialController

def main():
    "Testing routine."
    samples = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    strategy = FixedSampleStrategy(samples)
    controller = SerialController(strategy, lambda x: (x-0.123)*(x-0.123))
    result = controller.run()
    print(result.value, result.params)

if __name__ == '__main__':
    main()
