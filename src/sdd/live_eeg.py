"""T18 and the opt-in single-energy bridge from an eight-channel LSL stream."""
import argparse
from collections import deque
import json
import math
from pathlib import Path
import time
import tomllib

import numpy as np
from pylsl import local_clock

from src.eeg_control_demo import ControlSession
from src.sonification.protocol import OrganismControlSender, OrganismVoicingFrame
from src.window_engine import connect_openbci_lsl, describe_lsl_stream, list_openbci_lsl
from .session_runtime import SessionRuntime
from .session_types import FrameEnvelope


UNIT_ALIASES = {
    "uv": "uV", "µv": "uV", "μv": "uV", "microvolt": "uV",
    "microvolts": "uV", "microvolts (uv)": "uV",
}


class _DryClient:
    def __init__(self):
        self.messages = []

    def send_message(self, address, values):
        self.messages.append((address, tuple(values)))


def _unit(value):
    return UNIT_ALIASES.get(value.strip().lower()) if isinstance(value, str) else None


def _metadata_dict(metadata, roles):
    return {
        "name": metadata.name, "type": metadata.stream_type,
        "source_id": metadata.source_id, "uid": metadata.uid,
        "hostname": metadata.hostname, "channel_count": metadata.channel_count,
        "nominal_srate_hz": metadata.nominal_srate,
        "reported_labels": metadata.channel_labels,
        "reported_units": metadata.channel_units,
        "configured_roles": roles, "upstream_prefiltering": metadata.prefiltering,
    }


def list_streams(wait_time):
    streams = list_openbci_lsl(wait_time)
    if not streams:
        print("No eight-channel type=EEG LSL candidates found.")
        return 1
    for index, stream in enumerate(streams):
        metadata = describe_lsl_stream(stream)
        print(json.dumps({"index": index, **_metadata_dict(metadata, ())}, ensure_ascii=False))
    return 0


