(
// Python sends OSC here.
thisProcess.openUDPPort(9000);

s.boot;

s.waitForBoot({
    SynthDef(\biosignalInstrument, {
        |eegLow = 0.2,
        eegMid = 0.3,
        eegHigh = 0.5,
        eog = 0.0,
        emg = 0.0|

        var low;
        var mid;
        var high;
        var eye;
        var muscle;
        var baseFrequency;
        var pitchMovement;
        var tonalLayer;
        var muscleLayer;
        var output;

        // Smooth control changes and prevent clicks.
        low = Lag.kr(eegLow.clip(0, 1), 1.5);
        mid = Lag.kr(eegMid.clip(0, 1), 1.5);
        high = Lag.kr(eegHigh.clip(0, 1), 1.5);
        eye = Lag.kr(eog.clip(0, 1), 0.5);
        muscle = Lag.kr(emg.clip(0, 1), 0.15);

        // EEG proportions define the continuous tonal layer.
        baseFrequency = mid.linexp(0, 1, 110, 260);

        pitchMovement = SinOsc.kr(
            low.linlin(0, 1, 0.05, 0.5)
        ).range(
            1 - (eye * 0.04),
            1 + (eye * 0.04)
        );

        tonalLayer = SinOsc.ar(
            [
                baseFrequency * pitchMovement,
                baseFrequency * 1.005 * pitchMovement
            ],
            0,
            0.025
        );

        tonalLayer = tonalLayer + SinOsc.ar(
            [
                baseFrequency * 2,
                baseFrequency * 2.01
            ],
            0,
            high * 0.008
        );

        // EMG adds continuous texture, not an event sound.
        muscleLayer = BPF.ar(
            WhiteNoise.ar(0.025 ! 2),
            muscle.linexp(0, 1, 500, 4000),
            0.25
        ) * muscle;

        output = tonalLayer + muscleLayer;

        // Protect against clipped controls and excessive output.
        output = LeakDC.ar(output);
        output = Limiter.ar(output, 0.08);

        Out.ar(0, output);
    }).add;

    s.sync;

    ~biosignalInstrument = Synth(\biosignalInstrument);

    OSCdef(
        \eegLowInput,
        { |message|
            ~biosignalInstrument.set(
                \eegLow,
                message[1].asFloat.clip(0, 1)
            );
        },
        "/eeg/4_8",
        recvPort: 9000
    );

    OSCdef(
        \eegMidInput,
        { |message|
            ~biosignalInstrument.set(
                \eegMid,
                message[1].asFloat.clip(0, 1)
            );
        },
        "/eeg/8_13",
        recvPort: 9000
    );

    OSCdef(
        \eegHighInput,
        { |message|
            ~biosignalInstrument.set(
                \eegHigh,
                message[1].asFloat.clip(0, 1)
            );
        },
        "/eeg/13_30",
        recvPort: 9000
    );

    OSCdef(
        \eogInput,
        { |message|
            ~biosignalInstrument.set(
                \eog,
                message[1].asFloat.clip(0, 1)
            );
        },
        "/body/eog",
        recvPort: 9000
    );

    OSCdef(
        \emgInput,
        { |message|
            ~biosignalInstrument.set(
                \emg,
                message[1].asFloat.clip(0, 1)
            );
        },
        "/body/emg",
        recvPort: 9000
    );

    "BIOSIGNAL INSTRUMENT READY".postln;
});
)