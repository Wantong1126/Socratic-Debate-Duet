import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
import wave

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

from src.sonification.controls import (
    BAND_FIELDS,
    DESCRIPTOR_FIELDS,
    frame_to_instrument_controls,
)
from src.sonification.protocol import (
    ORGANISM_FRAME_ADDRESS,
    ORGANISM_PARAMETER_ORDER,
    ORGANISM_PROTOCOL_VERSION,
    OrganismControlFrame,
    OrganismControlSender,
)
from src.sonification.synthetic_demo import (
    BASELINE,
    DEFAULT_ISOLATED_DURATION,
    ISOLATED_BAND_BASELINE,
    ISOLATED_HIGH,
    ISOLATED_LOW,
    ISOLATED_MASTER_ENERGY,
    audition_value_at,
    combined_frame_at,
    isolated_frame_at,
    iter_frames,
    run_transport,
)
from scripts.analyze_eeg_organism_v2_isolated import analyze_directory


ROOT = Path(__file__).resolve().parents[1]


class RecordingClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


class CountingClient:
    def __init__(self):
        self.count = 0
        self.last = None

    def send_message(self, address, values):
        self.count += 1
        self.last = (address, tuple(values))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError("scheduler attempted a negative sleep")
        self.now += seconds


class TimedSender:
    def __init__(self, clock, *, stall_after=None, stall_seconds=0.0,
                 interrupt_after=None):
        self.clock = clock
        self.stall_after = stall_after
        self.stall_seconds = stall_seconds
        self.interrupt_after = interrupt_after
        self.times = []

    def send(self, frame):
        if self.interrupt_after is not None and len(self.times) >= self.interrupt_after:
            raise KeyboardInterrupt
        self.times.append(self.clock.monotonic())
        if self.stall_after is not None and len(self.times) == self.stall_after:
            self.clock.now += self.stall_seconds


