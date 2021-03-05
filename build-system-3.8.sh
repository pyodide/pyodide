#!/bin/bash
reset

# running in pyodide git tree from CI
if [ -d /home/runner/work/pyodide ]
then
    patch -p1 < build-system-3.8.diff
    mkdir -p /home/runner/work/pyodide/pyodide/packages/.artifacts/lib/python
else
    mkdir -p packages/.artifacts/lib/python
fi


# trouble with cross compilation or circular deps on a failed package
# most likely pkg that rely on egg decompression or include path redirection

# TODO incremental build of those
# regex failed once
PACKAGES="\
 kiwisolver\
 pandas setuptools glpk traits nlopt Jinja2 jedi autograd matplotlib cloudpickle docutils\
 networkx lxml pytest mpmath nltk bleach yt zarr cytoolz python-sat biopython\
 regex Pygments attrs numpy pillow webencodings\
 html5lib imageio joblib libiconv libxml libxslt xlrd asciitree beautifulsoup4\
 packaging cssselect patsy pluggy msgpack MarkupSafe more-itertools pyparsing decorator\
 CLAPACK pyodide-interrupts toolz uncertainties atomicwrites\
 numcodecs nose cycler soupsieve sympy freesasa\
 statsmodels\
 swiglpk optlang mne scipy pywavelets scikit-learn scikit-image astropy\
"



export HOSTPYTHON=$(command -v python3.8)
export PYTHON_FOR_BUILD=$HOSTPYTHON

mkdir -p bin
ln -sf $HOSTPYTHON ./bin/python
ln -sf $HOSTPYTHON ./bin/python3
ln -sf $HOSTPYTHON ./bin/python3.8

echo $PYTHON_FOR_BUILD > bin/PYTHON_FOR_BUILD

export PATH=$(pwd)/bin:$PATH

# clean packages
PYODIDE_PACKAGES="micropip,distlib,parso,pytz,python-dateutil,six,zlib,future,py" make


unset PYODIDE_PACKAGES

> FAILURES

for package in $PACKAGES
do
    echo "building $package ..."
    if PYODIDE_PACKAGES="$package" emmake make 2>&1 >/dev/null
    then
        echo "$package -> ok"
    else
        echo "$package" >> FAILURES
        echo "$package :  FAILED !"
        echo
    fi
done

echo
echo

cat FAILURES

# try to understand why this one fails
CC=emcc CXX=em++ PYODIDE_PACKAGES="kiwisolver" emmake make
