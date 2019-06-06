import numpy as np
from matplotlib.backends.browser_backend import \
    FigureCanvasWasm, NavigationToolbar2Wasm
from matplotlib.backend_bases import (
    GraphicsContextBase, RendererBase,
    FigureManagerBase, _Backend
)

from matplotlib import cbook, __version__
from matplotlib.colors import colorConverter, rgb2hex
from matplotlib.transforms import Affine2D
from matplotlib.path import Path
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
            renderer = RendererHTMLCanvas(ctx, width, height,
                                          dpi=self.figure.dpi)
            self.figure.draw(renderer)
        finally:
            self.figure.dpi = orig_dpi
            self._idle_scheduled = False

    def get_pixel_data(self):
        canvas = self.get_element('canvas')
        ctx = canvas.getContext("2d")
        canvas_data = ctx.getImageData(0, 0, int(ctx.width),
                                       int(ctx.height)).data
        canvas_data = np.asarray(canvas_data, dtype=np.uint8)
        pixel_data = np.reshape(canvas_data, (int(ctx.height),
                                int(ctx.width), 4))
        return pixel_data

    def print_png(self, filename_or_obj, *args,
                  metadata=None, **kwargs):

        from matplotlib import _png

        if metadata is None:
            metadata = {}
        metadata = {
            "Software":
                f"matplotlib version{__version__}, http://matplotlib.org/",
            **metadata,
        }

        data = self.get_pixel_data()
        with cbook.open_file_cm(filename_or_obj, "wb") as fh:
            _png.write_png(data, fh, self.figure.dpi, metadata=metadata)


class NavigationToolbar2HTMLCanvas(NavigationToolbar2Wasm):

    def download(self, format, mimetype):
        # Creates a temporary `a` element with a URL containing the image
        # content, and then virtually clicks it. Kind of magical, but it
        # works...
        element = document.createElement('a')
        data = io.BytesIO()

        if format == 'png':
            FigureCanvasHTMLCanvas.print_png(self.canvas, data)
        else:
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

    def _matplotlib_color_to_CSS(self, color, alpha=None, is_RGB=True):
        if not is_RGB:
            R, G, B, alpha = colorConverter.to_rgba(color)
            color = (R, G, B)

        if (len(color) == 4) and (alpha is None):
            alpha = color[3]

        if alpha is None:
            CSS_color = rgb2hex(color[:3])

        else:
            R = int(color[0] * 255)
            G = int(color[1] * 255)
            B = int(color[2] * 255)
            CSS_color = """rgba({0:d}, {1:d},
                                {2:d}, {3:.3g})""".format(R, G, B, alpha)

        return CSS_color

    def _set_style(self, gc, rgbFace=None):
        if rgbFace is not None:
            self.ctx.fillStyle = self._matplotlib_color_to_CSS(rgbFace,
                                                               gc.get_alpha())

        if gc.get_capstyle():
            self.ctx.lineCap = _capstyle_d[gc.get_capstyle()]

        self.ctx.strokeStyle = self._matplotlib_color_to_CSS(gc.get_rgb(),
                                                             gc.get_alpha())
        self.ctx.lineWidth = self.points_to_pixels(gc.get_linewidth())

    def _path_helper(self, ctx, path, transform, clip=None):
        ctx.beginPath()
        for points, code in path.iter_segments(transform,
                                               remove_nans=True, clip=clip):
            points += 0.5
            if code == Path.MOVETO:
                ctx.moveTo(points[0], points[1])
            elif code == Path.LINETO:
                ctx.lineTo(points[0], points[1])
            elif code == Path.CURVE3:
                ctx.quadraticCurveTo(*points)
            elif code == Path.CURVE4:
                ctx.bezierCurveTo(*points)
            elif code == Path.CLOSEPOLY:
                ctx.closePath()

    def draw_path(self, gc, path, transform, rgbFace=None):
        self._set_style(gc, rgbFace)
        if rgbFace is None and gc.get_hatch() is None:
            figure_clip = (0, 0, self.width, self.height)

        else:
            figure_clip = None

        transform += Affine2D().scale(1, -1).translate(0, self.height)
        self._path_helper(self.ctx, path, transform, figure_clip)
        self.ctx.stroke()

        if rgbFace is not None:
            self.ctx.fill()
            self.ctx.fillStyle = '#000000'

    def draw_markers(self, gc, marker_path, marker_trans, path,
                     trans, rgbFace=None):
        super().draw_markers(gc, marker_path, marker_trans, path,
                             trans, rgbFace)


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
