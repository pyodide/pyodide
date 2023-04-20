from pytest_pyodide import run_in_pyodide

THIS = """
Beautiful is better than ugly.
Explicit is better than implicit.
Simple is better than complex.
Complex is better than complicated.
Flat is better than nested.
Sparse is better than dense.
Readability counts.
Special cases aren't special enough to break the rules.
Although practicality beats purity.
Errors should never pass silently.
Unless explicitly silenced.
In the face of ambiguity, refuse the temptation to guess.
There should be one-- and preferably only one --obvious way to do it.
Although that way may not be obvious at first unless you're Dutch.
Now is better than never.
Although never is often better than *right* now.
If the implementation is hard to explain, it's a bad idea.
If the implementation is easy to explain, it may be a good idea.
Namespaces are one honking great idea -- let's do more of those!
"""


def test_wordcloud(selenium):
    @run_in_pyodide(packages=["wordcloud"])
    def _test_wordcloud_inner(selenium, words):
        from wordcloud.wordcloud import WordCloud

        wc = WordCloud()
        wc.generate(words)

        assert wc.words_ == {
            "better": 1.0,
            "Although": 0.375,
            "never": 0.375,
            "one": 0.375,
            "idea": 0.375,
            "complex": 0.25,
            "Special": 0.25,
            "Unless": 0.25,
            "obvious": 0.25,
            "way": 0.25,
            "may": 0.25,
            "Now": 0.25,
            "implementation": 0.25,
            "explain": 0.25,
            "Beautiful": 0.125,
            "ugly": 0.125,
            "Explicit": 0.125,
            "implicit": 0.125,
            "Simple": 0.125,
            "complicated": 0.125,
            "Flat": 0.125,
            "nested": 0.125,
            "Sparse": 0.125,
            "dense": 0.125,
            "Readability": 0.125,
            "counts": 0.125,
            "cases": 0.125,
            "enough": 0.125,
            "break": 0.125,
            "rules": 0.125,
            "practicality": 0.125,
            "beats": 0.125,
            "purity": 0.125,
            "Errors": 0.125,
            "pass": 0.125,
            "silently": 0.125,
            "explicitly": 0.125,
            "silenced": 0.125,
            "face": 0.125,
            "ambiguity": 0.125,
            "refuse": 0.125,
            "temptation": 0.125,
            "guess": 0.125,
            "preferably": 0.125,
            "first": 0.125,
            "Dutch": 0.125,
            "often": 0.125,
            "right": 0.125,
            "hard": 0.125,
            "bad": 0.125,
            "easy": 0.125,
            "good": 0.125,
            "Namespaces": 0.125,
            "honking": 0.125,
            "great": 0.125,
            "let": 0.125,
        }

        svg = wc.to_svg()
        assert svg.startswith("<svg") and svg.endswith("</svg>")

    _test_wordcloud_inner(selenium, THIS)
