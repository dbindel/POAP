"""
.. module:: strategy
   :synopsis: Basic strategy classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

import threading
import Queue


class Proposal(object):
    """Represent a proposed action.

    Attributes:
        action: String describing the action
        args: Tuple of arguments to pass to the action
        accepted: Flag set on accept/reject decision
        callbacks: Functions to call on accept/reject of action
    """

    def __init__(self, action, *args):
        """Initialize the request.

        Args:
            action: String describing the action
            args:   Tuple of arguments to pass to the action
        """
        self.action = action
        self.args = args
        self.accepted = False
        self.callbacks = []

    def copy(self):
        "Make a copy of the proposal with no callbacks/decorations."
        return Proposal(self.action, *self.args)

    def add_callback(self, callback):
        "Add a callback subscriber to the action."
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        "Remove a callback subscriber."
        self.callbacks = [c for c in self.callbacks if c != callback]

    def accept(self):
        "Mark the action as accepted and execute callbacks."
        self.accepted = True
        for callback in self.callbacks:
            callback(self)

    def reject(self):
        "Mark action as rejected and execute callbacks."
        self.accepted = False
        for callback in self.callbacks:
            callback(self)


class EvalRecord(object):
    """Represent progress of a function evaluation.

    Attributes:
        params: Evaluation point for the function
        status: Status of the evaluation (pending, running, killed, completed)
        value: Return value (if completed)
        callbacks: Functions to call on status updates
    """

    def __init__(self, params, status='pending'):
        """Initialize the record.

        Args:
            params: Evaluation point for the function
        Kwargs:
            status: Status of the evaluation (default 'pending')
        """
        self.params = params
        self.status = status
        self.value = None
        self.callbacks = []

    def add_callback(self, callback):
        "Add a callback for update events."
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        "Remove a callback subscriber."
        self.callbacks = [c for c in self.callbacks if c != callback]

    def update(self):
        "Execute callbacks."
        for callback in self.callbacks:
            callback(self)

    def kill(self):
        "Change status to 'killed' and execute callbacks."
        self.status = 'killed'
        self.update()

    def complete(self, value):
        "Change status to 'completed' and execute callbacks."
        self.status = 'completed'
        self.value = value
        self.update()

    def is_done(self):
        "Check whether the status indicates the evaluation is finished."
        return (self.status == 'completed' or
                self.status == 'killed' or
                self.status == 'cancelled')


class FixedSampleStrategy(object):
    """Sample at a fixed set of points.

    The fixed sampling strategy is appropriate for any non-adaptive
    sampling scheme.  Since the strategy is non-adaptive, we can
    employ as many available workers as we have points to process.
    We keep trying any evaluation that fails, and suggest termination
    only when all evaluations are complete.
    """

    def __init__(self, points):
        "Initialize the sampling scheme."
        def point_generator():
            "Generator wrapping the points list."
            for point in points:
                yield point
        self.point_generator = point_generator()
        self.proposed_points = []
        self.outstanding = 0

    def propose_action(self):
        "Propose an action based on outstanding points."
        try:
            if not self.proposed_points:
                point = self.point_generator.next()
                self.proposed_points.append(point)
            point = self.proposed_points.pop()
            proposal = Proposal('eval', point)
            proposal.add_callback(self.on_reply)
            return proposal
        except StopIteration:
            if self.outstanding == 0:
                return Proposal('terminate')
            return None

    def on_reply(self, proposal):
        "Handle a proposal reply."
        if proposal.accepted:
            self.outstanding = self.outstanding + 1
            proposal.record.add_callback(self.on_update)
        else:
            self.proposed_points.append(proposal.args[0])

    def on_update(self, record):
        "Re-request evaluation on cancellation."
        if record.status == 'completed':
            self.outstanding = self.outstanding-1
        elif record.is_done():
            self.proposed_points.append(*record.params)


class CoroutineStrategy(object):
    """Event-driven to serial adapter using coroutines.

    The coroutine strategy runs a standard sequential optimization algorithm
    in a Python coroutine, with which the strategy communicates via send/yield
    directives.  The optimization coroutine yields the parameters at which
    it would like function values; the strategy then requests the function
    evaluation and returns the value with a send command when it becomes
    available.

    Attributes:
        optimizer: Optimizer function (takes objective as an argument)
        proposalq: Queue of proposed actions caused by optimizer.
        valueq:    Queue of function values from proposed actions.
        thread:    Thread in which the optimizer runs.
        proposal:  Proposal that the strategy is currently requesting.
    """

    def __init__(self, coroutine):
        "Initialize the strategy."
        self.coroutine = coroutine
        self.done = False
        try:
            self.proposal = Proposal('eval', self.coroutine.next())
        except StopIteration:
            self.proposal = Proposal('terminate')

    def add_proposal_callback(self, proposal):
        "Add a reply callback for eval proposals."
        if proposal.action == 'eval':
            proposal.add_callback(self.on_reply)
        return proposal

    def next_request(self, value):
        "Request next function evaluation."
        try:
            self.proposal = Proposal('eval', self.coroutine.send(value))
        except StopIteration:
            self.proposal = Proposal('terminate')

    def propose_action(self):
        "If we have a pending request, propose it."
        proposal = None
        if self.proposal:
            proposal = self.add_proposal_callback(self.proposal)
            self.proposal = None
        return proposal

    def on_reply(self, proposal):
        "If proposal accepted, wait for result; else, propose again."
        if proposal.accepted:
            proposal.record.add_callback(self.on_update)
        else:
            self.proposal = proposal.copy()

    def on_update(self, record):
        "Return or re-request on completion or cancellation."
        if record.status == 'completed':
            self.next_request(record.value)
        elif record.is_done():
            self.proposal = Proposal('eval', *record.params)


class ThreadStrategy(object):
    """Event-driven to serial adapter using threads.

    The thread strategy runs a standard sequential optimization algorithm
    in a separate thread of control, with which the strategy communicates
    via queues.  The optimizer thread intercepts function evaluation requests
    and completion and turns them into proposals for the strategy, which
    it places in a proposal queue.  The optimizer then waits for the requested
    values (if any) to appear in the reply queue.

    Attributes:
        optimizer: Optimizer function (takes objective as an argument)
        proposalq: Queue of proposed actions caused by optimizer.
        valueq:    Queue of function values from proposed actions.
        thread:    Thread in which the optimizer runs.
        proposal:  Proposal that the strategy is currently requesting.
    """

    def __init__(self, optimizer):
        """Initialize the strategy.

        Args:
            optimizer: Optimizer function (takes objective as an argument)
        """
        self.optimizer = optimizer
        self.proposalq = Queue.Queue()
        self.valueq = Queue.Queue()
        self.thread = OptimizerThread(self)
        self.thread.setDaemon(True)
        self.thread.start()
        self.proposal = self.proposalq.get()

    def add_proposal_callback(self, proposal):
        "Add a reply callback for eval proposals."
        if proposal.action == 'eval':
            proposal.add_callback(self.on_reply)
        return proposal

    def propose_action(self):
        "If we have a pending request, propose it."
        proposal = None
        if self.proposal:
            proposal = self.add_proposal_callback(self.proposal)
            self.proposal = None
        return proposal

    def on_reply(self, proposal):
        "If proposal accepted, wait for result; else, propose again."
        if proposal.accepted:
            proposal.record.add_callback(self.on_update)
        else:
            self.proposal = proposal.copy()

    def on_update(self, record):
        "Return or re-request on completion or cancellation."
        if record.status == 'completed':
            self.valueq.put(record.value)
            self.proposal = self.proposalq.get()
        elif record.is_done():
            self.proposal = Proposal('eval', *record.params)


class OptimizerThread(threading.Thread):
    "Thread running serial optimizer."

    def __init__(self, strategy):
        "Initialize thread with hookup to strategy."
        super(OptimizerThread, self).__init__()
        self.strategy = strategy
        self.proposalq = strategy.proposalq
        self.valueq = strategy.valueq

    def objective(self, args):
        "Provide function call interface to ThreadStrategy."
        self.proposalq.put(Proposal('eval', args))
        return self.valueq.get()

    def run(self):
        "Thread main routine."
        try:
            self.strategy.optimizer(self.objective)
        finally:
            self.proposalq.put(Proposal('terminate'))
