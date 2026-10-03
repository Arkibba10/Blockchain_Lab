
import json
import struct
import uuid

MAX_FRAME_BYTES = 1024 * 1024
CHUNK_SIZE = 64 * 1024


def new_peer_id():
    return uuid.uuid4().hex[:8]


def recv_exact(sock, n):
    if n < 0:
        raise ValueError("cannot receive a negative number of bytes")

    data = b""
    while len(data) < n:
        chunk = sock.recv(min(CHUNK_SIZE, n - len(data)))
        if not chunk:
            raise ConnectionError("peer closed the connection mid-message")
        data += chunk
    return data


def send_message(sock, message, send_lock=None):
    payload = json.dumps(message).encode("utf-8")
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("message is too large to send")

    header = struct.pack("!I", len(payload))

    if send_lock is not None:
        with send_lock:
            sock.sendall(header + payload)
    else:
        sock.sendall(header + payload)

    return len(payload)


def recv_message(sock):
    raw_length = recv_exact(sock, 4)
    (length,) = struct.unpack("!I", raw_length)

    if length == 0 or length > MAX_FRAME_BYTES:
        raise ValueError("invalid frame length: %d" % length)

    payload = recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))
