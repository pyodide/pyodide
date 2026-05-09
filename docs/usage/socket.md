(node-socket)=

# Using Sockets

```{admonition} This is experimental
:class: warning

This feature is only available in Node.js environments. It is not supported in browsers.
```

By default, Pyodide does not support sockets in the browser.
This is because the browser does not have a standard API for sockets, so Pyodide does not include a socket implementation
and instead raises an error when you try to use sockets in the browser.

However, if you are running Pyodide in a Node.js environment, we provide a experimental API to use sockets.

## Enabling socket support

To enable socket support, you need to call `await pyodide.useNodeSockFS()` before importing any Python modules that use sockets.

```javascript
const pyodide = await loadPyodide();
await pyodide.useNodeSockFS();
```

This feature requires JavaScript Promise Integration. If you are using Node.js <= 24, you need to explicitly enable it by adding
`--experimental-wasm-stack-switching` flag when running your Node.js application:

```bash
node --experimental-wasm-stack-switching
```

If you are using Node.js >= 25, Promise Integration is enabled by default, so you don't need to do anything special.

That's all. After that, you can use sockets in your Python code as you normally would.

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

Many database drivers use sockets to connect to the database server. With socket support enabled, you can use these drivers in Pyodide running in Node.js.

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
