/**
 * @returns A new asynchronous lock
 * @private
 */
export function createLock() {
  // This is a promise that is resolved when the lock is open, not resolved when lock is held.
  let _lock = Promise.resolve()

  /**
   * Acquire the async lock
   * @returns A zero argument function that releases the lock.
   * @private
   */
  async function acquireLock() {
    const old_lock = _lock
    let releaseLock: () => void
    _lock = new Promise((resolve) => (releaseLock = resolve))
    await old_lock
    // @ts-ignore
    return releaseLock
  }
  return acquireLock
}
