# UAP P2P Network

**CSE 433 - Blockchain & Distributed Security Lab**
University of Asia Pacific

Two or more independent peers that exchange text messages and files directly
over TCP. There is no central server, no database and no relay — every message
travels straight from the sender to the receiver.

---

## 1. Get the code

### Option A — Download the ZIP (easiest)

1. Open the repository page on GitHub.
2. Click the green **Code** button, then **Download ZIP**.
3. Extract it. Windows extracts to a folder called `P2P_Network-main`.
4. Open that folder.

### Option B — Clone it

```bash
git clone https://github.com/Arkibba10/P2P_Network.git
cd P2P_Network
```

### Option C — From VS Code

Open VS Code → **File → Open Folder** → select the extracted folder →
**Ctrl + `** to open its terminal. You are now already in the right directory.

Either way you should end up with these six items:

```
P2P_Network/
├── main.py
├── p2p_node.py
├── protocol.py
├── requirements.txt
├── README.md
└── downloads/        (created automatically on first run)
```

---

## 2. Run it

There is **nothing to install.** The project uses only the Python standard
library, so this step is optional:

```bash
pip install -r requirements.txt   # succeeds, installs nothing
```

All you need is **Python 3.9 or newer**. Check with `python --version`.

Then, from inside the project folder:

```bash
python main.py
```

> On Windows, if `python` is not recognised, use `py main.py` instead.
> If you see `ModuleNotFoundError: No module named 'tkinter'` on Linux, run
> `sudo apt install python3-tk`.

A window titled **UAP P2P Network** opens.

---

## 3. Connect two peers

Every peer needs its **own port**, and every peer is **its own server**. To talk
to someone you dial their IP and port; they do nothing but wait.

**Step 1 — start two windows.** Open two terminals in the project folder and run
`python main.py` in both.

**Step 2 — give each one an identity.** In the *My Peer* frame:

| Window | Name | Port |
| --- | --- | --- |
| First | `Alice` | `5000` |
| Second | `Bob` | `5001` |

Press **Start Peer** in both.

**Step 3 — connect from one side only.** In Alice's *Connect to Another Peer*
frame enter IP `127.0.0.1` and Port `5001` (Bob's port), then press **Connect**.

Bob's window fills in by itself — he never presses Connect. Both peer lists now
show each other, for example `Bob [7f3a91c2]   127.0.0.1:5001`.

> Two processes cannot listen on the same port. If you give both peers port
> `5000` the second one reports *"Port 5000 is already in use."*

### Across two computers (LAN)

1. Start a peer on **each** computer with different ports.
2. Find each machine's IP:
   - Windows: `ipconfig` → look for *IPv4 Address*, e.g. `192.168.1.5`
   - macOS / Linux: `ifconfig` or `ip addr` → look for *inet*
3. On computer A, enter **computer B's IP and B's port**, then **Connect**.
4. If it fails, the firewall is blocking you. Allow Python on the **Private**
   network: *Windows Security → Firewall → Allow an app through firewall*.

---

## 4. What it does

| Feature | Behaviour |
| --- | --- |
| **Text messaging** | Select a peer, type, press **Send** (or `Enter`). Appears instantly on both screens. |
| **File transfer** | Any type — text, image, audio, video, PDF, ZIP. Streamed in 64 KB blocks, so a 2 GB video costs the same memory as a 2 KB note. |
| **No overwrites** | A second file of the same name is saved as `report_1.pdf`. Nothing you already have is ever replaced. |
| **Live peer list** | Peers appear and vanish as they connect and disconnect. |
| **Error handling** | Bad input, refused connections, busy ports and mid-transfer drops are all reported in the log. The app never crashes. |
| **Cross-platform** | Windows, macOS and Linux. One machine or a whole LAN. |

Sending is always **one-to-one**. A peer cannot broadcast, and nothing is ever
relayed through an intermediate peer.

---

## 5. How it happens

### 5.1 A peer is both a client and a server

There is no central server, so how do two peers find each other? They cannot
broadcast over TCP, so **every peer listens for itself** *and* dials others when
it needs to:

```
   listening socket   ->  accept()   ->  peers who dialled ME
   connecting socket  ->  connect()  ->  peers I dialled
