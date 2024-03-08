import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture(scope="function")
def selenium_sdl(selenium_standalone):
    if selenium_standalone.browser == "node":
        pytest.skip("No document object")

    selenium_standalone.run_js(
        """
        var sdl2Canvas = document.createElement("canvas");
        sdl2Canvas.id = "canvas";

        document.body.appendChild(sdl2Canvas);
        pyodide.canvas.setCanvas2D(sdl2Canvas);
        """
    )
    yield selenium_standalone


@run_in_pyodide(packages=["pygame-ce"])
def test_init(selenium_sdl):
    import pygame.display

    pygame.display.init()


@pytest.mark.driver_timeout(300)
@run_in_pyodide(packages=["pygame-ce", "pygame-ce-tests", "pytest"])
def test_run_tests(selenium_sdl):
    import os
    from pathlib import Path

    import pygame
    import pytest

    if "CI" in os.environ:
        pytest.skip("Skipped in CI (takes too long to run)")

    test_path = Path(pygame.__file__).parent / "tests"

    def runtest(test_filter, ignore_filters):
        ignore_filter = []
        for ignore in ignore_filters:
            ignore_filter.append("--ignore-glob")
            ignore_filter.append(ignore)

        ret = pytest.main(
            [
                "--pyargs",
                str(test_path),
                "--continue-on-collection-errors",
                "-v",
                *ignore_filter,
                "-k",
                test_filter,
            ]
        )
        assert ret == 0

    runtest(
        (
            "not test_init "  # Mix_QuerySpec
            "and not test_quit__and_init "  # Mix_QuerySpec
            "and not test_print_debug "  # Mix_Linked_Version
            "and not FullscreenToggleTests "  # hangs
            "and not TimeModuleTest "  # NotImplementedError: set_timer is not implemented on WASM yet
            "and not thread "  # threading
            "and not iconify "  # not supported
            "and not caption "  # doesn't work
            "and not set_gamma "  # doesn't work
            "and not DisplayUpdateInteractiveTest "  # cannot block
            "and not test_get_flags__display_surf "  # doesn't work (gfx?)
            "and not test_toggle_fullscreen "  # not supported
            "and not test_set_icon_interactive "  # cannot block
            "and not opengl "  # opengl
            "and not MessageBoxInteractiveTest "  # No message system available
            "and not test_gaussian_blur "  # tiff format
            "and not test_box_blur  "  # tiff format
            "and not test_blur_in_place "  # tiff format
            "and not deprecation "
            "and not test_save_tga "  # tga
            "and not test_save_pathlib "  # tga
            "and not test_load_sized_svg "  # svg
            "and not test_load_extended "  # svg
            "and not test_rotozoom_keeps_colorkey "  # surface (gfx?)
            "and not test_format_newbuf "  # surface (gfx?)
            "and not test_save_to_fileobject "  # tga
            "and not test_magic "  # no fixture
            "and not test_load_non_string_file "  # can't access resource on platform
            "and not test_save__to_fileobject_w_namehint_argument "  # can't access resource on platform (tga)
            "and not testLoadBytesIO "  # can't access resource on platform
            "and not VisualTests "  # cannot block
            "and not test_load_from_invalid_sized_file_obj "  # can't access resource on platform
        ),
        # Following tests are ignored
        [
            test_path / "sndarray_test.py",  # numpy
            test_path / "surfarray_test.py",  # numpy
            test_path / "midi_test.py",  # pygame.pypm not supported
            test_path / "mixer_test.py",  # lots of TODOs in mixer module
            test_path / "mixer_music_test.py",  # lots of TODOs in mixer module
            test_path / "window_test.py",  # signature mismatch
            test_path / "threads_test.py",  # threads
            test_path / "joystick_test.py",  # nonsense
            test_path / "scrap_test.py",  # clipboard
            test_path / "docs_test.py",  # document removed to reduce size
            test_path / "touch_test.py",  # touch
            test_path / "gfxdraw_test.py",  # doesn't work (FIXME)
            test_path
            / "event_test.py",  # NotImplementedError: set_timer is not implemented on WASM yet
            test_path / "mouse_test.py",  # freetype does not work (FIXME)
            test_path / "freetype_test.py",  # freetype does not work (FIXME)
            test_path / "ftfont_test.py",  # freetype does not work (FIXME)
            test_path / "video_test.py",  # signature mismatch
        ],
    )
