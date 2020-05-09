# Installing packages from PyPI

Pyodide has experimental support for installing pure Python wheels from PyPI.

For use in Iodide:

```
%% py
import micropip
micropip.install('snowballstemmer')

# Iodide implicitly waits for the promise to resolve when the packages have finished
# installing...

%% py
import snowballstemmer
stemmer = snowballstemmer.stemmer('english')
stemmer.stemWords('go goes going gone'.split())
```

For use outside of Iodide (just Python), you can use the `then` method on the
`Promise` that `micropip.install` returns to do work once the packages have
finished loading:

```
def do_work(*args):
  import snowballstemmer
  stemmer = snowballstemmer.stemmer('english')
  stemmer.stemWords('go goes going gone'.split())

import micropip
micropip.install('snowballstemmer').then(do_work)
```
