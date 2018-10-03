# setup: import numpy as np ; grid_shape = (512, 512) ; grid = np.zeros(grid_shape) ; block_low = int(grid_shape[0] * .4) ; block_high = int(grid_shape[0] * .5) ; grid[block_low:block_high, block_low:block_high] = 0.005  # noqa
# run: evolve(grid, 0.1)
# from: High Performance Python by Micha Gorelick and Ian Ozsvald,
# http://shop.oreilly.com/product/0636920028963.do

# pythran export evolve(float64[][], float)

import numpy as np


def laplacian(grid):
    return (np.roll(grid, +1, 0) + np.roll(grid, -1, 0)
            + np.roll(grid, +1, 1) + np.roll(grid, -1, 1) - 4 * grid)


def evolve(grid, dt, D=1):
    return grid + dt * D * laplacian(grid)
