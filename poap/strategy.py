"""
.. module:: strategy
   :synopsis: Basic strategy classes for asynchronous optimization.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

try:
    import Queue
except ImportError:
    import queue as Queue

import threading
import numpy
import random
from collections import deque


class Proposal(object):
    """Represent a proposed action.

    We currently recognize three types of proposals: evaluation requests
    ("eval"), requests to stop an evaluation ("kill"), and requests
    to terminate the optimization ("terminate").  When an evaluation
    proposal is accepted, the controller adds an evaluation record to the
    proposal before notifying subscribers.

    Attributes:
        action: String describing the action
        args: Tuple of arguments to pass to the action
        accepted: Flag set on accept/reject decision
        callbacks: Functions to call on accept/reject of action
        record: Evaluation record for accepted evaluation proposals
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

    An evaluation record includes the evaluation point, status of the
    evaluation, and a list of callbacks.  The status may be pending,
    running, killed (deliberately), cancelled (due to a crash or
    failure) or completed.  Once the function evaluation is completed,
    the value is stored as an attribute in the evaluation record.  The
    evaluation record callbacks are triggered on any relevant event,
    including not only status changes but also intermediate results.
    The nature of these intermediate results (lower bounds, initial
    estimates, etc) is somewhat application-dependent.

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

    def running(self):
        "Change status to 'running' and execute callbacks."
        self.status = 'running'
        self.update()

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


class BaseStrategy(object):
    """Base strategy class.

    The BaseStrategy class provides some support for the basic callback
    flow common to most strategies: handlers are called when an evaluation
    is accepted or rejected; and if an evaluation proposal is accepted,
    the record is decorated so that an on_update handler is called for
    subsequent updates.

    Note that not all strategies follow this pattern -- the only requirement
    for a strategy is that it implement propose_action.
    """

    def propose_eval(self, *args):
        "Generate an eval proposal with a callback to on_reply."
        proposal = Proposal('eval', *args)
        proposal.add_callback(self.on_reply)
        return proposal

    def proposal_copy(self, proposal):
        "Copy a proposal and add back an on_reply callback."
        proposal = proposal.copy()
        if proposal.action == 'eval':
            proposal.add_callback(self.on_reply)
        return proposal

    def on_reply(self, proposal):
        "Default handling of proposal."
        if proposal.accepted:
            proposal.record.add_callback(self.on_update)
            self.on_reply_accept(proposal)
        else:
            self.on_reply_reject(proposal)

    def on_reply_accept(self, proposal):
        "Handle proposal acceptance."
        pass

    def on_reply_reject(self, proposal):
        "Handle proposal rejection."
        pass

    def on_update(self, record):
        "Process update."
        if record.status == 'completed':
            self.on_complete(record)
        elif record.is_done():
            self.on_kill(record)

    def on_complete(self, record):
        "Process completed record."
        pass

    def on_kill(self, record):
        "Process killed or cancelled record."
        pass


class RetryStrategy(BaseStrategy):
    """Manage proposal resubmissions for another strategy.

    The RetryStrategy keeps a queue of points that another strategy
    would like evaluated.  If a proposal generated by the
    RetryStrategy is rejected, or i the function evaluation terminates
    unsuccessfully, the RetryStrategy adds it back to the queue of
    points to be evaluated.

    Attributes:
        strategy: Strategy for which we manage resubmissions
        num_pending: Number of proposals/fevals in flight
        pointq: Queue of evaluation points to be sent
        tagname: Name of attribute used to store auxiliary data
    """

    def __init__(self, strategy, tagname=None):
        self.strategy = strategy
        self.tagname = None
        self.num_pending = 0
        self.pointq = []

    def _set_tag(self, obj, tag):
        "Set the tag data field on a proposal or record."
        if self.tagname:
            setattr(obj, self.tagname, tag)

    def _get_tag(self, obj):
        "Get the tag data field from a proposal or record."
        if self.tagname:
            return getattr(obj, self.tagname)
        return None

    def append(self, point, tag=None):
        "Add a point to the queue."
        self.pointq.append((point, tag))

    def num_outstanding(self):
        "Return number of outstanding fevals"
        return len(self.pointq) + self.num_pending

    def propose_action(self):
        "Propose an action."
        if self.pointq:
            self.num_pending += 1
            x, tag = self.pointq.pop()
            proposal = self.propose_eval(x)
            self._set_tag(proposal, tag)
            return proposal
        return None

    def on_reply_accept(self, proposal):
        "Process a response to a proposal."
        self._set_tag(proposal.record, self._get_tag(proposal))

    def on_reply_reject(self, proposal):
        "Process a response to a proposal."
        self.num_pending -= 1
        self.pointq.append((proposal.args[0], self._get_tag(proposal)))

    def on_update(self, record):
        "Process a response to a record update."
        if record.status == 'completed':
            self.num_pending -= 1
            if hasattr(self.strategy, "on_complete"):
                self.strategy.on_complete(record)
        elif record.is_done():
            self.num_pending -= 1
            self.pointq.append((record.params, self._get_tag(record)))
        else:
            if hasattr(self.strategy, "on_update"):
                self.strategy.on_update(record)


