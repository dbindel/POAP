export PYTHONPATH=../..:

dummy_sim: dummy_sim.c
	gcc -o $@ $<

.PHONY: test testmpi
test: dummy_sim
	python test_strategies.py
	python test_input_strategy.py
	python test_coroutine_strategy.py
	python test_fixed_strategy.py
	python test_maxterm_strategy.py
	python test_process_worker.py
	python test_simteam_controller.py
	python test_thread_controller.py
	python test_thread_strategy.py
	python test_tcpserve.py

testmpi: dummy_sim
	mpirun -n 2 python mpi_silly.py
	mpirun -n 3 python test_mpiserve.py
	mpirun -n 3 python test_mpi_process_worker.py

.PHONY: pytest cover clean

pytest:
	py.test

cover:
	py.test --cov=.. --cov-report=annotate

clean:
	rm -f dummy_sim *.pyc
	rm -f *,cover ../*,cover
	rm -f *.log-*
