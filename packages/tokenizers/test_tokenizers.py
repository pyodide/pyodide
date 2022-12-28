import pathlib

import pytest
from pytest_pyodide import run_in_pyodide

TEST_DATA_PATH = pathlib.Path(__file__).parent / "test_data"


def test_pretrained(selenium):
    @run_in_pyodide(packages=["tokenizers"])
    def run(selenium, pretrained):
        from tokenizers import Tokenizer

        tokenizer = Tokenizer.from_str(pretrained)
        output = tokenizer.encode("Hello, y'all!", "How are you 😁 ?")
        tokens = [
            "[CLS]",
            "hello",
            ",",
            "y",
            "'",
            "all",
            "!",
            "[SEP]",
            "how",
            "are",
            "you",
            "[UNK]",
            "?",
            "[SEP]",
        ]
        assert output.tokens == tokens

    pretrained = (TEST_DATA_PATH / "bert-base-uncased-tokenizer.json").read_text()
    run(selenium, pretrained)


@run_in_pyodide(packages=["tokenizers"])
def test_bpe_train_from_iterator(selenium):
    from tokenizers import SentencePieceBPETokenizer

    text = ["A first sentence", "Another sentence", "And a last one"]
    tokenizer = SentencePieceBPETokenizer()
    tokenizer.train_from_iterator(text, show_progress=False)

    output = tokenizer.encode("A sentence")
    assert output.tokens == ["▁A", "▁sentence"]


@run_in_pyodide(packages=["tokenizers", "pytest"])
def test_unigram_train_from_iterator(selenium):
    import pytest
    from tokenizers import SentencePieceUnigramTokenizer

    text = ["A first sentence", "Another sentence", "And a last one"]
    tokenizer = SentencePieceUnigramTokenizer()
    tokenizer.train_from_iterator(text, show_progress=False)

    output = tokenizer.encode("A sentence")
    assert output.tokens == ["▁A", "▁", "s", "en", "t", "en", "c", "e"]

    with pytest.raises(Exception) as excinfo:
        _ = tokenizer.encode("A sentence 🤗")
    assert str(excinfo.value) == "Encountered an unknown token but `unk_id` is missing"


@run_in_pyodide(packages=["tokenizers"])
def test_unigram_train_from_iterator_with_unk_token(selenium):
    from tokenizers import SentencePieceUnigramTokenizer

    text = ["A first sentence", "Another sentence", "And a last one"]
    tokenizer = SentencePieceUnigramTokenizer()
    tokenizer.train_from_iterator(
        text,
        vocab_size=100,
        show_progress=False,
        special_tokens=["<unk>"],
        unk_token="<unk>",
    )
    output = tokenizer.encode("A sentence 🤗")
    assert output.ids[-1] == 0
    assert output.tokens == ["▁A", "▁", "s", "en", "t", "en", "c", "e", "▁", "🤗"]


@pytest.mark.skip(
    reason="PyThreadState_Get: the function must be called with the GIL held, but the GIL is released (the current Python thread state is NULL)"
)
@run_in_pyodide(packages=["tokenizers"])
def test_unigram_train_file(selenium):
    from tokenizers import SentencePieceUnigramTokenizer

    filename = "file.txt"
    with open(filename, "w") as f:
        f.write("A first sentence\nAnother sentence\nAnd a last one")

    tokenizer = SentencePieceUnigramTokenizer()
    tokenizer.train(files=filename, show_progress=False)

    output = tokenizer.encode("A sentence")
    assert output.tokens == ["▁A", "▁", "s", "en", "t", "en", "c", "e"]
