import React, { useSyncExternalStore } from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import GeneratedArtifact from '../src/components/GeneratedArtifact';
import ArtifactCanvas from '../src/components/ArtifactCanvas';
import { SUBJECT_COLORS } from '../src/components/artifacts/StudyTracker';
import { parseGeneratedArtifact, isStudyEditDecision } from '../src/types/artifacts';
import { addStudyEntry, removeStudyEntry, calculateDailyTotals, calculateSubjectTotals } from '../src/services/studyTracker';
import { ArtifactAccessDenied, ArtifactClient } from '../src/services/artifactClient';
import { canvasFromHistory } from '../src/services/canvasHistory';
import fixture from '../../tests/fixtures/artifacts/valid_study_tracker.json';
import colorEdit from '../../tests/fixtures/artifacts/valid_color_edit.json';
import graphEdit from '../../tests/fixtures/artifacts/valid_graph_edit.json';
import invalidColor from '../../tests/fixtures/artifacts/invalid_color.json';
import invalidRenderer from '../../tests/fixtures/artifacts/invalid_renderer.json';

const entry = { id: 'entry_1', subject_id: 'economics', date: '2026-09-14', minutes: 60 };
const copy = () => JSON.parse(JSON.stringify(fixture));
beforeAll(() => { Element.prototype.scrollTo = jest.fn(); });

