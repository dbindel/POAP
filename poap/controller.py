"""
.. module:: controller
   :synopsis: Basic controller classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

from poap.strategy import EvalRecord


class Controller(object):
    """Base class for controller.

    Attributes:
        strategy: Strategy for choosing optimization actions.
        fevals: Database of function evaluations.
        feval_callbacks: List of callbacks to execute on new eval record
        term_callbacks: List of callbacks to execute on termination
        can_work: True if workers are available
    """

    def __init__(self, strategy):
        "Initialize the controller."
        self.strategy = strategy
        self.fevals = []
        self.feval_callbacks = []
        self.term_callbacks = []
        self.can_work = False

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

    def __init__(self, strategy, objective):
        "Initialize the controller."
        Controller.__init__(self, strategy)
        self.objective = objective
        self.can_work = True

    def run(self):
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
