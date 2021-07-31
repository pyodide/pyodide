from cffi_example.person import Person


def test_get_age(self):
    p = Person(u"Alex", u"Smith", 72)
    assert p.get_age() == 72
    assert self.p.get_full_name() == u"Alex Smith"

    p = Person(u"x" * 100, u"y" * 100, 72)
    assert p.get_full_name() == u"x" * 100
