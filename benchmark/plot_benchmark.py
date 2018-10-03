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
    results.append((k, v['firefox'] / v['native'], v['chrome'] / v['native']))
results.sort(key=lambda x: x[1], reverse=True)

names = [x[0] for x in results]
firefox = [x[1] for x in results]
chrome = [x[2] for x in results]

width = 0.35
y_pos = np.arange(len(results))
ax.barh(y_pos, firefox, width, color='#ff9400', label='firefox')
ax.barh(y_pos + width, chrome, width, color='#45a1ff', label='chrome')
ax.set_yticks(y_pos + width / 2)
ax.set_yticklabels(names)
ax.invert_yaxis()
ax.set_xlabel('Slowdown factor (WebAssembly:Native)')
ax.set_title('Python benchmarks')
ax.axvline(1.0, color='red')
ax.grid(axis='x')
ax.legend(loc='lower right')

plt.savefig(sys.argv[-1])
