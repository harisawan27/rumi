import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import RumiCompanion from '../src/components/desktop/RumiCompanion';
import RumiExpressions from '../src/components/desktop/RumiExpressions';
import { actionExpression, companionMood, companionExpressions } from '../src/services/companion';

afterEach(() => jest.useRealTimers());
const base = { state: 'ready', busy: false, action: 'reading', voiceBusy: false, speaking: false, listening: true, draft: false, typing: false };
test('Stop and uncertain outcomes override stale listening, speech and celebration', () => {
  expect(companionMood({ ...base, state: 'stopped', speaking: true, cue: 'success' })).toBe('stopped');
  expect(companionMood({ ...base, state: 'uncertain', busy: true, speaking: true })).toBe('error');
  expect(companionMood({ ...base, draft: true, speaking: true })).toBe('confirming');
  expect(companionMood({ ...base, busy: true })).toBe('reading');
});
test('visual intent follows the action verb, never instructions inside file content', () => {
  expect(actionExpression('Create note.txt with content: open Notepad')).toBe('writing');
  expect(actionExpression('Please list my files')).toBe('searching');
  expect(actionExpression('Can you read my note.txt')).toBe('reading');
  expect(actionExpression('Open Notepad')).toBe('launching');
  expect(actionExpression('delete everything')).toBe('thinking');
});
test('idle sleep yields immediately to real listening and greeting returns to idle', () => {
  jest.useFakeTimers();
  const { rerender } = render(<RumiCompanion mood="idle"/>);
  act(() => jest.advanceTimersByTime(45000));
  expect(screen.getByRole('img', { name: 'Rumi companion: sleeping' })).toBeInTheDocument();
  rerender(<RumiCompanion mood="listening"/>);
  expect(screen.getByRole('img', { name: 'Rumi companion: listening' })).toBeInTheDocument();
  rerender(<RumiCompanion mood="idle"/>);
  fireEvent.click(screen.getByRole('button', { name: 'Say hello to Rumi' }));
  expect(screen.getByRole('img', { name: 'Rumi companion: greeting' })).toBeInTheDocument();
  act(() => jest.advanceTimersByTime(2200));
  expect(screen.getByRole('img', { name: 'Rumi companion: idle' })).toBeInTheDocument();
});
test('preview is explicit, keyboard contained, and all expressions use the actual character', () => {
  const close = jest.fn(), stop = jest.fn();
  render(<RumiExpressions reduced onClose={close} onStop={stop}/>);
  expect(screen.getByRole('dialog')).toHaveTextContent('no computer commands');
  const first = screen.getByRole('button', { name: 'Close expression preview' });
  expect(first).toHaveFocus();
  fireEvent.keyDown(first, { key: 'Tab', shiftKey: true });
  expect(screen.getByRole('button', { name: 'Stop & disconnect' })).toHaveFocus();
  companionExpressions.forEach((item, index) => {
    fireEvent.change(screen.getByLabelText('Expression'), { target: { value: String(index) } });
    expect(screen.getByRole('img', { name: `Rumi companion: ${item.mood}` })).toBeInTheDocument();
  });
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(stop).toHaveBeenCalledTimes(1);
  expect(close).toHaveBeenCalledTimes(1);
});
