#!/usr/bin/env python

import json
import random
import sys

random.seed(0)

print("Content-Type: application/json")
print()

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
N_ROWS = 91746

data = {}

for name, generator in columns:
    column = {}
    for i in range(N_ROWS):
        column[str(i)] = generator()
    data[name] = column

json.dump(data, sys.stdout)
