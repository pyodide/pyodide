import matplotlib.pyplot as plt
import numpy as np
import json
import sys

plt.rcdefaults()
fig, ax = plt.subplots(constrained_layout=True, figsize=(8, 8))

with open(sys.argv[-2]) as fp:
    content = json.load(fp)

results = []
for k, v in content.items():
    results.append((k, v[1] / v[0]))
results.sort(key=lambda x: x[1], reverse=True)

names = [x[0] for x in results]
values = [x[1] for x in results]

y_pos = np.arange(len(results))
ax.barh(y_pos, values, align='center')
ax.set_yticks(y_pos)
ax.set_yticklabels(names)
ax.invert_yaxis()
ax.set_xlabel('Slowdown factor (WebAssembly:Native)')
ax.set_title('Python benchmarks')
ax.axvline(1.0, color='red')
ax.grid()

plt.savefig(sys.argv[-1])
