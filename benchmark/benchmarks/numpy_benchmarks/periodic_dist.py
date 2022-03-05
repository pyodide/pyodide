# setup: import numpy as np ; N = 20 ; x = y = z = np.arange(0., N, 0.1) ; L = 4 ; periodic = True  # noqa
# run: periodic_dist(x, x, x, L,periodic, periodic, periodic)

# pythran export periodic_dist(float [], float[], float[], int, bool,
# bool, bool)
import numpy as np


def periodic_dist(x, y, z, L, periodicX, periodicY, periodicZ):
    """Computes distances between all particles and places the result
    in a matrix such that the ij th matrix entry corresponds to the
    distance between particle i and j"""
    N = len(x)
    xtemp = np.tile(x, (N, 1))
    dx = xtemp - xtemp.T
    ytemp = np.tile(y, (N, 1))
    dy = ytemp - ytemp.T
    ztemp = np.tile(z, (N, 1))
    dz = ztemp - ztemp.T

    # Particles 'feel' each other across the periodic boundaries
    if periodicX:
        dx[dx > L / 2] = dx[dx > L / 2] - L
        dx[dx < -L / 2] = dx[dx < -L / 2] + L

    if periodicY:
        dy[dy > L / 2] = dy[dy > L / 2] - L
        dy[dy < -L / 2] = dy[dy < -L / 2] + L

    if periodicZ:
        dz[dz > L / 2] = dz[dz > L / 2] - L
        dz[dz < -L / 2] = dz[dz < -L / 2] + L

    # Total Distances
    d = np.sqrt(dx**2 + dy**2 + dz**2)

    # Mark zero entries with negative 1 to avoid divergences
    d[d == 0] = -1

    return d, dx, dy, dz
