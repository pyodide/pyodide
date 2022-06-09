from functools import reduce

import pytest
from pyodide_test_runner import run_in_pyodide

# Need to skip_refcount_check because we use matplotlib
DECORATORS = [
    pytest.mark.xfail_browsers(
        node="galpy loads matplotlib and there are no supported matplotlib backends on node"
    ),
    pytest.mark.skip_refcount_check,
]


def galpy_test_decorator(f):
    return reduce(lambda x, g: g(x), DECORATORS, f)


@galpy_test_decorator
@run_in_pyodide(
    packages=[
        "galpy",
    ]
)
def test_integrate(selenium):
    import numpy
    from galpy.orbit import Orbit
    from galpy.potential import MWPotential2014

    ts = numpy.linspace(0.0, 100.0, 1001)
    o = Orbit()
    o.integrate(ts, MWPotential2014)
    assert (
        numpy.fabs(numpy.std(o.E(ts)) / numpy.mean(o.E(ts))) < 1e-10
    ), "Orbit integration does not conserve energy"
    return None


@galpy_test_decorator
@run_in_pyodide(
    packages=[
        "galpy",
    ]
)
def test_actionAngle(selenium):
    import numpy
    from galpy.orbit import Orbit
    from galpy.potential import MWPotential2014

    ts = numpy.linspace(0.0, 100.0, 1001)
    o = Orbit()
    o.integrate(ts, MWPotential2014)
    all_os = o(ts)
    jrs = all_os.jr(pot=MWPotential2014)
    jzs = all_os.jz(pot=MWPotential2014)
    assert (
        numpy.fabs(numpy.std(jrs) / numpy.mean(jrs)) < 1e-4
    ), "Actions not conserved during orbit integration"
    assert (
        numpy.fabs(numpy.std(jzs) / numpy.mean(jzs)) < 1e-3
    ), "Actions not conserved during orbit integration"
    return None


@galpy_test_decorator
@run_in_pyodide(
    packages=[
        "galpy",
    ]
)
def test_isotropic_hernquist_sigmar(selenium):
    import numpy
    from galpy import potential
    from galpy.df import isotropicHernquistdf, jeans

    def check_sigmar_against_jeans(
        samp, pot, tol, beta=0.0, dens=None, rmin=None, rmax=None, bins=31
    ):
        """Check that sigma_r(r) obtained from a sampling agrees with that
        coming from the Jeans equation
        Does this by logarithmically binning in r between rmin and rmax"""
        vrs = (samp.vR() * samp.R() + samp.vz() * samp.z()) / samp.r()
        logrs = numpy.log(samp.r())
        if rmin is None:
            numpy.exp(numpy.amin(logrs))
        if rmax is None:
            numpy.exp(numpy.amax(logrs))
        w, e = numpy.histogram(
            logrs,
            range=(numpy.log(rmin), numpy.log(rmax)),
            bins=bins,
            weights=numpy.ones_like(logrs),
        )
        mv2, _ = numpy.histogram(
            logrs,
            range=(numpy.log(rmin), numpy.log(rmax)),
            bins=bins,
            weights=vrs**2.0,
        )
        samp_sigr = numpy.sqrt(mv2 / w)
        brs = numpy.exp((numpy.roll(e, -1) + e)[:-1] / 2.0)
        for ii, br in enumerate(brs):
            assert (
                numpy.fabs(
                    samp_sigr[ii] / jeans.sigmar(pot, br, beta=beta, dens=dens) - 1.0
                )
                < tol
            ), "sigma_r(r) from samples does not agree with that obtained from the Jeans equation"
        return None

    pot = potential.HernquistPotential(amp=2.3, a=1.3)
    dfh = isotropicHernquistdf(pot=pot)
    numpy.random.seed(10)
    samp = dfh.sample(n=300000)
    tol = 0.05
    check_sigmar_against_jeans(
        samp,
        pot,
        tol,
        beta=0.0,
        rmin=pot._scale / 10.0,
        rmax=pot._scale * 10.0,
        bins=31,
    )
    return None
