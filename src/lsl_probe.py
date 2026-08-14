from pylsl import StreamInlet, resolve_streams

print("Searching for LSL streams...")

streams = resolve_streams(wait_time=5.0)

if not streams:
    raise SystemExit(
        "No LSL streams found. "
        "Start Time Series LSL output in OpenBCI GUI first."
    )

print(f"Found {len(streams)} stream(s):")

for index, info in enumerate(streams):
    print(
        f"[{index}] "
        f"name={info.name()} | "
        f"type={info.type()} | "
        f"channels={info.channel_count()} | "
        f"rate={info.nominal_srate()} Hz"
    )

selected = next(
    (stream for stream in streams if stream.channel_count() == 8),
    streams[0],
)

print(f"\nConnecting to: {selected.name()}")

inlet = StreamInlet(selected, max_buflen=10)

for sample_number in range(10):
    sample, timestamp = inlet.pull_sample(timeout=3.0)

    if sample is None:
        print("Timed out waiting for a sample.")
        continue

    preview = ", ".join(f"{value:.2f}" for value in sample[:8])
    print(f"{sample_number + 1:02d} | {timestamp:.3f} | {preview}")

print("\nLSL → Python connection works.")