class FixedSampleStrategy(BaseStrategy):
    """Sample at a fixed set of points.

    The fixed sampling strategy is appropriate for any non-adaptive
    sampling scheme.  Since the strategy is non-adaptive, we can
    employ as many available workers as we have points to process.  We
    keep trying any evaluation that fails, and suggest termination
    only when all evaluations are complete.  The points in the
    experimental design can be provided as any iterable object (e.g. a
    list or a generator function).  One can use a generator for an
    infinite sequence if the fixed sampling strategy is used in
    combination with a strategy that provides a termination criterion.
    """

    def __init__(self, points):
        """Initialize the sampling scheme.

        Args:
            points: Points list or generator function.
        """
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
                point = next(self.point_generator)
                self.proposed_points.append(point)
            point = self.proposed_points.pop()
            return self.propose_eval(point)
        except StopIteration:
            if self.outstanding == 0:
                return Proposal('terminate')
            return None

    def on_reply_accept(self, proposal):
        "Handle a proposal acceptance."
        self.outstanding += 1

    def on_reply_reject(self, proposal):
        "Handle a proposal rejection."
        self.proposed_points.append(proposal.args[0])

    def on_complete(self, record):
        "Update counts on successful completion"
        self.outstanding -= 1

    def on_kill(self, record):
        "Re-request evaluation on cancellation."
        self.outstanding -= 1
        self.proposed_points.append(*record.params)


class CoroutineStrategy(BaseStrategy):
    """Event-driven to serial adapter using coroutines.

    The coroutine strategy runs a standard sequential optimization algorithm
    in a Python coroutine, with which the strategy communicates via send/yield
    directives.  The optimization coroutine yields the parameters at which
    it would like function values; the strategy then requests the function
    evaluation and returns the value with a send command when it becomes
    available.

    Attributes:
        coroutine: Optimizer coroutine
        proposal:  Proposal that the strategy is currently requesting.
    """

    def __init__(self, coroutine):
        "Initialize the strategy."
        self.coroutine = coroutine
        self.done = False
        try:
            self.proposal = self.propose_eval(next(self.coroutine))
        except StopIteration:
            self.proposal = Proposal('terminate')

    def next_request(self, value):
        "Request next function evaluation."
        try:
            self.proposal = self.propose_eval(self.coroutine.send(value))
        except StopIteration:
            self.proposal = Proposal('terminate')

    def propose_action(self):
        "If we have a pending request, propose it."
        proposal, self.proposal = self.proposal, None
        return proposal

    def on_reply_reject(self, proposal):
        "If proposal rejected, propose again."
        self.proposal = self.proposal_copy(proposal)

    def on_complete(self, record):
        "Return point to coroutine"
        self.next_request(record.value)

    def on_kill(self, record):
        "Re-request point"
        self.proposal = self.propose_eval(*record.params)


class CoroutineBatchStrategy(BaseStrategy):
    """Event-driven to synchronous parallel adapter using coroutines.

    The coroutine strategy runs a synchronous parallel optimization
    algorithm in a Python coroutine, with which the strategy
    communicates via send/yield directives.  The optimization
    coroutine yields batches of parameters at which it would like
    function values; the strategy then requests the function
    evaluation and returns the records associated with those function
    evaluations when all have been completed.

    Attributes:
        coroutine: Optimizer coroutine
        on_feval_start: Handler to be called on start of feval
        on_feval_done: Handler to be called on successful feval completion
        num_pending: Number of in-flight proposals and evaluations
        pointq: Points that need to be proposed
        results: Completion records to be returned to the coroutine
    """

    def __init__(self, coroutine, on_feval_start=None, on_feval_done=None):
        self.coroutine = coroutine
        self.on_feval_start = on_feval_start
        self.on_feval_done = on_feval_done
        self.num_pending = 0
        self.pointq = []
        self.results = []
        try:
            self.start_batch(next(self.coroutine))
        except StopIteration:
            pass

    def start_batch(self, xs):
        "Start evaluation of a batch of points."
        self.num_pending = 0
        for ii in range(xs.shape[0]):
            self.pointq.append((ii, numpy.asarray(xs[ii, :])))
        self.results = [None for ii in range(xs.shape[0])]

    def propose_action(self):
        "If we have a pending request, propose it."
        try:
            if not self.pointq and self.num_pending == 0:
                self.start_batch(self.coroutine.send(self.results))
            if self.pointq:
                self.num_pending += 1
                batch_id, x = self.pointq.pop()
                proposal = self.propose_eval(x)
                proposal.batch_id = batch_id
                return proposal
            return None
        except StopIteration:
            return Proposal('terminate')

    def on_reply_accept(self, proposal):
        "If proposal accepted, wait for result."
        if self.on_feval_start:
            self.on_feval_start(proposal.record)
        proposal.record.batch_id = proposal.batch_id

    def on_reply_reject(self, proposal):
        "Propose again."
        self.num_pending -= 1
        self.pointq.append((proposal.batch_id, proposal.args[0]))

    def on_complete(self, record):
        "Return or re-request on completion or cancellation."
        self.num_pending -= 1
        self.results[record.batch_id] = record
        if self.on_feval_done:
            self.on_feval_done(record)

    def on_kill(self, record):
        "Return or re-request on completion or cancellation."
        self.num_pending -= 1
        self.pointq.append((record.batch_id, record.params))


