"""Replaceable OSC transport for Tidal/SuperDirt control values."""

import time

from pythonosc.udp_client import SimpleUDPClient


class TidalControlOscSender:
    """Send named float controls as ``/ctrl <name> <value>`` UDP packets."""

    def __init__(self, host="127.0.0.1", port=6010, client=None):
        self.host = host
        self.port = int(port)
        self.client = client or SimpleUDPClient(host, self.port)
        self.last_values = {}
        self.packet_count = 0
        self.started_at = time.monotonic()

    def send(self, controls):
        for name, value in controls.items():
            value = float(value)
            self.client.send_message("/ctrl", [str(name), value])
            self.last_values[str(name)] = value
            self.packet_count += 1

    @property
    def packet_rate(self):
        elapsed = time.monotonic() - self.started_at
        return self.packet_count / elapsed if elapsed > 0 else 0.0

    def close(self):
        socket = getattr(self.client, "_sock", None)
        if socket is not None:
            socket.close()
