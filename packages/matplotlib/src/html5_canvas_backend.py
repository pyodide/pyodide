import numpy as np
from matplotlib.backends.browser_backend import FigureCanvasWasm, NavigationToolbar2Wasm
from matplotlib.backend_bases import (
    GraphicsContextBase,
    RendererBase,
    FigureManagerBase,
    _Backend,
)

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from matplotlib import __version__
from matplotlib.colors import colorConverter, rgb2hex
from matplotlib.transforms import Affine2D
from matplotlib.path import Path
from matplotlib import interactive

from matplotlib.cbook import maxdict
from matplotlib.font_manager import findfont
from matplotlib.ft2font import FT2Font, LOAD_NO_HINTING
from matplotlib.mathtext import MathTextParser

from pyodide import create_proxy

from js import document, window, XMLHttpRequest, ImageData, FontFace

import base64
import io
import math

_capstyle_d = {"projecting": "square", "butt": "butt", "round": "round"}

# The URLs of fonts that have already been loaded into the browser
_font_set = set()

if hasattr(window, "testing"):
    _base_fonts_url = "/fonts/"
else:
    _base_fonts_url = "/pyodide/fonts/"

interactive(True)


class FigureCanvasHTMLCanvas(FigureCanvasWasm):
    def __init__(self, *args, **kwargs):
        FigureCanvasWasm.__init__(self, *args, **kwargs)

        # A count of the fonts loaded. To support testing
        window.font_counter = 0

    def create_root_element(self):
        root_element = document.createElement("div")
        document.body.appendChild(root_element)
        return root_element

    def get_dpi_ratio(self, context):
        if hasattr(window, "testing"):
            return 2.0
        else:
            return super().get_dpi_ratio(context)

    def draw(self):
        # Render the figure using custom renderer
        self._idle_scheduled = True
        orig_dpi = self.figure.dpi
        if self._ratio != 1:
            self.figure.dpi *= self._ratio
        try:
            width, height = self.get_width_height()
            canvas = self.get_element("canvas")
            if canvas is None:
                return
            ctx = canvas.getContext("2d")
            renderer = RendererHTMLCanvas(ctx, width, height, self.figure.dpi, self)
            self.figure.draw(renderer)
        finally:
            self.figure.dpi = orig_dpi
            self._idle_scheduled = False

    def get_pixel_data(self):
        """
        Directly getting the underlying pixel data (using `getImageData()`)
        results in a different (but similar) image than the reference image.
        The method below takes a longer route
        (pixels --> encode PNG --> decode PNG --> pixels)
        but gives us the exact pixel data that the reference image has allowing
        us to do a fair comparison test.
        """
        canvas = self.get_element("canvas")
        img_URL = canvas.toDataURL("image/png")[21:]
        canvas_base64 = base64.b64decode(img_URL)
        return np.asarray(Image.open(io.BytesIO(canvas_base64)))

    def compare_reference_image(self, url, threshold):
        canvas_data = self.get_pixel_data()

        def _get_url_async(url, threshold):
            req = XMLHttpRequest.new()
            req.open("GET", url, True)
            req.responseType = "arraybuffer"

            def callback(e):
                if req.readyState == 4:
                    ref_data = np.asarray(Image.open(io.BytesIO(req.response.to_py())))
                    mean_deviation = np.mean(np.abs(canvas_data - ref_data))
                    window.deviation = mean_deviation

                    # converts a `numpy._bool` type explicitly to `bool`
                    window.result = bool(mean_deviation <= threshold)

            req.onreadystatechange = callback
            req.send(None)

        _get_url_async(url, threshold)

    def print_png(
        self, filename_or_obj, *args, metadata=None, pil_kwargs=None, **kwargs
    ):

        if metadata is None:
            metadata = {}
        if pil_kwargs is None:
            pil_kwargs = {}
        metadata = {
            "Software": f"matplotlib version{__version__}, http://matplotlib.org/",
            **metadata,
        }

        if "pnginfo" not in pil_kwargs:
            pnginfo = PngInfo()
            for k, v in metadata.items():
                pnginfo.add_text(k, v)
            pil_kwargs["pnginfo"] = pnginfo
        pil_kwargs.setdefault("dpi", (self.figure.dpi, self.figure.dpi))

        data = self.get_pixel_data()

        (Image.fromarray(data).save(filename_or_obj, format="png", **pil_kwargs))


