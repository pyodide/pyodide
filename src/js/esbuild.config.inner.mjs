import { build } from 'esbuild'
import { config } from './esbuild.config.shared.mjs'

try {
  await build(
    config({
      input: 'api',
      output: 'src/js/generated/_pyodide.out.js',
      format: 'iife',
    }),
  )
} catch ({ message }) {
  console.error(message)
}
