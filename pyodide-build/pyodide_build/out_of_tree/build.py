import os

from .. import common, pypabuild, pywasmcross


from unearth.finder import PackageFinder,TargetPython
from tempfile import TemporaryDirectory
import shutil
from pathlib import Path

def fetch_pypi_package(package_spec,destdir):
    tp=TargetPython(py_ver=(3,10),platforms=['emscripten_2_0_27_wasm32'],abis='cp310')
    pf=PackageFinder(index_urls=['https://pypi.org/simple/'],target_python=tp)
    match=pf.find_best_match(package_spec)
    if match.best==None:
        if len(match.candidates)!=0:
            error=f"""Can't find version matching {package_spec}
versions found:
"""
            for c in match.candidates:
                error+="  "+c.version+"\n"
            raise RuntimeError(error)
        else:
            raise RuntimeError(f"Can't find package: {package_spec}")
    with TemporaryDirectory() as download_dir:
        return pf.download_and_unpack(link=match.best.link,location=destdir,download_dir=download_dir)

def run(exports, package,args):
    cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"

    curdir=Path.cwd()
    (curdir / "dist").mkdir(exist_ok=True)
    tmpdir=None
    temppath=None
    if len(package)>0:
        tmpdir=TemporaryDirectory()
        temppath=Path(tmpdir.name)
        # get package from pypi
        package_path=fetch_pypi_package(package,temppath)
        if package_path.is_dir()==False:
            # a wheel has been downloaded - just copy to dist folder
            shutil.copy( str(package_path),str(curdir / "dist"))
            return
        os.chdir(temppath)
    build_env_ctx = pywasmcross.get_build_env(
        env=os.environ.copy(),
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        exports=exports,
    )

    with build_env_ctx as env:
        pypabuild.build(env, " ".join(args))

    if temppath:
        for src in (temppath / "dist").iterdir():
            shutil.copy(str(src),str(curdir / "dist"))
    os.chdir(str(curdir))
