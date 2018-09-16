#!/bin/bash
set -x -e
git clone git@github.com:iodide-project/pyodide-demo
cp build/* pyodide-demo
cd pyodide-demo
git checkout --orphan tmp
git add *
git config --global user.email "deploybot@nowhere.com"
git config --global user.name "Deploybot"
git commit -m "Deployed from Circle-CI $CIRCLE_BUILD_NUM"
git checkout master
git reset --hard tmp
git push origin -f master
