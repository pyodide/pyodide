export async function runBenchmark(loadPyodide, distName, iterations, pystonePath) {
  const py = await loadPyodide();

  const pystoneCode = read(pystonePath);
  py.runPython(pystoneCode);

  console.log(`=== ${distName} ===`);
  const msValues = [];
  for (let i = 0; i < iterations; i++) {
    const proxy = py.runPython(`[run_benchmark() * 1000]`);
    const result = proxy.toJs();
    proxy.destroy();
    const ms = result[0];
    msValues.push(ms);
    console.log(`  Run ${i + 1}: ${ms.toFixed(1)}ms`);
  }

  const min = Math.min(...msValues);
  const max = Math.max(...msValues);
  const avg = msValues.reduce((a, b) => a + b, 0) / msValues.length;
  console.log(
    `  Min: ${min.toFixed(1)}ms  Avg: ${avg.toFixed(1)}ms  Max: ${max.toFixed(1)}ms`,
  );
}
