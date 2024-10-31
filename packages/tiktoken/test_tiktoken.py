from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["tiktoken"])
def test_tiktoken(selenium):
    import tiktoken

    # In the selenium environment, we cannot fetch a pre-trained tokenizer from tiktoken, so we create a basic one
    def make_encoding():
        # This pattern splits on whitespace and punctuation
        basic_pat_str = r"\w+|[^\w\s]+|\s"
        basic_mergeable_ranks = {
            b"Hello": 0,
            b"world": 1,
            b"!": 2,
            b",": 3,
            b"<|endoftext|>": 4,
            b" ": 5,
        }
        basic_special_tokens = {"<|endoftext|>": 4}
        return tiktoken.Encoding(
            name="basic",
            pat_str=basic_pat_str,
            mergeable_ranks=basic_mergeable_ranks,
            special_tokens=basic_special_tokens,
        )

    encoding = make_encoding()
    test_str = "Hello, world!"
    encoded = encoding.encode(test_str)
    decoded = encoding.decode(encoded)
    assert decoded == test_str
