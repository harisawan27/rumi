import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import NativeDesktop from '../src/components/desktop/NativeDesktop';
const active = { active: true, workspace: 'C:\\RumiTest', session_id: 'native-session', seconds_remaining: 900 };
const inactive = { active: false };
let api;
beforeEach(() => {
  api = { status: jest.fn(async () => inactive), choose_workspace: jest.fn(async () => active), command: jest.fn(), stop: jest.fn(async () => inactive) };
  window.pywebview = { api };
  global.fetch = jest.fn();
});
afterEach(() => { delete window.pywebview; jest.useRealTimers(); });
async function connect() {
  render(<NativeDesktop />);
  await act(async () => {});
  fireEvent.click(screen.getByRole('button', { name: 'Choose folder & enable' }));
  await screen.findByText('Connected to your folder');
  api.status.mockResolvedValue(active);
}

test('ordinary browser cannot issue local commands or grant itself a folder', async () => {
  delete window.pywebview;
  render(<NativeDesktop />);
  expect(screen.getByRole('button', { name: 'Choose folder & enable' })).toBeDisabled();
  expect(screen.getByLabelText('Local command')).toBeDisabled();
  expect(screen.getByText('Open this workspace in Rumi Desktop.')).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('native create/read receipts render as plain text without any cloud request', async () => {
  await connect();
  api.command.mockImplementation(async request => ({ request_id: request.request_id, state: 'succeeded', operation: 'read_text', result: { text: '<script>private</script>' } }));
  fireEvent.click(screen.getByRole('button', { name: 'Read that file', exact: true }));
  await screen.findByText('<script>private</script>');
  expect(document.querySelector('pre script')).toBeNull();
  expect(api.command).toHaveBeenCalledWith(expect.objectContaining({ text: 'Read that file', session_id: active.session_id }));
  expect(global.fetch).not.toHaveBeenCalled();
});

test('Stop clears private data and suppresses a late native result', async () => {
  await connect();
  let resolve;
  api.command.mockImplementation(() => new Promise(r => { resolve = r; }));
  fireEvent.click(screen.getByRole('button', { name: 'Read that file', exact: true }));
  const request = api.command.mock.calls[0][0];
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  await act(async () => resolve({ request_id: request.request_id, state: 'succeeded', operation: 'read_text', result: { text: 'late secret' } }));
  expect(screen.queryByText('late secret')).not.toBeInTheDocument();
  expect(screen.queryByText(active.workspace)).not.toBeInTheDocument();
  expect(api.stop).toHaveBeenCalled();
});

test('stop during folder consent cannot enable the UI later', async () => {
  let resolve;
  api.choose_workspace.mockImplementation(() => new Promise(r => { resolve = r; }));
  render(<NativeDesktop />);
  await act(async () => {});
  fireEvent.click(screen.getByRole('button', { name: 'Choose folder & enable' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  await act(async () => resolve(active));
  expect(screen.queryByText('Connected to your folder')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Local command')).toBeDisabled();
});

test('polling cannot restore permission after Stop even if the host still reports active', async () => {
  jest.useFakeTimers();
  await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  api.status.mockResolvedValue(active);
  await act(async () => jest.advanceTimersByTime(2000));
  expect(screen.getByLabelText('Local command')).toBeDisabled();
  expect(screen.queryByText(active.workspace)).not.toBeInTheDocument();
  expect(screen.getByText(/Local permission cleared/)).toBeInTheDocument();
});

test('host permission loss removes private results', async () => {
  jest.useFakeTimers();
  await connect();
  api.command.mockImplementation(async request => ({ request_id: request.request_id, state: 'succeeded', operation: 'read_text', result: { text: 'private body' } }));
  fireEvent.click(screen.getByRole('button', { name: 'Read that file', exact: true }));
  await act(async () => {});
  expect(screen.getByText('private body')).toBeInTheDocument();
  api.status.mockResolvedValue(inactive);
  await act(async () => jest.advanceTimersByTime(2000));
  expect(screen.queryByText('private body')).not.toBeInTheDocument();
  expect(screen.getByText(/Local permission ended/)).toBeInTheDocument();
});

test('timeout is uncertain, revokes access and never retries a command', async () => {
  jest.useFakeTimers();
  await connect();
  api.command.mockImplementation(() => new Promise(() => {}));
  fireEvent.click(screen.getByRole('button', { name: 'Open Notepad', exact: true }));
  await act(async () => jest.advanceTimersByTime(20000));
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.stop).toHaveBeenCalled();
  expect(screen.getByText(/The action may have completed/)).toBeInTheDocument();
  expect(screen.getByLabelText('Local command')).toBeDisabled();
});

test('a mismatched receipt fails closed and keyboard Stop remains available', async () => {
  await connect();
  api.command.mockResolvedValue({ request_id: 'wrong', state: 'succeeded', result: { text: 'wrong private data' } });
  fireEvent.click(screen.getByRole('button', { name: 'List text files', exact: true }));
  await waitFor(() => expect(screen.getByLabelText('Local command')).toBeDisabled());
  expect(screen.queryByText('wrong private data')).not.toBeInTheDocument();
  fireEvent.keyDown(window, { key: '>', code: 'Period', ctrlKey: true, shiftKey: true });
  expect(screen.getByText(/Local permission cleared/)).toBeInTheDocument();
});
