# pyodide.http

The `pyodide.http` module provides HTTP client functionality specifically designed for browser and WebAssembly environments where traditional Python HTTP libraries (like `urllib` or `requests`) face significant limitations.

## Network Limitations in Pyodide

Due to browser security constraints and WebAssembly's sandboxed environment, standard Python networking libraries have several limitations:

- **No raw socket access**: Browser security prevents direct socket operations
- **CORS restrictions**: Cross-origin requests are limited by browser CORS policies  
- **No synchronous networking in main thread**: Traditional blocking HTTP calls can freeze the browser UI
- **Limited protocol support**: Only HTTP/HTTPS protocols are available, no TCP/UDP sockets

## HTTP Client Alternatives

Pyodide provides two complementary HTTP client solutions:

### `pyfetch` - Asynchronous HTTP Client

Based on the browser's native Fetch API, `pyfetch` provides:
- **Asynchronous operations**: Non-blocking HTTP requests using async/await
- **Full browser integration**: Leverages browser's networking stack and security features
- **Modern API**: Clean, Promise-based interface similar to JavaScript fetch()
- **Advanced features**: Support for streaming, request/response manipulation, and abort signals

```python
# Asynchronous HTTP request
from pyodide.http import pyfetch
response = await pyfetch("https://api.example.com/data")
data = await response.json()
```

### `pyxhr` - Synchronous HTTP Client  

Based on XMLHttpRequest, `pyxhr` provides:
- **Synchronous operations**: Blocking HTTP requests for simpler code patterns
- **requests-like API**: Familiar interface for Python developers
- **Browser compatibility**: Works in all modern browsers supporting XMLHttpRequest
- **Lightweight**: Minimal overhead for simple HTTP operations

```python
# Synchronous HTTP request
from pyodide.http import pyxhr
response = pyxhr.get("https://api.example.com/data")
data = response.json()
```

## Choosing Between pyfetch and pyxhr

**Use `pyfetch` when:**
- Working with async/await patterns
- Need advanced features like streaming or request cancellation
- Building responsive web applications that shouldn't block the UI
- Integrating with other asynchronous Python code

**Use `pyxhr` when:**
- Prefer synchronous, blocking operations
- Porting existing code that uses requests-like patterns  
- Need simple HTTP operations without async complexity
- Working in environments where sync operations are acceptable

```{eval-rst}
.. currentmodule:: pyodide.http

.. automodule:: pyodide.http
   :members:
   :autosummary:
   :autosummary-no-nesting:
```
