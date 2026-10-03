import os
import queue
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from p2p_node import P2PNode

APP_TITLE = "UAP P2P Network"
HERE = os.path.dirname(os.path.abspath(__file__))
POLL_MS = 80


def is_valid_ip(text):
    text = text.strip()
    if text == "localhost":
        return True
    parts = text.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or not 0 <= int(part) <= 255:
            return False
    return True


def read_port(text):
    text = text.strip()
    if not text or not re.fullmatch(r"\d+", text):
        return None
    value = int(text)
    return value if 1 <= value <= 65535 else None


class P2PApp:
    def __init__(self, root):
        self.root = root
        self.node = None
        self.peer_rows = []
        self._events = queue.Queue()
        self._alive = True

        root.title(APP_TITLE)
        root.geometry("900x640")
        root.minsize(760, 560)
        root.configure(bg="#f0f0f0")

        self._build_widgets()
        self.set_status("Enter a name and port, then press Start Peer.")
        root.after(POLL_MS, self._drain)

    def _build_widgets(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        my_peer = ttk.LabelFrame(outer, text="My Peer", padding=10)
        my_peer.pack(fill="x")

        ttk.Label(my_peer, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value="Alice")
        self.name_entry = ttk.Entry(my_peer, textvariable=self.name_var, width=18)
        self.name_entry.grid(row=0, column=1, sticky="w", padx=(6, 16))

        ttk.Label(my_peer, text="Port:").grid(row=0, column=2, sticky="w")
        self.port_var = tk.StringVar(value="5000")
        self.port_entry = ttk.Entry(my_peer, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3, sticky="w", padx=(6, 16))

        self.start_btn = ttk.Button(my_peer, text="Start Peer", command=self.on_start)
        self.start_btn.grid(row=0, column=4, padx=(0, 8))
        self.stop_btn = ttk.Button(my_peer, text="Stop", command=self.on_stop,
                                   state="disabled")
        self.stop_btn.grid(row=0, column=5)

        self.identity_var = tk.StringVar(value="Not started")
        ttk.Label(my_peer, textvariable=self.identity_var,
                  foreground="#1a4f8a").grid(row=1, column=0, columnspan=6,
                                             sticky="w", pady=(8, 0))

        connect = ttk.LabelFrame(outer, text="Connect to Another Peer", padding=10)
        connect.pack(fill="x", pady=(10, 0))

        ttk.Label(connect, text="IP:").grid(row=0, column=0, sticky="w")
        self.ip_var = tk.StringVar(value="127.0.0.1")
        self.ip_entry = ttk.Entry(connect, textvariable=self.ip_var, width=18)
        self.ip_entry.grid(row=0, column=1, sticky="w", padx=(6, 16))

        ttk.Label(connect, text="Port:").grid(row=0, column=2, sticky="w")
        self.remote_port_var = tk.StringVar(value="5001")
        self.remote_port_entry = ttk.Entry(connect, textvariable=self.remote_port_var,
                                           width=8)
        self.remote_port_entry.grid(row=0, column=3, sticky="w", padx=(6, 16))

        self.connect_btn = ttk.Button(connect, text="Connect", command=self.on_connect,
                                      state="disabled")
        self.connect_btn.grid(row=0, column=4)

        middle = ttk.PanedWindow(outer, orient="horizontal")
        middle.pack(fill="both", expand=True, pady=10)

        peers_box = ttk.LabelFrame(middle, text="Connected Peers", padding=8)
        self.peer_list = tk.Listbox(peers_box, font=("Consolas", 10),
                                    activestyle="none", exportselection=False)
        peer_scroll = ttk.Scrollbar(peers_box, orient="vertical",
                                    command=self.peer_list.yview)
        self.peer_list.configure(yscrollcommand=peer_scroll.set)
        peer_scroll.pack(side="right", fill="y")
        self.peer_list.pack(side="left", fill="both", expand=True)
        self.peer_list.bind("<<ListboxSelect>>", self.on_select_peer)
        middle.add(peers_box, weight=1)

        log_box = ttk.LabelFrame(middle, text="Messages / Events", padding=8)
        self.log = tk.Text(log_box, height=12, wrap="word", state="disabled",
                           font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4",
                           insertbackground="#d4d4d4")
        log_scroll = ttk.Scrollbar(log_box, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.log.tag_configure("system", foreground="#7ec8ff")
        self.log.tag_configure("error", foreground="#ff7b72")
        self.log.tag_configure("sent", foreground="#9be28f")
        self.log.tag_configure("recv", foreground="#e6e6e6")
        middle.add(log_box, weight=3)

        send_text = ttk.LabelFrame(outer, text="Send Text", padding=10)
        send_text.pack(fill="x")
        send_text.columnconfigure(1, weight=1)

        ttk.Label(send_text, text="To:").grid(row=0, column=0, sticky="w")
        self.text_var = tk.StringVar()
        self.text_entry = ttk.Entry(send_text, textvariable=self.text_var)
        self.text_entry.grid(row=0, column=1, sticky="ew", padx=6)
        self.text_entry.bind("<Return>", lambda _event: self.on_send_text())
        self.send_text_btn = ttk.Button(send_text, text="Send",
                                        command=self.on_send_text, state="disabled")
        self.send_text_btn.grid(row=0, column=2)

        send_file = ttk.LabelFrame(outer, text="Send File", padding=10)
        send_file.pack(fill="x", pady=(10, 0))

        ttk.Label(send_file, text="Selected peer:").grid(row=0, column=0, sticky="w")
        self.target_var = tk.StringVar(value="(none)")
        ttk.Label(send_file, textvariable=self.target_var,
                  foreground="#555").grid(row=0, column=1, sticky="w", padx=6)
        self.send_file_btn = ttk.Button(send_file, text="Choose File & Send",
                                        command=self.on_send_file, state="disabled")
        self.send_file_btn.grid(row=0, column=2, sticky="e")
        ttk.Label(send_file, text="Text, image, audio, video, PDF, ZIP, etc.",
                  foreground="#666", font=("", 9, "italic")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=(8, 4)).pack(fill="x", side="bottom")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_log(self, text):
        self.log.configure(state="normal")
        if text.startswith("[ERROR]"):
            tag = "error"
        elif text.startswith("[SYSTEM]"):
            tag = "system"
        elif text.startswith("You ->"):
            tag = "sent"
        else:
            tag = "recv"
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_status(self, text):
        self.status_var.set(text)

    def warn(self, title, message):
        self.add_log("[ERROR] " + message)
        self.set_status(message)
        try:
            messagebox.showwarning(title, message, parent=self.root)
        except tk.TclError:
            pass

    def _on_event(self, kind, *args):
        self._events.put((kind, args))

    def _drain(self):
        try:
            while True:
                kind, args = self._events.get_nowait()
                handler = getattr(self, "_show_" + kind, None)
                if handler is not None:
                    handler(*args)
        except queue.Empty:
            pass
        except tk.TclError:
            self._alive = False
            return
        if self._alive:
            try:
                self.root.after(POLL_MS, self._drain)
            except tk.TclError:
                self._alive = False

    def _show_log(self, message):
        self.add_log(message)

    def _show_peers(self, peers):
        self.refresh_peer_list(peers)

    def _show_text(self, peer_name, message):
        self.add_log("%s -> You: %s" % (peer_name, message))

    def _show_file(self, peer_name, filename, path):
        self.add_log("%s -> You: File received: %s" % (peer_name, filename))

    def refresh_peer_list(self, peers):
        selected = self.selected_peer_id()
        self.peer_list.delete(0, "end")
        self.peer_rows = []
        for peer in peers:
            self.peer_rows.append(peer["peer_id"])
            self.peer_list.insert("end", "%s [%s]   %s:%d"
                                  % (peer["peer_name"], peer["peer_id"],
                                     peer["ip"], peer["port"]))
        if selected in self.peer_rows:
            self.peer_list.selection_set(self.peer_rows.index(selected))
        elif self.peer_rows:
            self.peer_list.selection_set(0)
        else:
            self.target_var.set("(none)")

        if self.peer_rows:
            name = self.peer_rows[self.peer_list.curselection()[0]]
            self._show_target(name)
        self.update_buttons()

    def selected_peer_id(self):
        selection = self.peer_list.curselection()
        if not selection:
            return None
        index = selection[0]
        if 0 <= index < len(self.peer_rows):
            return self.peer_rows[index]
        return None

    def _show_target(self, peer_id):
        for peer in self.node.get_peers() if self.node else []:
            if peer["peer_id"] == peer_id:
                self.target_var.set("%s [%s]" % (peer["peer_name"], peer["peer_id"]))
                return

    def on_select_peer(self, _event=None):
        peer_id = self.selected_peer_id()
        if peer_id:
            self._show_target(peer_id)
        self.update_buttons()

    def update_buttons(self):
        running = self.node is not None and self.node.running
        has_peer = self.selected_peer_id() is not None
        self.connect_btn.configure(state="normal" if running else "disabled")
        self.send_text_btn.configure(state="normal" if (running and has_peer) else "disabled")
        self.send_file_btn.configure(state="normal" if (running and has_peer) else "disabled")

    def on_start(self):
        name = self.name_var.get().strip()
        if not name:
            self.warn("Name required", "Please enter a peer name before starting.")
            return

        port = read_port(self.port_var.get())
        if port is None:
            self.warn("Invalid port",
                      "Port must be a whole number between 1 and 65535.")
            return

        self.node = P2PNode(name, port,
                            on_log=lambda m: self._on_event("log", m),
                            on_peer_list_changed=lambda p: self._on_event("peers", p),
                            on_text=lambda pid, nm, msg: self._on_event("text", nm, msg),
                            on_file_received=lambda pid, nm, fn, path:
                                self._on_event("file", nm, fn, path))

        if not self.node.start():
            self.node = None
            self.set_status("Could not start the peer.")
            return

        self.identity_var.set("Name: %s  |  ID: %s  |  Port: %d"
                              % (self.node.peer_name, self.node.peer_id, port))
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.name_entry.configure(state="disabled")
        self.port_entry.configure(state="disabled")
        self.update_buttons()
        self.set_status("Running as %s [%s] on port %d"
                        % (name, self.node.peer_id, port))
        self.text_entry.focus_set()

    def on_stop(self):
        if self.node is not None:
            self.node.stop()
            self.node = None
        self.identity_var.set("Not started")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.name_entry.configure(state="normal")
        self.port_entry.configure(state="normal")
        self.peer_list.delete(0, "end")
        self.peer_rows = []
        self.target_var.set("(none)")
        self.update_buttons()
        self.set_status("Peer stopped.")

    def on_connect(self):
        if self.node is None or not self.node.running:
            self.warn("Not running", "Start the peer before connecting.")
            return

        ip = self.ip_var.get().strip()
        if not is_valid_ip(ip):
            self.warn("Invalid IP",
                      "Enter a valid IPv4 address, for example 127.0.0.1 or 192.168.1.5.")
            return

        port = read_port(self.remote_port_var.get())
        if port is None:
            self.warn("Invalid port",
                      "Port must be a whole number between 1 and 65535.")
            return

        self.set_status("Connecting to %s:%d ..." % (ip, port))
        self.add_log("[SYSTEM] Connecting to %s:%d" % (ip, port))
        self.node.connect_to_peer(ip, port)

    def on_send_text(self):
        if self.node is None or not self.node.running:
            self.warn("Not running", "Start the peer before sending.")
            return

        peer_id = self.selected_peer_id()
        if peer_id is None:
            self.warn("No peer selected",
                      "Select a peer in the Connected Peers list first.")
            return

        message = self.text_var.get()
        if not message.strip():
            self.warn("Empty message", "Type a message before sending.")
            return

        if self.node.send_text(peer_id, message):
            self.text_var.set("")
            self.set_status("Message sent.")

    def on_send_file(self):
        if self.node is None or not self.node.running:
            self.warn("Not running", "Start the peer before sending a file.")
            return

        peer_id = self.selected_peer_id()
        if peer_id is None:
            self.warn("No peer selected",
                      "Select a peer in the Connected Peers list first.")
            return

        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a file to send",
            initialdir=HERE)
        if not path:
            self.set_status("File selection cancelled.")
            return

        if self.node.send_file(peer_id, path):
            self.set_status("File sent: %s" % os.path.basename(path))
        else:
            self.set_status("File was not sent.")

    def on_close(self):
        self._alive = False
        if self.node is not None:
            self.node.stop()
            self.node = None
        self.root.destroy()


def main():
    root = tk.Tk()
    P2PApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
