import socket


# Temporary fix from https://github.com/SeleniumHQ/selenium/pull/6480
# to avoid ConnectionError in selenium

def _selenium_is_connectable(port, host="localhost"):
    """
    Tries to connect to the server at port to see if it is running.
    :Args:
     - port - The port to connect.
    """
    socket_ = None
    try:
        socket_ = socket.create_connection((host, port), 1)
        result = True
    except (socket.error, ConnectionError):
        result = False
    finally:
        if socket_:
            socket_.close()
    return result
