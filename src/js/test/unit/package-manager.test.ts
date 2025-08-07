import * as chai from 'chai'
import sinon from 'sinon'
import { PackageManager, toStringArray } from '../../load-package.ts'
import { genMockAPI, genMockModule } from './test-helper.ts'
import { calculateInstallBaseUrl } from '../../compat'

describe('PackageManager', () => {
  it('should initialize with API and Module', () => {
    const mockApi = genMockAPI()
    const mockMod = genMockModule()
    const _ = new PackageManager(mockApi, mockMod)
  })
})

describe('logStdout and logStderr', () => {
  it('Should use console.log and console.error if no logger is provided', () => {
    const mockApi = genMockAPI()
    const mockMod = genMockModule()

    const pm = new PackageManager(mockApi, mockMod)

    const logSpy = sinon.spy(pm, 'stdout')
    const errorSpy = sinon.spy(pm, 'stderr')

    pm.logStdout('stdout')
    pm.logStderr('stderr')

    chai.assert.isTrue(logSpy.calledOnce)
    chai.assert.isTrue(errorSpy.calledOnce)
    chai.assert.isTrue(logSpy.calledWith('stdout'))
    chai.assert.isTrue(errorSpy.calledWith('stderr'))

    logSpy.restore()
    errorSpy.restore()
  })

  it('Should be overwritten when setCallbacks is called', () => {
    const mockApi = genMockAPI()
    const mockMod = genMockModule()

    const pm = new PackageManager(mockApi, mockMod)

    const stdoutLogger = sinon.spy()
    const stderrLogger = sinon.spy()

    pm.setCallbacks(
      stdoutLogger,
      stderrLogger,
    )(() => {
      pm.logStdout('stdout')
      pm.logStderr('stderr')
    })()

    chai.assert.isTrue(stdoutLogger.calledOnce)
    chai.assert.isTrue(stderrLogger.calledOnce)
    chai.assert.isTrue(stdoutLogger.calledWith('stdout'))
    chai.assert.isTrue(stderrLogger.calledWith('stderr'))
  })
})

describe('toStringArray', () => {
  it('Should convert string to array of strings', () => {
    chai.assert.deepEqual(toStringArray('hello'), ['hello'])
  })

  it('Should return the array if it is already an array', () => {
    chai.assert.deepEqual(toStringArray(['hello', 'world']), ['hello', 'world'])
  })

  it('Should convert PyProxy to array of strings', () => {
    // TODO: use real PyProxy
    const pyProxyMock = {
      toJs: () => ['hello', 'world'],
    }

    chai.assert.deepEqual(toStringArray(pyProxyMock), ['hello', 'world'])
  })
})

describe('getLoadedPackageChannel', () => {
  it('Should return the loaded package from loadedPackages obj', () => {
    const mockApi = genMockAPI()
    const mockMod = genMockModule()

    const pm = new PackageManager(mockApi, mockMod)
    pm.loadedPackages = {
      package: 'channel',
    }

    const loadedPackage = pm.getLoadedPackageChannel('package')
    chai.assert.equal(loadedPackage, 'channel')

    const notLoadedPackage = pm.getLoadedPackageChannel('notLoadedPackage')
    chai.assert.equal(notLoadedPackage, null)
  })

  describe('streamReady and flushing buffers', () => {
    it('Should flush stdout and stderr buffers when stream is ready', () => {
      const mockApi = genMockAPI()
      const mockMod = genMockModule()

      const logStdoutSpy = sinon.spy(mockMod, '_print_stdout')
      const logStderrSpy = sinon.spy(mockMod, '_print_stderr')

      const pm = new PackageManager(mockApi, mockMod)
      pm.logStdout('stdout message')
      pm.logStderr('stderr message')

      // not called yet, buffers should not be flushed
      chai.assert.isFalse(logStdoutSpy.called)
      chai.assert.isFalse(logStderrSpy.called)

      pm.flushBuffers()

      // now buffers should be flushed
      chai.assert.isTrue(logStdoutSpy.calledOnce)
      chai.assert.isTrue(logStderrSpy.calledOnce)
    })
  })
})

describe('calculateInstallBaseUrl', () => {
  let originalLocation: any

  beforeEach(() => {
    // Store original location
    originalLocation = globalThis.location
  })

  afterEach(() => {
    // Restore original location
    if (originalLocation) {
      globalThis.location = originalLocation
    } else {
      delete (globalThis as any).location
    }
  })

  it('Should extract base URL from absolute HTTP URL', () => {
    const result = calculateInstallBaseUrl(
      'https://cdn.example.com/pyodide/pyodide-lock.json',
    )
    chai.assert.equal(result, 'https://cdn.example.com/pyodide/')
  })

  it('Should extract base URL from file URL', () => {
    const result = calculateInstallBaseUrl(
      'file:///tmp/pyodide/pyodide-lock.json',
    )
    chai.assert.equal(result, 'file:///tmp/pyodide/')
  })

  it('Should extract base URL from relative URL with path', () => {
    const result = calculateInstallBaseUrl('./pyodide/pyodide-lock.json')
    chai.assert.equal(result, './pyodide/')
  })

  it('Should extract base URL from relative URL with parent directory', () => {
    const result = calculateInstallBaseUrl('../pyodide/pyodide-lock.json')
    chai.assert.equal(result, '../pyodide/')
  })

  it('Should handle URL with no path component', () => {
    const result = calculateInstallBaseUrl('pyodide-lock.json')
    chai.assert.equal(result, '.')
  })

  it('Should handle empty string', () => {
    const result = calculateInstallBaseUrl('')
    chai.assert.equal(result, '.')
  })

  it('Should fallback to location when URL has no slash', () => {
    // Mock browser location
    ;(globalThis as any).location = {
      toString: () => 'https://example.com/app/',
    }

    const result = calculateInstallBaseUrl('pyodide-lock.json')
    chai.assert.equal(result, 'https://example.com/app/')
  })

  it('Should fallback to location when URL is empty', () => {
    // Mock browser location
    ;(globalThis as any).location = {
      toString: () => 'https://example.com/app/',
    }

    const result = calculateInstallBaseUrl('')
    chai.assert.equal(result, 'https://example.com/app/')
  })

  it("Should fallback to '.' when no location available", () => {
    // Remove location to simulate environment without location
    delete (globalThis as any).location

    const result = calculateInstallBaseUrl('pyodide-lock.json')
    chai.assert.equal(result, '.')
  })

  it('Should handle URL with query parameters', () => {
    const result = calculateInstallBaseUrl(
      'https://cdn.example.com/pyodide/pyodide-lock.json?v=1.0',
    )
    chai.assert.equal(result, 'https://cdn.example.com/pyodide/')
  })

  it('Should handle URL with hash fragment', () => {
    const result = calculateInstallBaseUrl(
      'https://cdn.example.com/pyodide/pyodide-lock.json#section',
    )
    chai.assert.equal(result, 'https://cdn.example.com/pyodide/')
  })

  it('Should handle URL with both query parameters and hash', () => {
    const result = calculateInstallBaseUrl(
      'https://cdn.example.com/pyodide/pyodide-lock.json?v=1.0#section',
    )
    chai.assert.equal(result, 'https://cdn.example.com/pyodide/')
  })

  it('Should handle URL with username and password', () => {
    const result = calculateInstallBaseUrl(
      'https://user:pass@cdn.example.com/pyodide/pyodide-lock.json',
    )
    chai.assert.equal(result, 'https://user:pass@cdn.example.com/pyodide/')
  })
})
