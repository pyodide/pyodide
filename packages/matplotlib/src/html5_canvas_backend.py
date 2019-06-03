import numpy as np
from matplotlib.backends.browser_backend import \
    FigureCanvasWasm, NavigationToolbar2Wasm
from matplotlib.backend_bases import (
    GraphicsContextBase, RendererBase,
    FigureManagerBase, _Backend
)
from matplotlib import interactive

from js import document

import base64
import io

_capstyle_d = {'projecting': 'square', 'butt': 'butt', 'round': 'round'}

interactive(True)


class FigureCanvasHTMLCanvas(FigureCanvasWasm):

    def __init__(self, *args, **kwargs):
        FigureCanvasWasm.__init__(self, *args, **kwargs)

    def draw(self):
        # Render the figure using custom renderer
        self._idle_scheduled = True
        orig_dpi = self.figure.dpi
        if self._ratio != 1:
            self.figure.dpi *= self._ratio
        try:
            width, height = self.get_width_height()
            canvas = self.get_element('canvas')
            if canvas is None:
                return
            ctx = canvas.getContext("2d")
            renderer = RendererHTMLCanvas(ctx, width, height, dpi=72)
            self.figure.draw(renderer)
        finally:
            self.figure.dpi = orig_dpi
            self._idle_scheduled = False


class NavigationToolbar2HTMLCanvas(NavigationToolbar2Wasm):
    """
    Is a copy of what Agg backend uses, needs to change!
    """
    def download(self, format, mimetype):
        # Creates a temporary `a` element with a URL containing the image
        # content, and then virtually clicks it. Kind of magical, but it
        # works...
        element = document.createElement('a')
        data = io.BytesIO()
        try:
            self.canvas.figure.savefig(data, format=format)
        except Exception:
            raise
        element.setAttribute('href', 'data:{};base64,{}'.format(
            mimetype, base64.b64encode(data.getvalue()).decode('ascii')))
        element.setAttribute('download', 'plot.{}'.format(format))
        element.style.display = 'none'
        document.body.appendChild(element)
        element.click()
        document.body.removeChild(element)


class GraphicsContextHTMLCanvas(GraphicsContextBase):

    def __init__(self, renderer):
        super().__init__()
        self.renderer = renderer

    def restore(self):
        self.renderer.ctx.restore()

    def set_capstyle(self, cs):
        if cs in ['butt', 'round', 'projecting']:
            self._capstyle = cs
            self.renderer.ctx.lineCap = _capstyle_d[cs]
        else:
            raise ValueError('Unrecognized cap style. Found {0}'.format(cs))

    def set_dashes(self, dash_offset, dash_list):
        self._dashes = dash_offset, dash_list
        if dash_offset is not None:
            self.renderer.ctx.lineDashOffset = dash_offset
        if dash_list is None:
            self.renderer.ctx.setLineDash([])
        else:
            dl = np.asarray(dash_list)
            dl = list(self.renderer.points_to_pixels(dl))
            self.renderer.ctx.setLineDash(dl)

    def set_joinstyle(self, js):
        if js in ['miter', 'round', 'bevel']:
            self._joinstyle = js
            self.renderer.ctx.lineJoin = js
        else:
            raise ValueError('Unrecognized join style. Found {0}'.format(js))

    def set_linewidth(self, w):
        self._linewidth = float(w)
        self.renderer.ctx.lineWidth = self.renderer.points_to_pixels(float(w))


class RendererHTMLCanvas(RendererBase):

    def __init__(self, ctx, width, height, dpi):
        super().__init__()
        self.ctx = ctx
        self.width = width
        self.height = height
        self.ctx.width = self.width
        self.ctx.height = self.height
        self.dpi = dpi

    def new_gc(self):
        return GraphicsContextHTMLCanvas(renderer=self)

    def points_to_pixels(self, points):
        return (points / 72.0) * self.dpi


class FigureManagerHTMLCanvas(FigureManagerBase):

    def __init__(self, canvas, num):
        super().__init__(canvas, num)
        self.set_window_title("Figure %d" % num)
        self.toolbar = NavigationToolbar2HTMLCanvas(canvas)

    def show(self):
        self.canvas.show()

    def resize(self, w, h):
        pass

    def set_window_title(self, title):
        self.canvas.set_window_title(title)


@_Backend.export
class _BackendHTMLCanvas(_Backend):
    FigureCanvas = FigureCanvasHTMLCanvas
    FigureManager = FigureManagerHTMLCanvas

    @staticmethod
    def show():
        from matplotlib import pyplot as plt
        plt.gcf().canvas.show()
