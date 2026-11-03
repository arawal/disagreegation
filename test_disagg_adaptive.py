"""Offline tests for the refinement logic using a synthetic field."""

import unittest

import disagg_adaptive as da


class FakeGrid:
    def __init__(self, nx, ny):
        self.nx, self.ny = nx, ny
        self.index = {(i, j): (str(i), str(j)) for i in range(nx) for j in range(ny)}

    def cell_has_points(self, i0, j0, i1, j1):
        return True


def truth(i, j):
    """Two regimes with a diagonal boundary; R drifts 0.9 km per step like a real distance."""
    if i + j < 40:
        return 7.75, 550.0 + 0.9 * (i + j)
    return 4.9, 10.0 + 0.9 * i


class RefineTest(unittest.TestCase):
    def run_refine(self, nx=37, ny=37, cell=12):
        grid = FakeGrid(nx, ny)
        calls = []
        cache = {}

        def fetch_many(ijs):
            # behaves like ServiceOracle: only uncached points cost a call
            for ij in ijs:
                if ij not in cache:
                    calls.append(ij)
                    cache[ij] = truth(*ij)
            return {ij: cache[ij] for ij in ijs}

        result = da.refine(grid, fetch_many, cell, 0.1, 5.0, log=lambda *a: None)
        return grid, result, calls

    def test_every_point_resolved_within_tolerance(self):
        grid, result, _ = self.run_refine()
        self.assertEqual(len(result), grid.nx * grid.ny)
        for (i, j), (mw, r, kind) in result.items():
            t_mw, t_r = truth(i, j)
            self.assertAlmostEqual(mw, t_mw, delta=0.1, msg=f"Mw at {(i, j)} {kind}")
            self.assertAlmostEqual(r, t_r, delta=5.0, msg=f"R at {(i, j)} {kind}")

    def test_far_fewer_calls_than_points(self):
        grid, result, calls = self.run_refine(nx=97, ny=97)
        self.assertEqual(len(calls), len(set(calls)), "no point fetched twice")
        print(f"\n  {len(calls)} calls for {grid.nx * grid.ny} points")
        self.assertLess(len(calls), 0.3 * grid.nx * grid.ny)

    def test_sampled_points_keep_exact_values(self):
        _, result, calls = self.run_refine()
        for ij in calls:
            mw, r, kind = result[ij]
            self.assertEqual(kind, "sampled")
            self.assertEqual((mw, r), truth(*ij))

    def test_split_even_and_odd(self):
        self.assertEqual(len(da.split(0, 0, 12, 12, 12)), 4)
        self.assertEqual(len(da.split(0, 0, 3, 3, 3)), 9)
        self.assertEqual(da.split(0, 0, 1, 1, 1), [(0, 0, 1)])

    def test_grid_edge_cells_are_clamped(self):
        grid, result, _ = self.run_refine(nx=27, ny=15, cell=12)
        self.assertEqual(len(result), 27 * 15)


if __name__ == "__main__":
    unittest.main()
