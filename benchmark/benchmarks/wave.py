# from https://github.com/sklam/numba-example-wavephysics
# setup: N=100
# run: wave(N)
import numpy as np


def physics(masspoints, dt, plunk, which):
    ppos = masspoints[1]
    cpos = masspoints[0]
    N = cpos.shape[0]
    # apply hooke's law
    HOOKE_K = 2100000.
    DAMPING = 0.0001
    MASS = .01

    force = np.zeros((N, 2))
    for i in range(1, N):
        dx, dy = cpos[i] - cpos[i - 1]
        dist = np.sqrt(dx**2 + dy**2)
        assert dist != 0
        fmag = -HOOKE_K * dist
        cosine = dx / dist
        sine = dy / dist
        fvec = np.array([fmag * cosine, fmag * sine])
        force[i - 1] -= fvec
        force[i] += fvec

    force[0] = force[-1] = 0, 0
    force[which][1] += plunk
    accel = force / MASS

    # verlet integration
    npos = (2 - DAMPING) * cpos - (1 - DAMPING) * ppos + accel * (dt**2)

    masspoints[1] = cpos
    masspoints[0] = npos

# pythran export wave(int)


def wave(PARTICLE_COUNT):
    SUBDIVISION = 300
    FRAMERATE = 60
    count = PARTICLE_COUNT
    width, height = 1200, 400

    masspoints = np.empty((2, count, 2), np.float64)
    initpos = np.zeros(count, np.float64)
    for i in range(1, count):
        initpos[i] = initpos[i - 1] + float(width) / count
    masspoints[:, :, 0] = initpos
    masspoints[:, :, 1] = height / 2
    f = 15
    plunk_pos = count // 2
    physics(masspoints, 1. / (SUBDIVISION * FRAMERATE), f, plunk_pos)
    return masspoints[0, count // 2]