class OrganismV2Tests(unittest.TestCase):
    def test_versioned_frame_order_length_address_and_one_packet(self):
        values = [index / 10 for index in range(9)]
        frame = OrganismControlFrame.from_values(values)
        self.assertEqual(ORGANISM_PROTOCOL_VERSION, 2)
        self.assertEqual(frame.version, 2)
        self.assertEqual(ORGANISM_FRAME_ADDRESS, "/eeg/organism/v2/frame")
        self.assertEqual(ORGANISM_PARAMETER_ORDER, (
            "energy", "centroid", "mobility", "spectral_entropy", "novelty",
            "delta", "theta", "alpha", "beta",
        ))
        self.assertEqual(len(frame.as_osc_values()), 9)
        client = RecordingClient()
        sender = OrganismControlSender(client=client)
        sender.send(frame)
        self.assertEqual(client.messages, [
            (ORGANISM_FRAME_ADDRESS, tuple(values))
        ])

    def test_actual_udp_transport_is_one_nine_value_frame_packet(self):
        received = []
        dispatcher = Dispatcher()
        dispatcher.map(
            ORGANISM_FRAME_ADDRESS,
            lambda address, *values: received.append((address, values)),
        )
        server = ThreadingOSCUDPServer(("127.0.0.1", 0), dispatcher)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        sender = OrganismControlSender("127.0.0.1", server.server_address[1])
        try:
            sender.send(OrganismControlFrame.from_values([0.1] * 9))
            deadline = time.monotonic() + 2
            while not received and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0][0], ORGANISM_FRAME_ADDRESS)
            self.assertEqual(len(received[0][1]), 9)
            self.assertTrue(all(
                abs(value - 0.1) < 1e-6 for value in received[0][1]
            ))
        finally:
            sender.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_frame_is_finite_clamped_and_strict(self):
        frame = OrganismControlFrame.from_values([
            -2, 2, math.nan, math.inf, -math.inf, 0.1, 0.2, 0.3, 0.4
        ])
        self.assertEqual(frame.as_osc_values()[:5], (0.0, 1.0, 0.0, 0.0, 0.0))
        self.assertTrue(all(
            math.isfinite(value) and 0 <= value <= 1
            for value in frame.as_osc_values()
        ))
        with self.assertRaises(ValueError):
            OrganismControlFrame.from_values([0] * 8)
        with self.assertRaises(ValueError):
            OrganismControlFrame.from_mapping({"energy": 0.5})

    def test_every_isolated_sweep_changes_only_its_selected_field(self):
        for field in DESCRIPTOR_FIELDS + BAND_FIELDS:
            low = isolated_frame_at(0, field=field, duration=8)
            high = isolated_frame_at(4, field=field, duration=8)
            changed = [
                name for name in ORGANISM_PARAMETER_ORDER
                if low.as_mapping()[name] != high.as_mapping()[name]
            ]
            self.assertEqual(changed, [field])
            for name in ORGANISM_PARAMETER_ORDER:
                if name != field:
                    expected = BASELINE[name]
                    if field in BAND_FIELDS and name in BAND_FIELDS:
                        expected = ISOLATED_BAND_BASELINE
                    if field in BAND_FIELDS and name == "energy":
                        expected = ISOLATED_MASTER_ENERGY
                    self.assertEqual(low.as_mapping()[name], expected)

    def test_one_shot_has_five_four_second_stages_and_eighty_one_frames(self):
        duration = DEFAULT_ISOLATED_DURATION
        self.assertEqual(duration, 20.0)
        expected = (
            (0.0, ISOLATED_LOW),
            (3.99, ISOLATED_LOW),
            (8.0, ISOLATED_HIGH),
            (11.99, ISOLATED_HIGH),
            (16.0, ISOLATED_LOW),
            (20.0, ISOLATED_LOW),
        )
        for elapsed, value in expected:
            self.assertAlmostEqual(audition_value_at(elapsed), value, places=6)
        frames = list(iter_frames("band", field="beta"))
        self.assertEqual(len(frames), 81)
        self.assertEqual((frames[0][0], frames[-1][0]), (0.0, 20.0))

    def test_energy_and_four_harmonic_groups_are_independent(self):
        base = OrganismControlFrame.from_mapping(BASELINE)
        energy_values = BASELINE.copy()
        energy_values["energy"] = 0.1
        energy_changed = frame_to_instrument_controls(
            OrganismControlFrame.from_mapping(energy_values)
        )
        base_controls = frame_to_instrument_controls(base)
        self.assertNotEqual(energy_changed.master_energy, base_controls.master_energy)
        self.assertEqual(
            energy_changed.group_amplitudes,
            base_controls.group_amplitudes,
        )

        for band_index, band in enumerate(BAND_FIELDS):
            values = BASELINE.copy()
            values[band] = 1.0 - values[band]
            changed = frame_to_instrument_controls(
                OrganismControlFrame.from_mapping(values)
            )
            self.assertEqual(changed.master_energy, base_controls.master_energy)
            changed_groups = [
                index for index, (left, right) in enumerate(zip(
                    base_controls.group_amplitudes, changed.group_amplitudes
                )) if left != right
            ]
            self.assertEqual(changed_groups, [band_index])

    def test_all_synthetic_modes_are_deterministic_and_four_hz_by_default(self):
        for mode, field in (("descriptor", "novelty"), ("band", "alpha"),
                            ("combined", None)):
            first = list(iter_frames(mode, field=field, duration=2))
            second = list(iter_frames(mode, field=field, duration=2))
            self.assertEqual(first, second)
            self.assertEqual(len(first), 9)
        self.assertNotEqual(combined_frame_at(0), combined_frame_at(12))

    def test_monotonic_pacing_is_four_hz(self):
        clock = FakeClock()
        sender = TimedSender(clock)
        logs = []
        sent = run_transport(
            "descriptor",
            field="energy",
            duration=2,
            rate=4,
            sender=sender,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            printer=logs.append,
        )
        self.assertEqual(sent, 9)
        self.assertEqual(sender.times, [index * 0.25 for index in range(9)])
        rows = [json.loads(line) for line in logs]
        self.assertEqual(rows[-1]["effective_send_hz"], 4.0)
        self.assertEqual(rows[-1]["interval_seconds"], 0.25)
        self.assertEqual(rows[-1]["skipped_deadlines"], 0)

    def test_late_deadlines_are_skipped_without_burst_catch_up(self):
        clock = FakeClock()
        sender = TimedSender(clock, stall_after=2, stall_seconds=1.1)
        logs = []
        sent = run_transport(
            "band",
            field="beta",
            duration=2,
            rate=4,
            sender=sender,
            clock=clock.monotonic,
            sleeper=clock.sleep,
            printer=logs.append,
        )
        self.assertLess(sent, 9)
        intervals = [right - left for left, right in zip(
            sender.times, sender.times[1:]
        )]
        self.assertTrue(all(interval >= 0.249 for interval in intervals))
        self.assertGreater(
            max(json.loads(line)["skipped_deadlines"] for line in logs),
            0,
        )

    def test_loop_can_be_interrupted_without_stop_or_catch_up_packets(self):
        clock = FakeClock()
        sender = TimedSender(clock, interrupt_after=10)
        with self.assertRaises(KeyboardInterrupt):
            run_transport(
                "descriptor",
                field="energy",
                duration=20,
                rate=4,
                sender=sender,
                loop=True,
                clock=clock.monotonic,
                sleeper=clock.sleep,
                printer=lambda line: None,
            )
        self.assertEqual(len(sender.times), 10)
        self.assertTrue(all(
            abs((right - left) - 0.25) < 1e-9
            for left, right in zip(sender.times, sender.times[1:])
        ))

    def test_long_transport_cannot_add_supercollider_nodes(self):
        client = CountingClient()
        sender = OrganismControlSender(client=client)
        frame = OrganismControlFrame.from_mapping(BASELINE)
        for _ in range(20000):
            sender.send(frame)
        self.assertEqual((sender.frame_count, client.count), (20000, 20000))
        self.assertEqual(client.last[0], ORGANISM_FRAME_ADDRESS)

        source = (ROOT / "sound" / "eeg_organism_v2_receiver.scd").read_text(
            encoding="utf-8"
        )
        frame_callback = source.split("OSCdef(\\eegOrganismV2Frame", 1)[1].split(
            "OSCdef(\\eegOrganismV2Stop", 1
        )[0]
        for constructor in (
            "Synth.tail(", "Synth.head(", "Synth.new(",
            "Group.tail(", "Group.head(", "Group.new(", "Buffer.", "Routine(",
        ):
            self.assertNotIn(constructor, frame_callback)
        self.assertEqual(source.count("Synth.tail("), 1)
        self.assertEqual(source.count("Group.tail("), 1)

    def test_receiver_stores_nine_values_has_watchdog_and_safe_stop(self):
        source = (ROOT / "sound" / "eeg_organism_v2_receiver.scd").read_text(
            encoding="utf-8"
        )
        for token in (
            "message.size == 10", "values.copyRange(5, 8)",
            "state[\\lastFrame]", "state[\\watchdog]",
            "'/eeg/organism/v2/frame'", "'/eeg/organism/v2/stop'",
            "\\masterEnergy, values[0]", "\\transportAlive, 1",
            "effectiveHz=", "interval=", "age=",
        ):
            self.assertIn(token, source)
        self.assertNotIn("s.quit", source)
        self.assertNotIn("Server.killAll", source)

    def test_v2_exact_harmonics_extend_beta_without_changing_fundamental(self):
        config = (ROOT / "config" / "eeg_organism_v2.scd").read_text(
            encoding="utf-8"
        )
        self.assertIn("[1, 2, 3]", config)
        self.assertIn("[4, 5, 6]", config)
        self.assertIn("[7, 9, 12]", config)
        self.assertIn("[24, 36, 48]", config)
        self.assertNotIn("fundamental:", config)
        core = (ROOT / "sound" / "eeg_harmonic_field_v2_core.scd").read_text(
            encoding="utf-8"
        )
        self.assertIn("weightedShapes.collect(_.squared)", core)
        self.assertIn("\\transportAlive", core)

    def test_cli_dry_run_prints_nine_values_and_rate_without_socket(self):
        result = subprocess.run(
            [sys.executable, "-m", "src.sonification.synthetic_demo",
             "--mode", "descriptor", "--field", "centroid",
             "--duration", "1", "--rate", "4", "--dry-run"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rows = [
            json.loads(line) for line in result.stdout.splitlines()
            if line.startswith("{")
        ]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            tuple(name for name in rows[0] if name in ORGANISM_PARAMETER_ORDER),
            ORGANISM_PARAMETER_ORDER,
        )
        self.assertEqual(rows[0]["sequence"], 0)
        self.assertIsNone(rows[0]["interval_seconds"])
        self.assertEqual(rows[1]["effective_send_hz"], 4.0)
        self.assertIn("ONE-SHOT mode", result.stdout)
        self.assertIn("ONE-SHOT complete", result.stdout)

    def test_isolated_wavs_are_stereo_48k_24bit_safe_and_spectrally_distinct(self):
        directory = ROOT / "recordings" / "eeg_organism_v2_isolated"
        files = sorted(directory.glob("*.wav"))
        self.assertEqual(len(files), 10)
        for path in files:
            with wave.open(str(path), "rb") as recording:
                self.assertEqual(recording.getnchannels(), 2)
                self.assertEqual(recording.getframerate(), 48000)
                self.assertEqual(recording.getsampwidth(), 3)

        report = analyze_directory(directory)
        energy = report["energy"]
        self.assertGreater(energy["high_minus_low_rms_db"], 18)
        self.assertLess(
            abs(
                energy["high"]["spectral_centroid_hz"]
                - energy["low"]["spectral_centroid_hz"]
            ),
            5,
        )
        for field in BAND_FIELDS:
            result = report[field]
            self.assertLess(abs(result["high_minus_low_rms_db"]), 2.5)
            self.assertLess(result["low"]["relevant_band_percent"], 0.01)
            self.assertGreater(result["high"]["relevant_band_percent"], 94)
            self.assertFalse(result["low"]["clipped"])
            self.assertFalse(result["high"]["clipped"])
        self.assertLess(
            report["delta"]["high"]["spectral_centroid_hz"],
            report["delta"]["low"]["spectral_centroid_hz"],
        )
        for field in ("theta", "alpha", "beta"):
            self.assertGreater(
                report[field]["high"]["spectral_centroid_hz"],
                report[field]["low"]["spectral_centroid_hz"],
            )


if __name__ == "__main__":
    unittest.main()
