"""
Add periodic logging to a controller.
"""

import logging


# Module logger
logger = logging.getLogger(__name__)


def add_monitor(controller, timeout):
    "Add a monitoring logger"

    def monitor():
        "Report progress of the optimization, roughly once a second."
        record = controller.best_point()
        if record:
            logger.info("Best point {0:.3e} @ {1}".format(
                record.value, record.params))
        else:
            logger.info("No points yet")
        controller.add_timer(timeout, monitor)

    controller.add_timer(timeout, monitor)