class ThreadStrategy(BaseStrategy):
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

    def __init__(self, optimizer, daemon=True):
        """Initialize the strategy.

        Args:
            optimizer: Optimizer function (takes objective as an argument)
        """
        self.optimizer = optimizer
        self.proposalq = Queue.Queue()
        self.valueq = Queue.Queue()
        self.thread = OptimizerThread(self)
        self.thread.setDaemon(daemon)
        self.thread.start()
        self.proposal = self.proposalq.get()

    def propose_action(self):
        "If we have a pending request, propose it."
        proposal, self.proposal = self.proposal, None
        return proposal

    def on_reply_reject(self, proposal):
        "Propose again."
        self.proposal = self.proposal_copy(proposal)

    def on_complete(self, record):
        "Return on completion"
        self.valueq.put(record.value)
        self.proposal = self.proposalq.get()

    def on_kill(self, record):
        "Re-request on cancellation."
        self.proposal = self.propose_eval(*record.params)


class OptimizerThread(threading.Thread):
    "Thread running serial optimizer."

    def __init__(self, strategy):
        "Initialize thread with hookup to strategy."
        super(OptimizerThread, self).__init__()
        self.strategy = strategy
        self.proposalq = strategy.proposalq
        self.valueq = strategy.valueq

    def objective(self, *args):
        "Provide function call interface to ThreadStrategy."
        self.proposalq.put(self.strategy.propose_eval(*args))
        return self.valueq.get()

    def run(self):
        "Thread main routine."
        try:
            self.strategy.optimizer(self.objective)
        finally:
            self.proposalq.put(Proposal('terminate'))


class CheckWorkerStrategy(object):
    """Preemptively kill eval proposals when there are no workers.

    A strategy like the fixed sampler is simple-minded, and will
    propose a function evaluation even if the controller has no
    workers available to carry it out.  This wrapper strategy
    intercepts proposals from a wrapped strategy like the fixed
    sampler, and only submits evaluation proposals if workers are
    available.
    """

    def __init__(self, controller, strategy):
        "Initialize checker strategy."
        self.controller = controller
        self.strategy = strategy

    def propose_action(self):
        "Generate filtered action proposal."
        proposal = self.strategy.propose_action()
        if (proposal and proposal.action == 'eval' and
                not self.controller.can_work()):
            proposal.reject()
            return None
        return proposal


class SimpleMergedStrategy(object):
    """Merge several strategies by taking the first valid proposal from them.

    The simplest combination strategy is to keep a list of several
    possible strategies in some priority order, query them for
    proposals in priority order, and pass on the first plausible
    proposal to the controller.

    Attributes:
        controller: Controller object used to determine whether we can eval
        strategies: Prioritized list of strategies
    """

    def __init__(self, controller, strategies):
        "Initialize merged strategy."
        self.controller = controller
        self.strategies = strategies

    def propose_action(self):
        "Go through strategies in order and choose the first valid action."
        for strategy in self.strategies:
            proposal = strategy.propose_action()
            if proposal is None:
                pass
            elif proposal.action == 'eval' and not self.controller.can_work():
                proposal.reject()
            else:
                return proposal


