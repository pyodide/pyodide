/**
 * For each continuation, we need to save and restore the Python wasm VM's
 * global state. There are three components to this:
 * 1. The Python threadState. This information includes the Python frame, the
 *    recursion_depth, etc. This is highly sensitive to the Python version. See
 *    threadstate.c.
 * 2. The "true wasm stack" / call stack state. This state we can't access and
 *    is magically handled by the JS VM if it supports JS Promise Integration
 *    and we ask nicely. This is contained in suspender.
 * 3. The "argument stack" / "addressable stack". This is a stack in linear
 *    memory. The compiler spills variables to this stack if someone takes a
 *    pointer to the variable because it is impossible to take a pointer to data
 *    on the true call stack.
 */

/**
 * Record the current Python thread state and the wasm call stack and argument
 * stack state. This is called by the hiwire_syncify wasm module just prior to
 * suspending the thread. `hiwire_syncify` uses `externref` for the return value
 * so we don't need to wrap this in a hiwire ID.
 */
function save_state() {
  const stackState = new StackState();
  return {
    threadState: Module._captureThreadState(),
    stackState,
    suspender: Module.suspenderGlobal.value,
  };
}

/**
 * Restore the Python thread state and the wasm argument stack state. This is
 * called by the hiwire_syncify wasm module upon resuming the thread. The
 * argument is the return value from save_state.
 */
function restore_state(state) {
  state.stackState.restore();
  Module._restoreThreadState(state.threadState);
  Module.suspenderGlobal.value = state.suspender;
  Module.validSuspender.value = true;
}

/*
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
class StackState {
  constructor() {
    /** current stack pointer */
    this.start = Module.___stack_pointer.value;
    /**
     * The value the stack pointer had when we entered Python. This is how far
     * up the stack the current continuation cares about. This was recorded just
     * before we entered Python in callPyObjectKwargsSuspending.
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

function patchHiwireSyncify() {
  const suspending_f = new WebAssembly.Function(
    { parameters: ["externref", "i32"], results: ["i32"] },
    async (x) => {
      return Hiwire.new_value(await Hiwire.get_value(x));
    },
    { suspending: "first" },
  );

  const module = new WebAssembly.Module(new Uint8Array(wrap_syncifying_wasm));

  const instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: suspending_f,
      c: Module.validSuspender,
      save: save_state,
      restore: restore_state,
    },
  });
  _hiwire_syncify = instance.exports.o;
}

Module.wrapApply = function (apply) {
  var module = new WebAssembly.Module(new Uint8Array(wrap_apply_wasm));
  var instance = new WebAssembly.Instance(module, {
    e: {
      s: Module.suspenderGlobal,
      i: apply,
    },
  });
  return new WebAssembly.Function(
    { parameters: ["i32", "i32", "i32", "i32", "i32"], results: ["externref"] },
    instance.exports.o,
    { promising: "first" },
  );
};

Module.initSuspenders = function () {
  try {
    // Feature detect externref. Also need it for wrapApply to work.
    Module.suspenderGlobal = new WebAssembly.Global(
      { value: "externref", mutable: true },
      null,
    );
    // Feature detect WebAssembly.Function and JS Promise integration
    Module.wrapApply(
      new WebAssembly.Function(
        { parameters: ["i32", "i32", "i32", "i32", "i32"], results: ["i32"] },
        () => {},
      ),
    );
  } catch (e) {
    // Browser doesn't support externref. This implies it also doesn't support
    // stack switching so we won't need a suspender.
    Module.validSuspender = { value: 0 };
    Module.suspendersAvailable = false;
    return;
  }
  Module.validSuspender = new WebAssembly.Global(
    { value: "i32", mutable: true },
    0,
  );
  patchHiwireSyncify();
  Module.suspendersAvailable = true;
};
