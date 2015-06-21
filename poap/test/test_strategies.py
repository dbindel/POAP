"""
.. module:: test_strategies
   :synopsis: Tests covering strategy module.
.. moduleauthor:: David Bindel <bindel@cornell.edu>
"""

from poap.controller import ScriptedController

from poap.strategy import FixedSampleStrategy
from poap.strategy import CoroutineStrategy
from poap.strategy import CoroutineBatchStrategy
from poap.strategy import PromiseStrategy
from poap.strategy import ThreadStrategy
from poap.strategy import CheckWorkerStrategy
from poap.strategy import SimpleMergedStrategy
from poap.strategy import MultiStartStrategy
from poap.strategy import MaxEvalStrategy
from poap.strategy import InputStrategy

import time


def test_fixed_sample1():
    "Check FixedStrategy in case of no kills or failures"
    c = ScriptedController()
    c.strategy = FixedSampleStrategy([1, 2, 3, 4])
    c.accept_eval(args=(1,)).complete(1)
    c.accept_eval(args=(2,)).complete(2)
    c.accept_eval(args=(3,)).complete(3)
    c.accept_eval(args=(4,)).complete(4)
    c.accept_terminate()
    c.terminate()


def test_fixed_sample2():
    "Check that FixedStrategy does retries and None proposals right"
    def run(strategy):
        c = ScriptedController()
        c.strategy = strategy
        r1 = c.accept_eval(args=(1,))
        r2 = c.accept_eval(args=(2,))
        c.reject_eval(args=(3,))
        r1.kill()
        r2.running()
        c.accept_eval(args=(3,)).complete(3)
        c.accept_eval(args=(1,)).complete(1)
        c.accept_eval(args=(4,)).complete(4)
        c.no_proposal()
        r2.complete(2)
        c.reject_terminate()
        c.accept_terminate()
        c.terminate()

    def g():
        for k in range(1, 5):
            yield k
    run(FixedSampleStrategy([1, 2, 3, 4]))
    run(FixedSampleStrategy(g()))


def coroutine_optimizer(pts):
    for p in pts:
        f = yield p
        assert f == p


def test_coroutine1():
    "Check coroutine strategy with immediate exit"
    c = ScriptedController()
    c.strategy = CoroutineStrategy(coroutine_optimizer([]))
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_coroutine2():
    "Check coroutine strategy for correct retry behavior"
    c = ScriptedController()
    c.strategy = CoroutineStrategy(coroutine_optimizer([1, 2, 3]))

    # Do we re-try a rejected proposal?
    c.reject_eval(args=(1,))
    r = c.accept_eval(args=(1,))
    c.no_proposal()
    r.complete(1)

    # Do we retry on kill?
    r = c.accept_eval(args=(2,))
    c.no_proposal()
    r.kill()
    r = c.accept_eval(args=(2,))
    r.running()
    c.no_proposal()
    r.complete(2)

    # And check the simple case where everything goes without incident
    c.accept_eval(args=(3,)).complete(3)
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def coroutine_batch_optimizer(batches):
    for b in batches:
        f = yield b
        assert f == b, "Expect {0}, saw {1}".format(b, f)


def test_coroutine_batch1():
    "Check coroutine batch strategy on immediate termination"
    c = ScriptedController()
    c.strategy = CoroutineBatchStrategy(coroutine_batch_optimizer([]))
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_coroutine_batch2():
    "Check coroutine batch strategy with empty list"
    c = ScriptedController()
    c.strategy = CoroutineBatchStrategy(coroutine_batch_optimizer([[]]))
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_coroutine_batch3():
    "Check coroutine batch strategy"
    c = ScriptedController()
    o = coroutine_batch_optimizer([[1, 2], [3, 4]])
    c.strategy = CoroutineBatchStrategy(o)

    # Make trouble for batch [1,2]
    c.reject_eval(args=(1,))
    c.reject_eval(args=(2,))
    r1 = c.accept_eval(args=(1,))
    r2 = c.accept_eval(args=(2,))
    c.no_proposal()
    r1.kill()
    c.accept_eval(args=(1,))
    r2.complete(2)
    c.no_proposal()
    r1.complete(1)

    # Let batch [3,4] go through without incident
    r = c.accept_eval(args=(3,))
    r.complete(3)
    r = c.accept_eval(args=(4,))
    r.complete(4)

    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_promise1():
    "Check promise batch strategy"
    c = ScriptedController()
    s = PromiseStrategy()
    c.strategy = s

    # Start promise and check not ready
    p = s.promise_eval(1)
    assert not p.ready()

    # Give the eval a hard time before completing
    c.reject_eval(args=(1,))
    r = c.accept_eval(args=(1,))
    r.kill()
    r = c.accept_eval(args=(1,))
    assert not p.ready()
    r.complete(1)

    # Check to make sure the value came through
    assert p.value == 1

    # Terminate
    s.terminate()
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def thread_optimizer(strategy, vs, v):
    assert vs == strategy.blocking_evals(vs)
    assert v == strategy.blocking_eval(v)


