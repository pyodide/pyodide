import * as chai from 'chai'
import {
  canonicalizePackageName,
  uriToPackageData,
} from '../../packaging-utils'

describe('canonicalizePackageName', () => {
  it('should return lower case', () => {
    chai.assert.equal(canonicalizePackageName('ABC'), 'abc')
  })
  it('should replace -, _, . with -', () => {
    chai.assert.equal(
      canonicalizePackageName('pytest-pyodide'),
      'pytest-pyodide',
    )
    chai.assert.equal(canonicalizePackageName('ruamel.yaml'), 'ruamel-yaml')
    chai.assert.equal(
      canonicalizePackageName('pytest_benchmark'),
      'pytest-benchmark',
    )
    chai.assert.equal(canonicalizePackageName('a_b-c.d'), 'a-b-c-d')
  })
})

describe('uriToPackageData', () => {
  it('should return the correct package data if a correct wheel URI is given', () => {
    const testcases: [
      string,
      { name: string; version: string; fileName: string },
    ][] = [
      [
        'https://files.pythonhosted.org/packages/70/8e/0e2d847013cb52cd35b38c009bb167a1a26b2ce6cd6965bf26b47bc0bf44/requests-2.31.0-py3-none-any.whl',
        {
          name: 'requests',
          version: '2.31.0',
          fileName: 'requests-2.31.0-py3-none-any.whl',
        },
      ],
      [
        'https://example.com/srtrain-2.3.0-py3-none-any.whl',
        {
          name: 'srtrain',
          version: '2.3.0',
          fileName: 'srtrain-2.3.0-py3-none-any.whl',
        },
      ],
      [
        'https://test.net/numpy-1.25.2-cp311-cp311-emscripten_3_1_45_wasm32.whl',
        {
          name: 'numpy',
          version: '1.25.2',
          fileName: 'numpy-1.25.2-cp311-cp311-emscripten_3_1_45_wasm32.whl',
        },
      ],
    ]

    testcases.forEach((tc) => {
      const [url, expected] = tc
      const pkgData = uriToPackageData(url)
      chai.assert.equal(pkgData?.name, expected.name)
      chai.assert.equal(pkgData?.version, expected.version)
      chai.assert.equal(pkgData?.fileName, expected.fileName)
    })
  })

  it('should return undefined if URI is not a valid wheel URI', () => {
    chai.assert.equal(uriToPackageData('requests'), undefined)
    chai.assert.equal(uriToPackageData('pyodide-lock'), undefined)
    chai.assert.equal(uriToPackageData('pytest_benchmark'), undefined)
  })
})