class NavigationToolbar2HTMLCanvas(NavigationToolbar2Wasm):
    def download(self, format, mimetype):
        """
        Creates a temporary `a` element with a URL containing the image
        content, and then virtually clicks it. Kind of magical, but it
        works...
        """
        element = document.createElement("a")
        data = io.BytesIO()

        if format == "png":
            FigureCanvasHTMLCanvas.print_png(self.canvas, data)
        else:
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


class GraphicsContextHTMLCanvas(GraphicsContextBase):
    def __init__(self, renderer):
        super().__init__()
        self.stroke = True
        self.renderer = renderer

    def restore(self):
        self.renderer.ctx.restore()

    def set_capstyle(self, cs):
        if cs in ["butt", "round", "projecting"]:
            self._capstyle = cs
            self.renderer.ctx.lineCap = _capstyle_d[cs]
        else:
            raise ValueError("Unrecognized cap style. Found {0}".format(cs))

    def set_clip_rectangle(self, rectangle):
        self.renderer.ctx.save()
        if not rectangle:
            self.renderer.ctx.restore()
            return
        x, y, w, h = np.round(rectangle.bounds)
        self.renderer.ctx.beginPath()
        self.renderer.ctx.rect(x, self.renderer.height - y - h, w, h)
        self.renderer.ctx.clip()

    def set_clip_path(self, path):
        self.renderer.ctx.save()
        if not path:
            self.renderer.ctx.restore()
            return
        tpath, affine = path.get_transformed_path_and_affine()
        affine = affine + Affine2D().scale(1, -1).translate(0, self.renderer.height)
        self.renderer._path_helper(self.renderer.ctx, tpath, affine)
        self.renderer.ctx.clip()

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
        if js in ["miter", "round", "bevel"]:
            self._joinstyle = js
            self.renderer.ctx.lineJoin = js
        else:
            raise ValueError("Unrecognized join style. Found {0}".format(js))

    def set_linewidth(self, w):
        self.stroke = w != 0
        self._linewidth = float(w)
        self.renderer.ctx.lineWidth = self.renderer.points_to_pixels(float(w))


