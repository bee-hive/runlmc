# Copyright (c) 2016, Vladimir Feinberg
# Licensed under the BSD 3-clause license (see LICENSE)

import numpy as np
import paramz.optimization
import scipy.linalg
import scipy.optimize
import scipy.spatial.distance

from .lmc import LMC
from ..kern.rbf import RBF
from ..util.testing_utils import RandomTest

class DerivFree(paramz.optimization.Optimizer):
    def __init__(self):
        super().__init__()

    def opt(self, x_init, f=None, **_):
        constraints = []
        self.x_opt = scipy.optimize.fmin_cobyla(f, x_init, constraints, disp=0)

class ExactAnalogue:
    def __init__(self, kerns, sizes, coregs):
        assert len(coregs) == len(kerns)
        assert set(map(len, coregs)) == {len(sizes)}
        self.kerns = kerns
        self.sizes = sizes
        self.coregs = coregs

        self.xss = [np.random.rand(sz) for sz in sizes]
        self.yss = [np.random.rand(sz) for sz in sizes]

    def gen_lmc(self, m):
        lmc = LMC(self.xss, self.yss, normalize=False, kernels=self.kerns, m=m)
        for lmc_coreg, coreg in zip(lmc.coreg_vecs, self.coregs):
            lmc_coreg[:] = coreg
        lmc.noise[:] = np.ones(len(self.sizes))
        return lmc

    def gen_exact_mat(self):
        exact_mat = np.identity(sum(self.sizes))
        for coreg, kern in zip(self.coregs, self.kerns):
            coreg_mat = np.outer(coreg, coreg)
            exact_mat += np.bmat(
                [[coreg_mat[i, j] *
                  self.pairwise_dists(kern, self.xss[i], self.xss[j])
                  for j in range(len(self.sizes))]
                 for i in range(len(self.sizes))]).A
        return exact_mat

    @staticmethod
    def pairwise_dists(kern, xs1, xs2):
        dists = scipy.spatial.distance.cdist(
            xs1.reshape(-1, 1), xs2.reshape(-1, 1))
        return kern.from_dist(dists).reshape(len(xs1), len(xs2))

class LMCTest(RandomTest):

    def setUp(self):
        super().setUp()

    @staticmethod
    def case_1d():
        kerns = [RBF(variance=2, inv_lengthscale=3)]
        szs = [15]
        coregs = [[1]]
        return ExactAnalogue(kerns, szs, coregs)

    @staticmethod
    def case_2d():
        kerns = [RBF(variance=2, inv_lengthscale=3),
                 RBF(variance=3, inv_lengthscale=2)]
        szs = [15, 20]
        coregs = [[1, 2], [3, 4]]
        return ExactAnalogue(kerns, szs, coregs)

    @staticmethod
    def case_large():
        kerns = [RBF(variance=2, inv_lengthscale=3),
                 RBF(variance=3, inv_lengthscale=2),
                 RBF(variance=1, inv_lengthscale=1)]
        szs = [15, 20, 10, 12, 13]
        coregs = [[1, 1, 1, 1, 2], [2, 1, 2, 1, 2], [-1, 1, -1, -1, -1]]
        return ExactAnalogue(kerns, szs, coregs)

    @staticmethod
    def avg_entry_diff(x1, x2):
        return np.fabs(x1 - x2).mean()

    def check_kernel_reconstruction(self, exact):
        actual = exact.gen_lmc(sum(exact.sizes)).K_SKI()
        exact_mat = exact.gen_exact_mat()
        np.testing.assert_allclose(
            exact_mat, actual, rtol=LMC.TOL, atol=LMC.TOL)
        avg_diff_sz = self.avg_entry_diff(exact_mat, actual)

        actual = exact.gen_lmc(sum(exact.sizes) * 2).K_SKI()
        np.testing.assert_allclose(
            exact_mat, actual, rtol=LMC.TOL, atol=LMC.TOL)
        avg_diff_2sz = self.avg_entry_diff(exact_mat, actual)

        self.assertGreater(avg_diff_sz, avg_diff_2sz)

    def check_normal_quadratic(self, exact):
        exact_mat = exact.gen_exact_mat()
        y = np.hstack(exact.yss)
        Kinv_y = np.linalg.solve(exact_mat, y)
        expected = y.dot(Kinv_y)

        lmc = exact.gen_lmc(sum(exact.sizes))
        lmc.TOL = 1e-15 # tighten tolerance for tests
        tol = 1e-4

        actual = lmc.normal_quadratic()
        np.testing.assert_allclose(expected, actual, rtol=tol, atol=tol)

    def test_no_kernel(self):
        mapnp = lambda x: list(map(np.array, x))
        basic_Xs = mapnp([[0, 1, 2], [0.5, 1.5, 2.5]])
        basic_Ys = mapnp([[5, 6, 7], [7, 6, 5]])
        self.assertRaises(ValueError, LMC,
                          basic_Xs, basic_Ys, kernels=[])

    def test_kernel_reconstruction_1d(self):
        ea = self.case_1d()
        self.check_kernel_reconstruction(ea)

    def test_kernel_reconstruction_2d(self):
        ea = self.case_2d()
        self.check_kernel_reconstruction(ea)

    def test_kernel_reconstruction_large(self):
        ea = self.case_large()
        self.check_kernel_reconstruction(ea)

    def test_normal_quadratic_1d(self):
        ea = self.case_1d()
        self.check_normal_quadratic(ea)

    def test_normal_quadratic_2d(self):
        ea = self.case_2d()
        self.check_normal_quadratic(ea)

    def test_normal_quadratic_large(self):
        ea = self.case_large()
        self.check_normal_quadratic(ea)

    # TODO compare raw_predict to SKI exact matrix
    # Eq. 7 in Sec. 5.1.1 in MSGP

    def test_1d_fit(self):
        ea = self.case_1d()
        noise = np.random.randn(len(ea.xss)) * 0.05
        ea.yss = [np.sin(ea.xss[0]) + noise]
        lmc = ea.gen_lmc(sum(ea.sizes))

        ll_before = lmc.log_likelihood()
        lmc.optimize(optimizer=DerivFree())
        ll_after = lmc.log_likelihood()

        self.assertGreater(ll_after, ll_before)

        # TODO reconstruction should be within max(noise) + 2 * tol + delta
        # test at xss + delta shifted

    def test_2d_fit(self):
        ea = self.case_2d()
        noises = [0.05 * np.random.randn(len(ea.xss[0])),
                  0.02 * np.random.randn(len(ea.xss[1]))]
        ea.yss = [np.sin(ea.xss[0]) + noises[0],
                  np.sin(ea.xss[1]) + noises[1]]
        lmc = ea.gen_lmc(sum(ea.sizes))

        ll_before = lmc.log_likelihood()
        lmc.optimize(optimizer=DerivFree())
        ll_after = lmc.log_likelihood()

        self.assertGreater(ll_after, ll_before)

        # TODO reconstruction, again.

    # TODO: test_coreg_nocov - requires rank 2, single kernel, l1 prior
    #       on coreg (should find identity matrix approx coregionalization
    #       after a couple random restarts (choose l2 err minimizing one,
    #       on data with no noise).
    # TODO: same as above, but find the covariance. (check we don't go to the
    #       identity)
