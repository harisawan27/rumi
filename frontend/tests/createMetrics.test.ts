import { CreateMetrics } from '../src/services/createMetrics';

const id = '5be2b39d-7258-4658-bfc0-554ba650c439';
test('diagnostics contain only correlated timings, discard stale work and deduplicate audio chunks', () => {
  const rows: object[] = [];
  let clock = 100;
  const metrics = new CreateMetrics(row => rows.push(row), () => clock);
  metrics.begin(id);
  clock = 150;
  metrics.mark(id, 'planner_started');
  metrics.mark('stale', 'canvas_interactive');
  metrics.mark(id, 'acknowledgement_audio_scheduled');
  metrics.mark(id, 'acknowledgement_audio_scheduled');
  metrics.cancel();
  metrics.mark(id, 'canvas_interactive');
  expect(rows).toHaveLength(3);
  expect(rows[0]).toEqual({event:'planner_started',request_id:id,elapsed_ms:50});
  expect(rows[2]).toEqual({event:'cancelled',request_id:id,elapsed_ms:50});
});

test('ordinary turns and invalid identifiers produce no telemetry', () => {
  const write = jest.fn();
  const metrics = new CreateMetrics(write);
  metrics.begin('private content');
  metrics.mark('private content', 'planner_started');
  metrics.begin(id);
  metrics.cancel();
  expect(write).not.toHaveBeenCalled();
});
