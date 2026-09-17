"""Validate IDs, dependency edges and the preferred topological order."""
import json
from pathlib import Path
data = json.loads(Path(__file__).with_name('requirements.json').read_text())
tasks = data['tasks']; ids = {t['id'] for t in tasks}
assert len(ids) == len(tasks), 'Duplicate IDs'
order = data['preferred_topological_order']
assert len(order) == len(ids) and set(order) == ids, 'Incomplete order'
pos = {node:i for i,node in enumerate(order)}
for task in tasks:
    for dep in task['depends_on']:
        assert dep in ids, f'Missing dependency {dep}'
        assert pos[dep] < pos[task['id']], f'Out-of-order edge: {dep} -> {task["id"]}'
edges = sum(len(t['depends_on']) for t in tasks)
print(f'PASS: {len(tasks)} tasks, {edges} dependency edges, acyclic preferred order.')
print(' '.join(order))
