#define PY_SSIZE_T_CLEAN
#include "Python.h"

PyThreadState* saved_state = NULL;

/**
 * Save the current thread state and create a new one from
 * the current interpreter state.
 */
void
save_current_thread_state()
{
  if (saved_state != NULL) {
#ifdef DEBUG_F
    printf("save_current_thread_state: already saved state");
#endif
    return;
  }
  PyThreadState* tstate = PyThreadState_Get();
  PyInterpreterState* interp = PyThreadState_GetInterpreter(tstate);

  PyThreadState* new_tstate = PyThreadState_New(interp);

  PyThreadState_Swap(new_tstate);
  saved_state = tstate;
}

/**
 * Restore the thread state that was saved by
 * save_current_thread_state.
 */
void
restore_thread_state()
{
  if (saved_state == NULL) {
#ifdef DEBUG_F
    printf("restore_thread_state: no saved state");
#endif
    return;
  }
  PyThreadState* tstate = PyThreadState_Get();
  PyThreadState_Swap(saved_state);
  PyThreadState_Clear(tstate);
  PyThreadState_Delete(tstate);

  saved_state = NULL;
}

int
is_thread_state_saved()
{
  return saved_state != NULL;
}
