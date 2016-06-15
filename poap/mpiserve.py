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

from poap.controller import ThreadController
from poap.controller import BaseWorkerThread

# Get module-level logger
logger = logging.getLogger(__name__)

# Get MPI communicator and rank
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
nproc = comm.Get_size()


class MPIHub(threading.Thread):
    """Queue-based asynchronous communication over MPI.

    The MPIHub object uses non-blocking sends and receives to communicate with
    any other MPI processes.  We handle outgoing messages via a queue, and
    incoming messages via a callback system.

    Attributes:
        handler: callback with the form handler(data, status)
        running: set to true if the main event loop should keep running
    """

    def __init__(self, handler=None):
        super(MPIHub, self).__init__()
        self.queue = Queue.Queue()
        self.running = False
        self.handler = handler

    def send(self, dest, data):
        logger.debug("{0}: Queueing send".format(rank))
        def msg():
            logger.debug("Execute isend {0}->{1}: {2}".format(rank, dest, data))
            comm.isend(data, dest=dest, tag=0)
        self.queue.put(msg)

    def shutdown(self):
        def msg():
            self.running = False
        self.queue.put(msg)

    def run(self):
        s = MPI.Status()
        req = comm.irecv()
        self.running = True
        logger.debug("Starting hub main routine")
        while self.running or not self.queue.empty():
            time.sleep(0)
            if not self.queue.empty():
                logger.debug("Hub handling outgoing message")
                m = self.queue.get_nowait()
                m()
            elif req.Get_status(status=s):
                logger.debug("Hub handling incoming message")
                data = req.wait(status=s)
                req = comm.irecv()
                if self.handler:
                    self.handler(data, s)
                else:
                    logger.warning("Unhandled from {0}".format(s.source))
        logger.debug("Hub shuts down".format(rank))


class MPIMasterHub(MPIHub):
    """Manage a collection of remote workers connected via MPI.

    The MPIMasterHub is an MPIHub that connects each worker process
    to a local proxy.  The proxies can be used with the thread controller
    in the same way that a local process would.

    The server sends messages of the for
        ('eval', record_id, args)
        ('kill', record_id)
        ('terminate')
    The default messages received are
        ('running', record_id)
        ('kill', record_id)
        ('cancel', record_id)
        ('complete', record_id, value)
    """

    class WorkerProxy(object):
        def __init__(self, rank, hub):
            self.rank = rank
            self.hub = hub
        def eval(self, record):
            self.hub.records[id(record)] = record
            self.hub.send(self.rank, ('eval', id(record), record.params))
        def kill(self, record):
            self.hub.records[id(record)] = record
            self.hub.send(self.rank, ('kill', id(record)))
        def terminate(self):
            self.hub.send(self.rank, ('terminate',))

    def __init__(self, strategy=None, handlers={}):
        """Initialize the hub

        Args:
            strategy: Strategy object to connect to controllers
            handlers: Dictionary of specialized message handlers
        """
        super(MPIMasterHub, self).__init__(handler=self._handle_message)
        self.message_handlers = handlers
        self.controller = ThreadController()
        self.controller.strategy = strategy
        self.controller.add_term_callback(self.shutdown)
        self.records = {}
        self.workers = [None]
        for j in range(1,nproc):
            logger.debug("Add proxy for MPI proc {0}".format(j))
            worker = MPIMasterHub.WorkerProxy(j, self)
            self.workers.append(worker)
            self.controller.add_term_callback(worker.terminate)
            self.controller.add_worker(worker)

    def _handle_message(self, args, s):
        "Receive a record status message"
        logger.debug("Handling message: {0}".format(args))
        mname = args[0]
        record = self.records[args[1]]
        controller = self.controller
        if mname in self.message_handlers:
            handler = self.message_handlers[mname]
            controller.add_message(lambda: handler(record, *args[2:]))
        else:
            method = getattr(record, mname)
            controller.add_message(lambda: method(*args[2:]))
        if mname == 'complete' or mname == 'cancel' or mname == 'kill':
            logger.debug("Re-queueing worker")
            controller.add_worker(self.workers[s.source])


class MPIWorkerHub(MPIHub):
    """Base class for workers to communicate with a main controller hub.

    The send routine sends a message to the main controller, and
    eval/kill/terminate messages get dispatched to the worker.
    """

    def __init__(self, worker):
        super(MPIWorkerHub, self).__init__(handler=self._handle_message)
        self.worker = worker

    def send(self, *args):
        MPIHub.send(self, 0, args)

    def running(self, record_id):
        self.send('running', record_id)

    def finish_success(self, record_id, value):
        self.send('complete', record_id, value)

    def finish_cancel(self, record_id):
        self.send('cancel', record_id)

    def finish_killed(self, record_id):
        self.send('kill', record_id)

    def _handle_message(self, args, s):
        logger.debug("Worker hub gets message {0}".format(args))
        self.worker.msg.put(args)


class MPIWorker(object):

    def __init__(self):
        self.hub = MPIWorkerHub(self)
        self.running = False
        self.msg = Queue.Queue()

    def eval(self, record_id, params):
        pass

    def kill(self, record_id):
        pass

    def terminate(self):
        self.running = False

    def run(self):
        logger.debug("Enter worker runner")
        self.running = True
        self.hub.start()
        while self.running:
            logger.debug("Worker awaits work")
            data = self.msg.get()
            logger.debug("Worker got command: {0}".format(data))
            method = getattr(self, data[0])
            method(*data[1:])
        logger.debug("Worker shuts down")
        self.hub.shutdown()


class MPISimpleWorker(MPIWorker):

    def __init__(self, f):
        super(MPISimpleWorker, self).__init__()
        self.f = f

    def eval(self, record_id, params):
        logger.debug("Eval {0} at {1}".format(record_id, params))
        value = self.f(*params)
        self.hub.finish_success(record_id, value)
