import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import DesktopControls from '../src/components/DesktopControls';

jest.mock('../src/services/firebase', () => ({ auth: { currentUser: { getIdToken: jest.fn(async () => 'test-token') } } }));

beforeEach(() => { global.fetch = jest.fn(); });

test('private controls require verified presence', () => {
  render(<DesktopControls sessionId="session" allowed={false} />);
  fireEvent.click(screen.getByText('Computer'));
  expect(screen.getByText(/verify your presence/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Pairing code')).not.toBeInTheDocument();
});

test('pairing stays in memory and guest transition stops agent and clears file contents', async () => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ device_secret: 's'.repeat(40), workspace: 'test-workspace' }) });
  const view = render(<DesktopControls sessionId="session" allowed={true} />);
  fireEvent.click(screen.getByText('Computer'));
  fireEvent.change(screen.getByLabelText('Pairing code'), { target: { value: 'p'.repeat(32) } });
  fireEvent.click(screen.getByText('Connect', { exact: true }));
  await screen.findByText('Selected folder: test-workspace');
  fireEvent.change(screen.getByLabelText('Note'), { target: { value: 'private note' } });
  view.rerender(<DesktopControls sessionId="session" allowed={false} />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8765/stop', expect.anything()));
  expect(screen.queryByText('Selected folder: test-workspace')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('private note')).not.toBeInTheDocument();
});

test('late pairing cannot restore private controls after revocation', async () => {
  let resolve;
  global.fetch.mockImplementation(() => new Promise(r => { resolve = r; }));
  const view = render(<DesktopControls sessionId="session" allowed={true} />);
  fireEvent.click(screen.getByText('Computer'));
  fireEvent.change(screen.getByLabelText('Pairing code'), { target: { value: 'p'.repeat(32) } });
  fireEvent.click(screen.getByText('Connect', { exact: true }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  view.rerender(<DesktopControls sessionId="session" allowed={false} />);
  resolve({ ok: true, json: async () => ({ device_secret: 's'.repeat(40), workspace: 'private-workspace' }) });
  await waitFor(() => expect(screen.getByText(/verify your presence/)).toBeInTheDocument());
  expect(screen.queryByText(/private-workspace/)).not.toBeInTheDocument();
});

async function connect() {
  render(<DesktopControls sessionId="session" allowed={true} />);
  fireEvent.click(screen.getByText('Computer'));
  fireEvent.change(screen.getByLabelText('Pairing code'), { target: { value: 'p'.repeat(32) } });
  fireEvent.click(screen.getByText('Connect', { exact: true }));
  await screen.findByText('Selected folder: test-workspace');
}

test('file controls send scoped requests and render returned contents as text', async () => {
  global.fetch.mockImplementation(async (url, options) => {
    if (url.endsWith('/pair')) return { ok: true, json: async () => ({ device_secret: 's'.repeat(40), workspace: 'test-workspace' }) };
    if (url.endsWith('/stop')) return { ok: true };
    const request = JSON.parse(options.body);
    return { ok: true, json: async () => ({ request_id: request.request_id, state: 'succeeded', result: { text: '<script>private fixture</script>' } }) };
  });
  await connect();
  fireEvent.change(screen.getByLabelText('Filename'), { target: { value: 'test.txt' } });
  fireEvent.click(screen.getByText('Read file'));
  await screen.findByText('<script>private fixture</script>');
  const [url, options] = global.fetch.mock.calls.find(([u]) => u.endsWith('/execute'));
  expect(url).toBe('http://127.0.0.1:8765/execute');
  expect(JSON.parse(options.body)).toMatchObject({ session_id: 'session', action: { operation: 'read_text', name: 'test.txt' } });
  expect(options.headers['X-Rumi-Device']).toBe('s'.repeat(40));
  expect(document.querySelector('script')).toBeNull();
  expect(screen.queryByText('File created and its contents verified.')).not.toBeInTheDocument();
});

test('stop discards a late file response and clears the filename', async () => {
  let finish;
  global.fetch.mockImplementation(async (url, options) => {
    if (url.endsWith('/pair')) return { ok: true, json: async () => ({ device_secret: 's'.repeat(40), workspace: 'test-workspace' }) };
    if (url.endsWith('/stop')) return { ok: true };
    const request = JSON.parse(options.body);
    return new Promise(resolve => { finish = () => resolve({ ok: true, json: async () => ({ request_id: request.request_id, state: 'succeeded', result: { text: 'late private text' } }) }); });
  });
  await connect();
  fireEvent.change(screen.getByLabelText('Filename'), { target: { value: 'private-name.txt' } });
  fireEvent.click(screen.getByText('Read file'));
  await waitFor(() => expect(finish).toBeDefined());
  fireEvent.click(screen.getByText('Stop and disconnect'));
  await act(async () => { finish(); });
  expect(screen.queryByText('late private text')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('private-name.txt')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Pairing code')).toBeInTheDocument();
});

test.each(['guest', 'new-session'])('private results are hidden before cleanup effects on %s', async (transition) => {
  const frames = [];
  function Observe({ allowed, sessionId }) {
    React.useLayoutEffect(() => {
      if (!allowed || sessionId !== 'session') frames.push(document.body.textContent);
    }, [allowed, sessionId]);
    return <DesktopControls allowed={allowed} sessionId={sessionId} />;
  }
  global.fetch.mockImplementation(async (url, options) => {
    if (url.endsWith('/pair')) return { ok: true, json: async () => ({ device_secret: 's'.repeat(40), workspace: 'private-folder' }) };
    if (url.endsWith('/stop')) return { ok: true };
    const request = JSON.parse(options.body);
    return { ok: true, json: async () => ({ request_id: request.request_id, state: 'succeeded', result: { text: 'private file contents' } }) };
  });
  const view = render(<Observe allowed={true} sessionId="session" />);
  fireEvent.click(screen.getByText('Computer'));
  fireEvent.change(screen.getByLabelText('Pairing code'), { target: { value: 'p'.repeat(32) } });
  fireEvent.click(screen.getByText('Connect', { exact: true }));
  await screen.findByText('Selected folder: private-folder');
  fireEvent.click(screen.getByText('Read file'));
  await screen.findByText('private file contents');
  view.rerender(<Observe allowed={transition !== 'guest'} sessionId={transition === 'new-session' ? 'second' : 'session'} />);
  expect(frames).toHaveLength(1);
  expect(frames[0]).not.toContain('private file contents');
  expect(frames[0]).not.toContain('private-folder');
});
