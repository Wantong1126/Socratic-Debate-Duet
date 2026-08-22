"""Run six-channel EEG controls, OSC output, and a validation dashboard."""

import argparse
from collections import deque
from datetime import datetime
import html
from pathlib import Path
import webbrowser

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .eeg_control_features import CHANNELS, EEGControlFeatureEngine
from .eeg_features import clean_eeg
from .tidal_osc import TidalControlOscSender
from .window_engine import record_lsl_seconds

SCENARIOS = ("amplitude only", "envelope slope only", "waveform mobility only",
             "spectral centroid only", "entropy only", "pair similarity and lag")


def deterministic_scenarios(seconds, sample_rate=250.0):
    """Generate deterministic, one-property-at-a-time validation intervals."""
    count = int(round(seconds * sample_rate))
    t = np.arange(count) / sample_rate
    eeg = np.column_stack([np.sin(2 * np.pi * (6 + i) * t + i * 0.2) for i in range(6)])
    edges = np.linspace(0, count, len(SCENARIOS) + 1, dtype=int)

    start, stop = edges[0], edges[1]
    local = np.linspace(0, 1, stop - start, endpoint=False)
    eeg[start:stop, 0] *= 1 + local

    start, stop = edges[1], edges[2]
    local_t = t[start:stop] - t[start]
    envelope = 0.5 + local_t / max(local_t[-1], 1 / sample_rate)
    eeg[start:stop, 1] = envelope * np.sin(2 * np.pi * 7 * t[start:stop] + 0.2)

    start, stop = edges[2], edges[3]
    local = np.linspace(0, 1, stop - start, endpoint=False)
    phase = 2 * np.pi * np.cumsum((8 + 8 * local) / sample_rate)
    eeg[start:stop, 2] = np.sin(phase)

    start, stop = edges[3], edges[4]
    local = np.linspace(0, 1, stop - start, endpoint=False)
    low = np.sin(2 * np.pi * 5 * t[start:stop])
    high = np.sin(2 * np.pi * 25 * t[start:stop])
    eeg[start:stop, 3] = ((1 - local) * low + local * high) / np.sqrt((1 - local) ** 2 + local ** 2)

    start, stop = edges[4], edges[5]
    local = np.linspace(0, 1, stop - start, endpoint=False)
    tones = sum(np.sin(2 * np.pi * frequency * t[start:stop] + frequency * 0.1)
                for frequency in (5, 11, 17, 23, 31)) / np.sqrt(5)
    eeg[start:stop, 4] = ((1 - local) * np.sin(2 * np.pi * 10 * t[start:stop]) + local * tones) / np.sqrt((1 - local) ** 2 + local ** 2)

    start, stop = edges[5], edges[6]
    pair_t = t[start:stop]
    common = (np.sin(2 * np.pi * 6.3 * pair_t)
              + 0.55 * np.sin(2 * np.pi * 10.7 * pair_t + 0.4)
              + 0.3 * np.sin(2 * np.pi * 17.2 * pair_t + 1.1))
    common /= np.sqrt(np.mean(common ** 2))
    lag = int(round(0.04 * sample_rate))
    eeg[start:stop, 4] = common
    midpoint = (stop - start) // 2
    partner = common.copy()
    partner[midpoint:] = np.concatenate((np.zeros(lag), common[midpoint:-lag]))
    eeg[start:stop, 5] = partner
    body = np.zeros((count, 2), dtype=float)
    return np.column_stack((eeg, body)), t, edges / sample_rate


class ControlSession:
    def __init__(self, sample_rate, update_rate, baseline_seconds, sender):
        self.sample_rate = float(sample_rate)
        self.update_rate = float(update_rate)
        self.window_samples = int(round(2.0 * sample_rate))
        self.update_samples = max(1, int(round(sample_rate / update_rate)))
        self.buffer = deque(maxlen=self.window_samples)
        self.engine = EEGControlFeatureEngine(sample_rate, update_rate, baseline_seconds)
        self.sender = sender
        self.frames, self.frame_times = [], []
        self.total_samples = 0
        self.last_update_sample = 0

    def add_chunk(self, chunk, timestamps=None):
        for row_index, row in enumerate(np.asarray(chunk, dtype=float)):
            self.buffer.append(row[:6])
            self.total_samples += 1
            if len(self.buffer) < self.window_samples:
                continue
            if self.total_samples - self.last_update_sample < self.update_samples:
                continue
            self.last_update_sample = self.total_samples
            frame = self.engine.update(np.asarray(self.buffer))
            self.sender.send(frame.normalized)
            self.frames.append(frame)
            if timestamps is not None and row_index < len(timestamps):
                self.frame_times.append(float(timestamps[row_index]))
            else:
                self.frame_times.append(self.total_samples / self.sample_rate)


