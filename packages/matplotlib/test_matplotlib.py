import base64
import pathlib
import textwrap
from functools import reduce

import pytest

REFERENCE_IMAGES_PATH = pathlib.Path(__file__).parent / "reference-images"

DECORATORS = [
    pytest.mark.xfail_browsers(node="No supported matplotlib backends on node"),
    pytest.mark.skip_refcount_check,
    pytest.mark.skip_pyproxy_check,
]


def matplotlib_test_decorator(f):
    return reduce(lambda x, g: g(x), DECORATORS, f)


def run_with_resolve(selenium, code):
    selenium.run_js(
        f"""
        try {{
            let promise = new Promise((resolve) => self.resolve = resolve);
            pyodide.runPython({code!r});
            await promise;
        }} finally {{
            delete self.resolve;
        }}
        """
    )


def patch_font_loading_and_dpi(target_font=""):
    """Monkey-patches font loading and dpi to allow testing"""
    return textwrap.dedent(
        f"""from matplotlib.backends.html5_canvas_backend import RendererHTMLCanvas
        from matplotlib.backends.html5_canvas_backend import FigureCanvasHTMLCanvas
        FigureCanvasHTMLCanvas.get_dpi_ratio = lambda self, context: 2.0
        load_font_into_web = RendererHTMLCanvas.load_font_into_web
        def load_font_into_web_wrapper(self, loaded_font, font_url, orig_function=load_font_into_web):
            fontface = orig_function(self, loaded_font, font_url)

            target_font = {target_font!r}
            if not target_font or target_font == fontface.family:
                try:
                    from js import resolve
                    resolve()
                except Exception as e:
                    raise ValueError("unable to resolve") from e

        RendererHTMLCanvas.load_font_into_web = load_font_into_web_wrapper
        """
    )


def save_canvas_data(selenium, output_path):
    canvas_data = selenium.run(
        """
        import base64
        canvas = plt.gcf().canvas.get_element("canvas")
        canvas_data = canvas.toDataURL("image/png")[21:]
        canvas_data
        """
    )

    canvas_png = base64.b64decode(canvas_data)
    output_path.write_bytes(canvas_png)


def compare_with_reference_image(selenium, reference_image):
    reference_image_encoded = base64.b64encode(reference_image.read_bytes())
    deviation = selenium.run(
        f"""
        import io
        import base64
        import numpy as np
        from PIL import Image
        canvas_data = plt.gcf().canvas.get_pixel_data()
        ref_data = np.asarray(Image.open(io.BytesIO(base64.b64decode({reference_image_encoded!r}))))

        deviation = np.mean(np.abs(canvas_data - ref_data))
        float(deviation)
        """
    )

    # Note: uncomment this line if you want to save the output canvas image (for comparison).
    # save_canvas_data(selenium, reference_image.with_name(f"output-{reference_image.name}"))

    return deviation == 0.0


@matplotlib_test_decorator
def test_matplotlib(selenium):
    selenium.load_package("matplotlib")
    selenium.run(
        """
        from matplotlib import pyplot as plt
        plt.figure()
        plt.plot([1,2,3])
        plt.show()
        """
    )


@matplotlib_test_decorator
def test_svg(selenium):
    selenium.load_package("matplotlib")
    content = selenium.run(
        """
        from matplotlib import pyplot as plt
        import io
        plt.figure()
        x = plt.plot([1,2,3])
        fd = io.BytesIO()
        plt.savefig(fd, format='svg')
        fd.getvalue().decode('utf8')
        """
    )
    assert len(content) == 14998
    assert content.startswith("<?xml")


@matplotlib_test_decorator
def test_pdf(selenium):
    selenium.load_package("matplotlib")
    selenium.run(
        """
        from matplotlib import pyplot as plt
        plt.figure()
        x = plt.plot([1,2,3])
        import io
        fd = io.BytesIO()
        plt.savefig(fd, format='pdf')
        """
    )


def test_font_manager(selenium):
    """
    Comparing vendored fontlist.json version with the one built
    by font_manager.py.

    If you try to update Matplotlib and this test fails, try to
    update fontlist.json.
    """
    selenium.load_package("matplotlib")
    selenium.run(
        """
        from matplotlib import font_manager as fm
        import os
        import json

        # get fontlist form file
        fontist_file = os.path.join(os.path.dirname(fm.__file__), 'fontlist.json')
        with open(fontist_file) as f:
            fontlist_vendor = json.loads(f.read())

        # get fontlist from build
        fontlist_built = json.loads(json.dumps(fm.FontManager(), cls=fm._JSONEncoder))

        # reodering list to compare
        for list in ('afmlist', 'ttflist'):
            for fontlist in (fontlist_vendor, fontlist_built):
                fontlist[list].sort(key=lambda x: x['fname'])
        """
    )
    assert selenium.run("fontlist_built == fontlist_vendor")


