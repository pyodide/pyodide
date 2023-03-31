# non-native
# setup: import matplotlib ; import numpy as np ; matplotlib.use('module://matplotlib_pyodide.html5_canvas_backend') ; from matplotlib import pyplot as plt ; from matplotlib.dates import (YEARLY, DateFormatter, rrulewrapper, RRuleLocator, drange) ; import datetime  # noqa: E501
# run: canvas_text_rotated()

# pythran export canvas_text_rotated()
import matplotlib
import numpy as np

matplotlib.use("module://matplotlib_pyodide.html5_canvas_backend")
import datetime  # noqa: E402

from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.dates import (  # noqa: E402
    YEARLY,
    DateFormatter,  # noqa: E402
    RRuleLocator,  # noqa: E402
    drange,
    rrulewrapper,
)


def canvas_text_rotated():
    # tick every 5th easter
    np.random.seed(42)
    rule = rrulewrapper(YEARLY, byeaster=1, interval=5)
    loc = RRuleLocator(rule)
    formatter = DateFormatter("%m/%d/%y")
    date1 = datetime.date(1952, 1, 1)
    date2 = datetime.date(2004, 4, 12)
    delta = datetime.timedelta(days=100)

    dates = drange(date1, date2, delta)
    s = np.random.rand(len(dates))  # make up some random y values

    fig, ax = plt.subplots()
    plt.plot_date(dates, s)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(formatter)
    labels = ax.get_xticklabels()
    plt.setp(labels, rotation=30, fontsize=10)

    plt.show()
    plt.close("all")
    plt.clf()
