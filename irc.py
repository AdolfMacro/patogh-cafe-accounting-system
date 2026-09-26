import socket
import ssl
import threading
import time
import queue


class IRCClient:
    """
    IRC client with dedicated sender thread.
    Messages are queued and sent by a background thread that sleeps until woken.
    """

    def __init__(self, settings, on_connected=None, on_error=None):
        self.settings = settings
        self.on_connected = on_connected
        self.on_error = on_error
        self.sock = None
        self.running = False
        self.connected = False
        self.recv_thread = None
        self.send_thread = None
        self.send_queue = queue.Queue()

    def connect(self):
        if self.running:
            return False
        self.running = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()
        return True

    def _recv_loop(self):
        try:
            host = self.settings["host"]
            port = int(self.settings.get("port", 6697))
            use_ssl = self.settings.get("ssl", True)

            raw = socket.create_connection((host, port), timeout=15)
            if use_ssl:
                ctx = ssl.create_default_context()
                self.sock = ctx.wrap_socket(raw, server_hostname=host)
            else:
                self.sock = raw
            self.sock.settimeout(1.0)

            nick = self.settings.get("nickname", "PATOGH")
            user = self.settings.get("username", "patogh")
            real = self.settings.get("realname", "PATOGH Cafe")
            pwd = self.settings.get("password", "")

            if pwd:
                self._send_raw(f"PASS {pwd}")
            self._send_raw(f"NICK {nick}")
            self._send_raw(f"USER {user} 0 * :{real}")

            buf = ""
            while self.running:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        break
                    buf += data.decode("utf-8", errors="replace")
                    while "\r\n" in buf:
                        line, buf = buf.split("\r\n", 1)
                        if line.startswith("PING"):
                            self.send_queue.put(("raw", f"PONG {line[4:].strip()}"))
                        elif " 001 " in line or (len(line.split()) > 1 and line.split()[1] == "001"):
                            chan = self.settings.get("channel", "").strip()
                            if chan:
                                self.send_queue.put(("raw", f"JOIN {chan}"))
                            self.connected = True
                            if self.on_connected:
                                self.on_connected()
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception as e:
            if self.on_error:
                self.on_error(e)
        finally:
            self._cleanup()

    def _send_loop(self):
        """Dedicated sender thread - sleeps until messages arrive."""
        while self.running:
            try:
                # Block until a message is available (sleeps here)
                item = self.send_queue.get(timeout=0.5)
                if item is None:  # Shutdown signal
                    break
                msg_type, payload = item
                if msg_type == "raw":
                    self._send_raw(payload)
                elif msg_type == "privmsg":
                    target, text = payload
                    self._send_raw(f"PRIVMSG {target} :{text}")
                self.send_queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                break

    def _send_raw(self, cmd):
        if not self.sock:
            return False
        try:
            self.sock.sendall((cmd + "\r\n").encode("utf-8"))
            return True
        except Exception:
            return False

    def send_message(self, text, target=None):
        """Thread-safe: called from UI thread, queues message for sender thread."""
        if not self.connected:
            return False
        if target is None:
            target = self.settings.get("channel", "")
        # Put in queue - sender thread wakes up and sends
        self.send_queue.put(("privmsg", (target, text)))
        return True

    def disconnect(self):
        self.running = False
        self.send_queue.put(None)  # Wake up sender thread to exit
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _cleanup(self):
        self.running = False
        self.connected = False
        self.send_queue.put(None)
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def is_connected(self):
        return self.connected


class IRCManager:
    """Simple wrapper for PATOGH."""

    def __init__(self, settings):
        self.settings = settings
        self.client = None

    def connect(self, on_connected=None, on_error=None):
        self.client = IRCClient(self.settings, on_connected, on_error)
        return self.client.connect()

    def disconnect(self):
        if self.client:
            self.client.disconnect()
            self.client = None

    def send_message(self, text, target=None):
        if not self.client or not self.client.is_connected():
            return False
        if target is None:
            target = self.settings.get("channel", "")
        return self.client.send_message(text, target)

    def is_connected(self):
        return self.client is not None and self.client.is_connected()