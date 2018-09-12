#!/usr/bin/env python

import json
import random
import sys

random.seed(0)

columns = [
    ('column0', lambda: 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX'),
    ('column1', lambda: random.choice([
        'notification-interval-longer', 'notification-interval-short', 'control'])),
    ('column2', lambda: random.choice([True, False])),
    ('column3', lambda: random.randint(0, 4)),
    ('column4', lambda: random.randint(0, 4)),
    ('column5', lambda: random.randint(0, 4)),
    ('column6', lambda: random.randint(0, 4)),
    ('column7', lambda: random.randint(0, 4))
]

N_ROWS = 91746  # the output JSON size will be ~15 MB/10k rows


class StreamDict(dict):
    """
    To serialize to JSON, we create an iterable object that inherits from a
    known supported object type: dict.
    """
    def __init__(self, generator):
        self.generator = generator

    def items(self):
        for i in range(N_ROWS):
            yield i, self.generator()

    def __len__(self):
        return 1


data = {}
for name, generator in columns:
    data[name] = StreamDict(generator)


print("Content-Type: application/json")
print()
json.dump(data, sys.stdout)
