# @app.command("create")
# def _create(
#     path: Path = typer.Argument(
#         DIRNAME, help="path to cross-build environment directory"
#     ),
#     root: Path = typer.Option(
#         None, help="path to pyodide root directory, if not given, will be inferred"
#     ),
#     skip_missing_files: bool = typer.Option(
#         False,
#         help="skip if cross build files are missing instead of raising an error. This is useful for testing.",
#     ),
# ) -> None:
#     """
#     Create cross-build environment.

#     The create environment is then used to cross-compile packages out-of-tree.
#     Note: this is a private endpoint that should not be used outside of the Pyodide Makefile.
#     """

#     create(path, pyodide_root=root, skip_missing_files=skip_missing_files)
#     typer.echo(f"Pyodide cross-build environment created at {path.resolve()}")


# def test_xbuildenv_create(selenium, tmp_path):
#     # selenium fixture is added to ensure that Pyodide is built... it's a hack
#     from conftest import package_is_built

#     envpath = Path(tmp_path) / ".xbuildenv"
#     result = runner.invoke(
#         xbuildenv.app,
#         [
#             "create",
#             str(envpath),
#             "--skip-missing-files",
#         ],
#     )
#     assert result.exit_code == 0, result.stdout
#     assert "cross-build environment created at" in result.stdout
#     assert (envpath / "xbuildenv").exists()
#     assert (envpath / "xbuildenv" / "pyodide-root").is_dir()
#     assert (envpath / "xbuildenv" / "site-packages-extras").is_dir()
#     assert (envpath / "xbuildenv" / "requirements.txt").exists()

#     if not package_is_built("scipy"):
#         # creating xbuildenv without building scipy will raise error
#         result = runner.invoke(
#             xbuildenv.app,
#             [
#                 "create",
#                 str(tmp_path / ".xbuildenv"),
#             ],
#         )
#         assert result.exit_code != 0, result.stdout
#         assert isinstance(result.exception, FileNotFoundError), result.exception