def run(args):
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    source_config, analysis = config["source"], config["analysis"]
    roles = tuple(source_config["channel_roles"])
    if len(roles) != 8:
        raise ValueError("live configuration must define exactly eight channel roles")
    inlet, stream, sample_rate = connect_openbci_lsl(
        args.wait_time, stream_name=args.stream_name, source_id=args.source_id,
    )
    time_correction = float(inlet.time_correction(timeout=2.0))
    metadata = describe_lsl_stream(stream)
    if not math.isfinite(sample_rate) or sample_rate <= 2 * analysis["lowpass_hz"]:
        raise RuntimeError(
            f"reported sampling rate {sample_rate:g} Hz cannot support the configured "
            f"{analysis['lowpass_hz']:g} Hz analysis limit"
        )
    reported_units = tuple(_unit(value) for value in metadata.channel_units)
    configured_unit = _unit(source_config.get("sample_unit", ""))
    declared_unit = _unit(args.sample_unit) if args.sample_unit else configured_unit
    units = tuple(unit or declared_unit for unit in reported_units)
    eeg_units_known = all(unit == "uV" for unit in units[:6])
    unit_source = "lsl_metadata" if all(reported_units[:6]) else (
        "operator_gui_confirmation" if declared_unit else "unknown"
    )
    source_confirmed = args.source == "live" and args.confirm_live_hardware
    effective_prefiltering = (
        metadata.prefiltering if metadata.prefiltering.lower() != "unknown"
        else args.upstream_filtering or source_config.get("upstream_filtering", "unknown")
    )
    print("SOURCE " + json.dumps({
        "declared": args.source, "live_hardware_confirmed": source_confirmed,
        "warning": "LSL name/type alone does not prove a human live source",
    }, ensure_ascii=False))
    print("STREAM " + json.dumps(_metadata_dict(metadata, roles), ensure_ascii=False))
    print(f"LSL_TIME_CORRECTION seconds={time_correction:.9f} raw_timestamps_preserved_in_diagnostics=true")
    print("GROUPS EEG=Ch1-6:F3,F4,C3,C4,P3,P4 EOG=Ch7:vertical_EOG EMG=Ch8:jaw_EMG")
    print(f"REFERENCE {source_config['reference']} | BIAS {source_config['bias']}")
    print(f"GUI_DATA_TYPE {source_config.get('lsl_data_type', 'unknown')}")
    print(f"UNITS status={'confirmed_uV' if eeg_units_known else 'unknown_or_mismatched'} "
          f"reported={metadata.channel_units} effective={units} source={unit_source}")
    print(f"UPSTREAM_FILTERING {effective_prefiltering}")
    if args.sound and not source_confirmed:
        raise RuntimeError("--sound requires --source live --confirm-live-hardware")
    if args.sound and not eeg_units_known:
        raise RuntimeError("--sound blocked: Ch1-6 units must be reported as microvolts")
    if args.sound and not args.confirm_channel_order:
        raise RuntimeError("--sound requires --confirm-channel-order for Ch1-8")
    if args.sound and effective_prefiltering == "unknown":
        raise RuntimeError("--sound requires reported filtering or --upstream-filtering")
    if args.sound and args.duration <= analysis["baseline_seconds"] + 2:
        raise RuntimeError("--sound duration must include baseline plus at least two listening seconds")

    client = None if args.sound else _DryClient()
    sender = OrganismControlSender(**config["transport"], client=client)
    session_id = f"live-energy-{int(time.time())}"
    runtime = SessionRuntime(
        sender, session_id=session_id, participant_id=source_config["participant_id"],
        rate=config["session"]["control_hz"],
        max_age=config["session"]["max_age_seconds"],
    )
    fixed = tuple(config["mapping"]["fixed"])
    sequence = 0
    envelope_mode = {"live": "live", "synthetic": "fixture", "replay": "replay"}[args.source]

    def on_frame(frame, lsl_timestamp):
        nonlocal sequence
        now = time.monotonic()
        age = local_clock() - (float(lsl_timestamp) + time_correction)
        sampled_at = now - max(0.0, age)
        f3_warnings = frame.quality_warnings.get(analysis["energy_channel"], [])
        energy_bounds = session.engine.bounds.get("eeg1_energy") if session.engine.bounds else None
        scale_valid = (energy_bounds is not None
                       and energy_bounds[1]-energy_bounds[0] > np.finfo(float).eps
                       * max(abs(energy_bounds[0]), abs(energy_bounds[1]), 1.0) * 32)
        valid = bool(frame.normalized) and not f3_warnings and eeg_units_known \
            and scale_valid and math.isfinite(age) \
            and 0 <= age <= config["session"]["max_age_seconds"]
        values = list(fixed)
        if frame.normalized:
            values[0] = frame.normalized["eeg1_energy"]
        reasons = []
        if not frame.normalized:
            reasons.append("personal_baseline_incomplete")
        if f3_warnings:
            reasons.append("F3:" + ",".join(f3_warnings))
        if not eeg_units_known:
            reasons.append("unknown_eeg_unit")
        if frame.normalized and not scale_valid:
            reasons.append("personal_energy_range_degenerate")
        if not math.isfinite(age) or not 0 <= age <= config["session"]["max_age_seconds"]:
            reasons.append("stale_lsl_timestamp")
        envelope = FrameEnvelope(
            session_id, source_config["participant_id"], sequence,
            sampled_at, now, envelope_mode, tuple(values), valid=valid,
            reason=";".join(reasons),
        )
        sequence += 1
        runtime.offer(envelope)
        runtime.tick()
        if frame.normalized:
            energy_unit = "uV^2" if eeg_units_known else "unknown_unit_squared"
            print(f"ENERGY formula=Welch_integral_{analysis['highpass_hz']:g}-{analysis['lowpass_hz']:g}Hz(F3)^2 "
                  f"unit={energy_unit} "
                  f"raw={frame.raw['eeg1_energy']:.6g} normalized={frame.normalized['eeg1_energy']:.3f} "
                  f"valid={valid} fixed_fields={tuple(values[1:])}")

    session = ControlSession(
        sample_rate, analysis["update_rate_hz"], analysis["baseline_seconds"],
        sender, window_seconds=analysis["window_seconds"],
        analysis_low_hz=analysis["highpass_hz"],
        analysis_high_hz=analysis["lowpass_hz"],
        smoothing_seconds=analysis["smoothing_seconds"], diagnostics=False,
        control_hz=config["session"]["control_hz"],
        frame_callback=on_frame, transmit=False,
        required_quality_channels=(0,),
        saturation_abs=(analysis["rail_limit_uv"] * analysis["saturation_fraction"]
                        if eeg_units_known else None),
    )
    if args.sound:
        sender.send_voicing(OrganismVoicingFrame.from_active(
            config["mapping"]["frequencies_hz"], config["mapping"]["weights"],
        ))
        print("AUDIO enabled: only normalized F3 energy is live; eight other frame fields are fixed.")
    else:
        print("AUDIO disabled (default diagnostic mode).")

    started = time.monotonic()
    first_lsl = last_lsl = None
    sample_count = 0
    recent = deque(maxlen=max(2, int(round(sample_rate * analysis["window_seconds"]))))
    next_status = started
    try:
        while time.monotonic() - started < args.duration:
            chunk, timestamps = inlet.pull_chunk(
                timeout=0.25, max_samples=max(1, int(round(sample_rate / analysis["update_rate_hz"])))
            )
            now = time.monotonic()
            if not chunk:
                runtime.tick()
                continue
            data = np.asarray(chunk, dtype=float)
            stamp = np.asarray(timestamps, dtype=float)
            if data.ndim != 2 or data.shape[1] < 8 or len(stamp) != len(data):
                print(f"QUALITY invalid_shape samples={data.shape} timestamps={len(stamp)}")
                continue
            data = data[:, :8]
            sample_count += len(data)
            first_lsl = float(stamp[0]) if first_lsl is None else first_lsl
            last_lsl = float(stamp[-1])
            recent.extend(data)
            session.add_chunk(data, stamp)
            if now >= next_status:
                window = np.asarray(recent, dtype=float)
                disabled = [roles[i] for i in range(8)
                            if window.size and np.all(np.isfinite(window[:, i]))
                            and np.ptp(window[:, i]) <= analysis["flatline_peak_to_peak_min"]]
                saturated = [roles[i] for i in range(8)
                             if eeg_units_known and window.size
                             and np.any(np.abs(window[:, i]) >= analysis["rail_limit_uv"]
                                       * analysis["saturation_fraction"])]
                finite = bool(np.isfinite(window).all())
                lsl_elapsed = max(last_lsl-first_lsl, np.finfo(float).eps)
                observed_rate = (sample_count-1)/lsl_elapsed if sample_count > 1 else 0.0
                rate_ok = abs(observed_rate-sample_rate)/sample_rate <= analysis["arrival_rate_tolerance"]
                timestamp_age = local_clock()-(last_lsl+time_correction)
                quality = ("valid" if finite and not disabled and not saturated
                           and rate_ok and timestamp_age <= 0.5 else "invalid")
                print("SAMPLES " + " ".join(f"{role}={value:.3f}" for role, value in zip(roles, data[-1])))
                print(f"TIMING lsl={last_lsl:.6f} arrival_monotonic={now:.6f} "
                      f"nominal_rate_hz={sample_rate:g} observed_rate_hz={observed_rate:.2f} "
                      f"timestamp_age_s={timestamp_age:.3f}")
                print(f"QUALITY {quality} finite={finite} disabled_or_flat={disabled} "
                      f"saturated={saturated} rate_ok={rate_ok}")
                next_status = now + 1.0
        if sample_count == 0:
            raise RuntimeError(
                f"selected stream {metadata.name!r} was discoverable but produced no samples"
            )
        if args.verify_stop:
            print(f"STOP CHECK: stop the OpenBCI GUI data stream now; waiting up to {args.stop_wait:g} seconds.")
            deadline = time.monotonic() + args.stop_wait
            last_new = time.monotonic()
            while time.monotonic() < deadline:
                chunk, timestamps = inlet.pull_chunk(timeout=0.25, max_samples=256)
                if chunk:
                    last_new = time.monotonic()
                    data = np.asarray(chunk, dtype=float)
                    stamp = np.asarray(timestamps, dtype=float)
                    if data.ndim == 2 and data.shape[1] >= 8 and len(stamp) == len(data):
                        sample_count += len(data)
                        session.add_chunk(data[:, :8], stamp)
                    continue
                runtime.tick()
                if time.monotonic()-last_new >= args.stale_seconds:
                    print(f"STOP CONFIRMED no_new_samples_for_s={args.stale_seconds:g}")
                    break
            else:
                raise RuntimeError("stop check failed: samples continued for the entire wait period")
    finally:
        runtime.stop("completed")
        sender.close()
    print(json.dumps({
        "source": args.source, "live_hardware_confirmed": source_confirmed,
        "samples": sample_count, "frames_sent": sender.frame_count if args.sound else 0,
        "audio": args.sound, "raw_saved": False,
    }))
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/live_eeg.toml"))
    parser.add_argument("--list-streams", action="store_true")
    parser.add_argument("--stream-name")
    parser.add_argument("--source-id")
    parser.add_argument("--source", choices=("live", "synthetic", "replay"), default="live")
    parser.add_argument("--confirm-live-hardware", action="store_true")
    parser.add_argument("--confirm-channel-order", action="store_true")
    parser.add_argument("--upstream-filtering",
                        help="GUI-reported filtering when LSL metadata says unknown")
    parser.add_argument("--sample-unit", choices=("uV",),
                        help="GUI-confirmed sample unit when LSL metadata omits units")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--wait-time", type=float, default=5.0)
    parser.add_argument("--verify-stop", action="store_true")
    parser.add_argument("--stop-wait", type=float, default=30.0)
    parser.add_argument("--stale-seconds", type=float, default=2.0)
    parser.add_argument("--sound", action="store_true",
                        help="explicitly send normalized F3 energy to the running current receiver")
    args = parser.parse_args(argv)
    if min(args.duration, args.wait_time, args.stop_wait, args.stale_seconds) <= 0:
        parser.error("durations must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        return list_streams(args.wait_time) if args.list_streams else run(args)
    except RuntimeError as exc:
        raise SystemExit(f"Live LSL error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
