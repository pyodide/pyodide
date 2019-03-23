import pytest


def test_nltk_edit_distance(selenium):
    selenium.load_package('nltk')
    selenium.run('import nltk')
    edit_distance = selenium.run("nltk.edit_distance('foo', 'food')")
    assert edit_distance == 1


def test_nltk_jaccard_distance(selenium):
    selenium.load_package('nltk')
    selenium.run('import nltk')
    jaccard_distance = selenium.run("""
        nltk.jaccard_distance(set('mapping'), set('mappings'))
    """)
    assert jaccard_distance == pytest.approx(0.1428571)


def test_nltk_ngrams(selenium):
    selenium.load_package('nltk')
    selenium.run('import nltk')
    ngrams = selenium.run("list(nltk.ngrams('master', n=3))")
    assert len(ngrams) == 4
    assert ngrams[0] == ['m', 'a', 's']
    assert ngrams[1] == ['a', 's', 't']
    assert ngrams[2] == ['s', 't', 'e']
    assert ngrams[3] == ['t', 'e', 'r']
