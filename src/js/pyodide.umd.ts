import { loadPyodide, version } from './pyodide'
import { type PackageData } from './types'
export { loadPyodide, version, type PackageData }
;(globalThis as any).loadPyodide = loadPyodide
