(
// Known failure case: another receiver is using port 9000.
if(thisProcess.openUDPPort(9000).not) {
    Error(
        "UDP port 9000 is unavailable. Stop osc_receiver.py first."
    ).throw;
};

s.options.numOutputBusChannels = 2;
s.boot;

s.waitForBoot({
    SynthDef(\agoraDuet, {
        |out = 0,
        eegLow = 0.2,
        eegMid = 0.3,
        eegHigh = 0.5,
        eog = 0.0,
        emg = 0.0,
        master = 0.6|

        var low;
        var mid;
        var high;
        var eye;
        var muscle;

        var phraseRate;
        var melodyTrigger;
        var degree;
        var baseMidi;
        var melodyFrequency;
        var melodyEnvelope;
        var melody;

        var droneFrequencies;
        var droneAmplitudes;
        var drone;
        var tonalLayer;

        var bodyRate;
        var bodyTrigger;
        var bodyEnvelope;
        var bodyCentre;
        var bodyTexture;

        var spatialTone;
        var output;

        // Smooth data changes so OSC updates do not click.
        low = Lag.kr(eegLow.clip(0, 1), 2.0);
        mid = Lag.kr(eegMid.clip(0, 1), 2.0);
        high = Lag.kr(eegHigh.clip(0, 1), 2.0);
        eye = Lag.kr(eog.clip(0, 1), 0.6);
        muscle = Lag.kr(emg.clip(0, 1), 0.18);

        // Autonomous melodic phrase.
        // EEG shapes its pace and register, not its semantic meaning.
        phraseRate = low.linexp(0, 1, 0.12, 0.70);
        melodyTrigger = Impulse.kr(phraseRate);

        degree = Demand.kr(
            melodyTrigger,
            0,
            Dseq(
                [0, 7, 2, 9, 5, 4, 11, 7],
                inf
            )
        );

        baseMidi = 43 + degree + (mid * 7);

        // EOG activity changes glide continuously.
        melodyFrequency = Lag.kr(
            baseMidi.midicps,
            eye.linlin(0, 1, 0.15, 2.0)
        );

        melodyEnvelope = Decay2.kr(
            melodyTrigger,
            0.25,
            3.5
        );

        melody = SinOsc.ar(
            [
                melodyFrequency,
                melodyFrequency * 1.004
            ],
            0,
            melodyEnvelope * 0.018
        );

        // Slowly moving harmonic field.
        droneFrequencies = (
            [55, 82.5, 110, 165]
            * (
                1
                + LFNoise2.kr(
                    [0.031, 0.043, 0.057, 0.071]
                ).range(-0.003, 0.003)
            )
        );

        droneAmplitudes = (
            [
                low,
                mid,
                high,
                (mid + high) * 0.5
            ]
            * [0.018, 0.015, 0.010, 0.007]
        );

        drone = Splay.ar(
            SinOsc.ar(
                droneFrequencies,
                0,
                droneAmplitudes
            ),
            spread: 0.8,
            level: 1.0
        );

        // High-band proportion changes spectral brightness.
        tonalLayer = LPF.ar(
            drone + melody,
            high.linexp(0, 1, 900, 6500)
        );

        // EMG controls the density and brightness of a
        // continuous stochastic texture.
        bodyRate = muscle.linexp(0, 1, 0.4, 14);
        bodyTrigger = Dust.kr(bodyRate);

        bodyEnvelope = Decay2.kr(
            bodyTrigger,
            0.01,
            muscle.linlin(0, 1, 0.08, 0.35)
        );

        bodyCentre = LFNoise2.kr(
            bodyRate.linlin(0.4, 14, 0.2, 3)
        ).exprange(350, 4800);

        bodyTexture = BPF.ar(
            PinkNoise.ar(0.04 ! 2),
            bodyCentre,
            0.22
        ) * bodyEnvelope * muscle;

        // EOG controls depth/space rather than left/right eye position.
        spatialTone = FreeVerb2.ar(
            tonalLayer[0],
            tonalLayer[1],
            mix: eye.linlin(0, 1, 0.12, 0.55),
            room: 0.82,
            damp: 0.55
        );

        output = spatialTone + bodyTexture;
        output = LeakDC.ar(output);
        output = Limiter.ar(output, 0.08);
        output = output * master;

        Out.ar(out, output);
    }).add;

    s.sync;

    ~agoraDuet = Synth(\agoraDuet);

    OSCdef(
        \eegLowInput,
        { |message|
            ~agoraDuet.set(
                \eegLow,
                message[1].asFloat.clip(0, 1)
            );
        },
        '/eeg/4_8',
        recvPort: 9000
    );

    OSCdef(
        \eegMidInput,
        { |message|
            ~agoraDuet.set(
                \eegMid,
                message[1].asFloat.clip(0, 1)
            );
        },
        '/eeg/8_13',
        recvPort: 9000
    );

    OSCdef(
        \eegHighInput,
        { |message|
            ~agoraDuet.set(
                \eegHigh,
                message[1].asFloat.clip(0, 1)
            );
        },
        '/eeg/13_30',
        recvPort: 9000
    );

    OSCdef(
        \eogInput,
        { |message|
            ~agoraDuet.set(
                \eog,
                message[1].asFloat.clip(0, 1)
            );
        },
        '/body/eog',
        recvPort: 9000
    );

    OSCdef(
        \emgInput,
        { |message|
            ~agoraDuet.set(
                \emg,
                message[1].asFloat.clip(0, 1)
            );
        },
        '/body/emg',
        recvPort: 9000
    );

    "AGORA DUET READY — listening on UDP 9000".postln;
});
)

(
OSCdef(\eegLowInput).free;
OSCdef(\eegMidInput).free;
OSCdef(\eegHighInput).free;
OSCdef(\eogInput).free;
OSCdef(\emgInput).free;

~agoraDuet.free;

"AGORA DUET STOPPED".postln;
)