def _scenario_spans(axes, edges):
    if edges is None:
        return
    for axis in np.atleast_1d(axes):
        for i, label in enumerate(SCENARIOS):
            axis.axvspan(edges[i], edges[i + 1], alpha=0.035 if i % 2 else 0.075, color="black")
        for edge in edges[1:-1]:
            axis.axvline(edge, color="grey", lw=0.4)


def _save_plots(output_dir, samples, sample_rate, session, scenario_edges):
    eeg = samples[:, :6]
    repaired = np.where(np.isfinite(eeg), eeg, 0.0)
    cleaned = clean_eeg(repaired)
    t = np.arange(len(eeg)) / sample_rate
    fig, axes = plt.subplots(6, 2, figsize=(15, 13), sharex=True, constrained_layout=True)
    for i, name in enumerate(CHANNELS):
        axes[i, 0].plot(t, eeg[:, i], lw=0.45); axes[i, 0].set_ylabel(name.upper())
        axes[i, 1].plot(t, cleaned[:, i], lw=0.45)
    axes[0, 0].set_title("Raw EEG"); axes[0, 1].set_title("Cleaned EEG")
    axes[-1, 0].set_xlabel("seconds"); axes[-1, 1].set_xlabel("seconds")
    _scenario_spans(axes.ravel(), scenario_edges)
    fig.savefig(output_dir / "eeg_traces.png", dpi=120); plt.close(fig)

    frame_t = np.asarray(session.frame_times)
    if frame_t.size and frame_t[0] > 1000:
        frame_t = frame_t - frame_t[0] + 2.0
    fig, axes = plt.subplots(6, 2, figsize=(16, 14), sharex=True, constrained_layout=True)
    descriptors = ("energy", "energy_slope", "mobility", "centroid", "entropy", "novelty")
    for row, descriptor in enumerate(descriptors):
        for channel in CHANNELS:
            key = f"{channel}_{descriptor}"
            axes[row, 0].plot(frame_t, [f.raw[key] for f in session.frames], label=channel.upper(), lw=0.8)
            axes[row, 1].plot(frame_t, [f.normalized[key] for f in session.frames], label=channel.upper(), lw=0.8)
        axes[row, 0].set_ylabel(descriptor); axes[row, 1].set_ylim(-0.02, 1.02)
    axes[0, 0].set_title("Raw channel descriptors"); axes[0, 1].set_title("Robust-normalised channel descriptors")
    axes[0, 0].legend(ncol=6, fontsize=7); axes[0, 1].legend(ncol=6, fontsize=7)
    _scenario_spans(axes.ravel(), scenario_edges)
    fig.savefig(output_dir / "channel_features.png", dpi=120); plt.close(fig)

    fig, axes = plt.subplots(3, 2, figsize=(15, 9), sharex=True, constrained_layout=True)
    for row, descriptor in enumerate(("asymmetry", "similarity", "lag")):
        for pair in ("f3_f4", "c3_c4", "p3_p4"):
            key = f"{pair}_{descriptor}"
            axes[row, 0].plot(frame_t, [f.raw[key] for f in session.frames], label=pair.upper(), lw=0.9)
            axes[row, 1].plot(frame_t, [f.normalized[key] for f in session.frames], label=pair.upper(), lw=0.9)
        axes[row, 0].set_ylabel(descriptor); axes[row, 1].set_ylim(-0.02, 1.02)
    axes[0, 0].set_title("Raw pair descriptors"); axes[0, 1].set_title("Robust-normalised pair descriptors")
    axes[0, 0].legend(); axes[0, 1].legend(); _scenario_spans(axes.ravel(), scenario_edges)
    fig.savefig(output_dir / "pair_features.png", dpi=120); plt.close(fig)

    fig, axis = plt.subplots(figsize=(12, 3), constrained_layout=True)
    axis.plot(frame_t, [f.baseline_progress for f in session.frames])
    axis.set(title="Rolling robust baseline progress", xlabel="seconds", ylabel="fraction", ylim=(-0.02, 1.02))
    _scenario_spans([axis], scenario_edges)
    fig.savefig(output_dir / "baseline.png", dpi=120); plt.close(fig)


