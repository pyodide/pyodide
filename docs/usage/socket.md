(node-socket)=

# Using Sockets

```{admonition} This is experimental
:class: warning

This feature is experimental and may change or be removed in future versions of Pyodide.
This feature is only available in Node.js and is not supported in browsers.
```

By default, Pyodide does not support sockets in the browser.
Browsers do not provide a standard low-level socket API, so Pyodide does not include a browser socket
implementation and raises an error if your code tries to use sockets there.

If you are running Pyodide in Node.js, you can enable an experimental socket API.

## Enabling socket support

Call `await pyodide.useNodeSockFS()` before importing any Python modules that use sockets.

```javascript
const pyodide = await loadPyodide();
await pyodide.useNodeSockFS();
```

This feature requires JavaScript Promise Integration.

If you are using Node.js <= 24, enable it explicitly with the `--experimental-wasm-stack-switching` flag:

```bash
node --experimental-wasm-stack-switching
```

If you are using Node.js >= 25, Promise Integration is enabled by default.

After this setup, you can use sockets in Python as usual.

## Example

### Using sockets directly in Python

```python
import socket

# Create a socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Connect to a server
s.connect(('localhost', 8080))
# Send some data
s.sendall(b'Hello, world')
# Receive some data
data = s.recv(1024)
print('Received', repr(data))
# Close the socket
s.close()
```

### Using sockets with database drivers

Many database drivers use sockets to connect to a database server.
With socket support enabled, you can use these drivers in Pyodide on Node.js.

For example, you can use the `pymysql` driver to connect to a MySQL database:

```python
import pymysql

# Connect to the database
connection = pymysql.connect(host='localhost', user='user', password='password', database='test')
# Create a cursor
cursor = connection.cursor()
# Execute a query
cursor.execute('SELECT * FROM my_table')
# Fetch the results
results = cursor.fetchall()
print(results)
# Close the connection
connection.close()
```
