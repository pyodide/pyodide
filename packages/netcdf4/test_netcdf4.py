# mypy: ignore-errors

import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["netCDF4", "numpy"])
def test_netCDF4_tutorial(selenium):
    import re
    from datetime import datetime

    DATETIME_PATTERN = re.compile(
        r"[a-zA-Z]{3}\s+[a-zA-Z]{3}\s+[0-9]{1,2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2}\s+[0-9]{4}"
    )
    DATETIME_FORMAT = "%a %b %d %H:%M:%S %Y"

    stdouts = [
        "NETCDF4",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): \n    variables(dimensions): \n    groups: forecasts, analyses",
        "<class 'netCDF4.Group'>\ngroup /forecasts:\n    dimensions(sizes): \n    variables(dimensions): \n    groups: model1, model2",
        "<class 'netCDF4.Group'>\ngroup /analyses:\n    dimensions(sizes): \n    variables(dimensions): \n    groups: ",
        "<class 'netCDF4.Group'>\ngroup /forecasts/model1:\n    dimensions(sizes): \n    variables(dimensions): \n    groups: ",
        "<class 'netCDF4.Group'>\ngroup /forecasts/model2:\n    dimensions(sizes): \n    variables(dimensions): \n    groups: ",
        "{'level': <class 'netCDF4.Dimension'> (unlimited): name = 'level', size = 0, 'time': <class 'netCDF4.Dimension'> (unlimited): name = 'time', size = 0, 'lat': <class 'netCDF4.Dimension'>: name = 'lat', size = 73, 'lon': <class 'netCDF4.Dimension'>: name = 'lon', size = 144}",
        "144",
        "False",
        "True",
        "<class 'netCDF4.Dimension'> (unlimited): name = 'level', size = 0",
        "<class 'netCDF4.Dimension'> (unlimited): name = 'time', size = 0",
        "<class 'netCDF4.Dimension'>: name = 'lat', size = 73",
        "<class 'netCDF4.Dimension'>: name = 'lon', size = 144",
        "<class 'netCDF4.Dimension'> (unlimited): name = 'time', size = 0",
        "<class 'netCDF4.Variable'>\nfloat32 temp(time, level, lat, lon)\n    least_significant_digit: 3\nunlimited dimensions: time, level\ncurrent shape = (0, 0, 73, 144)\nfilling on, default _FillValue of 9.969209968386869e+36 used",
        "<class 'netCDF4.Group'>\ngroup /forecasts/model1:\n    dimensions(sizes): \n    variables(dimensions): float32 temp(time, level, lat, lon)\n    groups: ",
        "<class 'netCDF4.Variable'>\nfloat32 temp(time, level, lat, lon)\npath = /forecasts/model1\nunlimited dimensions: time, level\ncurrent shape = (0, 0, 73, 144)\nfilling on, default _FillValue of 9.969209968386869e+36 used",
        "Global attr description = bogus example script",
        "Global attr history = Created %a %b %d %H:%M:%S %Y",
        "Global attr source = netCDF4 python module tutorial",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    description: bogus example script\n    history: Created %a %b %d %H:%M:%S %Y\n    source: netCDF4 python module tutorial\n    dimensions(sizes): level(0), time(0), lat(73), lon(144)\n    variables(dimensions): float64 time(time), int32 level(level), float32 lat(lat), float32 lon(lon), float32 temp(time, level, lat, lon)\n    groups: forecasts, analyses",
        "{'description': 'bogus example script', 'history': 'Created %a %b %d %H:%M:%S %Y', 'source': 'netCDF4 python module tutorial'}",
        "{'time': <class 'netCDF4.Variable'>\nfloat64 time(time)\n    units: hours since 0001-01-01 00:00:00.0\n    calendar: gregorian\nunlimited dimensions: time\ncurrent shape = (0,)\nfilling on, default _FillValue of 9.969209968386869e+36 used, 'level': <class 'netCDF4.Variable'>\nint32 level(level)\n    units: hPa\nunlimited dimensions: level\ncurrent shape = (0,)\nfilling on, default _FillValue of -2147483647 used, 'lat': <class 'netCDF4.Variable'>\nfloat32 lat(lat)\n    units: degrees north\nunlimited dimensions: \ncurrent shape = (73,)\nfilling on, default _FillValue of 9.969209968386869e+36 used, 'lon': <class 'netCDF4.Variable'>\nfloat32 lon(lon)\n    units: degrees east\nunlimited dimensions: \ncurrent shape = (144,)\nfilling on, default _FillValue of 9.969209968386869e+36 used, 'temp': <class 'netCDF4.Variable'>\nfloat32 temp(time, level, lat, lon)\n    least_significant_digit: 3\nunlimited dimensions: time, level\ncurrent shape = (0, 0, 73, 144)\nfilling on, default _FillValue of 9.969209968386869e+36 used}",
        "latitudes =\n [-90.  -87.5 -85.  -82.5 -80.  -77.5 -75.  -72.5 -70.  -67.5 -65.  -62.5\n -60.  -57.5 -55.  -52.5 -50.  -47.5 -45.  -42.5 -40.  -37.5 -35.  -32.5\n -30.  -27.5 -25.  -22.5 -20.  -17.5 -15.  -12.5 -10.   -7.5  -5.   -2.5\n   0.    2.5   5.    7.5  10.   12.5  15.   17.5  20.   22.5  25.   27.5\n  30.   32.5  35.   37.5  40.   42.5  45.   47.5  50.   52.5  55.   57.5\n  60.   62.5  65.   67.5  70.   72.5  75.   77.5  80.   82.5  85.   87.5\n  90. ]",
        "longitudes =\n [-180.  -177.5 -175.  -172.5 -170.  -167.5 -165.  -162.5 -160.  -157.5\n -155.  -152.5 -150.  -147.5 -145.  -142.5 -140.  -137.5 -135.  -132.5\n -130.  -127.5 -125.  -122.5 -120.  -117.5 -115.  -112.5 -110.  -107.5\n -105.  -102.5 -100.   -97.5  -95.   -92.5  -90.   -87.5  -85.   -82.5\n  -80.   -77.5  -75.   -72.5  -70.   -67.5  -65.   -62.5  -60.   -57.5\n  -55.   -52.5  -50.   -47.5  -45.   -42.5  -40.   -37.5  -35.   -32.5\n  -30.   -27.5  -25.   -22.5  -20.   -17.5  -15.   -12.5  -10.    -7.5\n   -5.    -2.5    0.     2.5    5.     7.5   10.    12.5   15.    17.5\n   20.    22.5   25.    27.5   30.    32.5   35.    37.5   40.    42.5\n   45.    47.5   50.    52.5   55.    57.5   60.    62.5   65.    67.5\n   70.    72.5   75.    77.5   80.    82.5   85.    87.5   90.    92.5\n   95.    97.5  100.   102.5  105.   107.5  110.   112.5  115.   117.5\n  120.   122.5  125.   127.5  130.   132.5  135.   137.5  140.   142.5\n  145.   147.5  150.   152.5  155.   157.5  160.   162.5  165.   167.5\n  170.   172.5  175.   177.5]",
        "temp shape before adding data =  (0, 0, 73, 144)",
        "temp shape after adding data =  (5, 10, 73, 144)",
        "levels shape after adding pressure data =  (10,)",
        "shape of fancy temp slice =  (3, 3, 36, 71)",
        "(4, 4)",
        "time values (in units hours since 0001-01-01 00:00:00.0):\n[17533104. 17533116. 17533128. 17533140. 17533152.]",
        "dates corresponding to time values:\n[cftime.DatetimeGregorian(2001, 3, 1, 0, 0, 0, 0, has_year_zero=False)\n cftime.DatetimeGregorian(2001, 3, 1, 12, 0, 0, 0, has_year_zero=False)\n cftime.DatetimeGregorian(2001, 3, 2, 0, 0, 0, 0, has_year_zero=False)\n cftime.DatetimeGregorian(2001, 3, 2, 12, 0, 0, 0, has_year_zero=False)\n cftime.DatetimeGregorian(2001, 3, 3, 0, 0, 0, 0, has_year_zero=False)]",
        "[ 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23\n 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47\n 48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63 64 65 66 67 68 69 70 71\n 72 73 74 75 76 77 78 79 80 81 82 83 84 85 86 87 88 89 90 91 92 93 94 95\n 96 97 98 99]",
        "complex128",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x_dim(3)\n    variables(dimensions): {'names': ['real', 'imag'], 'formats': ['<f8', '<f8'], 'offsets': [0, 8], 'itemsize': 16, 'aligned': True} cmplx_var(x_dim)\n    groups: ",
        "<class 'netCDF4.Variable'>\ncompound cmplx_var(x_dim)\ncompound data type: {'names': ['real', 'imag'], 'formats': ['<f8', '<f8'], 'offsets': [0, 8], 'itemsize': 16, 'aligned': True}\nunlimited dimensions: x_dim\ncurrent shape = (3,)",
        "{'complex128': <class 'netCDF4.CompoundType'>: name = 'complex128', numpy dtype = {'names': ['real', 'imag'], 'formats': ['<f8', '<f8'], 'offsets': [0, 8], 'itemsize': 16, 'aligned': True}}",
        "<class 'netCDF4.CompoundType'>: name = 'complex128', numpy dtype = {'names': ['real', 'imag'], 'formats': ['<f8', '<f8'], 'offsets': [0, 8], 'itemsize': 16, 'aligned': True}",
        "(3,)",
        "complex128 [ 0.54030231+0.84147098j -0.84147098+0.54030231j -0.54030231-0.84147098j]",
        "complex128 [ 0.54030231+0.84147098j -0.84147098+0.54030231j -0.54030231-0.84147098j]",
        "{'wind_data': <class 'netCDF4.CompoundType'>: name = 'wind_data', numpy dtype = {'names': ['speed', 'direction'], 'formats': ['<f4', '<i4'], 'offsets': [0, 4], 'itemsize': 8, 'aligned': True}, 'station_data': <class 'netCDF4.CompoundType'>: name = 'station_data', numpy dtype = {'names': ['latitude', 'longitude', 'surface_wind', 'temp_sounding', 'press_sounding', 'location_name'], 'formats': ['<f4', '<f4', [('speed', '<f4'), ('direction', '<i4')], ('<f4', (10,)), ('<i4', (10,)), ('S1', (12,))], 'offsets': [0, 4, 8, 16, 56, 96], 'itemsize': 108, 'aligned': True}, 'wind_data_units': <class 'netCDF4.CompoundType'>: name = 'wind_data_units', numpy dtype = {'names': ['speed', 'direction'], 'formats': [('S1', (12,)), ('S1', (12,))], 'offsets': [0, 12], 'itemsize': 24, 'aligned': True}, 'station_data_units': <class 'netCDF4.CompoundType'>: name = 'station_data_units', numpy dtype = {'names': ['latitude', 'longitude', 'surface_wind', 'temp_sounding', 'location_name', 'press_sounding'], 'formats': [('S1', (12,)), ('S1', (12,)), [('speed', 'S1', (12,)), ('direction', 'S1', (12,))], ('S1', (12,)), ('S1', (12,)), ('S1', (12,))], 'offsets': [0, 12, 24, 48, 60, 72], 'itemsize': 84, 'aligned': True}}",
        "[('latitude', 'S12'), ('longitude', 'S12'), ('surface_wind', [('speed', 'S12'), ('direction', 'S12')]), ('temp_sounding', 'S12'), ('location_name', 'S12'), ('press_sounding', 'S12')]",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): station(2)\n    variables(dimensions): {'names': ['latitude', 'longitude', 'surface_wind', 'temp_sounding', 'press_sounding', 'location_name'], 'formats': ['<f4', '<f4', [('speed', '<f4'), ('direction', '<i4')], ('<f4', (10,)), ('<i4', (10,)), ('S1', (12,))], 'offsets': [0, 4, 8, 16, 56, 96], 'itemsize': 108, 'aligned': True} station_obs(station)\n    groups: ",
        "<class 'netCDF4.Variable'>\ncompound station_obs(station)\n    units: (b'degrees N', b'degrees W', (b'm/s', b'degrees'), b'Kelvin', b'None', b'hPa')\ncompound data type: {'names': ['latitude', 'longitude', 'surface_wind', 'temp_sounding', 'press_sounding', 'location_name'], 'formats': ['<f4', '<f4', [('speed', '<f4'), ('direction', '<i4')], ('<f4', (10,)), ('<i4', (10,)), ('S1', (12,))], 'offsets': [0, 4, 8, 16, 56, 96], 'itemsize': 108, 'aligned': True}\nunlimited dimensions: station\ncurrent shape = (2,)",
        "data in a variable of compound type:",
        "[(40.  , -105.  , ( 12.5, 270), [280.3, 272. , 270. , 269. , 266. , 258. , 254.1, 250. , 245.5, 240. ], [800, 750, 700, 650, 600, 550, 500, 450, 400, 350], b'Boulder, CO')\n (40.78,  -73.99, (-12.5,  90), [290.2, 282.5, 279. , 277.9, 276. , 266. , 264.1, 260. , 255.5, 243. ], [900, 850, 800, 750, 700, 650, 600, 550, 500, 450], b'New York, NY')]",
        "<class 'netCDF4.Variable'>\nvlen phony_vlen_var(y, x)\nvlen data type: int32\nunlimited dimensions: \ncurrent shape = (4, 3)",
        "vlen variable =\n [[array([1, 2, 3, 4, 5, 6, 7]) array([1, 2, 3, 4, 5]) array([1])]\n [array([1, 2, 3]) array([1, 2]) array([1])]\n [array([1]) array([1, 2, 3, 4, 5, 6, 7]) array([1])]\n [array([1, 2, 3, 4, 5, 6]) array([1, 2, 3, 4, 5]) array([1])]]",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x(3), y(4)\n    variables(dimensions): int32 phony_vlen_var(y, x)\n    groups: ",
        "<class 'netCDF4.Variable'>\nvlen phony_vlen_var(y, x)\nvlen data type: int32\nunlimited dimensions: \ncurrent shape = (4, 3)",
        "<class 'netCDF4.VLType'>: name = 'phony_vlen', numpy dtype = int32",
        "variable-length string variable:\n ['ZOGMRmJo' 'BxdAK1fku' 'lgOzaanCtv' 'D5ALrXJCDU' 'W9r' 'Y7edBPrthEr'\n 'OVeqx' 'aH1ZXc5A' 'LC1ajPJ' 'du']",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x(3), y(4), z(10)\n    variables(dimensions): int32 phony_vlen_var(y, x), <class 'str'> strvar(z)\n    groups: ",
        "<class 'netCDF4.Variable'>\nvlen strvar(z)\nvlen data type: <class 'str'>\nunlimited dimensions: \ncurrent shape = (10,)",
        "<class 'netCDF4.EnumType'>: name = 'cloud_t', numpy dtype = uint8, fields/values ={'Altocumulus': 7, 'Missing': 255, 'Stratus': 2, 'Clear': 0, 'Nimbostratus': 6, 'Cumulus': 4, 'Altostratus': 5, 'Cumulonimbus': 1, 'Stratocumulus': 3}",
        "<class 'netCDF4.Variable'>\nenum primary_cloud(time)\n    _FillValue: 255\nenum data type: uint8\nunlimited dimensions: time\ncurrent shape = (5,)",
        "{'Altocumulus': 7, 'Missing': 255, 'Stratus': 2, 'Clear': 0, 'Nimbostratus': 6, 'Cumulus': 4, 'Altostratus': 5, 'Cumulonimbus': 1, 'Stratocumulus': 3}",
        "[0 2 4 -- 1]",
        "[[b'f' b'o' b'o']\n [b'b' b'a' b'r']]",
        "['foo' 'bar']",
        "{'names': ['observation', 'station_name'], 'formats': ['<f4', ('S1', (12,))], 'offsets': [0, 4], 'itemsize': 16, 'aligned': True}",
        "[(123.  , b'Boulder') (  3.14, b'New York')]",
        "{'names': ['observation', 'station_name'], 'formats': ['<f4', 'S12'], 'offsets': [0, 4], 'itemsize': 16, 'aligned': True}",
        "[(123.  , [b'B', b'o', b'u', b'l', b'd', b'e', b'r', b'', b'', b'', b'', b''])\n (  3.14, [b'N', b'e', b'w', b' ', b'Y', b'o', b'r', b'k', b'', b'', b'', b''])]",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x(5)\n    variables(dimensions): int32 v(x)\n    groups: ",
        "[0 1 2 3 4]",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x(5)\n    variables(dimensions): int32 v(x)\n    groups: ",
        "[0 1 2 3 4]",
        "<class 'memoryview'>",
        "<class 'netCDF4.Dataset'>\nroot group (NETCDF4 data model, file format HDF5):\n    dimensions(sizes): x(5)\n    variables(dimensions): int32 v(x)\n    groups: ",
        "[0 1 2 3 4]",
    ]

    def replace_netcdf_datetime(match):
        try:
            datetime.strptime(match.group(0), DATETIME_FORMAT)
        except Exception:
            return match.group(0)
        else:
            return DATETIME_FORMAT

    def assert_print(*args):
        output = " ".join(str(a) for a in args)

        # Clean up string representations to match the expected format
        # by replacing quoted class representations with unquoted ones.
        # I am not sure why this is necessary, but it seems to be a difference
        # in how CPython is stricter about quotes in string representations.
        output = output.replace("\"<class '", "<class '")
        output = output.replace('>"', ">")

        output = DATETIME_PATTERN.sub(replace_netcdf_datetime, output)

        expected = stdouts.pop(0)

        if output != expected:
            assert output == expected, f"{repr(output)} != {repr(expected)}"

    """
    Test adopted from (but with reproducible randomness):
    https://github.com/Unidata/netcdf4-python/blob/master/examples/tutorial.py
    Released under the MIT License
    """

    from numpy.random import PCG64, Generator

    rng = Generator(PCG64(seed=42))

    from netCDF4 import Dataset

    # code from tutorial.

    # create a file (Dataset object, also the root group).
    rootgrp = Dataset("test.nc", "w", format="NETCDF4")
    assert_print(rootgrp.file_format)
    rootgrp.close()

    # create some groups.
    rootgrp = Dataset("test.nc", "a")
    rootgrp.createGroup("forecasts")
    rootgrp.createGroup("analyses")
    rootgrp.createGroup("/forecasts/model1")
    rootgrp.createGroup("/forecasts/model2")

    # walk the group tree using a Python generator.
    def walktree(top):
        yield top.groups.values()
        for value in top.groups.values():
            yield from walktree(value)

    assert_print(rootgrp)
    for children in walktree(rootgrp):
        for child in children:
            assert_print(child)

    # dimensions.
    rootgrp.createDimension("level", None)
    time = rootgrp.createDimension("time", None)
    rootgrp.createDimension("lat", 73)
    lon = rootgrp.createDimension("lon", 144)

    assert_print(rootgrp.dimensions)

    assert_print(len(lon))
    assert_print(lon.isunlimited())
    assert_print(time.isunlimited())

    for dimobj in rootgrp.dimensions.values():
        assert_print(dimobj)

    assert_print(time)

    # variables.
    times = rootgrp.createVariable("time", "f8", ("time",))
    levels = rootgrp.createVariable("level", "i4", ("level",))
    latitudes = rootgrp.createVariable("lat", "f4", ("lat",))
    longitudes = rootgrp.createVariable("lon", "f4", ("lon",))
    # 2 unlimited dimensions.
    # temp = rootgrp.createVariable('temp','f4',('time','level','lat','lon',))
    # this makes the compression 'lossy' (preserving a precision of 1/1000)
    # try it and see how much smaller the file gets.
    temp = rootgrp.createVariable(
        "temp",
        "f4",
        (
            "time",
            "level",
            "lat",
            "lon",
        ),
        least_significant_digit=3,
    )
    assert_print(temp)
    # create variable in a group using a path.
    temp = rootgrp.createVariable(
        "/forecasts/model1/temp",
        "f4",
        (
            "time",
            "level",
            "lat",
            "lon",
        ),
    )
    assert_print(rootgrp["/forecasts/model1"])  # print the Group instance
    assert_print(rootgrp["/forecasts/model1/temp"])  # print the Variable instance

    # attributes.
    import time

    rootgrp.description = "bogus example script"
    rootgrp.history = "Created " + time.ctime(time.time())
    rootgrp.source = "netCDF4 python module tutorial"
    latitudes.units = "degrees north"
    longitudes.units = "degrees east"
    levels.units = "hPa"
    temp.units = "K"
    times.units = "hours since 0001-01-01 00:00:00.0"
    times.calendar = "gregorian"

    for name in rootgrp.ncattrs():
        assert_print("Global attr", name, "=", getattr(rootgrp, name))

    assert_print(rootgrp)

    assert_print(rootgrp.__dict__)

    assert_print(rootgrp.variables)

    import numpy as np

    # no unlimited dimension, just assign to slice.
    lats = np.arange(-90, 91, 2.5)
    lons = np.arange(-180, 180, 2.5)
    latitudes[:] = lats
    longitudes[:] = lons
    assert_print("latitudes =\n", latitudes[:])
    assert_print("longitudes =\n", longitudes[:])

    # append along two unlimited dimensions by assigning to slice.
    nlats = len(rootgrp.dimensions["lat"])
    nlons = len(rootgrp.dimensions["lon"])
    assert_print("temp shape before adding data = ", temp.shape)

    temp[0:5, 0:10, :, :] = rng.uniform(size=(5, 10, nlats, nlons))
    assert_print("temp shape after adding data = ", temp.shape)
    # levels have grown, but no values yet assigned.
    assert_print("levels shape after adding pressure data = ", levels.shape)

    # assign values to levels dimension variable.
    levels[:] = [1000.0, 850.0, 700.0, 500.0, 300.0, 250.0, 200.0, 150.0, 100.0, 50.0]
    # fancy slicing
    tempdat = temp[::2, [1, 3, 6], lats > 0, lons > 0]
    assert_print("shape of fancy temp slice = ", tempdat.shape)
    assert_print(temp[0, 0, [0, 1, 2, 3], [0, 1, 2, 3]].shape)

    # fill in times.
    from datetime import timedelta

    from netCDF4 import date2num, num2date

    dates = [
        datetime(2001, 3, 1) + n * timedelta(hours=12) for n in range(temp.shape[0])
    ]
    times[:] = date2num(dates, units=times.units, calendar=times.calendar)
    assert_print(f"time values (in units {times.units}):\n{times[:]}")
    dates = num2date(times[:], units=times.units, calendar=times.calendar)
    assert_print(f"dates corresponding to time values:\n{dates}")

    rootgrp.close()

    # create a series of netCDF files with a variable sharing
    # the same unlimited dimension.
    for nfile in range(10):
        f = Dataset("mftest" + repr(nfile) + ".nc", "w", format="NETCDF4_CLASSIC")
        f.createDimension("x", None)
        x = f.createVariable("x", "i", ("x",))
        x[0:10] = np.arange(nfile * 10, 10 * (nfile + 1))
        f.close()
    # now read all those files in at once, in one Dataset.
    from netCDF4 import MFDataset

    f = MFDataset("mftest*nc")
    assert_print(f.variables["x"][:])

    # example showing how to save numpy complex arrays using compound types.
    f = Dataset("complex.nc", "w")
    size = 3  # length of 1-d complex array
    # create sample complex data.
    datac = np.exp(1j * (1.0 + np.linspace(0, np.pi, size)))
    assert_print(datac.dtype)
    # create complex128 compound data type.
    complex128 = np.dtype([("real", np.float64), ("imag", np.float64)])
    complex128_t = f.createCompoundType(complex128, "complex128")
    # create a variable with this data type, write some data to it.
    f.createDimension("x_dim", None)
    v = f.createVariable("cmplx_var", complex128_t, "x_dim")
    data = np.empty(size, complex128)  # numpy structured array
    data["real"] = datac.real
    data["imag"] = datac.imag
    v[:] = data
    # close and reopen the file, check the contents.
    f.close()
    f = Dataset("complex.nc")
    assert_print(f)
    assert_print(f.variables["cmplx_var"])
    assert_print(f.cmptypes)
    assert_print(f.cmptypes["complex128"])
    v = f.variables["cmplx_var"]
    assert_print(v.shape)
    datain = v[:]  # read in all the data into a numpy structured array
    # create an empty numpy complex array
    datac2 = np.empty(datain.shape, np.complex128)
    # .. fill it with contents of structured array.
    datac2.real = datain["real"]
    datac2.imag = datain["imag"]
    assert_print(datac.dtype, datac)
    assert_print(datac2.dtype, datac2)

    # more complex compound type example.
    f = Dataset("compound_example.nc", "w")  # create a new dataset.
    # create an unlimited  dimension call 'station'
    f.createDimension("station", None)
    # define a compound data type (can contain arrays, or nested compound types).
    winddtype = np.dtype([("speed", "f4"), ("direction", "i4")])
    statdtype = np.dtype(
        [
            ("latitude", "f4"),
            ("longitude", "f4"),
            ("surface_wind", winddtype),
            ("temp_sounding", "f4", 10),
            ("press_sounding", "i4", 10),
            ("location_name", "S12"),
        ]
    )
    # use this data type definitions to create a compound data types
    # called using the createCompoundType Dataset method.
    # create a compound type for vector wind which will be nested inside
    # the station data type. This must be done first!
    f.createCompoundType(winddtype, "wind_data")
    # now that wind_data_t is defined, create the station data type.
    station_data_t = f.createCompoundType(statdtype, "station_data")
    # create nested compound data types to hold the units variable attribute.
    winddtype_units = np.dtype([("speed", "S12"), ("direction", "S12")])
    statdtype_units = np.dtype(
        [
            ("latitude", "S12"),
            ("longitude", "S12"),
            ("surface_wind", winddtype_units),
            ("temp_sounding", "S12"),
            ("location_name", "S12"),
            ("press_sounding", "S12"),
        ]
    )
    # create the wind_data_units type first, since it will nested inside
    # the station_data_units data type.
    f.createCompoundType(winddtype_units, "wind_data_units")
    f.createCompoundType(statdtype_units, "station_data_units")
    # create a variable of of type 'station_data_t'
    statdat = f.createVariable("station_obs", station_data_t, ("station",))
    # create a numpy structured array, assign data to it.
    data = np.empty(1, statdtype)
    data["latitude"] = 40.0
    data["longitude"] = -105.0
    data["surface_wind"]["speed"] = 12.5
    data["surface_wind"]["direction"] = 270
    data["temp_sounding"] = (
        280.3,
        272.0,
        270.0,
        269.0,
        266.0,
        258.0,
        254.1,
        250.0,
        245.5,
        240.0,
    )
    data["press_sounding"] = range(800, 300, -50)
    data["location_name"] = "Boulder, CO"
    # assign structured array to variable slice.
    statdat[0] = data
    # or just assign a tuple of values to variable slice
    # (will automatically be converted to a structured array).
    statdat[1] = np.array(
        (
            40.78,
            -73.99,
            (-12.5, 90),
            (290.2, 282.5, 279.0, 277.9, 276.0, 266.0, 264.1, 260.0, 255.5, 243.0),
            range(900, 400, -50),
            "New York, NY",
        ),
        data.dtype,
    )
    assert_print(f.cmptypes)
    windunits = np.empty(1, winddtype_units)
    stationobs_units = np.empty(1, statdtype_units)
    windunits["speed"] = "m/s"
    windunits["direction"] = "degrees"
    stationobs_units["latitude"] = "degrees N"
    stationobs_units["longitude"] = "degrees W"
    stationobs_units["surface_wind"] = windunits
    stationobs_units["location_name"] = "None"
    stationobs_units["temp_sounding"] = "Kelvin"
    stationobs_units["press_sounding"] = "hPa"
    assert_print(stationobs_units.dtype)
    statdat.units = stationobs_units
    # close and reopen the file.
    f.close()
    f = Dataset("compound_example.nc")
    assert_print(f)
    statdat = f.variables["station_obs"]
    assert_print(statdat)
    # print out data in variable.
    assert_print("data in a variable of compound type:")
    assert_print(statdat[:])
    f.close()

    f = Dataset("tst_vlen.nc", "w")
    vlen_t = f.createVLType(np.int32, "phony_vlen")
    x = f.createDimension("x", 3)
    y = f.createDimension("y", 4)
    vlvar = f.createVariable("phony_vlen_var", vlen_t, ("y", "x"))

    data = np.empty(len(y) * len(x), object)
    for n in range(len(y) * len(x)):
        data[n] = np.arange(rng.integers(1, 10), dtype="int32") + 1
    data = np.reshape(data, (len(y), len(x)))  # type: ignore[assignment]
    vlvar[:] = data
    assert_print(vlvar)
    assert_print("vlen variable =\n", vlvar[:])
    assert_print(f)
    assert_print(f.variables["phony_vlen_var"])
    assert_print(f.vltypes["phony_vlen"])
    f.createDimension("z", 10)
    strvar = f.createVariable("strvar", str, "z")
    chars = list("1234567890aabcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    data = np.empty(10, object)
    for n in range(10):
        stringlen = rng.integers(2, 12)
        data[n] = "".join([rng.choice(chars) for i in range(stringlen)])
    strvar[:] = data
    assert_print("variable-length string variable:\n", strvar[:])
    assert_print(f)
    assert_print(f.variables["strvar"])
    f.close()

    # Enum type example.
    f = Dataset("clouds.nc", "w")
    # python dict describing the allowed values and their names.
    enum_dict = {
        "Altocumulus": 7,
        "Missing": 255,
        "Stratus": 2,
        "Clear": 0,
        "Nimbostratus": 6,
        "Cumulus": 4,
        "Altostratus": 5,
        "Cumulonimbus": 1,
        "Stratocumulus": 3,
    }
    # create the Enum type called 'cloud_t'.
    cloud_type = f.createEnumType(np.uint8, "cloud_t", enum_dict)
    assert_print(cloud_type)
    time = f.createDimension("time", None)
    # create a 1d variable of type 'cloud_type' called 'primary_clouds'.
    # The fill_value is set to the 'Missing' named value.
    cloud_var = f.createVariable(
        "primary_cloud", cloud_type, "time", fill_value=enum_dict["Missing"]
    )
    # write some data to the variable.
    cloud_var[:] = [
        enum_dict["Clear"],
        enum_dict["Stratus"],
        enum_dict["Cumulus"],
        enum_dict["Missing"],
        enum_dict["Cumulonimbus"],
    ]
    # close file, reopen it.
    f.close()
    f = Dataset("clouds.nc")
    cloud_var = f.variables["primary_cloud"]
    assert_print(cloud_var)
    assert_print(cloud_var.datatype.enum_dict)
    assert_print(cloud_var[:])
    f.close()

    # dealing with strings
    from netCDF4 import stringtochar

    nc = Dataset("stringtest.nc", "w", format="NETCDF4_CLASSIC")
    nc.createDimension("nchars", 3)
    nc.createDimension("nstrings", None)
    v = nc.createVariable("strings", "S1", ("nstrings", "nchars"))
    datain = np.array(["foo", "bar"], dtype="S3")
    v[:] = stringtochar(datain)  # manual conversion to char array
    assert_print(v[:])  # data returned as char array
    v._Encoding = "ascii"  # this enables automatic conversion
    v[:] = datain  # conversion to char array done internally
    assert_print(v[:])  # data returned in numpy string array
    nc.close()
    # strings in compound types
    nc = Dataset("compoundstring_example.nc", "w")
    dtype = np.dtype([("observation", "f4"), ("station_name", "S12")])
    station_data_t = nc.createCompoundType(dtype, "station_data")
    nc.createDimension("station", None)
    statdat = nc.createVariable("station_obs", station_data_t, ("station",))
    data = np.empty(2, station_data_t.dtype_view)
    data["observation"][:] = (123.0, 3.14)
    data["station_name"][:] = ("Boulder", "New York")
    assert_print(statdat.dtype)  # strings actually stored as character arrays
    statdat[:] = data  # strings converted to character arrays internally
    assert_print(statdat[:])  # character arrays converted back to strings
    assert_print(statdat[:].dtype)
    statdat.set_auto_chartostring(False)  # turn off auto-conversion
    statdat[:] = data.view(station_data_t.dtype)
    assert_print(statdat[:])  # now structured array with char array subtype is returned
    nc.close()

    # create a diskless (in-memory) Dataset, and persist the file
    # to disk when it is closed.
    nc = Dataset("diskless_example.nc", "w", diskless=True, persist=True)
    nc.createDimension("x", None)
    v = nc.createVariable("v", np.int32, "x")
    v[0:5] = np.arange(5)
    assert_print(nc)
    assert_print(nc["v"][:])
    nc.close()  # file saved to disk
    # create an in-memory dataset from an existing python memory
    # buffer.
    # read the newly created netcdf file into a python bytes object.
    f = open("diskless_example.nc", "rb")
    nc_bytes = f.read()
    f.close()
    # create a netCDF in-memory dataset from the bytes object.
    nc = Dataset("inmemory.nc", memory=nc_bytes)
    assert_print(nc)
    assert_print(nc["v"][:])
    nc.close()
    # create an in-memory Dataset and retrieve memory buffer
    # estimated size is 1028 bytes - this is actually only
    # used if format is NETCDF3 (ignored for NETCDF4/HDF5 files).
    nc = Dataset("inmemory.nc", mode="w", memory=1028)
    nc.createDimension("x", None)
    v = nc.createVariable("v", np.int32, "x")
    v[0:5] = np.arange(5)
    nc_buf = nc.close()  # close returns memoryview
    assert_print(type(nc_buf))
    # save nc_buf to disk, read it back in and check.
    f = open("inmemory.nc", "wb")
    f.write(nc_buf)
    f.close()
    nc = Dataset("inmemory.nc")
    assert_print(nc)
    assert_print(nc["v"][:])
    nc.close()