def test_thread1():
    "Check promise batch strategy"
    c = ScriptedController()
    c.strategy = ThreadStrategy(c, lambda s: thread_optimizer(s, [1, 2], 3))

    # Make some trouble for the first two points
    r1 = c.accept_eval(args=(1,), skip=True)
    c.reject_eval(args=(2,), skip=True)
    r2 = c.accept_eval(args=(2,), skip=True)
    c.no_proposal()
    r1.kill()
    r1 = c.accept_eval(args=(1,), skip=True)
    c.no_proposal()
    r1.complete(1)
    r2.complete(2)

    # Let the third proposal go through easy
    r3 = c.accept_eval(args=(3,), skip=True)
    c.no_proposal()
    r3.complete(3)

    # Reject two termination messages before we quit
    c.reject_terminate(skip=True)
    c.reject_terminate(skip=True)
    c.accept_terminate(skip=True)
    c.terminate()


def test_check_worker0():
    "Check: Without CheckWorkerStrategy, FixedStrategy ignores availability"
    c = ScriptedController()
    c.strategy = FixedSampleStrategy([1, 2])
    c.set_worker(False)
    r1 = c.accept_eval(args=(1,))
    r1.complete(1)
    r2 = c.accept_eval(args=(2,))
    r2.complete(2)
    c.accept_terminate()
    c.terminate()


def test_check_worker1():
    "Test CheckWorkerStrategy"
    c = ScriptedController()
    strategy = FixedSampleStrategy([1, 2])
    c.strategy = CheckWorkerStrategy(c, strategy)
    r1 = c.accept_eval(args=(1,))
    c.set_worker(False)
    r2 = c.no_proposal()
    r1.complete(1)
    c.set_worker(True)
    r2 = c.accept_eval(args=(2,))
    r2.complete(2)
    c.accept_terminate()
    c.terminate()


def test_simple_merge1():
    "Test SimpleMergeStrategy"
    c = ScriptedController()
    strategy1 = PromiseStrategy(block=False)
    strategy2 = FixedSampleStrategy([1, 2, 3])
    c.strategy = SimpleMergedStrategy(c, [strategy1, strategy2])

    # Allow strategy2 to get one in, then strategy1 pre-empts
    c.set_worker(False)
    c.no_proposal()
    c.set_worker(True)
    r1 = c.accept_eval(args=(1,))
    p = strategy1.promise_eval(100)
    r2 = c.accept_eval(args=(100,))
    r1.complete(1)
    assert not p.ready()
    r2.complete(100)
    assert p.value == 100
    strategy1.terminate()

    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_multistart1():
    "Test MultistartStrategy"
    c = ScriptedController()
    strategy1 = PromiseStrategy(block=False)
    strategy2 = FixedSampleStrategy([1, 2, 3])
    c.strategy = MultiStartStrategy(c, [strategy1, strategy2])

    # Allow strategy2 to get one in, then strategy1 pre-empts
    r1 = c.accept_eval(args=(1,))
    p = strategy1.promise_eval(100)
    time.sleep(0.1)
    r2 = c.accept_eval(args=(100,))
    r1.complete(1)
    assert not p.ready()
    r2.complete(100)
    assert p.value == 100
    strategy1.terminate()

    # Now strategy2 finishes
    c.accept_eval(args=(2,)).complete(2)
    c.accept_eval(args=(3,)).complete(3)

    # Now we should see termination
    c.reject_terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def test_maxeval1():
    "Test MaxEvalStrategy"
    c = ScriptedController()
    strategy1 = MaxEvalStrategy(c, 2)
    strategy2 = FixedSampleStrategy([1, 2, 3, 4, 5])
    c.strategy = SimpleMergedStrategy(c, [strategy1, strategy2])
    c.accept_eval(args=(1,)).complete(1)
    c.accept_eval(args=(2,)).complete(2)
    c.accept_terminate()
    c.terminate()


def test_input1():
    "Test InputStrategy"
    c = ScriptedController()
    strategy = FixedSampleStrategy([1, 2, 3])
    strategy = InputStrategy(c, strategy)
    c.strategy = strategy
    r = c.accept_eval(args=(1,))
    strategy.kill(r)
    c.accept_kill(r)
    r.kill()
    r = c.accept_eval(args=(1,))
    r.complete(1)
    strategy.eval(100)
    c.reject_eval(args=(100,))
    c.accept_eval(args=(100,)).complete(100)
    c.accept_eval(args=(2,)).complete(2)
    strategy.eval(101)
    r = c.accept_eval(args=(101,))
    strategy.kill(r)
    c.reject_kill(r)
    r.complete(101)
    strategy.terminate()
    c.reject_terminate()
    c.accept_terminate()
    c.terminate()


def main():
    test_fixed_sample1()
    test_fixed_sample2()
    test_coroutine1()
    test_coroutine2()
    test_coroutine_batch1()
    test_coroutine_batch2()
    test_coroutine_batch3()
    test_promise1()
    test_thread1()
    test_check_worker0()
    test_check_worker1()
    test_simple_merge1()
    test_multistart1()
    test_maxeval1()


if __name__ == "__main__":
    main()
