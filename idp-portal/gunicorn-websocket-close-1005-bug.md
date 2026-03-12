# Bug Report: ASGI WebSocket Worker Sends Reserved Close Code 1005

**Component:** `gunicorn.asgi.websocket.WebSocketProtocol._handle_close`
**Version:** 25.1.0 (latest as of 2026-03-11)
**Severity:** High — causes all WebSocket connections to fail in Chrome/Chromium when the client closes with no status code

---

## Summary

When a WebSocket client sends a **Close frame with no payload** (no status code, which is valid per RFC 6455 §5.5.1), Gunicorn's ASGI worker echoes back a Close frame containing status code **1005 (`CLOSE_NO_STATUS`)**.

RFC 6455 §7.4.1 explicitly prohibits this:

> *"1005 is a reserved value and MUST NOT be set as a status code in a Close control frame by an endpoint."*

Chrome (and other spec-compliant browsers) detect this violation and report:

```
WebSocket connection to 'ws://...' failed:
Received a broken close frame containing a reserved status code.
```

The connection is terminated abnormally, preventing any subsequent WebSocket reconnection from working correctly.

---

## Affected Code

**File:** `gunicorn/asgi/websocket.py`
**Method:** `WebSocketProtocol._handle_close`

```python
async def _handle_close(self, payload):
    """Handle incoming close frame."""
    if len(payload) >= 2:
        self.close_code = struct.unpack("!H", payload[:2])[0]
        self.close_reason = payload[2:].decode("utf-8", errors="replace")
    else:
        self.close_code = CLOSE_NO_STATUS  # ← BUG: stores 1005
        self.close_reason = ""

    # Echo close frame back if we haven't already sent one
    if not self.closed:
        await self._send_close(self.close_code, self.close_reason)  # ← sends 1005 in frame

    self.closed = True
```

When `len(payload) == 0`, the code stores `CLOSE_NO_STATUS = 1005` and then sends it back to the client via `_send_close`. Sending 1005 in a Close frame is a protocol violation.

---

## Reproduction

### Minimal Python test

```python
import socket, base64, os, struct, json, time

# 1. Establish a WebSocket connection
key = base64.b64encode(os.urandom(16)).decode()
request = (
    "GET /ws/test HTTP/1.1\r\n"
    "Host: localhost:8000\r\n"
    "Upgrade: websocket\r\n"
    "Connection: Upgrade\r\n"
    "Sec-WebSocket-Version: 13\r\n"
    f"Sec-WebSocket-Key: {key}\r\n"
    "Origin: http://localhost:8080\r\n"
    "\r\n"
)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect(("127.0.0.1", 8000))
s.sendall(request.encode())
response = s.recv(4096)
assert b"101" in response, "WebSocket upgrade failed"

# 2. Send a Close frame with NO payload (valid per RFC 6455 §5.5.1)
mask_key = os.urandom(4)
empty_close_frame = bytes([0x88, 0x80]) + mask_key  # opcode=close, MASK=1, len=0, no payload
s.sendall(empty_close_frame)

# 3. Read the server's response
data = s.recv(4096)

# Parse close frame
opcode = data[0] & 0x0F
assert opcode == 0x08, f"Expected close frame (0x08), got opcode {opcode}"

if len(data) >= 4:
    code = struct.unpack("!H", data[2:4])[0]
    print(f"Server close code: {code}")
    if code == 1005:
        print("BUG CONFIRMED: server sent reserved code 1005 in a close frame!")
    elif code == 1000:
        print("OK: server correctly sent 1000 (Normal Closure)")
else:
    print("Server sent close frame with no payload (also acceptable)")

s.close()
```

**Expected output:**
```
Server close code: 1000
OK: server correctly sent 1000 (Normal Closure)
```

**Actual output (Gunicorn 25.1.0):**
```
Server close code: 1005
BUG CONFIRMED: server sent reserved code 1005 in a close frame!
```

### Minimal ASGI application