class RendererHTMLCanvas(RendererBase):
    def __init__(self, ctx, width, height, dpi, fig):
        super().__init__()
        self.fig = fig
        self.ctx = ctx
        self.width = width
        self.height = height
        self.ctx.width = self.width
        self.ctx.height = self.height
        self.dpi = dpi
        self.fontd = maxdict(50)
        self.mathtext_parser = MathTextParser("bitmap")

    def new_gc(self):
        return GraphicsContextHTMLCanvas(renderer=self)

    def points_to_pixels(self, points):
        return (points / 72.0) * self.dpi

    def _matplotlib_color_to_CSS(self, color, alpha, alpha_overrides, is_RGB=True):
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
            if len(color) == 3 or alpha_overrides:
                CSS_color = """rgba({0:d}, {1:d}, {2:d}, {3:.3g})""".format(
                    R, G, B, alpha
                )
            else:
                CSS_color = """rgba({0:d}, {1:d}, {2:d}, {3:.3g})""".format(
                    R, G, B, color[3]
                )

        return CSS_color

    def _set_style(self, gc, rgbFace=None):
        if rgbFace is not None:
            self.ctx.fillStyle = self._matplotlib_color_to_CSS(
                rgbFace, gc.get_alpha(), gc.get_forced_alpha()
            )

        if gc.get_capstyle():
            self.ctx.lineCap = _capstyle_d[gc.get_capstyle()]

        self.ctx.strokeStyle = self._matplotlib_color_to_CSS(
            gc.get_rgb(), gc.get_alpha(), gc.get_forced_alpha()
        )

        self.ctx.lineWidth = self.points_to_pixels(gc.get_linewidth())

    def _path_helper(self, ctx, path, transform, clip=None):
        ctx.beginPath()
        for points, code in path.iter_segments(transform, remove_nans=True, clip=clip):
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

        if rgbFace is not None:
            self.ctx.fill()
            self.ctx.fillStyle = "#000000"

        if gc.stroke:
            self.ctx.stroke()

    def draw_markers(self, gc, marker_path, marker_trans, path, trans, rgbFace=None):
        super().draw_markers(gc, marker_path, marker_trans, path, trans, rgbFace)

    def draw_image(self, gc, x, y, im, transform=None):
        im = np.flipud(im)
        h, w, d = im.shape
        y = self.ctx.height - y - h
        im = np.ravel(np.uint8(np.reshape(im, (h * w * d, -1)))).tobytes()
        pixels_proxy = create_proxy(im)
        pixels_buf = pixels_proxy.getBuffer("u8clamped")
        img_data = ImageData.new(pixels_buf.data, w, h)
        self.ctx.save()
        in_memory_canvas = document.createElement("canvas")
        in_memory_canvas.width = w
        in_memory_canvas.height = h
        in_memory_canvas_context = in_memory_canvas.getContext("2d")
        in_memory_canvas_context.putImageData(img_data, 0, 0)
        self.ctx.drawImage(in_memory_canvas, x, y, w, h)
        self.ctx.restore()
        pixels_proxy.destroy()
        pixels_buf.release()

    def _get_font(self, prop):
        key = hash(prop)
        font_value = self.fontd.get(key)
        if font_value is None:
            fname = findfont(prop)
            font_value = self.fontd.get(fname)
            if font_value is None:
                font = FT2Font(str(fname))
                font_file_name = fname[fname.rfind("/") + 1 :]
                font_value = font, font_file_name
                self.fontd[fname] = font_value
            self.fontd[key] = font_value
        font, font_file_name = font_value
        font.clear()
        font.set_size(prop.get_size_in_points(), self.dpi)
        return font, font_file_name

    def get_text_width_height_descent(self, s, prop, ismath):
        if ismath:
            image, d = self.mathtext_parser.parse(s, self.dpi, prop)
            w, h = image.get_width(), image.get_height()
        else:
            font, _ = self._get_font(prop)
            font.set_text(s, 0.0, flags=LOAD_NO_HINTING)
            w, h = font.get_width_height()
            w /= 64.0
            h /= 64.0
            d = font.get_descent() / 64.0
        return w, h, d

    def _draw_math_text(self, gc, x, y, s, prop, angle):
        rgba, descent = self.mathtext_parser.to_rgba(
            s, gc.get_rgb(), self.dpi, prop.get_size_in_points()
        )
        height, width, _ = rgba.shape
        angle = math.radians(angle)
        if angle != 0:
            self.ctx.save()
            self.ctx.translate(x, y)
            self.ctx.rotate(-angle)
            self.ctx.translate(-x, -y)
        self.draw_image(gc, x, -y - descent, np.flipud(rgba))
        if angle != 0:
            self.ctx.restore()

    def draw_text(self, gc, x, y, s, prop, angle, ismath=False, mtext=None):
        def _load_font_into_web(loaded_face):
            document.fonts.add(loaded_face)
            window.font_counter += 1
            self.fig.draw_idle()

        if ismath:
            self._draw_math_text(gc, x, y, s, prop, angle)
            return
        angle = math.radians(angle)
        width, height, descent = self.get_text_width_height_descent(s, prop, ismath)
        x -= math.sin(angle) * descent
        y -= math.cos(angle) * descent - self.ctx.height
        font_size = self.points_to_pixels(prop.get_size_in_points())

        _, font_file_name = self._get_font(prop)

        font_face_arguments = (
            prop.get_name(),
            "url({0})".format(_base_fonts_url + font_file_name),
        )

        # The following snippet loads a font into the browser's
        # environment if it wasn't loaded before. This check is necessary
        # to help us avoid loading the same font multiple times. Further,
        # it helps us to avoid the infinite loop of
        # load font --> redraw --> load font --> redraw --> ....

        if font_face_arguments not in _font_set:
            _font_set.add(font_face_arguments)
            f = FontFace.new(*font_face_arguments)
            f.load().then(_load_font_into_web)

        font_property_string = "{0} {1} {2:.3g}px {3}, {4}".format(
            prop.get_style(),
            prop.get_weight(),
            font_size,
            prop.get_name(),
            prop.get_family()[0],
        )
        if angle != 0:
            self.ctx.save()
            self.ctx.translate(x, y)
            self.ctx.rotate(-angle)
            self.ctx.translate(-x, -y)
        self.ctx.font = font_property_string
        self.ctx.fillStyle = self._matplotlib_color_to_CSS(
            gc.get_rgb(), gc.get_alpha(), gc.get_forced_alpha()
        )
        self.ctx.fillText(s, x, y)
        self.ctx.fillStyle = "#000000"
        if angle != 0:
            self.ctx.restore()


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