@matplotlib_test_decorator
def test_rendering(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import numpy as np
        from matplotlib import pyplot as plt
        t = np.arange(0.0, 2.0, 0.01)
        s = 1 + np.sin(2 * np.pi * t)
        plt.figure()
        plt.plot(t, s, linewidth=1.0, marker=11)
        plt.plot(t, t)
        plt.grid(True)
        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_draw_image(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import numpy as np
        import matplotlib.cm as cm
        import matplotlib.pyplot as plt
        import matplotlib.cbook as cbook
        from matplotlib.path import Path
        from matplotlib.patches import PathPatch
        delta = 0.025
        x = y = np.arange(-3.0, 3.0, delta)
        X, Y = np.meshgrid(x, y)
        Z1 = np.exp(-X**2 - Y**2)
        Z2 = np.exp(-(X - 1)**2 - (Y - 1)**2)
        Z = (Z1 - Z2) * 2
        plt.figure()
        plt.imshow(Z, interpolation='bilinear', cmap=cm.RdYlGn,
                origin='lower', extent=[-3, 3, -3, 3],
                vmax=abs(Z).max(), vmin=-abs(Z).max())
        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-image-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_draw_image_affine_transform(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import numpy as np
        import matplotlib.pyplot as plt
        import matplotlib.transforms as mtransforms

        def get_image():
            delta = 0.25
            x = y = np.arange(-3.0, 3.0, delta)
            X, Y = np.meshgrid(x, y)
            Z1 = np.exp(-X**2 - Y**2)
            Z2 = np.exp(-(X - 1)**2 - (Y - 1)**2)
            Z = (Z1 - Z2)
            return Z

        def do_plot(ax, Z, transform):
            im = ax.imshow(Z, interpolation='none',
                        origin='lower',
                        extent=[-2, 4, -3, 2], clip_on=True)

            trans_data = transform + ax.transData
            im.set_transform(trans_data)

            # display intended extent of the image
            x1, x2, y1, y2 = im.get_extent()
            ax.plot([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1], "y--",
                    transform=trans_data)
            ax.set_xlim(-5, 5)
            ax.set_ylim(-4, 4)

        # prepare image and figure
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
        Z = get_image()

        # image rotation
        do_plot(ax1, Z, mtransforms.Affine2D().rotate_deg(30))

        # image skew
        do_plot(ax2, Z, mtransforms.Affine2D().skew_deg(30, 15))

        # scale and reflection
        do_plot(ax3, Z, mtransforms.Affine2D().scale(-1, .5))

        # everything and a translation
        do_plot(ax4, Z, mtransforms.Affine2D().
                rotate_deg(30).skew_deg(30, 15).scale(-1, .5).translate(.5, -1))

        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-image-affine-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_draw_text_rotated(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import os
        os.environ["TESTING_MATPLOTLIB"] = "1"

        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import matplotlib.pyplot as plt
        from matplotlib.dates import (
            YEARLY, DateFormatter,
            rrulewrapper, RRuleLocator,
            drange)
        import numpy as np
        import datetime

        # tick every 5th easter
        np.random.seed(42)
        rule = rrulewrapper(YEARLY, byeaster=1, interval=5)
        loc = RRuleLocator(rule)
        formatter = DateFormatter('%m/%d/%y')
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
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-text-rotated-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_draw_math_text(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        """
        + r"""
        import os
        os.environ["TESTING_MATPLOTLIB"] = "1"

        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        from js import window
        window.testingMatplotlib = True
        import matplotlib.pyplot as plt
        import sys
        import re

        # Selection of features following
        # "Writing mathematical expressions" tutorial
        mathtext_titles = {
            0: "Header demo",
            1: "Subscripts and superscripts",
            2: "Fractions, binomials and stacked numbers",
            3: "Radicals",
            4: "Fonts",
            5: "Accents",
            6: "Greek, Hebrew",
            7: "Delimiters, functions and Symbols"}
        n_lines = len(mathtext_titles)

        # Randomly picked examples
        mathext_demos = {
            0: r"$W^{3\beta}_{\delta_1 \rho_1 \sigma_2} = "
            r"U^{3\beta}_{\delta_1 \rho_1} + \frac{1}{8 \pi 2} "
            r"\int^{\alpha_2}_{\alpha_2} d \alpha^\prime_2 \left[\frac{ "
            r"U^{2\beta}_{\delta_1 \rho_1} - \alpha^\prime_2U^{1\beta}_"
            r"{\rho_1 \sigma_2} }{U^{0\beta}_{\rho_1 \sigma_2}}\right]$",

            1: r"$\alpha_i > \beta_i,\ "
            r"\alpha_{i+1}^j = {\rm sin}(2\pi f_j t_i) e^{-5 t_i/\tau},\ "
            r"\ldots$",

            2: r"$\frac{3}{4},\ \binom{3}{4},\ \genfrac{}{}{0}{}{3}{4},\ "
            r"\left(\frac{5 - \frac{1}{x}}{4}\right),\ \ldots$",

            3: r"$\sqrt{2},\ \sqrt[3]{x},\ \ldots$",

            4: r"$\mathrm{Roman}\ , \ \mathit{Italic}\ , \ \mathtt{Typewriter} \ "
            r"\mathrm{or}\ \mathcal{CALLIGRAPHY}$",

            5: r"$\acute a,\ \bar a,\ \breve a,\ \dot a,\ \ddot a, \ \grave a, \ "
            r"\hat a,\ \tilde a,\ \vec a,\ \widehat{xyz},\ \widetilde{xyz},\ "
            r"\ldots$",

            6: r"$\alpha,\ \beta,\ \chi,\ \delta,\ \lambda,\ \mu,\ "
            r"\Delta,\ \Gamma,\ \Omega,\ \Phi,\ \Pi,\ \Upsilon,\ \nabla,\ "
            r"\aleph,\ \beth,\ \daleth,\ \gimel,\ \ldots$",

            7: r"$\coprod,\ \int,\ \oint,\ \prod,\ \sum,\ "
            r"\log,\ \sin,\ \approx,\ \oplus,\ \star,\ \varpropto,\ "
            r"\infty,\ \partial,\ \Re,\ \leftrightsquigarrow, \ \ldots$"}


        def doall():
            # Colors used in mpl online documentation.
            mpl_blue_rvb = (191. / 255., 209. / 256., 212. / 255.)
            mpl_orange_rvb = (202. / 255., 121. / 256., 0. / 255.)
            mpl_grey_rvb = (51. / 255., 51. / 255., 51. / 255.)

            # Creating figure and axis.
            plt.figure(figsize=(6, 7))
            plt.axes([0.01, 0.01, 0.98, 0.90], facecolor="white", frameon=True)
            plt.gca().set_xlim(0., 1.)
            plt.gca().set_ylim(0., 1.)
            plt.gca().set_title("Matplotlib's math rendering engine",
                                color=mpl_grey_rvb, fontsize=14, weight='bold')
            plt.gca().set_xticklabels("", visible=False)
            plt.gca().set_yticklabels("", visible=False)

            # Gap between lines in axes coords
            line_axesfrac = (1. / (n_lines))

            # Plotting header demonstration formula
            full_demo = mathext_demos[0]
            plt.annotate(full_demo,
                        xy=(0.5, 1. - 0.59 * line_axesfrac),
                        color=mpl_orange_rvb, ha='center', fontsize=20)

            # Plotting features demonstration formulae
            for i_line in range(1, n_lines):
                baseline = 1 - (i_line) * line_axesfrac
                baseline_next = baseline - line_axesfrac
                title = mathtext_titles[i_line] + ":"
                fill_color = ['white', mpl_blue_rvb][i_line % 2]
                plt.fill_between([0., 1.], [baseline, baseline],
                                [baseline_next, baseline_next],
                                color=fill_color, alpha=0.5)
                plt.annotate(title,
                            xy=(0.07, baseline - 0.3 * line_axesfrac),
                            color=mpl_grey_rvb, weight='bold')
                demo = mathext_demos[i_line]
                plt.annotate(demo,
                            xy=(0.05, baseline - 0.75 * line_axesfrac),
                            color=mpl_grey_rvb, fontsize=16)

            for i in range(n_lines):
                s = mathext_demos[i]
                print(i, s)
            plt.show()
        doall()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-math-text-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_custom_font_text(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi(target_font='cmsy10')}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import matplotlib.pyplot as plt
        import numpy as np

        f = {{'fontname': 'cmsy10'}}

        t = np.arange(0.0, 2.0, 0.01)
        s = 1 + np.sin(2 * np.pi * t)
        plt.figure()
        plt.title('A simple Sine Curve', **f)
        plt.plot(t, s, linewidth=1.0, marker=11)
        plt.plot(t, t)
        plt.grid(True)
        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium,
        REFERENCE_IMAGES_PATH / f"canvas-custom-font-text-{selenium.browser}.png",
    )


@matplotlib_test_decorator
def test_zoom_on_polar_plot(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import numpy as np
        import matplotlib.pyplot as plt
        np.random.seed(42)

        # Compute pie slices
        N = 20
        theta = np.linspace(0.0, 2 * np.pi, N, endpoint=False)
        radii = 10 * np.random.rand(N)
        width = np.pi / 4 * np.random.rand(N)

        ax = plt.subplot(111, projection='polar')
        bars = ax.bar(theta, radii, width=width, bottom=0.0)

        # Use custom colors and opacity
        for r, bar in zip(radii, bars):
            bar.set_facecolor(plt.cm.viridis(r / 10.))
            bar.set_alpha(0.5)

        ax.set_rlim([0,5])
        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-polar-zoom-{selenium.browser}.png"
    )


@matplotlib_test_decorator
def test_transparency(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("matplotlib")
    selenium.set_script_timeout(60)
    run_with_resolve(
        selenium,
        f"""
        {patch_font_loading_and_dpi()}
        import matplotlib
        matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
        import numpy as np
        np.random.seed(19680801)
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        for color in ['tab:blue', 'tab:orange', 'tab:green']:
            n = 100
            x, y = np.random.rand(2, n)
            scale = 200.0 * np.random.rand(n)
            ax.scatter(x, y, c=color, s=scale, label=color,
                    alpha=0.3, edgecolors='none')

        ax.legend()
        ax.grid(True)

        plt.show()
        """,
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / f"canvas-transparency-{selenium.browser}.png"
    )
