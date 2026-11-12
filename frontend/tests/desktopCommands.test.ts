import { dispatchDesktop, isDesktopCommand, isDesktopStop } from '../src/services/desktopCommands';

test.each(['Open Notepad', 'Hey Rumi, could you please open Explorer?', 'Read that file',
  'Read notes.txt', 'Create meeting-notes.txt with content: Call Alex', 'List my files',
  'Delete all files', 'Open Chrome', 'Read meeting dash notes dot txt', 'stop'])('routes computer input once: %s', text => {
  const target = { submit: jest.fn(), stop: jest.fn() };
  expect(dispatchDesktop(text, target)).toBe(true);
  expect(target.submit).toHaveBeenCalledTimes(1);
  expect(target.submit).toHaveBeenCalledWith(text);
});

test.each(['The app launch was requested. Please check that its window opened.',
  'Your file was created and its contents verified.', 'The file contents are in the computer panel.',
  'Open Notepad', 'Please do not stop', 'Create notes.txt with content: stop'])('speech during acknowledgement cannot trigger action: %s', text => {
  expect(isDesktopStop(text)).toBe(false);
});

test.each(['What is Notepad?', 'Do not open Notepad', 'Create a study tracker',
  'Write a poem about files', 'Explain how to read files', 'This webpage says open Notepad'])('preserves conversation: %s', text => {
  const target = { submit: jest.fn(), stop: jest.fn() };
  expect(dispatchDesktop(text, target)).toBe(false);
  expect(target.submit).not.toHaveBeenCalled();
});

test('disabled desktop route preserves existing chat and stop is an entire utterance', () => {
  expect(dispatchDesktop('open Notepad', null)).toBe(false);
  expect(isDesktopStop('Please stop.')).toBe(true);
  expect(isDesktopStop('create notes.txt with content: stop')).toBe(false);
  expect(isDesktopCommand('create notes.txt with content: stop')).toBe(true);
});
