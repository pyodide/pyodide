from pytest_pyodide import run_in_pyodide


async def echo(ws):
    async for msg in ws:
        await ws.send(msg)
        break
    running.set_result(False)


async def start_echo_server():
    import asyncio
    from websockets import serve

    global running
    running = asyncio.Future()
    async with serve(echo, "localhost", 8765) as server:
        await running


async def hello():
    from websockets import connect

    uri = "ws://localhost:8765"
    async with connect(uri) as ws:
        await ws.send("Hello, World!")
        msg = await ws.recv()
        assert msg == "Hello, World!"


@run_in_pyodide(packages=["websockets"])
async def test_websockets():
    import asyncio

    server_task = asyncio.create_task(start_echo_server())
    hello_task = asyncio.create_task(hello())
    await asyncio.gather(server_task, hello_task)
