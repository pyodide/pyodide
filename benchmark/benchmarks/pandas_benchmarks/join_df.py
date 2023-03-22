# setup: import pandas as pd ; import numpy ; N = 1000000 ; df1 = pd.DataFrame(numpy.random.randint(0, 10, size=(N, 3)), columns=["col1", "col2", "col3"]) ; df2 = pd.DataFrame(numpy.random.randint(0, 10, size=(N, 3)), columns=["col4", "col5", "col6"])  # noqa: E501
# run: join_df(df1, df2)


def join_df(df1, df2):
    return df1.join(df2, how="outer")