test('history references never hydrate embedded tracker data or offer Markdown followup', () => {
  const reference = canvasFromHistory({ kind: 'generated_ui', artifact_id: fixture.artifact_id,
    title: 'Saved tracker', timestamp: '', content: 'untrusted content', state: fixture.state });
  expect(reference.exchanges).toEqual([]);
  expect(reference.state).toBeUndefined();
  expect(reference.artifact_id).toBe(fixture.artifact_id);
  render(<ArtifactCanvas content={reference} onDismiss={() => {}} onFollowUp={jest.fn()} />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading saved tracker');
  expect(screen.queryByText('untrusted content')).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});

test('malformed generated history is harmless and legacy history still maps', () => {
  const reference = canvasFromHistory({ kind: 'generated_ui', artifact_id: '../foreign', title: 'Saved', timestamp: '' });
  expect(reference.artifact_id).toBeUndefined();
  render(<ArtifactCanvas content={reference} onDismiss={() => {}} />);
  expect(screen.getByRole('status')).toHaveTextContent('unavailable');
  expect(canvasFromHistory({ title: 'Legacy', content: 'Answer', timestamp: '' }).exchanges[0].response).toBe('Answer');
});

test('shared fixtures agree with server vocabulary', () => {
  expect(parseGeneratedArtifact(fixture)).toEqual(fixture);
  expect(isStudyEditDecision(colorEdit)).toBe(true);
  expect(isStudyEditDecision(graphEdit)).toBe(true);
  expect(isStudyEditDecision(invalidColor)).toBe(false);
  expect(isStudyEditDecision(invalidRenderer)).toBe(false);
  expect(parseGeneratedArtifact({ ...fixture, spec: { ...fixture.spec, subjects: [{ ...fixture.spec.subjects[0], color_token: invalidColor.edit.color_token }] } })).toBeNull();
  expect(parseGeneratedArtifact({ ...fixture, renderer: invalidRenderer.renderer })).toBeNull();
});
test.each([{ renderer: 'remote_module' }, { schema_version: 2 }, { css: 'background:red' }, { state: { entries: [ { ...entry, minutes: true } ] } }])('rejects malformed envelope %j', change => {
  render(<GeneratedArtifact artifact={{ ...fixture, ...change }} onEdit={jest.fn()} />);
  expect(screen.getByRole('status')).toHaveTextContent('unsupported or invalid');
  expect(screen.queryByRole('form')).not.toBeInTheDocument();
});
test('existing Canvas mounts the trusted empty tracker', () => {
  render(<ArtifactCanvas content={{ kind: 'generated_ui', artifact: fixture }} onDismiss={jest.fn()} />);
  expect(screen.getByText('No study entries yet.')).toBeInTheDocument();
  expect(screen.queryByPlaceholderText('Ask a follow-up…')).not.toBeInTheDocument();
});
test('legacy Canvas rendering is preserved', () => {
  render(<ArtifactCanvas content={{ title: 'Legacy', timestamp: '', exchanges: [{ query: 'Question', response: '**Answer**', type: 'markdown', timestamp: '' }] }} onDismiss={jest.fn()} />);
  expect(screen.getByText('Answer').tagName).toBe('STRONG');
});
test('add and remove interactions use explicit operations', async () => {
  const edit = jest.fn().mockResolvedValue(undefined);
  const { rerender } = render(<GeneratedArtifact artifact={fixture} onEdit={edit} />);
  fireEvent.change(screen.getByLabelText('Minutes'), { target: { value: '60' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  await waitFor(() => expect(edit).toHaveBeenCalledWith({ operation: 'add_entry', entry: expect.objectContaining({ subject_id: 'economics', date: '2026-09-14', minutes: 60 }) }));
  rerender(<GeneratedArtifact artifact={addStudyEntry(fixture, entry)} onEdit={edit} />);
  fireEvent.click(screen.getByRole('button', { name: 'Remove Economics entry on 2026-09-14' }));
  await waitFor(() => expect(edit).toHaveBeenLastCalledWith({ operation: 'remove_entry', entry_id: 'entry_1' }));
});
test.each([['Minutes', '0'], ['Minutes', '-1'], ['Minutes', '1.5'], ['Minutes', '1441'], ['Date', '2026-10-01']])('invalid %s %s never submits', (label, value) => {
  const edit = jest.fn();
  render(<GeneratedArtifact artifact={fixture} onEdit={edit} />);
  fireEvent.change(screen.getByLabelText('Minutes'), { target: { value: '60' } });
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: 'Add entry' }));
  expect(edit).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toHaveTextContent('Choose a subject');
});
test('totals, limits and removal are pure', () => {
  const a = addStudyEntry(fixture, entry);
  expect(fixture.state.entries).toEqual([]);
  expect(calculateDailyTotals(a)[0].minutes).toBe(60);
  expect(calculateDailyTotals(a)).toHaveLength(7);
  expect(calculateSubjectTotals(a).find(s => s.id === 'economics').minutes).toBe(60);
  expect(removeStudyEntry(a, entry.id).state.entries).toEqual([]);
  expect(() => addStudyEntry(a, entry)).toThrow();
  expect(() => addStudyEntry(a, { ...entry, id: 'entry_2', minutes: 1440 })).toThrow();
  expect(() => removeStudyEntry(a, 'missing')).toThrow();
});
test('graph is opt-in and preserves entries; colors belong to application', () => {
  const a = addStudyEntry(fixture, entry);
  const { rerender } = render(<GeneratedArtifact artifact={a} onEdit={jest.fn()} />);
  expect(screen.queryByRole('list', { name: 'Daily study graph' })).not.toBeInTheDocument();
  expect(document.querySelector('.study-dot')).toHaveStyle({ backgroundColor: SUBJECT_COLORS.gold });
  rerender(<GeneratedArtifact artifact={{ ...a, spec: { ...a.spec, show_daily_graph: true } }} onEdit={jest.fn()} />);
  expect(screen.getByRole('list', { name: 'Daily study graph' })).toHaveTextContent('2026-09-14: 60 min');
});
test('hostile-looking labels are literal text', () => {
  const a = copy(); a.spec.subjects[0].label = '<script>alert(1)</script>';
  render(<GeneratedArtifact artifact={a} onEdit={jest.fn()} />);
  expect(screen.getByRole('option', { name: '<script>alert(1)</script>' })).toBeInTheDocument();
  expect(document.querySelector('script')).toBeNull();
});

function response(path, artifact = fixture) {
  if (path.startsWith('access?')) return { request_id: new URLSearchParams(path.split('?')[1]).get('request_id'), lease_seconds: 5 };
  return { result: { type: 'artifact_result', request_id: new URLSearchParams(path.split('?')[1]).get('request_id'), artifact_id: artifact.artifact_id,
    revision: artifact.revision, state_revision: artifact.state_revision, renderer: artifact.renderer, artifact }, lease_seconds: 5 };
}
function View({ client }) {
  const view = useSyncExternalStore(client.subscribe, client.snapshot, client.snapshot);
  return view.artifact ? <GeneratedArtifact artifact={view.artifact} onEdit={client.edit} /> : <p>Locked</p>;
}
test('guest teardown and owner return require a fresh backend load; stale results cannot remount', async () => {
  let pending;
  const transport = jest.fn(async path => response(path));
  const client = new ArtifactClient(transport); client.configure('session_test', true);
  render(<View client={client} />);
  await act(() => client.load(fixture.artifact_id));
  expect(screen.getByRole('region', { name: 'Study tracker' })).toBeInTheDocument();
  transport.mockImplementation(path => new Promise(resolve => { pending = () => resolve(response(path)); }));
  let old;
  act(() => { old = client.reload(); });
  act(() => client.revoke());
  expect(screen.queryByRole('region', { name: 'Study tracker' })).not.toBeInTheDocument();
  await act(async () => { pending(); await old; });
  expect(screen.getByText('Locked')).toBeInTheDocument();
  act(() => client.configure('session_test', true));
  expect(screen.getByText('Locked')).toBeInTheDocument();
  await act(async () => { pending(); });
  expect(screen.getByRole('region', { name: 'Study tracker' })).toBeInTheDocument();
  act(() => client.dispose());
});
test('lease expiration clears private data when refresh stalls', async () => {
  jest.useFakeTimers();
  const transport = jest.fn(async path => response(path));
  const client = new ArtifactClient(transport); client.configure('session_test', true);
  await client.load(fixture.artifact_id);
  transport.mockImplementation(() => new Promise(() => {}));
  jest.advanceTimersByTime(5001);
  expect(client.snapshot().artifact).toBeNull();
  client.dispose(); jest.useRealTimers();
});
test.each(['request', 'target'])('mismatched %s cannot replace selected artifact', async kind => {
  const transport = jest.fn(async path => kind === 'request'
    ? ({ ...response(path), result: { ...response(path).result, request_id: 'wrong' } })
    : response(path, { ...fixture, artifact_id: '650e8400-e29b-41d4-a716-446655440000' }));
  const client = new ArtifactClient(transport); client.configure('session_test', true);
  await expect(client.load(fixture.artifact_id)).rejects.toThrow('Invalid artifact');
  expect(client.snapshot().artifact).toBeNull(); client.dispose();
});

test('switching selection discards the prior artifact response', async () => {
  let finishFirst;
  const second = { ...fixture, artifact_id: '650e8400-e29b-41d4-a716-446655440000', title: 'Selected tracker' };
  const client = new ArtifactClient(path => path.startsWith(fixture.artifact_id)
    ? new Promise(resolve => { finishFirst = () => resolve(response(path)); })
    : Promise.resolve(response(path, second)));
  client.configure('session_test', true);
  const first = client.load(fixture.artifact_id);
  await client.load(second.artifact_id);
  finishFirst(); await first;
  expect(client.snapshot().artifact.artifact_id).toBe(second.artifact_id);
  expect(client.snapshot().artifact.title).toBe('Selected tracker');
  client.dispose();
});

test('authorization failure stops refresh until a fresh owner signal', async () => {
  jest.useFakeTimers();
  const transport = jest.fn(async path => response(path));
  const client = new ArtifactClient(transport); client.configure('session_test', true);
  await client.load(fixture.artifact_id);
  transport.mockRejectedValue(new ArtifactAccessDenied('Owner verification required'));
  await expect(client.reload()).rejects.toThrow('Owner verification required');
  const calls = transport.mock.calls.length;
  jest.advanceTimersByTime(10000);
  expect(transport).toHaveBeenCalledTimes(calls);
  expect(client.snapshot().artifact).toBeNull();
  client.dispose(); jest.useRealTimers();
});

test('presence refresh does not repeatedly fetch the artifact document', async () => {
  jest.useFakeTimers();
  const transport = jest.fn(async path => response(path));
  const client = new ArtifactClient(transport); client.configure('session_test', true);
  await client.load(fixture.artifact_id);
  await jest.advanceTimersByTimeAsync(6000);
  expect(transport.mock.calls.filter(([path]) => path.startsWith(fixture.artifact_id))).toHaveLength(1);
  expect(transport.mock.calls.filter(([path]) => path.startsWith('access?'))).toHaveLength(3);
  expect(client.snapshot().artifact.artifact_id).toBe(fixture.artifact_id);
  client.dispose(); jest.useRealTimers();
});
