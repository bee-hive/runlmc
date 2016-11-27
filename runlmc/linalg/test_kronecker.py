# Copyright (c) 2016, Vladimir Feinberg
# Licensed under the BSD 3-clause license (see LICENSE)

from functools import reduce
import unittest

import numpy as np
import scipy.linalg

from .matrix import Matrix
from .kronecker import Kronecker
from .toeplitz import SymmToeplitz

class KroneckerTest(unittest.TestCase):

    def setUp(self):
        np.random.seed(1234)
        random = np.abs(np.hstack([np.random.rand(30), np.zeros(10)]))
        random[::-1].sort()
        random[0] += np.abs(random[1:]).sum()

        up = lambda x: np.diag(np.arange(x) + 1)
        down = lambda x: up(x)[::-1]

        self.examples = [
            [up(1), down(1)],
            [up(3), down(2)],
            [up(2), down(3)],
            [scipy.linalg.hilbert(3), scipy.linalg.hilbert(3)],
            [np.array([[2, 1], [0, 1]]), np.identity(2)],
            [np.random.randint(10, size=(2, 2)),
             np.random.randint(10, size=(3, 3))],
            [np.triu(np.ones((4, 4))), SymmToeplitz(np.arange(10)[::-1] + 1)],
            [SymmToeplitz(random), np.random.rand(5, 5)],
            [np.random.rand(100, 100), np.random.rand(5, 5)]]

        self.examples = [[self._symmetrize(x), self._symmetrize(y)]
                         for x, y in self.examples]

    @staticmethod
    def _symmetrize(x):
        if isinstance(x, Matrix):
            return x
        if np.allclose(np.triu(x), np.tril(x).T):
            return x
        return x + x.T

    @staticmethod
    def _generate(mats):
        my_kron = reduce(Kronecker, mats)
        mats = [scipy.linalg.toeplitz(x.top) if isinstance(x, SymmToeplitz)
                else x for x in mats]
        np_kron = reduce(np.kron, mats)
        return my_kron, np_kron

    def test_matvec(self):
        for mats in self.examples:
            my_kron, np_kron = self._generate(mats)
            x = np.arange(len(np_kron)) + 1
            np.testing.assert_allclose(my_kron.matvec(x), np_kron.dot(x))

    def test_eig(self):
        for mats in self.examples:
            my_kron, np_kron = self._generate(mats)
            tol = 1e-3
            np.testing.assert_allclose(my_kron.eig(tol), my_kron.eig(tol))

    def test_empty(self):
        empty = np.array([[]])
        one = np.array([[1]])
        self.assertRaises(ValueError, Kronecker, empty, one)
        self.assertRaises(ValueError, Kronecker, one, empty)
        self.assertRaises(ValueError, Kronecker, empty, empty)

    def test_type(self):
        class Dummy:
            shape = (1, 1)
        self.assertRaises(TypeError, Kronecker, Dummy(), np.array([[1]]))