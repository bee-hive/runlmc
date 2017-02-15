import os
import logging
import sys

import numpy as np
from standard_tester import *

from multiprocessing import Pool, cpu_count

from runlmc.models.lmc import LMC
from runlmc.kern.rbf import RBF
from runlmc.models.optimization import AdaDelta
from runlmc.models.gpy_lmc import GPyLMC

from runlmc.models.lmc import _LOG
from runlmc.approx.iterative import _LOG as _LOG2
logging.getLogger().addHandler(logging.StreamHandler())
_LOG.setLevel(logging.INFO)
_LOG2.setLevel(logging.INFO)

np.random.seed(1234)

# the columns with nonzero test holdout are in test_fx
xss, yss, test_xss, test_yss, test_fx, cols = foreign_exchange_2007()

runs = 10

import os

with Pool(cpu_count()) as pool:
    workers = pool.starmap(os.getpid, [[] for _ in range(4 * cpu_count())])
    workers = set(workers)
    print(len(workers), 'distinct workers launched')

    # Nguyen 2014 COGP uses Q=2 R=1, but that is not LMC
    # Álvarez and Lawrence 2010 Convolved GP has R=4, sort of.
    # Álvarez and Lawrence 2010 find that vanilla LMC works best with Q=1 R=2
    # that is what we use here
    ks = [RBF(name='rbf0')]
    ranks = [2]
    llgp_time, llgp_smse, llgp_nlpd, lmc = runlmc(
        runs, None, xss, yss, test_xss, test_yss,
        ks, ranks, {'verbosity': 100}, extrapool=pool)
    print('llgp time', llgp_time, 'smse', llgp_smse, 'nlpd', llgp_nlpd)

cogp_time, cogp_smse, cogp_nlpd, _, _ = cogp_fx2007(runs)
print('cogp time', cogp_time, 'smse', cogp_smse, 'nlpd', cogp_nlpd)