```

Both roles end up in the same `connected_peers` dictionary, so the rest of the
program does not care which is which.

```
Alice                                          Bob
-----                                           ---
bind(("0.0.0.0", 5000))  <- listening          bind(("0.0.0.0", 5001))
listen(10)                                     listen(10)
accept() ................ blocks, waiting ..... accept() returned a socket
recv HELLO from Alice
<----------------- send HELLO_ACK
Alice: registered Bob
Bob:   registered Alice
```

`0.0.0.0` means "every network interface", so the peer is reachable from the
localhost and from the LAN without reconfiguring anything.

### 5.2 The handshake — proving who is on the other end

A bare TCP connection proves nothing; the far end could be any program on the
machine. So the two sides introduce themselves before anything else:

```
Alice (the one who dialled)                 Bob (the one who answered)
---------------------------                 --------------------------
connect() -> TCP established
send  HELLO {peer_id, name, port} ------->  recv HELLO
                                             register Alice
                                     <----- send HELLO_ACK {peer_id,...}
recv HELLO_ACK
register Bob
```

`peer_id` is the **first 8 characters of a uuid4 hex string** (e.g. `7f3a91c2`),
generated locally with no registration anywhere. It becomes the key used
everywhere else in the program, so the GUI never handles a raw socket.

### 5.3 Framing — why one `send()` is not one message

TCP is a **stream of bytes with no message boundaries.** A single `send()` on one
machine can arrive as three `recv()` calls on another, and three sends can arrive
glued into one. So you can never just "read a message" from a socket.

Every message is therefore given a header saying how long it is:

```
  +-------------------------+-------------------------+-----------------+
  |  4 bytes: length         |  UTF-8 JSON payload      | raw file bytes  |
  +-------------------------+-------------------------+-----------------+
   struct.pack("!I", n)       {"type": "text", ...}     only for "file"
```

1. **Send** — `json.dumps()` the message, encode UTF-8, prepend its byte length
   with `struct.pack("!I", length)`. `!I` means *unsigned int, network
   (big-endian) byte order*.
2. **Receive** — read 4 bytes, `struct.unpack("!I", ...)` to learn the length,
   then read *precisely* that many bytes and `json.loads()` them.

`recv_exact()` is what makes step 2 reliable: `socket.recv(n)` is allowed to
return **fewer** than `n` bytes even on a healthy connection, so `recv_exact()`
loops until it has every byte it asked for, or raises `ConnectionError` if the
peer closes early.

A sanity check rejects a length of `0` or anything over 1 MB, so a corrupt or
hostile frame cannot make the program allocate gigabytes.

### 5.4 The four message types

| Type | Fields | Purpose |
| --- | --- | --- |
| `hello` | `peer_id`, `peer_name`, `port` | Sent by the peer that dialled, to introduce itself |
| `hello_ack` | `peer_id`, `peer_name`, `port` | The answering peer's reply |
| `text` | `sender_id`, `sender_name`, `message` | A chat message |
| `file` | `sender_id`, `sender_name`, `filename`, `filesize` | File metadata — the raw bytes follow |

### 5.5 Sending a file

The metadata frame must come **first**, because it tells the receiver a file is
coming, what it is called and — crucially — **exactly how many bytes to expect**.
Without `filesize` the receiver would have no idea where the file ends.

```
sender                                   receiver
------                                   --------
send  file {filename, filesize}   ------>  read metadata frame
                                          open downloads/<name>
