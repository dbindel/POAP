"""
.. module:: mpiserve
   :synopsis: MPI-based controller server and workers for POAP.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

# NB: Must do mpirun with a working mpi4py install.
#     See https://groups.google.com/forum/#!topic/mpi4py/ULMq-bC1oQA

try:
    import Queue
except ImportError:
    import queue as Queue

from mpi4py import MPI
import threading
import time
import logging

from poap.controller import Controller

# Get module-level logger
logger = logging.getLogger(__name__)

# Get MPI communicator and rank
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
nproc = comm.Get_size()


class MPIController(Controller):
    """MPI controller.

    The MPI controller *must* run at rank 0.

    The server sends messages of the form
        ('eval', record_id, args, extra_args)
        ('eval', record_id, args)
        ('kill', record_id)
        ('terminate')
    The default messages received are
        ('update_dict', record_id, dict)
        ('running', record_id)
        ('kill', record_id)
        ('cancel', record_id)
        ('complete', record_id, value)
    """

    def __init__(self, strategy=None):
        "Initialize the controller."
        Controller.__init__(self)
        self._workers = [w for w in range(1,nproc)]
        self._recids = {}
        self.strategy = strategy
        self.add_term_callback(self._send_shutdown)

    def can_work(self):
        "Return whether we can currently perform work."
        return len(self._workers) > 0

    def _handle_message(self):
        """Handle received messages.

        Receive record update messages of the form
            ('action', record_id, params)
        where 'action' is the name of an EvalRecord method and params is
        the list of parameters.  The record_id should be recorded in the
        hub's records table (which happens whenever it is referenced in
        a message sent to a worker).

        On a message indicating that the worker is done with the record,
        we add the worker that sent the message back to the free pool.
        """
        logger.debug("Handle incoming message")
        s = MPI.Status()
        data = comm.recv(status=s)
        mname = data[0]
        record = self._recids[data[1]]
        method = getattr(record, mname)
        method(*data[2:])
        if mname == 'complete' or mname == 'cancel' or mname == 'kill':
            logger.debug("Re-queueing worker")
            self._workers.append(s.source)

    def _submit_work(self, proposal):
        "Create new record and send to worker"
        worker = self._workers.pop()
        record = self.new_feval(proposal.args)
        record.worker = worker
        proposal.record = record
        self._recids[id(record)] = record
        proposal.accept()
        logger.debug("Dispatch eval request to {0}".format(worker))
        if record.extra_args is None:
            m = ('eval', id(record), record.params)
        else:
            m = ('eval', id(record), record.params, record.extra_args)
        comm.send(m, dest=worker, tag=0)

    def _kill_work(self, record):
        "Send a kill request to a worker"
        worker = record.worker
        logger.debug("Dispatch kill request to {0}".format(worker))
        comm.send(('kill', id(record)), dest=worker, tag=0)

    def _send_shutdown(self):
        "Send shutdown requests to all workers"
        for worker in range(1,nproc):
            comm.send(('terminate',), dest=worker, tag=0)

    def _run(self, merit=None, filter=filter):
        "Run the optimization and return the best value."
        while True:
            if comm.iprobe():
                self._handle_message()
            proposal = self.strategy.propose_action()
            if not proposal:
                self._handle_message()
            elif proposal.action == 'terminate':
                logger.debug("Accept terminate proposal")
                proposal.accept()
                return self.best_point(merit=merit, filter=filter)
            elif proposal.action == 'eval' and self.can_work():
                logger.debug("Accept eval proposal")
                self._submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done:
                logger.debug("Accept kill proposal")
                record = proposal.args[0]
                proposal.accept()
                self._kill_work(record)
            else:
                logger.debug("Reject proposal")
                proposal.reject()

    def run(self, merit=None, filter=None):
        """Run the optimization and return the best value.

        Args:
            merit: Function to minimize (default is r.value)
            filter: Predicate to use for filtering candidates

        Returns:
            Record minimizing merit() and satisfying filter();
            or None if nothing satisfies the filter
        """
        try:
            return self._run(merit=merit, filter=filter)
        finally:
            self.call_term_callbacks()


class MPIHub(threading.Thread):
    """Queue-based asynchronous communication over MPI.

    The MPIHub object uses non-blocking sends and receives to communicate with
    any other MPI processes.  We handle outgoing messages via a queue, and
    incoming messages via a callback system.  If an MPIHub object is handling
    the MPI communications for a particular rank, there should be *no other*
    MPI send/receive calls outside the MPIHub while the MPIHub thread is
    running.

    Attributes:
        running: set to true if the main event loop should keep running
    """

    def __init__(self):
        super(MPIHub, self).__init__()
        self.queue = Queue.Queue()
        self.running = False

    def send(self, dest, data):
        """Send a message (non-blocking) to another MPI process.

        Args:
            dest: Rank of the receiving process
            data: Data to be sent (must be amenable to pickling)
        """
        logger.debug("{0}: Queueing send".format(rank))
        def msg():
            logger.debug("Execute send {0}->{1}: {2}".format(rank, dest, data))
            comm.send(data, dest=dest, tag=0)
        self.queue.put(msg)

    def shutdown(self):
        """Send a shutdown message to the main routine.

        Note: A shutdown will only be processed *after* all pending
        outgoing messages have been sent.
        """
        def msg():
            self.running = False
        self.queue.put(msg)

    def handler(self, data, status):
        """Handle received messages.

        This function handles incoming messages.  It should be overloaded
        by classes inherited from MPIHub.

        Args:
            data: Data received
            status: MPI status object (the message source is status.source)
        """
        logger.warning("Unhandled from {0}".format(s.source))

    def run(self):
        """Main thread routine.

        The hub object waits until either an action (shutdown or message send)
        is placed in the outgoing queue or an MPI message is received.  All
        received messages are processed by handing them off to the handler.
        """
        self.running = True
        logger.debug("Starting hub main routine")
        while self.running or not self.queue.empty():
            time.sleep(0) # Yields to other threads
            if not self.queue.empty():
                logger.debug("Hub handling outgoing message")
                m = self.queue.get_nowait()
                m()
            elif comm.iprobe():
                logger.debug("Hub handling incoming message")
                s = MPI.Status()
                data = comm.recv(status=s)
                self.handler(data, s)
        logger.debug("Hub shuts down".format(rank))


class MPIWorkerHub(MPIHub):
    """Base class for workers to communicate with a main controller hub.

    The send routine sends a message to the main controller, and
    eval/kill/terminate messages get put on a local queue (msgq)
    for the worker to pick up.

    Attributes:
        msgq: Incoming message queue
    """

    def __init__(self):
        super(MPIWorkerHub, self).__init__()
        self.msgq = Queue.Queue()

    def send(self, *args):
        """Send a message to process 0 (where the controller lives)."""
        MPIHub.send(self, 0, args)

    def update(self, record_id, **kwargs):
        """Update a function evaluation status with a call to update_dict.

        Args:
            record_id: Identifier for the function evaluation
            kwargs: Named argument values
        """
        self.send('update_dict', record_id, kwargs)

    def running(self, record_id):
        """Indicate that a function evaluation is running.

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('running', record_id)

    def finish_success(self, record_id, value):
        """Indicate that a function evaluation completed successfully.

        Args:
            record_id: Identifier for the function evaluation
            value: Value returned by the feval
        """
        self.send('complete', record_id, value)

    def finish_cancel(self, record_id):
        """Indicate that a function evaluation was cancelled (at worker).

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('cancel', record_id)

    def finish_killed(self, record_id):
        """Indicate that a function evaluation was killed (controller request).

        Args:
            record_id: Identifier for the function evaluation
        """
        self.send('kill', record_id)

    def handler(self, data, status):
        """Handle received messages.

        Incoming messages are added to a queue for worker pickup.  The
        status is ignored, as we should just receive messages from process 0.

        Args:
            data: Data received
            status: MPI status object (the message source is status.source)
        """
        logger.debug("Worker hub gets message {0}".format(data))
        self.msgq.put(data)


class MPIWorker(object):
    """Base class for workers using MPI.

    A worker object spins up a hub and processes work request messages until
    it receives a termination request.
    """

    def __init__(self):
        self.running = False
        self.hub = MPIWorkerHub()

    def eval(self, record_id, params, extra_args=None):
        """Evaluate a function at a point.

        Args:
            record_id: Identifier for the function evaluation
            params: Set of parameters
            extra_args: Extra arguments
        """
        pass

    def kill(self, record_id):
        """Kill a running function evaluation.

        Args:
            record_id: Identifier for the function evaluation
        """
        pass

    def terminate(self):
        """Shut down the worker.
        """
        self.running = False

    def run(self):
        """Execute the worker process.

        The worker process does not run in its own thread; it only
        exits once a termination message has been received.
        """
        logger.debug("Enter worker runner")
        self.running = True
        self.hub.start()
        while self.running:
            logger.debug("Worker awaits work")
            data = self.hub.msgq.get()
            logger.debug("Worker got command: {0}".format(data))
            method = getattr(self, data[0])
            method(*data[1:])
        logger.debug("Worker shuts down")
        self.hub.shutdown()
        self.hub.join()


class MPISimpleWorker(MPIWorker):
    """Worker that calls a Python function.

    The MPISimpleWorker does ordinary Python function evaluations.
    Requests to kill a running evaluation are simply ignored.
    """

    def __init__(self, f):
        super(MPISimpleWorker, self).__init__()
        self.f = f

    def eval(self, record_id, params):
        """Evaluate a function at a point.

        Args:
            record_id: Identifier for the function evaluation
            params: Set of parameters
        """
        logger.debug("Eval {0} at {1}".format(record_id, params))
        try:
            value = self.f(*params)
            self.hub.finish_success(record_id, value)
        except:
            logger.warning("Function evaluation failed")
            self.hub.finish_cancelled(record_id)


class MPIProcessWorker(MPIWorker):
    """MPI worker that runs an evaluation in a subprocess

    The MPIProcessWorker is a base class for simulations that run a
    simulation in an external subprocess.  This class provides functionality
    just to allow graceful termination of the external simulations.

    Attributes:
        process: Handle for external subprocess
    """

    def __init__(self):
        super(MPIProcessWorker, self).__init__()

    def kill_process(self):
        "Kill the child process"
        if self.process is not None and self.process.poll() is None:
            logger.debug("MPIProcessWorker is killing subprocess")
            self.process.terminate()

    def kill(self, record_id):
        self.kill_process()

    def terminate(self):
        self.kill_process()
        MPIWorker.terminate(self)
