import sys
from pathlib import Path
import asyncio
import time

sys.path.append(str((Path(__file__).absolute().parent.parent / "pyodide-py")))

import asyncio
from threading import Thread


from _pyodide.syncify import (
    SyncifyableTask,
    syncify,
    TrivialSyncifier,
    set_syncifier,
)

set_syncifier(TrivialSyncifier())


class SleepTask(SyncifyableTask):
    def __init__(self, s):
        super().__init__()
        self.sleep_time = s
        self.completed = False

    def run(self):
        time.sleep(self.sleep_time)
        self.completed = True

    def do_sync(self):
        t = Thread(target=self.run)
        t.start()
        while True:
            if not t.is_alive():
                assert self.completed == True
                return
            yield

    async def do_async(self):
        await asyncio.sleep(self.sleep_time)


async def slow_gen():
    for i in range(1, 5):
        await SleepTask(i / 100)
        yield i


async def t1():
    last_time = time.time()

    def dt():
        nonlocal last_time
        cur_time = time.time()
        res = cur_time - last_time
        last_time = cur_time
        return res

    result = []
    async for x in slow_gen():
        result.append([dt(), x])
    await SleepTask(7 / 100)
    result.append([dt(), 7])
    return result


def test_syncify():
    result = syncify(t1())
    for [time, val] in result:
        assert val / 100 < time < val / 100 + 0.05

    result = asyncio.get_event_loop().run_until_complete(t1())
    for [time, val] in result:
        assert val / 100 < time < val / 100 + 0.05
