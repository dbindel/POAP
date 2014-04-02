
Introduction
============

Consider global minimization of a objective function :math:`f : D
\rightarrow \mathbb{R}` that takes a significant amount of time to
evaluate.  In general, :math:`D \subset \mathbb{R}^d` may be an
arbitrary compact set, but we will restrict our attention to
hypercubes.  We allow :math:`f` to be non-convex, and we
assume that derivatives are not easily available.

The Parallel Asynchronous Optimization via Response Surfaces (POARS)
framework is appropriate for global optimization of expensive
functions in which the time to evaluate a function may vary
significantly depending on the parameter values.  In this framework, a
master processor calls upon workers to evaluate the objective function
at sample points.  The master keeps track of function evaluations that
have been received, which are used to produce one or more response
surfaces; the master also tracks pending function evaluations.  Each
time a function evaluation is completed, the master assigns the
associate worker with a new sample point in a way that improves the
diversity of the sampling (by avoiding previous or pending evaluation
points) and/or improves the resolution in the neighborhood of a
promising expected local minimizer.


Basic protocol
==============

The actors in the basic optimization scheme are the master process and
the worker processes.  Each process transitions through a set of
states over the course of the optimization.  


Worker state machine
--------------------

.. graphviz::

   digraph worker_states {
       "start" -> "idle";
       "idle" -> "computing";
       "computing" -> "idle";
       "idle" -> "idle";
       "computing" -> "computing";
       "computing" -> "done";
   }

For the worker, the basic states are:

*start*
  The worker that has just come online.

*idle*
  The worker is waiting for the master to request a function
  evaluation.

*computing*
  The worker is currently working on a function evaluation.

*crashed*
  The worker failed (e.g. the node failed or a function evaluation
  crashed).

*done*
  The worker finished cleanly.

Master state machine
--------------------

.. graphviz::

   digraph worker_states {
       "start" -> "initial";
       "initial" -> "refine";
       "refine" -> "finishing";
       "finishing" -> "done";
       "initial" -> "initial";
   }


The states at the master are at least:

*start*
  The master has just come online.

*initial*
  The master is in the process of gathering an initial set of function
  values from which to build a response surface.

*refine*
  The master is gathering extra function evaluations in order to
  refine the response surface.

*finishing*
  The master is waiting for any intermediate results from workers
  before making its final determination of the anticipated optimum.

*done*
  The master finished cleanly.

State transitions at the master and at the workers occur based on
events, such as the completion of a function evaluation, the firing of
a timer, or the receipt of a message.  The basic transitions at the
worker are:

1. *start* to *idle* : After any initial startup, the worker contacts
   the master to request work and transitions to *idle*.

2. *idle* to *computing* : This transition occurs when the worker
   receives an evaluation request from the master.

3. *computing* to *idle* : When the worker finishes an evaluation, it
   sends the function value and a request for more work to the master,
   then returns to the idle state.

4. *computing* to *idle* : When the master sends a request to a worker
   to terminate a function evaluation, the worker sends any
   intermediate results to the master, along with a request for more
   work, then returns to the idle state.

5. *computing* to *computing* : In the computing state, the worker
   will periodically (based on timer events or progress through the
   simulation) send intermediate results to the master.  The nature of
   these intermediate results depends on the computation, and may be
   as simple as a heartbeat that lets the master know that the worker
   is still computing and has not crashed.

6. *idle* or *computing* to *done* : When the worker receives a shutdown
   request, it transitions to the done state and cleans up.

7. *idle* or *computing* to *crashed* : We suppose that a worker may
   fail, either during a function evaluation or in the idle state.
   This failure could come from a system event or from a failure of
   the function evaluation.  In this state, we assume the worker is
   incapable of sending messages; but if the master determines that a
   worker has crashed, the master may be able to shut down the worker.

The basic transitions at the master are:

1. *start* to *initial* : After the master starts up, it computes an
   initial experimental design, then transitions to the *initial*
   state.  This design comprises a set of points where the function
   value is desired, a priority for those function values, and a
   criterion for deciding when enough data has been received to declare
   the initial round of experiments complete.

2. *initial* to *initial* : In the *initial* state, the master may
   receive work requests from the worker.  Assuming that the initial
   experiments incomplete, the master will send points from
   the initial design and return to the *initial* state.

3. *initial* to *initial* : When the master receives a new result
   during the initial phase, it checks whether enough data has been
   received to move on to the next phase.  If not, it returns to the
   *initial* state.

4. *initial* to *refine* : When the master receives a new function
   value and determines enough data has been received, it moves to the
   *refine* phase.

5. *refine* to *refine* : When the master receives a work request
   during the *refine* state, it chooses a new point based both on how
   informative the point will be (based on how close it is to other
   prior or pending evaluation points) and how promising the point is
   (based on the value of the response surface).

6. *refine* to *refine* : When the master receives a new function
   value in the *refine* state, it incorporates that function value
   into the response surface.

7. *refine* to *done* : This transition occurs when the master reaches
   a termination criterion, whether it is based on the best function
   value, the number of function evaluations requested, or some
   measure of resources spent.  We currently do not allow termination
   during the initial set of experiments.

In this framework, the master and the worker interact through the
exchange of messages.  Messages from the worker to the master are:

*work request*
  When a worker first comes online, or when it becomes idle, it sends
  a work request to the master.

*intermediate result*
  A worker may send intermediate results during the computation, with
  lower bounds, upper bounds, or rough approximate solutions.  If
  there is no appropriate intermediate estimate of the function value,
  an intermediate result message may also be sent as a heartbeat to
  inform the master that the worker has not crashed and is continuing
  to make progress.

*result ready*
  If a function evaluation runs to successful completion, the worker
  sends the result to the master.

*failure notification* 
  If a simulation fails, the worker may send a failure notification to
  the master.  If the worker suffers a more catastrophic failure and
  cannot notify the master directly, the master may notice a failure
  by monitoring a heartbeat.

Messages from the master to the worker are:

*start evaluation*
  This message is sent in response to a work request from a worker.

*terminate evaluation*
  This message informs the worker that it should terminate a function
  evaluation in progress.

*shutdown*
  This message informs the worker that the master is ready to
  terminate the optimization, and the worker should shut down.


Optimization simulation
=======================

To systematically study how variability in function evaluation time
affects asynchronous parallel optimization, we use a discrete event
simulation framework.  Message transmission and receipt, heartbeats,
intermediate result production, and final result computation are all
represented as time-stamped events in a simulation event queue.

.. automodule:: poap.strategy
   :members:
   :undoc-members:

