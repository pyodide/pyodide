def test_regex(selenium, request):
    selenium.load_package("regex")
    assert selenium.run("import regex\nregex.search('o', 'foo').end()") == 2
