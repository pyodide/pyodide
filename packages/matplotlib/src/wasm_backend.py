from matplotlib.backends.browser_backend import \
    FigureCanvasWasm, NavigationToolbar2Wasm

from matplotlib.backends import backend_agg
from matplotlib.backend_bases import _Backend, FigureManagerBase
from matplotlib import interactive

from js import document
from js import ImageData

import base64
import io

interactive(True)


class FigureCanvasAggWasm(backend_agg.FigureCanvasAgg, FigureCanvasWasm):

    def __init__(self, *args, **kwargs):
        backend_agg.FigureCanvasAgg.__init__(self, *args, **kwargs)
        FigureCanvasWasm.__init__(self, *args, **kwargs)

    def draw(self):
        from pyodide import create_proxy

        # Render the figure using Agg
        self._idle_scheduled = True
        orig_dpi = self.figure.dpi
        if self._ratio != 1:
            self.figure.dpi *= self._ratio
        pixels_proxy = None
        pixels_buf = None
        try:
            super().draw()
            # Copy the image buffer to the canvas
            width, height = self.get_width_height()
            canvas = self.get_element("canvas")
            if canvas is None:
                return
            pixels = self.buffer_rgba().tobytes()
            pixels_proxy = create_proxy(pixels)
            pixels_buf = pixels_proxy.getBuffer("u8clamped")
            image_data = ImageData.new(pixels_buf.data, width, height)
            ctx = canvas.getContext("2d")
            ctx.putImageData(image_data, 0, 0)
        finally:
            self.figure.dpi = orig_dpi
            self._idle_scheduled = False
            if pixels_proxy:
                pixels_proxy.destroy()
            if pixels_buf:
                pixels_buf.release()


class NavigationToolbar2AggWasm(NavigationToolbar2Wasm):

    def download(self, format, mimetype):
        # Creates a temporary `a` element with a URL containing the image
        # content, and then virtually clicks it. Kind of magical, but it
        # works...
        element = document.createElement("a")
        data = io.BytesIO()
        try:
            self.canvas.figure.savefig(data, format=format)
        except Exception:
            raise
        element.setAttribute(
            "href",
            "data:{};base64,{}".format(
                mimetype, base64.b64encode(data.getvalue()).decode("ascii")
            ),
        )
        element.setAttribute("download", "plot.{}".format(format))
        element.style.display = "none"
        document.body.appendChild(element)
        element.click()
        document.body.removeChild(element)


class FigureManagerAggWasm(FigureManagerBase):

    def __init__(self, canvas, num):
        super().__init__(canvas, num)
        self.set_window_title("Figure %d" % num)
        self.toolbar = NavigationToolbar2AggWasm(canvas)

    def show(self):
        self.canvas.show()

    def resize(self, w, h):
        pass

    def set_window_title(self, title):
        self.canvas.set_window_title(title)


@_Backend.export
class _BackendWasmCoreAgg(_Backend):
    FigureCanvas = FigureCanvasAggWasm
    FigureManager = FigureManagerAggWasm

    @staticmethod
    def show():
        from matplotlib import pyplot as plt

        plt.gcf().canvas.show()
