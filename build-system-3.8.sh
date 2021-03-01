#!/bin/bash
reset
patch -p1 < build-system-3.8.diff

# trouble with cross compilation or circular deps on a failed package
# most likely pkg that rely on egg decompression or include path redirection
echo "FAILED=swiglpk,optlang,mne,scipy,pywavelets,\
scikit-learn,scikit-image,\
astropy,\
"

export TESTING="statsmodels,"

# kiwisolver need cppyy unpacking

export EGGUNPACK="kiwisolver,"

export CIRCULAR="\
pandas,setuptools,glpk,traits,nlopt,\
Jinja2,jedi,autograd,matplotlib,cloudpickle,docutils,\
networkx,lxml,pytest,mpmath,nltk,bleach,yt,\
zarr,cytoolz,python-sat,biopython,\
"
# clean packages

export PYODIDE_PACKAGES="Pygments,attrs,numpy,pillow,six,zlib,webencodings,regex,six,\
future,html5lib,imageio,joblib,libiconv,libxml,libxslt,xlrd,asciitree,beautifulsoup4,\
micropip,packaging,parso,pytz,python-dateutil,cssselect,distlib,\
patsy,pluggy,msgpack,MarkupSafe,more-itertools,pyparsing,decorator,\
CLAPACK,pyodide-interrupts,toolz,uncertainties,atomicwrites,\
numcodecs,nose,cycler,soupsieve,sympy,freesasa,\
${EGGUNPACK}${CIRCULAR}${TESTING}py
"

export HOSTPYTHON=$(command -v python3.8)
export PYTHON_FOR_BUILD=$HOSTPYTHON

mkdir -p bin
ln -sf $HOSTPYTHON ./bin/python
ln -sf $HOSTPYTHON ./bin/python3
ln -sf $HOSTPYTHON ./bin/python3.8

PATH=$(pwd)/bin:$PATH make


