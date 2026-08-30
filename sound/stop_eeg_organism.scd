// GRACEFUL STOP BLOCK: evaluate this file/block only when you want to stop.
(
if(~eegOrganism.notNil and: { ~eegOrganism[\stop].notNil }) {
    ~eegOrganism[\stop].value(false);
} {
    "EEG organism is not running.".postln;
};
)
