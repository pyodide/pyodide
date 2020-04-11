# Should this test fail, first ascertain two things:
#  - Both the bundled libmecab and the dictionary are built targeting utf-8
#  - The bundled _MeCab.so does not try to import any symbols that contain MeCab in their name (failing to link libmecab during build of the bundled library only results in a warning - some random integer will be thrown as an exception during instantiation of the Tagger)

def test_chasen(selenium):
	selenium.load_package("mecab-python3")
	selenium.run("import MeCab")
	tagged = selenium.run("MeCab.Tagger(\"-Ochasen\").parse(\"pythonが大好きです\")")
	split = tagged.splitlines()
	assert split[-1] == "EOS"
	assert len(split) > 2
	assert "詞" in tagged
	# I don't want to test too tightly, since the way MeCab splits up sentences may change over time
	# Checking for 詞 seems like a safe bet, since that is contained in the Japanese words for "noun", "verb", etc.
	# so it's very likely to be in the string no matter how the dictionary changes