stream 64 KB blocks with sendall() ----->  recv until filesize bytes read
sendall() guarantees a block is          close file
never sent only in part                  log "File received"
```

Three details make this safe:

- **Chunked.** The file is never loaded into memory, and `sendall()` keeps
  retrying until the whole block is out, so a short write cannot corrupt it.
- **Filenames are never trusted.** `os.path.basename()` strips any directory
  part, so a peer sending `../../windows/system32/evil.dll` can only ever create
  `evil.dll` inside `downloads/`.
- **No partial files.** If the sender vanishes halfway, the incomplete file is
  deleted rather than left looking finished.

### 5.6 Threads

`recv()` blocks — it sits doing nothing until data arrives. If one thread handled
every peer, a single silent peer would freeze the whole node. So there is **one
daemon thread per connection**, each with its own blocking receive loop.

Each connection also gets its **own send lock**. Without it, a text message sent
while a large file was streaming would land *in the middle of the file's bytes*
and corrupt it. The lock makes the two sends take turns.

Threads are marked `daemon=True` so Python does not wait for them at exit —
otherwise the blocking receive loops would stop the program from ever closing.

### 5.7 Keeping the GUI safe

`P2PNode` runs its networking in those threads, but **Tkinter may only be touched
from the thread that created the window.** Calling a widget from a socket thread
is undefined behaviour and usually crashes.

So the callbacks running on socket threads do the smallest possible thing: they
push a tuple onto a `queue.Queue`, which is thread-safe and has nothing to do with
Tk. The main thread drains that queue from an `after()` timer and updates the
widgets.

```
   socket thread          queue            main thread
   -----------          -----            ------------
   on_log(msg)    --->  [ ("log", …) ]  --after(80ms)-->  add_log(...)
   on_text(...)   --->  [ ("text", …) ] --after(80ms)-->  add_log(...)
   on_file(...)   --->  [ ("file", …) ] --after(80ms)-->  add_log(...)
                                                    + refresh peer list
```

No socket thread ever calls into Tkinter.

---

## 6. Project structure

| File | Responsibility |
| --- | --- |
| `protocol.py` | How bytes become messages: framing, `recv_exact`, JSON encode/decode |
| `p2p_node.py` | The `P2PNode` class: sockets, threads, handshake, sending and receiving |
| `main.py` | The Tkinter window: widgets, input validation, log lines |
| `downloads/` | Where received files are saved (created automatically) |

Each layer only knows about the one below it: `main.py` never touches a socket,
`p2p_node.py` never imports Tkinter.

---

## 7. Testing

| # | Test | Expected result |
| --- | --- | --- |
| 1 | Two peers on one machine | Both peer lists show each other |
| 2 | Send text both ways | Appears on both screens |
| 3 | Send a file | Receiver's `downloads/` holds a byte-identical copy |
| 4 | Send the same filename twice | Second arrives as `name_1.ext` |
| 5 | A→B→C all connected | A can send straight to C; B is not used as a relay |
| 6 | Large file (~12 MB) | Transfers with flat memory use |
| 7 | Invalid IP or port | Warning dialog, no crash |
| 8 | Connect to a dead port | *"Connection refused"* in the log |
| 9 | Two peers on one port | *"Port already in use"* |
| 10 | Peer closes mid-transfer | Partial file deleted, app survives |
| 11 | Peer disconnects while idle | Removed from the list, log notes it |

### Screenshots to capture

| What | Suggested filename |
| --- | --- |
| Main window, empty | `docs/screenshot-1-main-window.png` |
| Two peers connected | `docs/screenshot-2-connected.png` |
| Text exchange | `docs/screenshot-3-text.png` |
| File received | `docs/screenshot-4-file.png` |
| Three peers connected | `docs/screenshot-5-three-peers.png` |
| An error message | `docs/screenshot-6-error.png` |

---

## 8. Viva questions

**1. Difference between a client and a server?**
A server *listens* on a fixed port and waits (`bind` + `listen` + `accept`). A
client *actively dials* a known address (`connect`). One program can be both at
once, on different sockets.

**2. Why is a peer both a client and a server?**
There is no central server. Each peer listens so others can reach it, and dials
out when it wants to reach someone else. Both kinds of connection land in the
same `connected_peers` dictionary.

**3. IP address versus port?**
The IP identifies a *machine*; the port identifies a *program* on it.
`192.168.1.5` might run a browser on 443 and our peer on 5000. The pair
`(IP, port)` identifies one endpoint.

**4. Why must peers on one machine use different ports?**
Only one listening socket can hold a port at a time on a given IP. Hence Alice on
5000 and Bob on 5001.

**5. What do `connect()` and `accept()` do?**
`connect()` is the client's side: it performs the TCP three-way handshake
(SYN, SYN-ACK, ACK) and blocks until connected or failed. `accept()` is the
server's side: it blocks until a connection arrives, then returns the new socket
and the peer's address.

**6. Why TCP rather than UDP?**
TCP guarantees reliable, ordered delivery — every byte sent arrives exactly once.
A lost or reordered byte would corrupt a file. UDP is faster but guarantees
nothing, so we would have to build reliability ourselves.

**7. Why threads?**
Socket reads block. One thread handling all peers means a peer that connects and
then stays silent freezes everyone else. One thread per connection keeps each peer
independent.

**8. Purpose of the HELLO message?**
A raw TCP connection proves nothing — the far end could be any program. The
handshake exchanges `peer_id`, display name and port so both sides know who they
are talking to.

**9. What is framing, and why is it needed?**
TCP is a byte stream with no boundaries, so one `send()` can arrive as several
`recv()` calls. Framing adds a header giving the message length, so the receiver
knows exactly where one message ends and the next begins.

**10. Why can't one `recv()` be assumed to equal one message?**
`recv(n)` returns *up to* n bytes — whatever has arrived at that instant. It may
be a partial message or several messages. `recv_exact()` loops until it has the
exact byte count it needs.

**11. Why is metadata sent before the file bytes?**
The receiver must know a file is coming, what it is called and **exactly how many
bytes** to expect. Without `filesize` it would be guessing where the file ends.

**12. Why transfer in chunks?**
Memory: `f.read()` would pull a whole file into RAM, so a 2 GB video would need
2 GB. Reliability: `sendall()` retries until the entire block is sent, so a short
write cannot silently corrupt the file. 64 KB balances syscalls against memory.

**13. How does the receiver know the transfer finished?**
From `filesize` in the metadata. It reads in a loop until it has exactly that
many bytes, then returns to the normal receive loop.

**14. What happens on disconnect?**
`recv()` returns empty bytes, so `recv_exact()` raises `ConnectionError`. The
connection's thread catches it, removes the peer from `connected_peers`, closes
the socket and notifies the GUI. The app keeps running. A partial file is deleted.

**15. Where are received files stored?**
In `downloads/` next to `main.py`, created automatically. Names are taken from
the sender, with `_1`, `_2`, ... appended if already taken, so an existing file
is never overwritten.

**16. Is there a central server?**
No. No server process, no database, no relay. Every message and file goes
straight from sender to receiver. The only "server" is each peer's own listening
socket, so other peers can connect *to it*.

**17. What if a central server went offline?**
Here, nothing happens — there is no central server, and that is the main
advantage of P2P: no single point of failure. In a client-server design, if the
server went offline every client would lose the ability to reach any other.

**18. Challenges of large-scale Internet P2P?**
Finding peers (you cannot broadcast over TCP, so you need a tracker, DHT or
bootstrap nodes); crossing NAT and firewalls (UDP hole punching); keeping the
peer list fresh as peers come and go; and reliability — peers vanish at any
moment, so transfers need resuming and verification. This lab sidesteps all of
it by having peers connect by hand over a LAN.

**19. Why does each connection need its own send lock?**
So a text message sent while a large file is streaming cannot land in the middle
of the file's bytes. The lock makes the two sends take turns.

**20. Why are threads daemon threads?**
A daemon thread is destroyed automatically at program exit. Without
`daemon=True`, Python would wait for every blocking receive loop and the
application could never be closed.

---

## 9. Troubleshooting

| Problem | Fix |
| --- | --- |
| `No module named 'tkinter'` | Linux only: `sudo apt install python3-tk` |
| `python` not recognised (Windows) | Use `py main.py` |
| "Port 5000 is already in use" | Give each peer a different port |
| "Connection refused" | The other peer is not running, or wrong port |
| Works locally, fails over LAN | Firewall, or you are on guest Wi-Fi |
| "Cannot connect to yourself" | You entered your own port in the Connect frame |
| Nothing in the log after Connect | Press **Start Peer** first |
| File arrives as `photo_1.jpg` | `photo.jpg` already existed — nothing is overwritten |

---

## 10. Scope

Deliberately **not** implemented, as out of scope for this lab: blockchain,
encryption, authentication, NAT traversal, DHT, BitTorrent, databases, file
deduplication, chunk recovery, routing and cloud components. The transport is
plain TCP, so traffic is readable by anyone on the network path — a teaching
project, not a production one.
