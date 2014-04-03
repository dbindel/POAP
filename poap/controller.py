"""
.. module:: controller
   :synopsis: Basic controller classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

import Queue
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

    def run(self):
        "Run the optimization and return the best value."
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                raise NameError('No proposed action')
            if proposal.action == 'terminate':
                proposal.accept()
                self.call_term_callbacks()
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


class ThreadController(Controller):
    """Thread-based optimization controller.

    The optimizer dispatches work to a queue of worker threads.
    Each thread has a message queue that receives messages of
    the form

       ('eval', record)
       ('kill', record)

    We assume the worker will respond to eval requests, but
    may ignore kill requests.  On eval requests, the worker
    should either attempt the evaluation or mark the record
    as killed.  The worker sends status updates back to the
    controller in terms of lambdas (executed at the controller)
    that update the relevant record.  When the worker becomes
    available again, it should use add_worker to add itself
    back to the queue.

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

    def add_timer(self, timeout, callback):
        "Add a task to be executed after a timeout (e.g. for monitoring)."
        t = threading.Timer(timeout, lambda: self.messages.put(callback))
        t.start()

    def add_worker(self, worker):
        "Add a worker and queue a 'wake-up' message."
        self.workers.put(worker)
        self.messages.put(lambda: None)

    def can_work(self):
        "Claim we can work if a worker is available."
        return not self.workers.empty()

    def submit_work(self, proposal):
        "Submit proposed work."
        try:
            worker = self.workers.get_nowait()
            proposal.worker = worker
            proposal.record = self.new_feval(proposal.args)
            proposal.accept()
            worker.queue.put(('eval', proposal.record))
        except Queue.Empty:
            proposal.reject()

    def run_message(self):
        "Process a message, blocking for one if none is available."
        message = self.messages.get()
        message()

    def run_queued_messages(self):
        "Process any queued messages."
        while not self.messages.empty():
            self.run_message()

    def run(self):
        "Run the optimization and return the best value."
        self.run_queued_messages()
        while True:
            proposal = self.strategy.propose_action()
            if not proposal:
                self.run_queued_messages()
                self.run_message()
            elif proposal.action == 'terminate':
                print('Terminate')
                proposal.accept()
                self.call_term_callbacks()
                return self.best_point()
            elif proposal.action == 'eval' and self.can_work():
                self.submit_work(proposal)
            elif proposal.action == 'kill' and not proposal.record.is_done():
                print('Kill')
                proposal.worker.queue.put(('kill', proposal.record))
            else:
                proposal.reject()


class BasicWorkerThread(threading.Thread):
    """Basic worker for use with the thread controller."""

    def __init__(self, controller, objective):
        "Initialize the worker."
        super(BasicWorkerThread, self).__init__()
        self.controller = controller
        self.objective = objective
        self.queue = Queue.Queue()

    def run(self):
        "Run requests as long as we get them."
        while True:
            request = self.queue.get()
            if request[0] == 'eval':
                record = request[1]
                value = self.objective(*record.params)
                def message():
                    "Requested actions for the controller."
                    record.complete(value)
                    self.controller.add_worker(self)
                self.controller.messages.put(message)
            elif request[0] == 'terminate':
                return
