from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank == 1:
    data = {'a': 7, 'b': 3.14}
    comm.send(data, dest=0, tag=11)
elif rank == 0:
    data = comm.recv(source=1, tag=11)
    if data['a'] == 7:
        print("Success with simple MPI code.")
    else:
        print("Uh-oh")
