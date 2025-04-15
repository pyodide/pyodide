from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pymupdf"])
def test_textbox1(selenium):
    """Use TextWriter for text insertion."""
    import pymupdf

    sample_text = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed ante tellus, volutpat id lorem sit amet, blandit ultrices odio. Donec consectetur lacus massa, eu various felis hendrerit ac. Phasellus vitae lorem est.

Aliquam finibus finibus massa, ac dictum nibh bibendum id. Phasellus vel arcu vel urna convallis hendrerit id rutrum lectus. Ut sapien massa, egestas a turpis ut, finibus bibendum magna.

Proin venenatis, enim eu pellentesque maximus, mauris lectus elementum tellus, ut scelerisque nisl neque non tortor. Mauris nisl nunc, viverra vel nunc non, dignissim tempor nunc.

Curabitur volutpat magna ullamcorper urna faucibus, vitae dictum ante malesuada. Aliquam dapibus elit a magna pretium, id hendrerit nisl imperdiet. Cras vel augue odio.

Mauris eu facilisis ligula. Mauris sit amet feugiat ligula. Nulla bibendum fringilla tempor. Curabitur id orci vel lectus eleifend eleifend. Ut mi purus, fermentum et egestas et, vestibulum eget tortor. Etiam quis blandit augue."""

    doc = pymupdf.open()
    page = doc.new_page()
    rect = pymupdf.Rect(50, 50, 400, 400)
    blue = (0, 0, 1)
    tw = pymupdf.TextWriter(page.rect, color=blue)
    tw.fill_textbox(
        rect,
        sample_text,
        align=pymupdf.TEXT_ALIGN_LEFT,
        fontsize=12,
    )
    tw.write_text(page, morph=(rect.tl, pymupdf.Matrix(1, 1)))
    # check text containment
    assert page.get_text() == page.get_text(clip=rect)
    page.write_text(writers=tw)


@run_in_pyodide(packages=["pymupdf"])
def test_textbox2(selenium):
    """Use basic text insertion."""
    import pymupdf

    sample_text = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed ante tellus, volutpat id lorem sit amet, blandit ultrices odio. Donec consectetur lacus massa, eu various felis hendrerit ac. Phasellus vitae lorem est.

Aliquam finibus finibus massa, ac dictum nibh bibendum id. Phasellus vel arcu vel urna convallis hendrerit id rutrum lectus. Ut sapien massa, egestas a turpis ut, finibus bibendum magna.

Proin venenatis, enim eu pellentesque maximus, mauris lectus elementum tellus, ut scelerisque nisl neque non tortor. Mauris nisl nunc, viverra vel nunc non, dignissim tempor nunc.

Curabitur volutpat magna ullamcorper urna faucibus, vitae dictum ante malesuada. Aliquam dapibus elit a magna pretium, id hendrerit nisl imperdiet. Cras vel augue odio.

Mauris eu facilisis ligula. Mauris sit amet feugiat ligula. Nulla bibendum fringilla tempor. Curabitur id orci vel lectus eleifend eleifend. Ut mi purus, fermentum et egestas et, vestibulum eget tortor. Etiam quis blandit augue."""

    doc = pymupdf.open()
    ocg = doc.add_ocg("ocg1")
    page = doc.new_page()
    rect = pymupdf.Rect(50, 50, 400, 400)
    blue = pymupdf.utils.getColor("lightblue")
    _ = pymupdf.utils.getColorHSV("red")
    page.insert_textbox(
        rect,
        sample_text,
        align=pymupdf.TEXT_ALIGN_LEFT,
        fontsize=12,
        color=blue,
        oc=ocg,
    )
    # check text containment
    assert page.get_text() == page.get_text(clip=rect)


@run_in_pyodide(packages=["pymupdf"])
def test_htmlbox(selenium):
    """Write HTML-styled text into a rect with different rotations.

    The text is styled and contains a link.
    Then extract the text again, and
    - assert that text was written in the 4 different angles,
    - assert that text properties are correct (bold, italic, color),
    - assert that the link has been correctly inserted.

    We try to insert into a rectangle that is too small, setting
    scale=False and confirming we have a negative return code.
    """
    import pymupdf

    if not hasattr(pymupdf, "mupdf"):
        print("'test_htmlbox1' not executed in classic.")
        return

    rect = pymupdf.Rect(100, 100, 200, 200)  # this only works with scale=True

    base_text = """Lorem ipsum dolor sit amet, consectetur adipisici elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquid ex ea commodi consequat. Quis aute iure reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint obcaecat cupiditat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."""

    text = """Lorem ipsum dolor sit amet, consectetur adipisici elit, sed eiusmod tempor incidunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation <b>ullamco</b> <i>laboris</i> nisi ut aliquid ex ea commodi consequat. Quis aute iure reprehenderit in <span style="color: #0f0;font-weight:bold;">voluptate</span> velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint obcaecat cupiditat non proident, sunt in culpa qui <a href="https://www.artifex.com">officia</a> deserunt mollit anim id est laborum."""

    doc = pymupdf.Document()

    for rot in (0, 90, 180, 270):
        wdirs = ((1, 0), (0, -1), (-1, 0), (0, 1))  # all writing directions
        page = doc.new_page()
        spare_height, scale = page.insert_htmlbox(rect, text, rotate=rot, scale_low=1)
        assert spare_height < 0
        assert scale == 1
        spare_height, scale = page.insert_htmlbox(rect, text, rotate=rot, scale_low=0)
        assert spare_height == 0
        assert 0 < scale < 1
        page = doc.reload_page(page)
        link = page.get_links()[0]  # extracts the links on the page

        assert link["uri"] == "https://www.artifex.com"

        # Assert plain text is complete.
        # We must remove line breaks and any ligatures for this.
        assert base_text == page.get_text(flags=0)[:-1].replace("\n", " ")

        encounters = 0  # counts the words with selected properties
        for b in page.get_text("dict")["blocks"]:
            for l in b["lines"]:
                wdir = l["dir"]  # writing direction
                assert wdir == wdirs[page.number]
                for s in l["spans"]:
                    stext = s["text"]
                    color = pymupdf.sRGB_to_pdf(s["color"])
                    bold = bool(s["flags"] & 16)
                    italic = bool(s["flags"] & 2)
                    if stext in ("ullamco", "laboris", "voluptate"):
                        encounters += 1
                        if stext == "ullamco":
                            assert bold is True
                            assert italic is False
                            assert color == pymupdf.pdfcolor["black"]
                        elif stext == "laboris":
                            assert bold is False
                            assert italic is True
                            assert color == pymupdf.pdfcolor["black"]
                        elif stext == "voluptate":
                            assert bold is True
                            assert italic is False
                            assert color == pymupdf.pdfcolor["green"]
                    else:
                        assert bold is False
                        assert italic is False
        # all 3 special special words were encountered
        assert encounters == 3
