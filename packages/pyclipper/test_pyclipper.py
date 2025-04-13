from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pyclipper"])
def test_pyclippertest(selenium):
    import pyclipper

    subj = (
        ((180, 200), (260, 200), (260, 150), (180, 150)),
        ((215, 160), (230, 190), (200, 190)),
    )
    clip = ((190, 210), (240, 210), (240, 130), (190, 130))
    pc = pyclipper.Pyclipper()
    pc.AddPath(clip, pyclipper.PT_CLIP, True)
    pc.AddPaths(subj, pyclipper.PT_SUBJECT, True)
    solution = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD)
    assert solution == [
        [[240, 200], [190, 200], [190, 150], [240, 150]],
        [[200, 190], [230, 190], [215, 160]],
    ]
