=============================================================
POAP: Plumbing for Optimization with Asynchronous Parallelism
=============================================================

POAP provides an event-driven framework for building and
combining asynchronous optimization strategies.  A typical
optimization code written with POAP might look like:

.. code-block:: python

    from poap.strategy import FixedSampleStrategy
    from poap.strategy import CheckWorkStrategy
    from poap.controller import ThreadController
    from poap.controller import BasicWorkerThread

    # samples = list of sample points ...

    controller = ThreadController()
    sampler = FixedSampleStrategy(samples)
    controller.strategy = CheckWorkerStrategy(controller, sampler)

    for i in range(NUM_WORKERS):
        t = BasicWorkerThread(controller, objective)
        controller.launch_worker(t)

    result = controller.run()
    print 'Best result: {0} at {1}.format(result.value, result.params)

The basic ingredients are a controller capable of asking workers to
run function evaluations and a strategy for choosing where to sample.
The strategies send the controller proposed actions, which the
controller then accepts or rejects; the controller, in turn, informs
the strategies of relevant events through callback functions.

Most users will probably want to provide their own strategies,
controllers, or both.
