import * as chai from 'chai'
import { createResolvable } from '../../../common/resolveable'

describe('createResolvable', () => {
  it('should create a resolvable promise', () => {
    const resolvable = createResolvable()
    chai.assert.isFunction(resolvable.resolve)
    chai.assert.isFunction(resolvable.reject)
  })

  it('should resolve the promise', async () => {
    const resolvable = createResolvable()
    resolvable.resolve()
    await resolvable
  })

  it('should reject the promise', async () => {
    const resolvable = createResolvable()
    resolvable.reject()
    try {
      await resolvable
      chai.assert.fail('Promise should have been rejected')
    } catch (e) {
      chai.assert.isUndefined(e)
    }
  })
})
