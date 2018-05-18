from matplotlib.backends import backend_agg
from matplotlib.backend_bases import _Backend
from matplotlib import backend_bases, _png

from js import iodide
from js import document
from js import window
from js import ImageData
from js import Uint8ClampedArray


class FigureCanvasWasm(backend_agg.FigureCanvasAgg):
    supports_blit = False

    def __init__(self, *args, **kwargs):
        backend_agg.FigureCanvasAgg.__init__(self, *args, **kwargs)

        self._idle_scheduled = False
        self._id = "matplotlib_" + hex(id(self))[2:]

    def get_element(self):
        # TODO: Should we store a reference here instead of always looking it
        # up? I'm a little concerned about weird Python/JS
        # cross-memory-management issues...
        return document.getElementById(self._id)

    def get_canvas(self):
        return document.getElementById(self._id + 'canvas')

    def get_message_display(self):
        return document.getElementById(self._id + 'message')

    def show(self):
        renderer = self.get_renderer()
        width, height = self.get_width_height()
        div = iodide.output.element('div')
        div.id = self._id
        canvas = document.createElement('canvas')
        div.appendChild(canvas)
        canvas.id = self._id + 'canvas'
        canvas.setAttribute('width', width)
        canvas.setAttribute('height', height)
        canvas.addEventListener('click', self.onclick)
        canvas.addEventListener('mousemove', self.onmousemove)
        canvas.addEventListener('mouseup', self.onmouseup)
        canvas.addEventListener('mousedown', self.onmousedown)
        canvas.addEventListener('mouseenter', self.onmouseenter)
        canvas.addEventListener('mouseleave', self.onmouseleave)
        def ignore(event):
            event.preventDefault()
            return False
        window.addEventListener('contextmenu', ignore)
        bottom = document.createElement('div')
        toolbar = self.toolbar.get_element()
        bottom.appendChild(toolbar)
        message = document.createElement('span')
        message.id = self._id + 'message'
        bottom.appendChild(message)
        div.appendChild(bottom)
        self.draw()

    def draw(self):
        super().draw()
        width, height = self.get_width_height()
        canvas = self.get_canvas()
        image_data = ImageData.new(
            self.buffer_rgba(),
            width, height);
        ctx = canvas.getContext("2d");
        ctx.putImageData(image_data, 0, 0);
        self._idle_scheduled = False

    def draw_idle(self):
        if not self._idle_scheduled:
            self._idle_scheduled = True
            window.setTimeout(self.draw, 0)

    def set_message(self, message):
        message_display = self.get_message_display()
        if message_display is not None:
            message_display.textContent = message

    def _convert_mouse_event(self, event):
        width, height = self.get_width_height()
        x = event.offsetX
        y = height - event.offsetY
        button = event.button + 1
        if button == 3:
            event.preventDefault()
            event.stopPropagation()
        if button == 2:
            button = 3
        return x, y, button

    def onclick(self, event):
        x, y, button = self._convert_mouse_event(event)
        self.button_click_event(x, y, button, guiEvent=event)

    def onmousemove(self, event):
        x, y, button = self._convert_mouse_event(event)
        self.motion_notify_event(x, y, guiEvent=event)

    def onmouseup(self, event):
        x, y, button = self._convert_mouse_event(event)
        self.button_release_event(x, y, button, guiEvent=event)

    def onmousedown(self, event):
        x, y, button = self._convert_mouse_event(event)
        self.button_press_event(x, y, button, guiEvent=event)

    def onmouseenter(self, event):
        window.addEventListener('contextmenu', ignore)
        self.enter_notify_event(guiEvent=event)

    def onmouseleave(self, event):
        self.leave_notify_event(guiEvent=event)

    def onscroll(self, event):
        x, y, button = self._convert_mouse_event(event)
        self.scroll_event(x, y, event.deltaX, guiEvent=event)

    _cursor_map = {
        0: 'pointer',
        1: 'default',
        2: 'crosshair',
        3: 'move'
    }

    def set_cursor(self, cursor):
        self.get_canvas().style.cursor = self._cursor_map.get(cursor, 0)

    # def draw_cursor(self, event):
    #     # TODO
    #     pass

    # def get_window_title(self):
    #     # TODO
    #     pass

    # def set_window_title(self):
    #     # TODO
    #     pass

    # def resize_event(self):
    #     # TODO
    #     pass

    # def close_event(self):
    #     # TODO
    #     pass

    # def key_press_event(self):
    #     # TODO
    #     pass

    # def key_release_event(self):
    #     # TODO
    #     pass

    def new_timer(self, *args, **kwargs):
        return TimerWasm(*args, **kwargs)


_FONTAWESOME_ICONS = {
    'home': 'fa-home',
    'back': 'fa-arrow-left',
    'forward': 'fa-arrow-right',
    'zoom_to_rect': 'fa-search-plus',
    'move': 'fa-arrows',
    'download': 'download',
    None: None,
}


class NavigationToolbar2Wasm(backend_bases.NavigationToolbar2):
    def _init_toolbar(self):
        pass

    def get_element(self):
        div = document.createElement('span')
        for text, tooltip_text, image_file, name_of_method in self.toolitems:
            if image_file in _FONTAWESOME_ICONS:
                if image_file is None:
                    span = document.createElement('span')
                    span.style.minWidth = 16
                    span.style.textContent = ' '
                    div.appendChild(span)
                else:
                    button = document.createElement('button')
                    button.classList.add('fa')
                    button.classList.add(_FONTAWESOME_ICONS[image_file])
                    button.addEventListener('click', getattr(self, name_of_method))
                    div.appendChild(button)
        return div

    def set_message(self, message):
        self.canvas.set_message(message)

    def set_cursor(self, cursor):
        self.canvas.set_cursor(cursor)

    def draw_rubberband(self, event, x0, y0, x1, y1):
        pass

    def remove_rubberband(self):
        pass

    def save_figure(self, *args):
        pass


class FigureManagerWasm(backend_bases.FigureManagerBase):
    def __init__(self, canvas, num):
        backend_bases.FigureManagerBase.__init__(self, canvas, num)
        self.toolbar = NavigationToolbar2Wasm(canvas)

    def show(self):
        self.canvas.show()

    def resize(self, w, h):
        pass


class TimerWasm(backend_bases.TimerBase):
    def _timer_start(self):
        self._timer_stop()
        if self._single:
            self._timer = window.setTimeout(self._on_timer, self.interval)
        else:
            self._timer = window.setInterval(self._on_timer, self.interval)

    def _timer_stop(self):
        if self._timer is None:
            return
        elif self._single:
            window.clearTimeout(self._timer)
            self._timer = None
        else:
            window.clearInterval(self._timer)
            self._timer = None

    def _timer_set_interval(self):
        # Only stop and restart it if the timer has already been started
        if self._timer is not None:
            self._timer_stop()
            self._timer_start()


@_Backend.export
class _BackendWasmCoreAgg(_Backend):
    FigureCanvas = FigureCanvasWasm
    FigureManager = FigureManagerWasm

    @staticmethod
    def show():
        from matplotlib import pyplot as plt
        plt.gcf().canvas.show()
