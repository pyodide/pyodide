import numpy as np
from matplotlib.backend_bases import GraphicsContextBase, RendererBase

_capstyle_d = {'projecting' : 'square', 'butt' : 'butt', 'round': 'round'}

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
            self.renderer.ctx.setLineDash(list(self.renderer.points_to_pixels(dl)))

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