def write_dashboard(output_dir, samples, sample_rate, source, session, scenario_edges):
    output_dir.mkdir(parents=True, exist_ok=False)
    _save_plots(output_dir, samples, sample_rate, session, scenario_edges)
    last = session.frames[-1]
    rows = "".join(f"<tr><td><code>{html.escape(key)}</code></td><td>{last.raw[key]:.8g}</td><td>{last.normalized[key]:.6f}</td><td>{session.sender.last_values.get(key, float('nan')):.6f}</td></tr>" for key in sorted(last.raw))
    warning_rows = "".join(f"<tr><td>{name.upper()}</td><td>{html.escape(', '.join(items) if items else 'none')}</td></tr>" for name, items in last.quality_warnings.items())
    scenario_text = "" if scenario_edges is None else "<ol>" + "".join(f"<li>{html.escape(name)}: {scenario_edges[i]:.2f}–{scenario_edges[i+1]:.2f} s</li>" for i, name in enumerate(SCENARIOS)) + "</ol>"
    controls_per_frame = len(last.normalized)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>EEG control dashboard</title><style>body{{font:15px system-ui;max-width:1500px;margin:auto;padding:2rem}}img{{width:100%}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #bbb;padding:.3rem;text-align:left}}code{{background:#eee}}</style></head><body>
<h1>EEG → Tidal control validation</h1><p>Source: {html.escape(source)}; {len(samples)} samples at {sample_rate:g} Hz; six EEG channels; {len(session.frames)} control frames.</p>
<p>Feature update rate: {session.update_rate:g} Hz. OSC: <code>/ctrl name value</code> → {session.sender.host}:{session.sender.port}. Controls/frame: {controls_per_frame}; nominal packet rate: {controls_per_frame * session.update_rate:g} packets/s; packets sent: {session.sender.packet_count}. Envelope smoothing: 80 ms window, approximately 40 ms latency.</p>
<p>No raw 250 Hz waveform is sent over OSC. EOG/EMG are not used by this control bridge.</p><h2>Synthetic scenario schedule</h2>{scenario_text}
<h2>Raw and cleaned signals</h2><img src="eeg_traces.png"><h2>Per-channel controls</h2><img src="channel_features.png"><h2>Pair controls</h2><img src="pair_features.png"><h2>Baseline progress</h2><img src="baseline.png">
<h2>Last control frame and last OSC values</h2><table><tr><th>Control</th><th>Raw</th><th>Normalised</th><th>Last sent</th></tr>{rows}</table>
<h2>Last-window signal quality</h2><table><tr><th>Channel</th><th>Warnings</th></tr>{warning_rows}</table></body></html>"""
    dashboard = output_dir / "dashboard.html"
    dashboard.write_text(page, encoding="utf-8")
    return dashboard


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--update-rate", type=float, default=4.0)
    parser.add_argument("--baseline-seconds", type=float, default=20.0)
    parser.add_argument("--osc-host", default="127.0.0.1")
    parser.add_argument("--osc-port", type=int, default=6010)
    parser.add_argument("--open-dashboard", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.seconds < 2 or args.update_rate <= 0:
        raise SystemExit("--seconds must be at least 2 and --update-rate must be positive")
    sender = TidalControlOscSender(args.osc_host, args.osc_port)
    if args.synthetic:
        samples, timestamps, scenario_edges = deterministic_scenarios(args.seconds)
        sample_rate, source = 250.0, "deterministic synthetic scenarios"
        session = ControlSession(sample_rate, args.update_rate, args.baseline_seconds, sender)
        session.add_chunk(samples, timestamps)
    else:
        session_holder = {}
        def on_chunk(chunk, timestamps, sample_rate):
            if "session" not in session_holder:
                session_holder["session"] = ControlSession(sample_rate, args.update_rate, args.baseline_seconds, sender)
            session_holder["session"].add_chunk(chunk, timestamps)
        try:
            recording = record_lsl_seconds(args.seconds, chunk_callback=on_chunk)
        except RuntimeError as exc:
            raise SystemExit(f"Live LSL recording failed: {exc}") from exc
        samples, timestamps, sample_rate, source = recording.samples, recording.timestamps, recording.sample_rate, recording.stream_name
        scenario_edges = None
        session = session_holder["session"]
    if not session.frames:
        raise SystemExit("No complete two-second feature window was produced.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dashboard = write_dashboard(Path("reports/eeg_control") / stamp, samples, sample_rate, source, session, scenario_edges)
    print(f"Dashboard: {dashboard.resolve()}")
    print(f"Frames: {len(session.frames)} at {args.update_rate:g} Hz; OSC packets: {sender.packet_count}")
    sender.close()
    if args.open_dashboard:
        webbrowser.open(dashboard.resolve().as_uri())


if __name__ == "__main__":
    main()