Any ASGI application that accepts WebSocket connections will trigger the bug — no application-level code is required. The issue occurs in the protocol layer before the application receives the disconnect event.

```python
# app.py
async def application(scope, receive, send):
    if scope["type"] == "websocket":
        await send({"type": "websocket.accept"})
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                break
```

```bash
gunicorn app:application --worker-class asgi --bind 0.0.0.0:8000
```

---

## When Does This Trigger?

A WebSocket Close frame with no payload occurs in the following real-world situations:

1. **Browser `ws.close()` called without arguments on some platforms** — while Chrome 145 sends code 1000 in the close frame by default, certain browser/OS combinations or rapid page unloads can produce a no-payload close frame.
2. **Rapid navigation / component unmount** — when a React (or any SPA) component unmounts before the WebSocket open event completes, the browser may send a no-payload close frame.
3. **`ws.close()` with no arguments from other WebSocket clients** — curl-based tests, Python `websockets` library with `ws.close()` (no code), etc.
4. **Network intermediaries** — some proxies/load balancers forward the close with an empty body.

RFC 6455 §5.5.1 explicitly allows a Close frame with no Application Data:

> *"The Application data of the Close frame MAY be empty."*

---

## RFC Reference

**RFC 6455, Section 7.4.1 — Defined Status Codes:**

> *"1005 is a reserved value and MUST NOT be set as a status code in a Close control frame by an endpoint. It is designated for use in applications expecting a status code to indicate that no status code was actually present."*

The spec is clear: code 1005 is for internal/application use only. It must never appear on the wire in a Close frame.

---

## Proposed Fix

In `_handle_close`, use `CLOSE_NORMAL` (1000) instead of `CLOSE_NO_STATUS` (1005) when echoing back a no-payload Close frame:

```python
async def _handle_close(self, payload):
    """Handle incoming close frame."""
    if len(payload) >= 2:
        self.close_code = struct.unpack("!H", payload[:2])[0]
        self.close_reason = payload[2:].decode("utf-8", errors="replace")
    else:
        # RFC 6455 §7.4.1: 1005 MUST NOT be sent in a Close frame.
        # Use 1000 (Normal Closure) when echoing a no-payload Close.
        self.close_code = CLOSE_NORMAL
        self.close_reason = ""

    # Echo close frame back if we haven't already sent one
    if not self.closed:
        await self._send_close(self.close_code, self.close_reason)

    self.closed = True
```

An alternative (also RFC-compliant) is to send a Close frame with **no payload** in response to a no-payload Close, rather than adding a code:

```python
    else:
        # Respond with an empty close frame (no status code)
        if not self.closed:
            await self._send_frame(OPCODE_CLOSE, b"")
        self.closed = True
        return
```

Both approaches are valid. The one-line change to `CLOSE_NORMAL` is the minimal fix.

---

## Environment

| | |
|---|---|
| Gunicorn version | 25.1.0 |
| Python version | 3.12 |
| OS | Linux (Docker, Debian slim) |
| ASGI framework | Django Channels 4.3.2 |
| Nginx proxy | 1.29.6 (used as reverse proxy, not the source of the bug) |
| Browser | Chrome 145 (reports the malformed close frame) |

---

## Workaround (until fixed upstream)

Monkey-patch `WebSocketProtocol._handle_close` at ASGI application startup:

```python
# asgi.py
import struct

try:
    from gunicorn.asgi.websocket import WebSocketProtocol, CLOSE_NORMAL

    async def _patched_handle_close(self, payload: bytes) -> None:
        if len(payload) >= 2:
            self.close_code = struct.unpack("!H", payload[:2])[0]
            self.close_reason = payload[2:].decode("utf-8", errors="replace")
        else:
            self.close_code = CLOSE_NORMAL  # RFC 6455: never send 1005 in a frame
            self.close_reason = ""
        if not self.closed:
            await self._send_close(self.close_code, self.close_reason)
        self.closed = True

    WebSocketProtocol._handle_close = _patched_handle_close
except ImportError:
    pass
```
