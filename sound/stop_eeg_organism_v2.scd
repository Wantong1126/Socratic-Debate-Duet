// Gracefully stop only the v2 receiver and its dedicated nodes.
// SuperDirt and scsynth remain running.
(
if(~eegOrganismV2.notNil and: { ~eegOrganismV2[\stop].notNil }) {
    ~eegOrganismV2[\stop].value(false);
} {
    "Organism v2 receiver is not running.".postln;
};
)
