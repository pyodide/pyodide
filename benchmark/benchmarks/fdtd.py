# http://stackoverflow.com/questions/19367488/converting-function-to-numbapro-cuda
# setup: N = 10 ; import numpy ; a = numpy.random.rand(N,N)
# run: fdtd(a,10)

# pythran export fdtd(float[][], int)
import numpy as np


def fdtd(input_grid, steps):
    grid = input_grid.copy()
    old_grid = np.zeros_like(input_grid)
    previous_grid = np.zeros_like(input_grid)

    l_x = grid.shape[0]
    l_y = grid.shape[1]

    for i in range(steps):
        np.copyto(previous_grid, old_grid)
        np.copyto(old_grid, grid)

        for x in range(l_x):
            for y in range(l_y):
                grid[x, y] = 0.0
                if 0 < x + 1 < l_x:
                    grid[x, y] += old_grid[x + 1, y]
                if 0 < x - 1 < l_x:
                    grid[x, y] += old_grid[x - 1, y]
                if 0 < y + 1 < l_y:
                    grid[x, y] += old_grid[x, y + 1]
                if 0 < y - 1 < l_y:
                    grid[x, y] += old_grid[x, y - 1]

                grid[x, y] /= 2.0
                grid[x, y] -= previous_grid[x, y]

    return grid
