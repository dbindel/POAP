
Introduction
============

Consider global minimization of a objective function :math:`f : D
\rightarrow \mathbb{R}` that takes a significant amount of time to
evaluate.  If we have several processors, it may make sense to run
several concurrent function evaluations, dispatching processors to
work on new values as they finish the old ones.  The
Plumbing for Optimization with Asynchronous Parallelism (POAP)
provides a framework for coordinating such optimization procedures.

The purpose of the POAP framework is to provide a relatively simple
environment for describing and composing asynchronous optimization
strategies that are largely independent of the mechanics of how work
is actually dispatched to the worker processes.  The POAP framework is
organized around three types of interacting objects:

 - One or more *workers* actually compute function values, and
   may provide intermediate results.

 - A *strategy* object proposes control actions for the workers,
   such as starting a new function evaluation, killing
   a function evaluation that is underway, or terminating
   the optimization.  The strategy may changed proposed objects
   as it is informed of events such as availability of a new
   function value.
   
 - A *controller* accepts or rejects proposals by the strategy
   object, controls and monitors the workers, and informs the
   strategy object of events such as the processing of a proposal
   or status updates on a function evaluation.

Interaction between strategies and the controller is organized
around *proposals* and *evaluation records*.  At the beginning of the
optimization and on any later change to the system state, the
controller requests a proposal from the strategy.  The proposal
consists of an action (evaluate a function, kill a function, or
terminate the optimization), a list of parameters, and a list of
callback functions to be executed once the proposal is processed.  The
controller then either accepts the proposal (and sends a command to
the worker), or it rejects the proposal.

When the controller accepts a proposal to start a function evaluation,
it creates an *evaluation record* to share information about the
status of the evaluation with the strategy.  The evaluation record
includes of the evaluation point, the status of the evaluation, the
value (if completed), and a list of callback functions to be executed
on any update.

Once a proposal has been accepted or rejected, the controller
processes any pending system events (e.g. completed or canceled
function evaluations), notifies the strategy about updates, and
requests the next proposed action.

Different strategies can be composed by combining their control
actions in an intelligent way.  For example, a multi-start strategy
might cycle through a list of local optimization strategies,
forwarding the first plausible proposal to the controller.  Strategies
can also subscribe to be informed of all new function evaluations,
so that they incorporate any new function information -- even if a
different strategy originally requested that information.

Proposals and evaluation records
================================

Proposals
---------

.. autoclass:: poap.strategy.Proposal
   :members:

Evaluation records
------------------

.. autoclass:: poap.strategy.EvalRecord
   :members:

Strategies
==========

We provide some basic default strategies based on non-adaptive
sampling and serial optimization routines, and also some strategies
that adapt or combine other strategies.

Base strategy
-------------

.. autoclass:: poap.strategy.BaseStrategy
   :members:

Fixed sampling
--------------

.. autoclass:: poap.strategy.FixedSampleStrategy
   :members:

Coroutine adapters
------------------

.. autoclass:: poap.strategy.CoroutineStrategy
   :members:

.. autoclass:: poap.strategy.CoroutineBatchStrategy
   :members:

Threaded adapter
----------------

.. autoclass:: poap.strategy.PromiseStrategy
   :members:

.. autoclass:: poap.strategy.ThreadStrategy
   :members:

Filtering evaluation request
----------------------------

.. autoclass:: poap.strategy.CheckWorkerStrategy
   :members:

Simple prioritized mergers
--------------------------

.. autoclass:: poap.strategy.SimpleMergedStrategy
   :members:

Terminating on maximum evaluations
----------------------------------

.. autoclass:: poap.strategy.MaxEvalStrategy
   :members:

External input
--------------

.. autoclass:: poap.strategy.InputStrategy
   :members:

Failure testing
---------------

.. autoclass:: poap.strategy.ChaosMonkeyStrategy
   :members:

Controllers
===========

In addition to the controller base class, which provides some shared
functionality, we provide three example controllers: a serial
controller that simply runs function evaluations on demand; a threaded
controller that runs each worker in a separate Python thread; and a
modified threaded controller that allows workers to pause for some
period of virtual time in order to simulate the behavior of
long-running optimization codes.

Controller base class
---------------------

.. autoclass:: poap.controller.Controller
   :members:

Serial controller
-----------------

.. autoclass:: poap.controller.SerialController
   :members:

Thread controller
-----------------

.. autoclass:: poap.controller.ThreadController
   :members:

Simulation thread controller
----------------------------

.. autoclass:: poap.controller.SimThreadController
   :members:

Scripted controller
-------------------

.. autoclass:: poap.controller.ScriptedController
   :members:

Worker threads
==============

The multi-threaded controller employs a set of workers that are
capable of managing concurrent function evaluations.  This does *not*
provide parallelism on its own, but the worker threads can be used to
manage parallelism by separate external processes.

Worker thread base class
------------------------

.. autoclass:: poap.controller.BaseWorkerThread
   :members:

Basic worker thread
-------------------

.. autoclass:: poap.controller.BasicWorkerThread
   :members:

Process worker thread
---------------------

.. autoclass:: poap.controller.ProcessWorkerThread
   :members:

