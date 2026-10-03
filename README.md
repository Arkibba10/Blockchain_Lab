# UAP P2P Network

A lightweight peer-to-peer desktop application for sending text messages and files directly between peers over TCP, without a central server or relay.

## Project description

This project allows two or more peers to connect directly and exchange messages and files on the same machine or over a local network. Each peer runs its own listener and can connect to another peer by IP address and port. The communication is direct, peer-to-peer, and does not depend on a central coordinator.

## Requirements

- Python 3.9 or newer
- Tkinter (usually included with Python on Windows and macOS)
- Linux users may need:

```bash
sudo apt install python3-tk
```

## Installation and setup

### Option 1: Download the project

1. Download the repository as a ZIP file.
2. Extract it to a folder on your computer.
3. Open the extracted folder.

### Option 2: Clone the repository

```bash
git clone https://github.com/Arkibba10/P2P_Network.git
cd P2P_Network
```

### Optional dependency install

The project uses the Python standard library only, so installation is usually not required:

```bash
pip install -r requirements.txt
```

## How to run the application

From the project folder, run:

```bash
python main.py
```

If `python` is not recognized on Windows, use:

```bash
py main.py
```

A window titled `UAP P2P Network` will open.

## How to connect two peers

1. Open two terminal windows in the project folder.
2. Run `python main.py` in both.
3. In the first window, set:
   - Name: `Alice`
   - Port: `5000`
4. In the second window, set:
   - Name: `Bob`
   - Port: `5001`
5. Press **Start Peer** in both windows.
6. In Alice's **Connect to Another Peer** section, enter:
   - IP: `127.0.0.1`
   - Port: `5001`
7. Press **Connect**.

Bob will appear automatically in Alice's peer list, and the connection will be established.

![Peer Connected](screenshots/Peer%20Connected.png)

![Multiple Peer connected](screenshots/Multiple%20Peer%20connected.png)

![File Shared](screenshots/File%20Shared.png)

> If both peers use the same port, the second one will fail with a port already in use error.

## How to transfer files

After the peers are connected:

- Select a connected peer from the peer list.
- Use **Send Text** to send a message.
- Use **Choose File & Send** in the file section to transfer a file.

The receiver will get the file in the `downloads/` folder created automatically by the app.

![File transfer between two peers](c:\Users\User\AppData\Roaming\Code\agentSessionData\b062a7e0-9a9b-4a99-b83d-ce6a2522059d\attachments\20c0ec5f-22b1-4aa5-9d34-b34f90d8d281\Pasted Image.png)

## Example screenshots

### App startup

![UAP P2P Network app window](c:\Users\User\AppData\Roaming\Code\agentSessionData\b062a7e0-9a9b-4a99-b83d-ce6a2522059d\attachments\d381abd4-73c8-42f4-8885-589b75e4a090\Pasted Image.png)

### Multiple peers connected

![Three peers connected in the P2P app](c:\Users\User\AppData\Roaming\Code\agentSessionData\b062a7e0-9a9b-4a99-b83d-ce6a2522059d\attachments\44a0a08f-dded-469c-8a9e-8d1b243a06ec\Pasted Image.png)
