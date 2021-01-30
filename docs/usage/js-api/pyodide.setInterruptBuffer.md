(js_api_pyodide_setInterruptBuffer)= #
pyodide.setInterruptBuffer(interruptBuffer) This is a low level API for
handling keyboard interrupts.  Sets the pyodide interrupt buffer to be
`interruptBuffer`. If thereafter one sets `interruptBuffer[0] = 2;` (2 stands
for SIGINT) this will cause Pyodide to raise a `KeyboardInterupt`. The value of
`interruptBuffer[0]` will regularly be set back to zero.  This is intended for
use when Pyodide is running on a webworker. In this case, one should make
`interruptBuffer` a `SharedArrayBuffer` shared with the main thread. If the
user requests a keyboard interrupt from the main thread, then the main thread
can set `interruptBuffer[0] = 2;` and this will signal the webworker to raise a
KeyboardInterupt exception.


**Parameters**

| name               | type       | description
|
|--------------------|------------|------------------------------------------------------|
| *interruptBuffer*  | TypedArray | The SharedArrayBuffer to use as the interrupt buffer |
