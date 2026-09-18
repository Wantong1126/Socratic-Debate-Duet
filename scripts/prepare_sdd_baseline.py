"""Emit the T09 SC plan from the same fixture/config as the runtime."""
from pathlib import Path
import tomllib

from src.sdd.fixture_source import control_fixture
from src.sonification.protocol import OrganismVoicingFrame


def main():
    config = tomllib.loads(Path('config/sdd_v1.toml').read_text(encoding='utf-8'))
    session, mapping = config['session'], config['mapping']
    frames = control_fixture(duration=session['duration'], rate=session['control_hz'],
                             field=mapping['field'], levels=mapping['levels'], fixed=mapping['fixed'])
    voicing = OrganismVoicingFrame.from_active(mapping['frequencies_hz'], mapping['weights'])
    rows = ',\n'.join(f'[{frame.sampled_at}, {list(frame.values)}]' for frame in frames)
    output = Path('reports/sdd_v1/baseline_plan.scd')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f'(duration: {session["duration"]},\n'
                      f'frequencies: {list(voicing.frequencies_hz)},\n'
                      f'weights: {list(voicing.weights)},\nframes: [\n{rows}\n])\n', encoding='utf-8')


if __name__ == '__main__':
    main()
