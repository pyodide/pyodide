import io
from contextlib import redirect_stdout

from beepy import Style, Tag, mount, safe_html, state
from beepy.tags import button, p, textarea
from beepy.utils import ensure_sync, js

DEMO_CODE = safe_html(
    """# Example from python.org
def fib(n):
    a, b = 0, 1
    while a < n:
        print(a, end=' ')
        a, b = b, a+b
    print()
fib(1000)
"""
)


class Output(Tag, name="div"):
    children = [
        result := state("", model="change"),
    ]


class Main(Tag, name="main"):
    style = Style(
        button={"display": "block", "margin": "4px"},
        textarea={"height": "300px", "width": "400px"},
    )

    children = [
        run_btn := button("Run"),
        reset_btn := button("Reset"),
        input := textarea(value=DEMO_CODE),
        p("Output:"),
        out := Output(),
    ]

    @run_btn.on("click")
    async def run_code(self):
        with redirect_stdout(io.StringIO()) as f:
            await js.apy(self.input.value)
        self.out.result = f.getvalue()

    @reset_btn.on("click")
    def reset_to_demo(self):
        self.input.value = DEMO_CODE

    def mount(self):
        ensure_sync(self.run_code())


mount(Main(), "#root")
