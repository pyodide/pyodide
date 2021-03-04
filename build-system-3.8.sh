#!/bin/bash
reset

# running in pyodide git tree from CI
if [ -d /home/runner/work ]
then
    patch -p1 < build-system-3.8.diff
    mkdir -p /home/runner/work/pyodide/pyodide/packages/.artifacts/lib/python
fi


# trouble with cross compilation or circular deps on a failed package
# most likely pkg that rely on egg decompression or include path redirection
echo "FAILED=swiglpk,optlang,mne,scipy,pywavelets,\
scikit-learn,scikit-image,\
astropy,\
"

TESTING="statsmodels,"

# kiwisolver need cppyy unpacking

EGGUNPACK="kiwisolver,"

CIRCULAR="\
pandas,setuptools,glpk,traits,nlopt,\
Jinja2,jedi,autograd,matplotlib,cloudpickle,docutils,\
networkx,lxml,pytest,mpmath,nltk,bleach,yt,\
zarr,cytoolz,python-sat,biopython,\
"


# clean packages

MINIMAL="micropip,distlib,parso,pytz,python-dateutil,six,zlib,future,"

# regex failed once

FULL="${MINIMAL},regex,Pygments,attrs,numpy,pillow,webencodings,\
html5lib,imageio,joblib,libiconv,libxml,libxslt,xlrd,asciitree,beautifulsoup4,\
packaging,cssselect,patsy,pluggy,msgpack,MarkupSafe,more-itertools,pyparsing,decorator,\
CLAPACK,pyodide-interrupts,toolz,uncertainties,atomicwrites,\
numcodecs,nose,cycler,soupsieve,sympy,freesasa,\
"

# TODO incremental build of those
# ${MINIMAL}${EGGUNPACK}${CIRCULAR}${TESTING}py


export PYODIDE_PACKAGES="micropip,${MINIMAL}py"

export HOSTPYTHON=$(command -v python3.8)
export PYTHON_FOR_BUILD=$HOSTPYTHON

mkdir -p bin
ln -sf $HOSTPYTHON ./bin/python
ln -sf $HOSTPYTHON ./bin/python3
ln -sf $HOSTPYTHON ./bin/python3.8

echo $PYTHON_FOR_BUILD > bin/PYTHON_FOR_BUILD

PATH=$(pwd)/bin:$PATH make


