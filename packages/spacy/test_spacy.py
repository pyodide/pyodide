from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["spacy", "pyodide-http", "requests"])
def test_spacy(selenium):
    import pyodide_http

    pyodide_http.patch_all()
    import spacy

    import micropip

    await micropip.install(
        "https://vuizur.github.io/spacy-model-mirror/en_core_web_sm-3.6.0-py3-none-any.whl"
    )

    nlp = spacy.load("en_core_web_sm")
    text = "This is a sentence."
    doc = nlp(text)
    for token in doc:
        print(
            token.text,
            token.lemma_,
            token.pos_,
            token.tag_,
            token.dep_,
            token.shape_,
            token.is_alpha,
            token.is_stop,
        )

    assert doc[0].text == "This"
    assert doc[1].lemma_ == "be"
