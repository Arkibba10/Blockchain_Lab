

import os
import socket
import threading

from protocol import CHUNK_SIZE, new_peer_id, recv_message, send_message

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


class P2PNode:
    def __init__(self, peer_name, port,
                 on_log=None,
                 on_peer_list_changed=None,
                 on_text=None,
                 on_file_received=None):
        self.peer_name = peer_name
        self.peer_id = new_peer_id()
        self.port = int(port)
        self.download_dir = DOWNLOAD_DIR
        os.makedirs(self.download_dir, exist_ok=True)

        self.connected_peers = {}
        self.peers_lock = threading.Lock()

        self.server_socket = None
        self.running = False

        self.on_log = on_log or (lambda message: None)
        self.on_peer_list_changed = on_peer_list_changed or (lambda peers: None)
        self.on_text = on_text or (lambda peer_id, name, message: None)
        self.on_file_received = on_file_received or (
            lambda peer_id, name, filename, path: None
        )

    def _port_is_free(self, port):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
        finally:
            probe.close()

    def start(self):
        if self.running:
            self.on_log("[ERROR] Peer is already running")
            return False

        if not self._port_is_free(self.port):
            self.on_log("[ERROR] Port %d is already in use. Choose another port."
                        % self.port)
            return False

        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", self.port))
            server.listen(10)
            server.settimeout(0.5)
        except OSError as exc:
            self.on_log("[ERROR] Could not start on port %d: %s" % (self.port, exc))
            return False

        self.server_socket = server
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

        self.on_log("[SYSTEM] Peer started: %s [%s] on port %d"
                    % (self.peer_name, self.peer_id, self.port))
        return True

    def stop(self):
        self.running = False

        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        with self.peers_lock:
            peers = list(self.connected_peers.values())
            self.connected_peers.clear()

        for peer in peers:
            try:
                peer["sock"].close()
            except OSError:
                pass

        if peers:
            self.on_log("[SYSTEM] Disconnected from %d peer(s)" % len(peers))
        self.on_log("[SYSTEM] Peer stopped")
        self.on_peer_list_changed(self.get_peers())

    def _accept_loop(self):
        while self.running:
            try:
                conn, address = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            conn.settimeout(None)
            threading.Thread(target=self._handle_peer,
                             args=(conn, address, False),
                             daemon=True).start()

    def connect_to_peer(self, ip, port):
        if not self.running:
            self.on_log("[ERROR] Start the peer before connecting")
            return None

        if port == self.port and ip in ("127.0.0.1", "localhost", "0.0.0.0"):
            self.on_log("[ERROR] Cannot connect to yourself")
            return None

        with self.peers_lock:
            for peer in self.connected_peers.values():
                if peer["address"][0] == ip and peer["port"] == port:
                    self.on_log("[ERROR] Already connected to %s [%s]"
                                % (peer["peer_name"], peer["peer_id"]))
                    return None

        try:
            sock = socket.create_connection((ip, port), timeout=5)
            sock.settimeout(None)
        except socket.timeout:
            self.on_log("[ERROR] Connection failed: timed out")
            return None
        except ConnectionRefusedError:
            self.on_log("[ERROR] Connection failed: Connection refused (is the other peer running?)")
            return None
        except OSError as exc:
            self.on_log("[ERROR] Connection failed: %s" % exc)
            return None

        threading.Thread(target=self._handle_peer,
                         args=(sock, (ip, port), True),
                         daemon=True).start()
        return "pending"

    def _handle_peer(self, sock, address, is_initiator):
        peer = None
        try:
            if is_initiator:
                send_message(sock, {
                    "type": "hello",
                    "peer_id": self.peer_id,
                    "peer_name": self.peer_name,
                    "port": self.port,
                })
                reply = recv_message(sock)
                if reply.get("type") != "hello_ack":
                    raise ValueError("expected hello_ack, got %s" % reply.get("type"))
                peer = self._register_peer(sock, address, reply)
            else:
                request = recv_message(sock)
                if request.get("type") != "hello":
                    raise ValueError("expected hello, got %s" % request.get("type"))
                peer = self._register_peer(sock, address, request)
                send_message(sock, {
                    "type": "hello_ack",
                    "peer_id": self.peer_id,
                    "peer_name": self.peer_name,
                    "port": self.port,
                }, peer["send_lock"])

            if peer is None:
                return

            while self.running:
                message = recv_message(sock)
                self._dispatch(peer, message)

        except (ConnectionError, OSError) as exc:
            if peer is not None:
                self._drop_peer(peer, str(exc) or "connection closed")
            else:
                self.on_log("[SYSTEM] Connection from %s closed" % (address[0],))
        except ValueError as exc:
            self.on_log("[ERROR] Bad data from %s: %s" % (address[0], exc))
            if peer is not None:
                self._drop_peer(peer, "protocol error")
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _register_peer(self, sock, address, message):
        peer_id = str(message.get("peer_id", ""))
        peer_name = str(message.get("peer_name", "peer"))
        peer_port = int(message.get("port", 0))

        if not peer_id:
            self.on_log("[ERROR] Peer sent no peer_id")
            return None

        if peer_id == self.peer_id:
            self.on_log("[ERROR] Refusing a connection to myself [%s]" % peer_id)
            return None

        with self.peers_lock:
            if peer_id in self.connected_peers:
                self.on_log("[ERROR] %s [%s] is already connected"
                            % (peer_name, peer_id))
                return None
            peer = {
                "peer_id": peer_id,
                "peer_name": peer_name,
                "sock": sock,
                "address": address,
                "port": peer_port,
                "send_lock": threading.Lock(),
            }
            self.connected_peers[peer_id] = peer

        self.on_log("[SYSTEM] Connected to %s [%s] (%s:%d)"
                    % (peer_name, peer_id, address[0], peer_port))
        self.on_peer_list_changed(self.get_peers())
        return peer

    def _drop_peer(self, peer, reason):
        with self.peers_lock:
            if self.connected_peers.get(peer["peer_id"], {}).get("sock") is not peer["sock"]:
                return
            del self.connected_peers[peer["peer_id"]]

        self.on_log("[SYSTEM] %s [%s] disconnected (%s)"
                    % (peer["peer_name"], peer["peer_id"], reason))
        self.on_peer_list_changed(self.get_peers())

    def _dispatch(self, peer, message):
        kind = message.get("type")

        if kind == "text":
            sender_name = str(message.get("sender_name", peer["peer_name"]))
            text = str(message.get("message", ""))
            self.on_text(peer["peer_id"], sender_name, text)

        elif kind == "file":
            self._receive_file(peer, message)

        elif kind in ("hello", "hello_ack"):
            send_message(peer["sock"], {
                "type": "hello_ack" if kind == "hello" else "hello",
                "peer_id": self.peer_id,
                "peer_name": self.peer_name,
                "port": self.port,
            }, peer["send_lock"])

        else:
            raise ValueError("unknown message type %r" % kind)

    def _receive_file(self, peer, message):
        filename = os.path.basename(str(message.get("filename", "")))
        try:
            filesize = int(message.get("filesize", 0))
        except (TypeError, ValueError):
            raise ValueError("invalid filesize")

        if not filename:
            raise ValueError("no filename in file message")
        if filesize <= 0 or filesize > MAX_FILE_SIZE:
            raise ValueError("invalid filesize %d" % filesize)

        target = os.path.join(self.download_dir, filename)
        stem, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(target):
            target = os.path.join(self.download_dir, "%s_%d%s" % (stem, counter, ext))
            counter += 1

        self.on_log("[SYSTEM] Receiving %s (%d bytes) from %s"
                    % (filename, filesize, peer["peer_name"]))

        received = 0
        try:
            with open(target, "wb") as handle:
                while received < filesize:
                    want = min(CHUNK_SIZE, filesize - received)
                    data = peer["sock"].recv(want)
                    if not data:
                        raise ConnectionError("peer disconnected mid-transfer")
                    handle.write(data)
                    received += len(data)
        except BaseException:
            try:
                os.remove(target)
            except OSError:
                pass
            raise

        self.on_log("[SYSTEM] Saved %s to %s" % (filename, target))
        self.on_file_received(peer["peer_id"], peer["peer_name"],
                              os.path.basename(target), target)

    def get_peers(self):
        with self.peers_lock:
            return [
                {
                    "peer_id": p["peer_id"],
                    "peer_name": p["peer_name"],
                    "ip": p["address"][0],
                    "port": p["port"],
                }
                for p in self.connected_peers.values()
            ]

    def send_text(self, peer_id, message):
        peer = self._get_peer(peer_id)
        if peer is None:
            return False
        if not str(message).strip():
            self.on_log("[ERROR] Cannot send an empty message")
            return False

        payload = {
            "type": "text",
            "sender_id": self.peer_id,
            "sender_name": self.peer_name,
            "message": str(message),
        }
        try:
            send_message(peer["sock"], payload, peer["send_lock"])
        except OSError as exc:
            self.on_log("[ERROR] Could not send text: %s" % exc)
            self._drop_peer(peer, "send failed")
            return False

        self.on_log("You -> %s: %s" % (peer["peer_name"], message))
        return True

    def send_file(self, peer_id, filepath):
        peer = self._get_peer(peer_id)
        if peer is None:
            return False

        filepath = str(filepath).strip().strip('"')
        if not filepath:
            self.on_log("[ERROR] No file selected")
            return False
        if not os.path.isfile(filepath):
            self.on_log("[ERROR] File not found: %s" % filepath)
            return False

        try:
            filesize = os.path.getsize(filepath)
        except OSError as exc:
            self.on_log("[ERROR] Cannot read %s: %s" % (filepath, exc))
            return False

        if filesize <= 0:
            self.on_log("[ERROR] File is empty: %s" % filepath)
            return False
        if filesize > MAX_FILE_SIZE:
            self.on_log("[ERROR] File is too large (max %d MB)"
                        % (MAX_FILE_SIZE // (1024 * 1024)))
            return False

        filename = os.path.basename(filepath)

        try:
            source = open(filepath, "rb")
        except OSError as exc:
            self.on_log("[ERROR] Cannot open %s: %s" % (filepath, exc))
            return False

        try:
            with peer["send_lock"]:
                send_message(peer["sock"], {
                    "type": "file",
                    "sender_id": self.peer_id,
                    "sender_name": self.peer_name,
                    "filename": filename,
                    "filesize": filesize,
                })

                sent = 0
                while sent < filesize:
                    block = source.read(CHUNK_SIZE)
                    if not block:
                        break
                    peer["sock"].sendall(block)
                    sent += len(block)
        except OSError as exc:
            self.on_log("[ERROR] Transfer failed: %s" % exc)
            self._drop_peer(peer, "transfer failed")
            return False
        finally:
            source.close()

        self.on_log("You -> %s: File sent: %s" % (peer["peer_name"], filename))
        return True

    def _get_peer(self, peer_id):
        if not self.running:
            self.on_log("[ERROR] Start the peer first")
            return None
        with self.peers_lock:
            peer = self.connected_peers.get(peer_id)
        if peer is None:
            self.on_log("[ERROR] That peer is not connected. Select a peer from the list first.")
        return peer
