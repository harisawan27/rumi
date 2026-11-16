import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import NativeDesktop from '../src/components/desktop/NativeDesktop';
import { textPages } from '../src/services/nativeDesktop';
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
  api.status.mockResolvedValue(active);
  fireEvent.click(screen.getByRole('button', { name: 'Choose folder & enable' }));
  await screen.findByText('Connected to your folder');
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

async function voiceConnect() {
  jest.useFakeTimers();
  api.voice_start = jest.fn(async () => ({ active: true, voice_id: 3 }));
  api.voice_stop = jest.fn(async () => ({ active: false }));
  api.voice_poll = jest.fn(async () => ({ active: true, voice_id: 3, events: [] }));
  api.voice_speak = jest.fn(async () => ({ accepted: true }));
  api.command.mockImplementation(async request => ({ request_id: request.request_id, state: 'succeeded', operation: 'create_text' }));
  await connect();
  expect(api.voice_start).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Enable local voice' }));
  await act(async () => {});
}
async function hear(text, id = 1) {
  api.voice_poll.mockResolvedValueOnce({ active: true, voice_id: 3, events: [{ id, kind: 'transcript', text }] });
  await act(async () => jest.advanceTimersByTime(250));
}

test('voice starts explicitly and duplicate transcripts execute once without cloud requests', async () => {
  await voiceConnect();
  await hear('Open Notepad');
  await hear('Open Notepad');
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.command).toHaveBeenCalledWith(expect.objectContaining({ text: 'Open Notepad', session_id: active.session_id }));
  expect(api.voice_speak).toHaveBeenCalledWith(expect.objectContaining({ voice_id: 3, session_id: active.session_id }));
  expect(global.fetch).not.toHaveBeenCalled();
});

test('spoken creation needs confirmation and preserves exact recognized words', async () => {
  await voiceConnect();
  const request = 'Create test.txt with content: My exact words.';
  await hear(request);
  expect(api.command).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Local result')).toHaveTextContent(request);
  await hear('Open Notepad', 2);
  expect(api.command).not.toHaveBeenCalled();
  await hear('confirm', 3);
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.command).toHaveBeenCalledWith(expect.objectContaining({ text: request }));
});

test('expired voice confirmation never writes a file', async () => {
  await voiceConnect();
  await hear('Create test.txt with content: hello');
  await act(async () => jest.advanceTimersByTime(30001));
  await hear('confirm', 2);
  expect(api.command).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Confirm creation' })).not.toBeInTheDocument();
});

