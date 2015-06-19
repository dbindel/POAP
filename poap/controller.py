"""
.. module:: controller
   :synopsis: Basic controller classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

try:
    import Queue
except ImportError:
    import queue as Queue

import heapq
import threading
from poap.strategy import EvalRecord


class Controller(object):
    """Base class for controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations.
        feval_callbacks: List of callbacks to execute on new eval record
        term_callbacks: List of callbacks to execute on termination
    """

    def __init__(self):
        "Initialize the controller."
        self.strategy = None
        self.fevals = []
        self.feval_callbacks = []
        self.term_callbacks = []

    def add_timer(self, timeout, callback):
        "Add a task to be executed after a timeout (e.g. for monitoring)."
        thread = threading.Timer(timeout, callback)
        thread.start()

    def ping(self):
        "Tell controller to consult strategies when possible (if asynchronous)"
        pass

    def can_work(self):
        "Return whether we can currently perform work."
        return True

    def best_point(self):
        "Return the best point in the database."
        fcomplete = [f for f in self.fevals if f.status == 'completed']
        if fcomplete:
            return min(fcomplete, key=lambda x: x.value)

    def new_feval(self, params, status='pending'):
        """Add a function evaluation record to the database.
        """
        record = EvalRecord(params, status=status)
        self.fevals.append(record)
        for callback in self.feval_callbacks:
            callback(record)
        return record

    def call_term_callbacks(self):
        "Call termination callbacks."
        for callback in self.term_callbacks:
            callback()

    def add_term_callback(self, callback):
        "Add a callback for cleanup on termination."
        self.term_callbacks.append(callback)

    def add_feval_callback(self, callback):
        "Add a callback for notification on new fevals."
        self.feval_callbacks.append(callback)

    def remove_term_callback(self, callback):
        "Remove a callback from the term callback list."
        self.term_callbacks = [
            c for c in self.term_callbacks if c != callback
        ]

    def remove_feval_callback(self, callback):
        "Remove a callback from the feval callback list."
        self.feval_callbacks = [
            c for c in self.feval_callbacks if c != callback
        ]


class SerialController(Controller):
    """Serial optimization controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        objective: Objective function
        fevals: Database of function evaluations
    """

    def __init__(self, objective):
        "Initialize the controller."
        Controller.__init__(self)
        self.objective = objective

    def _run(self):
        "Run the optimization and return the best value."
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                raise NameError('No proposed action')
            if proposal.action == 'terminate':
                proposal.accept()
                return self.best_point()
            elif proposal.action == 'eval':
                proposal.record = self.new_feval(proposal.args)
                proposal.accept()
                value = self.objective(*proposal.record.params)
                proposal.record.complete(value)
            elif proposal.action == 'kill':
                proposal.reject()
            else:
                proposal.reject()

    def run(self):
        "Run the optimization and return the best value."
        try:
            return self._run()
        finally:
            self.call_term_callbacks()


class ThreadController(Controller):
    """Thread-based optimization controller.

    The optimizer dispatches work to a queue of workers.
    Each worker has methods of the form

       worker.eval(record)
       worker.kill(record)

    These methods are asynchronous: they start a function evaluation
    or termination, but do not necessarily complete it.  The worker
    must respond to eval requests, but may ignore kill requests.  On
    eval requests, the worker should either attempt the evaluation or
    mark the record as killed.  The worker sends status updates back
    to the controller in terms of lambdas (executed at the controller)
    that update the relevant record.  When the worker becomes
    available again, it should use add_worker to add itself back to
    the queue.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations
        workers: Queue of available worker threads
        messages: Queue of messages from workers

    """

    def __init__(self):
        "Initialize the controller."
        Controller.__init__(self)
        self.workers = Queue.Queue()
        self.messages = Queue.Queue()
        self.io_lock = threading.Lock()

    def ping(self):
        "Tell controller to consult strategies when possible"
        self.add_message()

    def lprint(self, *args):
        "Locking I/O."
        self.io_lock.acquire()
        print("{0}".format(*args))
        self.io_lock.release()

    def add_timer(self, timeout, callback):
        "Add a task to be executed after a timeout (e.g. for monitoring)."
        thread = threading.Timer(timeout, lambda: self.add_message(callback))
        thread.start()

    def add_message(self, message=None):
        "Queue up a message."
        if message is None:
            self.messages.put(lambda: None)
        else:
            self.messages.put(message)

    def add_worker(self, worker):
        "Add a worker and queue a 'wake-up' message."
        self.workers.put(worker)
        self.add_message()

    def launch_worker(self, worker, daemon=False):
        "Launch and take ownership of a new worker thread."
        self.add_worker(worker)
        self.add_term_callback(worker.terminate)
        worker.daemon = worker.daemon or daemon
        worker.start()

    def can_work(self):
        "Claim we can work if a worker is available."
        return not self.workers.empty()

    def _submit_work(self, proposal):
        "Submit proposed work."
        try:
            worker = self.workers.get_nowait()
            proposal.record = self.new_feval(proposal.args)
            proposal.record.worker = worker
            proposal.accept()
            worker.eval(proposal.record)
        except Queue.Empty:
            proposal.reject()

    def _run_message(self):
        "Process a message, blocking for one if none is available."
        message = self.messages.get()
        message()

    def _run_queued_messages(self):
        "Process any queued messages."
        while not self.messages.empty():
            self._run_message()

    def _run(self):
        "Run the optimization and return the best value."
        while True:
            self._run_queued_messages()
            proposal = self.strategy.propose_action()
            if not proposal:
                self._run_message()
            elif proposal.action == 'terminate':
                proposal.accept()
                return self.best_point()
            elif proposal.action == 'eval' and self.can_work():
                self._submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done():
                record = proposal.args[0]
                record.worker.kill(record)
            else:
                proposal.reject()

    def run(self):
        try:
            return self._run()
        finally:
            self.call_term_callbacks()


class BaseWorkerThread(threading.Thread):
    """Worker base class for use with the thread controller.

    The BaseWorkerThread class has a run routine that actually handles
    the worker event loop, and a set of helper routines for
    dispatching messages into the worker event loop (usually from the
    controller) and dispatching messages to the controller (usually
    from the worker).
    """

    def __init__(self, controller):
        "Initialize the worker."
        super(BaseWorkerThread, self).__init__()
        self.controller = controller
        self.queue = Queue.Queue()

    def eval(self, record):
        "Start evaluation."
        self.queue.put(('eval', record))

    def kill(self, record):
        "Send kill message to worker."
        self.queue.put(('kill', record))

    def terminate(self):
        "Send termination message to worker."
        self.queue.put(('terminate',))

    def lprint(self, *args):
        "Print log message at controller"
        self.controller.lprint(*args)

    def add_message(self, message):
        "Send message to be executed at the controller."
        self.controller.add_message(message)

    def add_worker(self):
        "Add worker back to the work queue."
        self.controller.add_worker(self)

    def finish_success(self, record, value):
        "Finish successful work on a record and add ourselves back."
        self.add_message(lambda: record.complete(value))
        self.add_worker()

    def finish_failure(self, record):
        "Finish recording failure on a record and add ourselves back."
        self.add_message(record.kill)
        self.add_worker()

    def handle_eval(self, record):
        "Process an eval request."
        pass

    def handle_kill(self, record):
        "Process a kill request"
        pass

    def handle_terminate(self):
        "Handle any cleanup on a terminate request"
        pass

    def run(self):
        "Run requests as long as we get them."
        while True:
            request = self.queue.get()
            if request[0] == 'eval':
                record = request[1]
                self.add_message(record.running)
                self.handle_eval(record)
            elif request[0] == 'kill':
                self.handle_kill(request[1])
            elif request[0] == 'terminate':
                self.handle_terminate()
                return


class BasicWorkerThread(BaseWorkerThread):
    """Basic worker for use with the thread controller.

    The BasicWorkerThread calls a Python objective function
    when asked to do an evaluation.  This is concurrent, but only
    results in parallelism if the objective function implementation
    itself allows parallelism (e.g. because it communicates with
    an external entity via a pipe, socket, or whatever).
    """

    def __init__(self, controller, objective):
        "Initialize the worker."
        super(BasicWorkerThread, self).__init__(controller)
        self.objective = objective

    def handle_eval(self, record):
        self.finish_success(record, self.objective(*record.params))


class ProcessWorkerThread(BaseWorkerThread):
    """Subprocess worker for use with the thread controller.

    The ProcessWorkerThread is meant for use as a base class.
    Implementations that inherit from ProcessWorkerThread should
    define a handle_eval method that sets the process field so that it
    can be interrupted if needed.  This allows use of blocking
    communication primitives while at the same time allowing
    interruption.
    """

    def __init__(self, controller):
        "Initialize the worker."
        super(ProcessWorkerThread, self).__init__(controller)
        self.process = None

    def kill(self, record):
        "Send kill message."
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        super(ProcessWorkerThread, self).kill(record)

    def terminate(self):
        "Send termination message."
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        super(ProcessWorkerThread, self).terminate()
        self.join()


class SimTeamController(Controller):
    """Simulated parallel optimization controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        objective: Objective function
        delay: Time delay function
        workers: Number of workers available
        fevals: Database of function evaluations
        time: Current simulated time
        time_events: Time-stamped event heap
    """

    def __init__(self, objective, delay, workers):
        "Initialize the controller."
        Controller.__init__(self)
        self.objective = objective
        self.delay = delay
        self.workers = workers
        self.time = 0
        self.time_events = []

    def can_work(self):
        "Check if there are workers available."
        return self.workers > 0

    def submit_work(self, proposal):
        "Submit a work event."
        self.workers = self.workers-1
        record = self.new_feval(proposal.args)
        proposal.record = record
        proposal.accept()

        def event():
            "Closure for marking record done at some later point."
            if not record.is_done():
                record.complete(self.objective(*record.params))
                self.workers = self.workers + 1

        self.add_timer(self.delay(), event)

    def kill_work(self, proposal):
        "Submit a kill event."
        record = proposal.args[0]

        def event():
            """Closure for canceling a function evaluation
            NB: This is a separate event because it will eventually have delay!
            """
            if not record.is_done():
                record.kill()
                self.workers = self.workers + 1

        self.add_timer(0, event)

    def advance_time(self):
        "Advance time to the next event."
        assert self.time_events, "Deadlock detected!"
        time, event = heapq.heappop(self.time_events)
        self.time = time
        event()

    def add_timer(self, timeout, event):
        "Add new timer event."
        heapq.heappush(self.time_events, (self.time + timeout, event))

    def _run(self):
        "Run the optimization and return the best value."
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                self.advance_time()
            elif proposal.action == 'terminate':
                proposal.accept()
                return self.best_point()
            elif proposal.action == 'eval' and self.can_work():
                self.submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.args[0].is_done():
                self.kill_work(proposal)
            else:
                proposal.reject()
                self.advance_time()

    def run(self):
        "Run the optimization and return the best value."
        try:
            return self._run()
        finally:
            self.call_term_callbacks()


class Monitor(object):
    """Monitor events observed by a controller.

    The monitor object provides hooks to monitor the progress of an
    optimization run by a controller.  Users should inherit from Monitor
    and add custom version of the methods

        on_new_feval(self, record)
        on_update(self, record)
        on_terminate(self)
    """

    def __init__(self, controller):
        """Initialize the monitor.

        Args:
            controller: The controller whose fevals we will monitor
        """
        self.controller = controller
        controller.add_feval_callback(self._add_on_update)
        controller.add_feval_callback(self.on_new_feval)
        controller.add_term_callback(self.on_terminate)

    def _add_on_update(self, record):
        "Internal handler -- add on_update callback to all new fevals."
        record.add_callback(self.on_update)

    def on_new_feval(self, record):
        "Handle new function evaluation request."
        pass

    def on_update(self, record):
        "Handle function evaluation update."
        pass

    def on_terminate(self):
        "Handle termination."
        pass
