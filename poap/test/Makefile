export PYTHONPATH=../..:

dummy_sim: dummy_sim.c
	gcc -o $@ $<

.PHONY: test
test: dummy_sim
	python test_input_strategy.py
	python test_coroutine_strategy.py
	python test_fixed_strategy.py
	python test_maxterm_strategy.py
	python test_process_worker.py
	python test_simteam_controller.py
	python test_thread_controller.py
	python test_thread_strategy.py
