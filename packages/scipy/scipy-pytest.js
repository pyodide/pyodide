const { opendir } = require('node:fs/promises')
const { loadPyodide } = require('pyodide')

async function main() {
  let exit_code = 0
  try {
    global.pyodide = await loadPyodide()
    let pyodide = global.pyodide
    const FS = pyodide.FS
    const NODEFS = FS.filesystems.NODEFS

    let mountDir = '/mnt'
    pyodide.FS.mkdir(mountDir)
    pyodide.FS.mount(pyodide.FS.filesystems.NODEFS, { root: '.' }, mountDir)

    // Copy pytest-specific files dir if they exist
    await pyodide.runPythonAsync(`
       import shutil
       import os

       pytest_filenames = ["/mnt/conftest.py", "/mnt/pytest.ini"]

       for filename in pytest_filenames:
           if os.path.exists(filename):
               shutil.copy(filename, ".")

       conftest_filename = "/mnt/conftest.py"
       if os.path.exists(conftest_filename):
           shutil.copy(conftest_filename, ".")
    `)

    await pyodide.loadPackage(['micropip'])
    await pyodide.runPythonAsync(`
       import micropip

       await micropip.install('scipy')

       try:
           await micropip.install('scipy-tests')
       except ValueError:
           print('Hoping scipy tests are included in the scipy wheel')

       pkg_list = micropip.list()
       print(pkg_list)
    `)

    // XXX: some Fortran test modules are removed in Pyodide through a patch
    // https://github.com/pyodide/pyodide/blob/main/packages/scipy/patches/0008-Remove-test-modules-that-fails-to-build.patch
    // In order to avoid import errors during test discovery, we delete the
    // problematic files. There seems to be no simpler way to do this with
    // pytest, in particular --ignore-glob still imports the ignored file for
    // some reason.
    await pyodide.runPythonAsync(`
      from pathlib import Path

      import scipy.io.tests
      path = Path(scipy.io.tests.__file__).parent / "test_fortran.py"
      os.unlink(path)

      import scipy.integrate.tests
      path = Path(scipy.integrate.tests.__file__).parent / "test_odeint_jac.py"
      os.unlink(path)
    `)

    await pyodide.runPythonAsync(
      "import micropip; micropip.install(['pytest', 'hypothesis', 'pooch', 'lzma'])",
    )
    let pytest = pyodide.pyimport('pytest')
    let args = process.argv.slice(2)
    console.log('pytest args:', args)
    exit_code = pytest.main(pyodide.toPy(args))
  } catch (e) {
    console.error(e)
    // Arbitrary exit code here. I have seen this code reached instead of a
    // Pyodide fatal error sometimes (I guess kind of similar to a random
    // Python error). When there is a Pyodide fatal error we don't end up here
    // somehow, and the exit code is 7
    exit_code = 66
  } finally {
    process.exit(exit_code)
  }
}

main()
