/**
 * Bundle the stack switching folder as iife and then export names exported from
 * stack_switching.mjs onto Module and into the Emscripten namespace.
 */

import { build } from 'esbuild'
import { dirname, join } from 'node:path'

const __dirname = dirname(new URL(import.meta.url).pathname)

const outfile = join(__dirname, 'stack_switching.out.js')
const globalName = 'StackSwitching'

const config = {
  entryPoints: [join(__dirname, 'stack_switching.mjs')],
  outfile,
  format: 'iife',
  bundle: true,
  globalName,
  metafile: true,
}

// First build as "esm" to get the list of exports. The metafile doesn't list
// exports except when we set `format: "esm"`. Setting bundle: false saves a
// tiny amount of time on this pass.
const { metafile } = await build(
  Object.assign({}, config, { format: 'esm', bundle: false }),
)

// The file name is the metafile.outputs key. It is relative to the current
// working directory, so it's annoying to work it out. There will only be one
// key in any case, so we just extract it with Object.values().
const exports = Object.values(metafile.outputs)[0].exports

// Add a footer that destructures the exports into the Emscripten namespace.
// Also Object.assign them onto Module.
const footer = `
  const {${exports}} = ${globalName};
  Object.assign(Module, ${globalName});
`.replaceAll(/\s/g, '')
config.footer = { js: footer }

// Build again, this time as an iife bundle with our extra footer.
await build(config)
