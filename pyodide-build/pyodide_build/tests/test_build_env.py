def xbuildenv(
    selenium,
):  # selenium fixture is just a hack to make this not to run in host test.
    pass


# class TestInTree:
#     pass

# class TestOutOfTree:
#     pass

# def test_get_make_environment_vars():
#     vars = get_make_environment_vars()
#     assert "SIDE_MODULE_LDFLAGS" in vars
#     assert "SIDE_MODULE_CFLAGS" in vars
#     assert "SIDE_MODULE_CXXFLAGS" in vars


# def test_get_build_flag():
#     common_flags = [
#         "SIDE_MODULE_LDFLAGS",
#         "SIDE_MODULE_CFLAGS",
#         "SIDE_MODULE_CXXFLAGS",

#     ]

#     for flag in common_flags:
#         build_env.get_build_flag(flag)

#     with pytest.raises(ValueError):
#         build_env.get_build_flag("NONEXISTENT_FLAG")
