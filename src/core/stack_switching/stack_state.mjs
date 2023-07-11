/**
 * Stack layout for a continuation (diagram stolen from greenlet).
 *
 *               |     ^^^       |
 *               |  older data   |
 *               |               |
 *  stack_stop . |_______________|
 *        .      |               |
 *        .      |     data      |
 *        .      |   in stack    |
 *        .    * |_______________| . .  _____________  stack_start + _copy.length
 *        .      |               |     |             |
 *        .      |     data      |     |  data saved |
 *        .      |   for next    |     |  in _copy   |
 *               | continuation  |     |             |
 * stack_start . |               | . . |_____________| stack_start
 *               |               |
 *               |  newer data   |
 *               |     vvv       |
 *
 * Each continuation has some part (possibly none) of its argument stack data
 * at the correct place on the actual stack and some part (possibly none) that
 * has been evicted to _copy by some other continuation that needed the space.
 */

/**
 * This is a list of continuations that have some of their state in the actual
 * argument stack. We need to keep track of them because restore() may need to
 * evict them from the stack in which case it will have to save their data.
 *
 * Invariants:
 * 1. This list contains a StackState for every continuation that at least
 *    partially on the argument stack except the currently executing one.
 *    (save_state will add the currently executing one to this list when it
 *    suspends.)
 * 2. The entries are sorted. Earlier entries occupy space further up on the
 *    stack, later entries occupy space lower down on the stack.
 * @private
 */
const stackStates = [];

/**
 * A class to help us keep track of the argument stack data for our individual
 * continuations. The suspender automatically and opaquely handles the call
 * stack for us, but the argument stack is an abstraction generated by the
 * compiler and we have to manage it ourselves.
 *
 * We only expose `restore` which ensures that the arg stack data is restored to
 * its proper location and the stack pointer and stackStop are in the correct
 * place. `restore` handles saving the data from other continuations that are
 * evicted.
 * @private
 */
export class StackState {
  constructor() {
    /** current stack pointer */
    this.start = Module.___stack_pointer.value;
    /**
     * The value the stack pointer had when we entered Python. This is how far
     * up the stack the current continuation cares about. This was recorded just
     * before we entered Python in suspendableApply.
     */
    this.stop = Module.stackStop;
    /**
     * Where we store the data if it gets ejected from the actual argument
     * stack.
     */
    this._copy = new Uint8Array(0);
    if (this.start !== this.stop) {
      // Edge case that probably never happens: If start and stop are equal, the
      // current continuation occupies no arg stack space.
      stackStates.push(this);
    }
  }

  /**
   * Restore the argument stack in preparation to run the continuation.
   * @returns How much data we copied. (Only for debugging purposes.)
   */
  restore() {
    let total = 0;
    // Search up the stack for things that need to be ejected in their entirety
    // and save them
    while (
      stackStates.length > 0 &&
      stackStates[stackStates.length - 1].stop < this.stop
    ) {
      total += stackStates.pop()._save();
    }
    // Part of one more object may need to be ejected.
    const last = stackStates[stackStates.length - 1];
    if (last && last !== this) {
      total += last._save_up_to(this.stop);
    }
    // If we just saved all of the last stackState it needs to be removed.
    // Alternatively, the current StackState may be on the stackStates list.
    // Technically it would make sense to leave it there, but we will add it
    // back if we suspend again and if we exit normally it gets removed from the
    // stack.
    if (last && last.stop === this.stop) {
      stackStates.pop();
    }
    if (this._copy.length !== 0) {
      // Now that we've saved everything that might be in our way we can restore
      // the current stack data if need be.
      Module.HEAP8.set(this._copy, this.start);
      total += this._copy.length;
      this._copy = new Uint8Array(0);
    }
    // Restore stack pointers
    Module.stackStop = this.stop;
    Module.___stack_pointer.value = this.start;
    return total;
  }

  /**
   * Copy part of a stack frame into the _copy Uint8Array
   * @param {number} stop What part of the frame to copy
   * @returns How much data we copied (for debugging only)
   */
  _save_up_to(stop) {
    let sz1 = this._copy.length;
    let sz2 = stop - this.start;
    if (sz2 <= sz1) {
      return 0;
    }
    const new_segment = HEAP8.subarray(this.start + sz1, this.start + sz2);
    const c = new Uint8Array(sz2);
    c.set(this._copy);
    c.set(new_segment, sz1);
    this._copy = c;
    return sz2;
  }

  /**
   * Copy all of a stack frame into its _copy Uint8Array
   * @returns How much data we copied (for debugging only)
   */
  _save() {
    return this._save_up_to(this.stop);
  }
}