class MultiStartStrategy(object):
    """Merge several strategies by taking the first valid eval proposal.

    This strategy is similar to the SimpleMergedStrategy, except that we
    only terminate once all the worker strategies have voted to terminate.

    Attributes:
        controller: Controller object used to determine whether we can eval
        strategies: Prioritized list of strategies
    """

    def __init__(self, controller, strategies):
        "Initialize merged strategy."
        self.controller = controller
        self.strategies = strategies

    def propose_action(self):
        """Go through strategies in order and choose the first valid action.
        Terminate iff all workers vote to terminate.
        """
        proposals = [strategy.propose_action() for strategy in self.strategies]
        chosen_proposal = None
        terminate_votes = 0
        for proposal in proposals:
            if not proposal:
                pass
            elif proposal.action == 'eval' and self.controller.can_work():
                chosen_proposal = proposal
            elif proposal.action == 'kill':
                chosen_proposal = proposal
            elif proposal.action == 'terminate':
                terminate_votes += 1
        for proposal in proposals:
            if proposal is not None and proposal != chosen_proposal:
                proposal.reject()
        if terminate_votes == len(proposals):
            return Proposal("terminate")
        return chosen_proposal


class MaxEvalStrategy(object):
    """Recommend termination of the iteration after some number of evals.

    Attributes:
        counter: Number of completed evals
        max_counter: Max number of evals
    """

    def __init__(self, controller, max_counter):
        """Initialize the strategy.

        Args:
            controller: Used for registering the feval callback
            max_counter: Maximum number of evals desired
        """
        self.counter = 0
        self.max_counter = max_counter
        controller.add_feval_callback(self.on_new_feval)

    def on_new_feval(self, record):
        "On every feval, add a callback."
        record.add_callback(self.on_update)

    def on_update(self, record):
        "On every completion, increment the counter."
        if record.status == 'completed':
            self.counter += 1

    def propose_action(self):
        "Propose termination once the eval counter is high enough."
        if self.counter >= self.max_counter:
            return Proposal('terminate')
        else:
            return None


class InputStrategy(object):
    """Insert requests from the outside world (e.g. from a GUI)."""

    def __init__(self, controller, strategy):
        self.controller = controller
        self.strategy = strategy
        self.proposals = deque([])

    def terminate(self):
        "Request termination of the optimization"
        self.proposals.append(Proposal('terminate'))
        self.controller.ping()

    def kill(self, record):
        "Request a function evaluation be killed"
        self.proposals.append(Proposal('kill', record))
        self.controller.ping()

    def eval(self, params, retry=True):
        "Request a new function evaluation"
        proposal = Proposal('eval', params)
        if retry:
            proposal.add_callback(self._on_reply)
        self.proposals.append(proposal)
        self.controller.ping()

    def _on_reply(self, proposal):
        "Re-try a function evaluation if rejected"
        if not proposal.accepted:
            self.eval(proposal.args, True)

    def propose_action(self):
        if self.proposals:
            return self.proposals.popleft()
        return self.strategy.propose_action()


class ChaosMonkeyStrategy(object):
    """Randomly kill running function evaluations.

    The ChaosMonkeyStrategy kills function evaluations at random from
    among all active function evaluations.  Attacks are associated
    with a Poisson process where the mean time between failures is
    specified at startup.  Useful mostly for testing the resilience of
    strategies to premature termination of their evaluations.  The
    controller may decide to ignore the proposed kill actions, in
    which case the monkey's attacks are ultimately futile.
    """

    def __init__(self, controller, strategy, logger=None, mtbf=1):
        """Release the chaos monkey!

        Args:
            controller: The controller whose fevals we will kill
            strategy: Parent strategy
            mtbf: Mean time between failure (assume Poisson process)
        """
        self.controller = controller
        self.strategy = strategy
        self.running_fevals = []
        self.lam = 1.0/mtbf
        self.logger = logger
        self.target = None
        controller.add_feval_callback(self.on_new_feval)
        controller.add_timer(random.expovariate(self.lam), self.on_timer)

    def log(self, msg):
        "Write message to the logger."
        if self.logger is not None:
            self.logger(msg)

    def on_new_feval(self, record):
        "On every feval, add a callback."
        record.chaos_target = False
        record.add_callback(self.on_update)

    def on_update(self, record):
        "On every completion, remove from list"
        if record.status == 'running' and not record.chaos_target:
            record.chaos_target = True
            self.running_fevals.append(record)
        elif record.is_done() and record.chaos_target:
            record.chaos_target = False
            self.running_fevals.remove(record)

    def on_timer(self):
        if self.running_fevals:
            record = self.running_fevals.pop()
            record.chaos_target = False
            self.target = record
            self.controller.ping()
        self.controller.add_timer(random.expovariate(self.lam), self.on_timer)

    def propose_action(self):
        if self.target:
            self.log("Monkey attack! {0}".format(self.target.params))
            proposal = Proposal('kill', self.target)
            self.target = None
        else:
            proposal = self.strategy.propose_action()
        return proposal
