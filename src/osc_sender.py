from pythonosc.udp_client import SimpleUDPClient


class FeatureOscSender:
    def __init__(self, host="127.0.0.1", port=9000):
        self.client = SimpleUDPClient(host, port)

    def send(self, eeg_features, body_controls):
        self.client.send_message(
            "/eeg/4_8",
            float(eeg_features["4_8_hz"]),
        )

        self.client.send_message(
            "/eeg/8_13",
            float(eeg_features["8_13_hz"]),
        )

        self.client.send_message(
            "/eeg/13_30",
            float(eeg_features["13_30_hz"]),
        )

        self.client.send_message(
            "/body/eog",
            float(body_controls["eog_control"]),
        )

        self.client.send_message(
            "/body/emg",
            float(body_controls["emg_control"]),
        )