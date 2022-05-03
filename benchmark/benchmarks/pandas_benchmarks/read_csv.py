# setup: import random ; TESTDATA = "col1;col2;col3\n" + "\n".join(";".join(map(str, [random.randint(0, 1) for _ in range(3)])) + "\n" for _ in range(10000))
# run: read_csv(TESTDATA)

from io import StringIO

import pandas as pd


def read_csv(data):
    return pd.read_csv(StringIO(data), sep=";")
