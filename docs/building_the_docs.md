(building_the_docs)=
# Building the docs

From the directory ``docs``, first install the python dependencies with ``pip install -r requirements-doc.txt``. 
Then to build the docs run ``make html``.
The built documentation will be in the subdirectory ``docs/_build/html``. To view them, cd into ``_build/html`` and start a file server, 
for instance ``http-server``.