from poap.controller import ScriptedController

# from poap.strategy import RetryStrategy
from poap.strategy import FixedSampleStrategy
from poap.strategy import CoroutineStrategy
from poap.strategy import CoroutineBatchStrategy
# from poap.strategy import ThreadStrategy
# from poap.strategy import OptimizerThread
# from poap.strategy import CheckWorkerStrategy
# from poap.strategy import SimpleMergedStrategy
# from poap.strategy import MultiStartStrategy
# from poap.strategy import MaxEvalStrategy
# from poap.strategy import InputStrategy


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
        c.accept_eval(args=(1,)).complete(1)
        c.accept_eval(args=(3,)).complete(3)
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
    c.reject_eval(args=(2,))
    r1 = c.accept_eval(args=(2,))
    c.reject_eval(args=(1,))
    r2 = c.accept_eval(args=(1,))
    c.no_proposal()
    r1.kill()
    c.accept_eval(args=(2,))
    r2.complete(1)
    c.no_proposal()
    r1.complete(2)

    # Let batch [3,4] go through without incident
    r = c.accept_eval(args=(4,))
    r.complete(4)
    r = c.accept_eval(args=(3,))
    r.complete(3)

    c.reject_terminate()
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


if __name__ == "__main__":
    main()