test('Stop suppresses a delayed voice start and never restores listening', async () => {
  let resolve;
  api.voice_start = jest.fn(() => new Promise(r => { resolve = r; }));
  await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Enable local voice' }));
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  await act(async () => resolve({ active: true, voice_id: 9 }));
  expect(screen.queryByRole('button', { name: 'Pause microphone' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Enable local voice' })).toBeDisabled();
});

test('late voice poll after Stop cannot execute or expose a transcript', async () => {
  await voiceConnect();
  let resolve;
  api.voice_poll.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  await act(async () => jest.advanceTimersByTime(250));
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  await act(async () => resolve({ active: true, voice_id: 3, events: [{ id: 1, kind: 'transcript', text: 'Open Notepad' }] }));
  expect(api.command).not.toHaveBeenCalled();
  expect(api.voice_speak).not.toHaveBeenCalled();
});

test('unavailable microphone leaves typing usable', async () => {
  api.voice_start = jest.fn(async () => { throw new Error('no device'); });
  await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Enable local voice' }));
  await screen.findByText(/Local voice is unavailable/);
  fireEvent.click(screen.getByRole('button', { name: 'Type a command' }));
  expect(screen.getByLabelText('Local command')).toBeEnabled();
});

test('result pagination retains all text including whitespace and wide characters', () => {
  const original = ('Long line\twith words 中文 👋\n\n' + 'x'.repeat(83)).repeat(30);
  const pages = textPages(original, 20, 3);
  expect(pages.length).toBeGreaterThan(1);
  expect(pages.join('')).toBe(original);
  expect(textPages('')).toEqual(['']);
});

test('voice can turn result pages without executing another local action', async () => {
  await voiceConnect();
  api.command.mockImplementation(async request => ({ request_id: request.request_id, state: 'succeeded', operation: 'read_text', result: { text: 'a'.repeat(700) + 'last page' } }));
  await hear('Read that file');
  const first = screen.getByLabelText('Local result').textContent;
  await hear('next page', 2);
  await hear('next page', 3);
  expect(screen.getByLabelText('Local result').textContent).not.toBe(first);
  expect(screen.getByLabelText('Local result')).toHaveTextContent('last page');
  expect(api.command).toHaveBeenCalledTimes(1);
});

test('character follows actual work, verified success, listening and native speech', async () => {
  await voiceConnect();
  expect(screen.getByRole('img', { name: 'Rumi companion: listening' })).toBeInTheDocument();
  let resolve;
  api.command.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  await hear('Read that file');
  expect(screen.getByRole('img', { name: 'Rumi companion: reading' })).toBeInTheDocument();
  const request = api.command.mock.calls[0][0];
  await act(async () => resolve({ request_id: request.request_id, state: 'succeeded', operation: 'read_text', result: { text: 'hello' } }));
  expect(screen.getByRole('img', { name: 'Rumi companion: success' })).toBeInTheDocument();
  api.voice_poll.mockResolvedValueOnce({ active: true, voice_id: 3, speaking: true });
  await act(async () => jest.advanceTimersByTime(250));
  expect(screen.getByRole('img', { name: 'Rumi companion: speaking' })).toBeInTheDocument();
  await act(async () => jest.advanceTimersByTime(250));
  await act(async () => jest.advanceTimersByTime(2700));
  expect(screen.getByRole('img', { name: 'Rumi companion: listening' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  expect(screen.getByRole('img', { name: 'Rumi companion: stopped' })).toBeInTheDocument();
});

test('launch dispatch gets acknowledgement, never a verified-success celebration', async () => {
  await connect();
  api.command.mockImplementation(async request => ({ request_id: request.request_id, state: 'dispatched', operation: 'open_app' }));
  fireEvent.click(screen.getByRole('button', { name: 'Open Notepad', exact: true }));
  await screen.findByRole('img', { name: 'Rumi companion: acknowledging' });
  expect(screen.queryByRole('img', { name: 'Rumi companion: success' })).not.toBeInTheDocument();
});

test('expression preview waits for microphone pause and Stop cancels a late opening', async () => {
  await voiceConnect();
  let resolve;
  api.voice_stop.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
  fireEvent.click(screen.getByRole('button', { name: 'Meet Rumi', exact: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Stop & disconnect' }));
  await act(async () => resolve({ active: false }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('voice can enable and run a Windows plan with separate explicit confirmation', async () => {
  const operatorGrant = { ...active, windows_control: true };
  api.enable_windows_control = jest.fn().mockResolvedValue(operatorGrant);
  await voiceConnect();
  api.status.mockResolvedValue(operatorGrant);
  api.command.mockImplementation(async request => ({
    request_id: request.request_id,
    operation: 'window_control',
    state: request.text === 'confirm window plan' ? 'succeeded' : 'plan',
    message: request.text === 'confirm window plan' ? 'Verified all 2 steps.' : 'Plan for a Windows app. Say Rumi confirm window plan.',
  }));
  await hear('enable Windows control');
  expect(api.enable_windows_control).toHaveBeenCalledTimes(1);
  await hear('control window press Find then expect Search', 2);
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.voice_speak).toHaveBeenLastCalledWith(expect.objectContaining({ text: expect.stringContaining('Say Rumi confirm window plan') }));
  await hear('confirm window plan', 3);
  expect(api.command).toHaveBeenLastCalledWith(expect.objectContaining({ text: 'confirm window plan' }));
  expect(screen.getByLabelText('Local result')).toHaveTextContent('Verified all 2 steps.');
});

test('compound voice request previews the exact note and uses a separate save confirmation', async () => {
  await voiceConnect();
  const message = 'Found the term. Say Rumi, confirm workflow save.';
  const text = 'Document search\nFound invoice in the document.\n';
  const command = 'find invoice in this document and save what you found as a note';
  api.command.mockImplementation(async request => ({
    request_id: request.request_id,
    operation: 'note_workflow',
    state: request.text === 'confirm workflow save' ? 'succeeded' : 'workflow_review',
    message: request.text === 'confirm workflow save' ? 'Saved and verified document-search.txt.' : message,
    result: { text, name: 'document-search.txt' },
  }));
  await hear('confirm workflow save');
  expect(api.command).not.toHaveBeenCalled();
  await hear(command, 2);
  expect(screen.getByRole('heading', { name: 'Review the note before saving' })).toBeInTheDocument();
  expect(screen.getByLabelText('Local result')).toHaveTextContent('Found invoice in the document.');
  expect(api.command).toHaveBeenCalledTimes(1);
  expect(api.voice_speak).toHaveBeenLastCalledWith(expect.objectContaining({ text: message }));
  await hear('confirm workflow save', 3);
  expect(api.command).toHaveBeenLastCalledWith(expect.objectContaining({ text: 'confirm workflow save' }));
  expect(screen.getByRole('heading', { name: 'Note saved and verified' })).toBeInTheDocument();
});

test('background wake holds a full résumé request until the user grants access and uses it', async () => {
  jest.useFakeTimers();
  const wake = { wake_enabled: true, wake_armed: true };
  const path = 'F:\\Workspace\\Resume\\Resume.docx';
  const command = 'make a new folder in F drive and make a resume for me in it';
  api.status.mockResolvedValue({ ...inactive, ...wake });
  api.wake_set = jest.fn();
  api.suspend_actions = jest.fn();
  api.voice_poll = jest.fn(async () => ({ active: true, voice_id: 3, events: [] }));
  api.voice_poll.mockResolvedValueOnce({ active: true, voice_id: 3, events: [{ id: 1, kind: 'wake_request', text: command }] });
  api.choose_workspace.mockResolvedValue({ ...active, ...wake, workspace: 'F:\\Workspace' });
  api.command.mockImplementation(async request => ({
    request_id: request.request_id,
    operation: 'resume_workflow',
    state: request.text === command ? 'resume_details' : request.text === 'confirm resume save' ? 'succeeded' : 'resume_review',
    message: request.text === command ? 'Say resume name followed by your name.' : 'Review your résumé.',
    result: { path, ...(request.text === 'resume details Built Windows applications' ? { text: 'Jane Doe\nBuilt Windows applications' } : {}) },
  }));
  render(<NativeDesktop />);
  await act(async () => {});
  await act(async () => jest.advanceTimersByTime(700));
  expect(screen.getByRole('heading', { name: 'I heard your request' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Use heard request' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Choose folder & enable' }));
  await act(async () => {});
  expect(api.command).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Use heard request' }));
  await act(async () => {});
  expect(api.command).toHaveBeenLastCalledWith(expect.objectContaining({ text: command }));
  expect(screen.getByRole('heading', { name: 'Add your résumé details' })).toBeInTheDocument();
  expect(screen.getByLabelText('Local result')).toHaveTextContent(path);
  await hear('resume details Built Windows applications', 2);
  expect(screen.getByRole('heading', { name: 'Review your résumé before saving' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Polish with Gemini' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Save Word file' }));
  await act(async () => {});
  expect(api.command).toHaveBeenLastCalledWith(expect.objectContaining({ text: 'confirm resume save' }));
  expect(screen.getByRole('heading', { name: 'Résumé saved and verified' })).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});
