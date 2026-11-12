import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import DesktopPreview from '../src/components/desktop/DesktopPreview';
import { previewReducer, previewTask } from '../src/services/desktopPreview';

beforeAll(() => {
  window.scrollTo = jest.fn();
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
});
beforeEach(() => {
  jest.useFakeTimers();
  localStorage.clear();
  global.fetch = jest.fn(() => { throw new Error('Preview must not use network APIs'); });
});
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
const send = text => {
  fireEvent.change(screen.getByLabelText('Ask Rumi'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: 'Send command' }));
};
const advance = () => act(() => jest.advanceTimersByTime(1400));

test('Stop cancels the running task, rejects stale completion, and never dispatches computer actions', () => {
  render(<DesktopPreview />);
  send('Open Chrome and Gmail');
  advance();
  fireEvent.click(screen.getByRole('button', { name: 'Stop rehearsal' }));
  act(() => jest.advanceTimersByTime(20000));
  expect(screen.getByText('Rehearsal stopped. No computer actions were performed.')).toBeInTheDocument();
  expect(screen.queryByText('REHEARSED')).not.toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('completed browser rehearsal is explicitly a simulation and recorded once', () => {
  render(<DesktopPreview />);
  send('Open Chrome and Gmail'); advance(); advance(); advance();
  expect(screen.getByText(/Browser workflow rehearsed. No browser was opened/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Activity' }));
  expect(screen.getAllByRole('heading', { name: 'Open Chrome & Gmail' })).toHaveLength(1);
  expect(screen.getByText('Rehearsed')).toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('a second command is not queued and stale timer events cannot alter a newer task', () => {
  const task = previewTask('open gmail');
  const first = previewReducer(null, { type: 'start', id: 1, task });
  expect(previewReducer(first, { type: 'start', id: 2, task })).toBe(first);
  const stopped = previewReducer(first, { type: 'stop' });
  const next = previewReducer(stopped, { type: 'start', id: 2, task });
  expect(previewReducer(next, { type: 'advance', id: 1 })).toBe(next);
  render(<DesktopPreview />);
  send('open gmail'); send('organize sample files');
  expect(screen.getByRole('status')).toHaveTextContent('One task at a time');
  expect(screen.getByRole('heading', { name: 'Open Chrome & Gmail' })).toBeInTheDocument();
});

test('unknown commands clarify; shutdown preview has no execution control', () => {
  render(<DesktopPreview />);
  send('delete my downloads');
  expect(screen.getByText(/Nothing was sent to AI/)).toBeInTheDocument();
  send('shut down my laptop');
  expect(screen.getByText('Shutdown is unavailable in this preview.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Keep working' }));
  expect(screen.getByRole('status')).toHaveTextContent('Your computer is still on');
  expect(screen.queryByRole('heading', { name: 'Shut down your computer' })).not.toBeInTheDocument();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('theme changes and undo work locally; only appearance preferences are persisted', () => {
  const { container } = render(<DesktopPreview />);
  send('switch to light mode');
  expect(container.firstChild).toHaveAttribute('data-theme', 'light');
  fireEvent.click(screen.getByRole('button', { name: 'Undo theme change' }));
  expect(container.firstChild).toHaveAttribute('data-theme', 'dark');
  send('write a welcome note');
  fireEvent.change(screen.getByLabelText('Edit welcome note'), { target: { value: 'private edited note' } });
  expect(localStorage.length).toBe(1);
  expect(localStorage.getItem(localStorage.key(0))).not.toContain('private');
  expect(global.fetch).not.toHaveBeenCalled();
});

test('voice rehearsal uses a sample transcript without requesting a microphone or AI', () => {
  const getUserMedia = jest.fn();
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
  render(<DesktopPreview />);
  fireEvent.click(screen.getByRole('button', { name: /Preview voice interaction/ }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText(/Your microphone is off/)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole('button', { name: 'Use sample transcript' }));
  expect(screen.getByRole('heading', { name: 'Open Chrome & Gmail' })).toBeInTheDocument();
  expect(getUserMedia).not.toHaveBeenCalled();
  expect(global.fetch).not.toHaveBeenCalled();
});

test('command shortcut and companion retain cancellation controls', () => {
  render(<DesktopPreview />);
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  expect(screen.getByLabelText('Quick command')).toHaveFocus();
  fireEvent.change(screen.getByLabelText('Quick command'), { target: { value: 'organize sample files' } });
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Send command' }));
  fireEvent.click(screen.getByRole('button', { name: 'Switch to compact companion' }));
  const companion = screen.getByRole('region', { name: 'Compact Rumi companion' });
  fireEvent.click(within(companion).getByRole('button', { name: 'Move companion to another corner' }));
  fireEvent.keyDown(window, { key: '>', code: 'Period', ctrlKey: true, shiftKey: true });
  expect(within(companion).getByRole('button', { name: 'Stop', exact: true })).toBeDisabled();
  expect(within(companion).getByRole('status')).toHaveTextContent('stopped');
});

test('hiding the page stops a rehearsal and appearance remains usable with blocked storage', () => {
  jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('disabled'); });
  const { container } = render(<DesktopPreview />);
  send('open gmail');
  const hidden = jest.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  fireEvent(document, new Event('visibilitychange'));
  expect(screen.getByRole('status')).toHaveTextContent('Rehearsal stopped');
  hidden.mockRestore();
  jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('disabled'); });
  send('light mode');
  expect(container.firstChild).toHaveAttribute('data-theme', 'light');
  jest.restoreAllMocks();
});
