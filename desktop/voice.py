"""Offline Windows speech, with explicit arming and bounded in-memory events.

No audio is persisted or sent to a service. Windows System.Speech is loaded only
when the user enables voice. The injected engine seam keeps lifecycle tests offline.
"""
import ctypes
import re
import threading
import time
from pathlib import Path


def addressed(text):
    match = re.match(r"^(?:hey\s+)?(?:rumi|roomie|roomy)[,.:!]?\s+(.+)$", text.strip(), re.I)
    return match[1].strip() if match else None


class WindowsSpeech:
    def __init__(self, detected, recognized, level, completed, failed):
        import clr
        root = ctypes.create_unicode_buffer(32768)
        if not ctypes.windll.kernel32.GetWindowsDirectoryW(root, len(root)):
            raise RuntimeError("Windows speech is unavailable")
        speech = Path(root.value) / "Microsoft.NET/Framework64/v4.0.30319/WPF/System.Speech.dll"
        clr.AddReference(str(speech))
        from System import TimeSpan, Array, String
        from System.Speech.Recognition import SpeechRecognitionEngine, DictationGrammar, Grammar, GrammarBuilder, Choices, RecognizeMode
        from System.Speech.Synthesis import SpeechSynthesizer
        recognizers = [r for r in SpeechRecognitionEngine.InstalledRecognizers() if str(r.Culture.Name).startswith("en-")]
        if not recognizers:
            raise RuntimeError("Install an English Windows speech recognizer to use local voice")
        self.recognizer = SpeechRecognitionEngine(recognizers[0])
        self.language = str(recognizers[0].Culture.Name)
        self.synth = None
        self._closed = False
        self._lifecycle = threading.Lock()
        self._mode = RecognizeMode.Multiple
        try:
            self.recognizer.LoadGrammar(DictationGrammar())
            builder = GrammarBuilder()
            builder.Culture = recognizers[0].Culture
            builder.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
            builder.Append(Choices(Array[String]([
                "stop", "listen", "confirm", "cancel", "open Notepad", "open Explorer",
                "list files", "list my files", "read that file", "hello", "thank you",
                "what can you do", "help", "are you there", "next page",
                "previous page", "show workspace", "show companion"])))
            self.recognizer.LoadGrammar(Grammar(builder))
            freeform = GrammarBuilder()
            freeform.Culture = recognizers[0].Culture
            freeform.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
            freeform.AppendDictation()
            self.recognizer.LoadGrammar(Grammar(freeform))
            self.recognizer.InitialSilenceTimeout = TimeSpan.FromSeconds(0)
            self.recognizer.EndSilenceTimeout = TimeSpan.FromMilliseconds(700)
            self.recognizer.EndSilenceTimeoutAmbiguous = TimeSpan.FromMilliseconds(1200)
            self.recognizer.BabbleTimeout = TimeSpan.FromSeconds(10)
            self.recognizer.SpeechDetected += lambda sender, event: detected()
            self.recognizer.SpeechRecognized += lambda sender, event: recognized(str(event.Result.Text), float(event.Result.Confidence))
            self.recognizer.AudioLevelUpdated += lambda sender, event: level(int(event.AudioLevel))
            self.recognizer.RecognizeCompleted += lambda sender, event: failed() if event.Error is not None else None
            self.synth = SpeechSynthesizer()
            self.synth.SetOutputToDefaultAudioDevice()
            self.synth.SpeakCompleted += lambda sender, event: completed()
        except Exception:
            self.close()
            raise

    def start(self):
        with self._lifecycle:
            if self._closed:
                raise RuntimeError("Voice was stopped")
            self.recognizer.SetInputToDefaultAudioDevice()
            self.recognizer.RecognizeAsync(self._mode)

    def speak(self, text):
        self.synth.SpeakAsync(text)

    def quiet(self):
        if self.synth:
            self.synth.SpeakAsyncCancelAll()

    def close(self):
        with self._lifecycle:
            self._close()

    def _close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.recognizer.RecognizeAsyncCancel()
        except Exception:
            pass
        try:
            self.recognizer.SetInputToNull()
        except Exception:
            pass
        try:
            self.recognizer.Dispose()
        finally:
            if self.synth:
                try:
                    self.synth.SpeakAsyncCancelAll()
                finally:
                    self.synth.Dispose()


class LocalVoice:
    def __init__(self, authorize, emergency_stop, factory=WindowsSpeech, clock=time.monotonic):
        self._authorize, self._emergency_stop = authorize, emergency_stop
        self._factory, self._clock = factory, clock
        self._lock = threading.RLock()
        self._epoch = 0
        self._engine = None
        self._active = self._starting = self._speaking = False
        self._events = []
        self._sequence = 0
        self._level = 0
        self._message = "Microphone off"
        self._language = ""
        self._last_heard = self._cooldown = 0
        self._blocked_utterance = False

    def _event(self, kind, text=""):
        if len(self._events) >= 8:
            self.stop("Voice paused because the interface fell behind. Enable it again.")
            return
        self._sequence += 1
        self._events.append({"id": self._sequence, "kind": kind, "text": text})

    def start(self):
        if not self._authorize():
            return self.stop("Choose a folder before enabling voice.")
        with self._lock:
            if self._active or self._starting:
                return self.poll()
            self._epoch += 1
            token = self._epoch
            self._starting = True
            self._events.clear()
            self._message = "Starting local voice…"
        engine = None
        try:
            engine = self._factory(
                lambda: self.detected(token),
                lambda text, confidence: self.recognized(token, text, confidence),
                lambda level: self.level(token, level),
                lambda: self.completed(token),
                lambda: self.failed(token))
            with self._lock:
                if token != self._epoch or not self._authorize():
                    engine.close()
                    return self.poll()
                self._engine = engine
                self._speaking = False
                self._blocked_utterance = False
                self._cooldown = 0
                self._last_heard = self._clock()
                self._language = engine.language
                self._message = 'Listening locally. Begin with “Rumi”.'
            engine.start()
            with self._lock:
                if token == self._epoch and self._authorize():
                    self._active = True
                    self._starting = False
                elif token == self._epoch:
                    self.stop("Local permission ended. Microphone off.")
            return self.poll()
        except Exception:
            if engine and engine is not self._engine:
                engine.close()
            with self._lock:
                if token == self._epoch:
                    return self.stop("Local voice could not start. Check your microphone and installed English Windows speech support.")
            return self.poll()

    def stop(self, message="Microphone off"):
        with self._lock:
            self._epoch += 1
            engine, self._engine = self._engine, None
            self._active = self._starting = self._speaking = False
            self._level = 0
            self._events.clear()
            self._message = message
        if engine:
            # Invalidate all callbacks before releasing hardware. Never wait for
            # .NET disposal on the emergency-Stop path.
            threading.Thread(target=self._dispose, args=(engine,), daemon=True).start()
        return {"active": False, "speaking": False, "level": 0, "message": message, "events": []}

    @staticmethod
    def _dispose(engine):
        try:
            engine.close()
        except Exception:
            pass

    def detected(self, token):
        with self._lock:
            if self._active and token == self._epoch:
                self._blocked_utterance = self._speaking or self._clock() < self._cooldown

    def level(self, token, level):
        with self._lock:
            if self._active and token == self._epoch:
                self._level = max(0, min(100, level))

    def recognized(self, token, text, confidence):
        with self._lock:
            if not self._active or token != self._epoch:
                return
            if not self._authorize():
                self.stop("Local permission ended. Microphone off.")
                return
            command = addressed(text)
            if not command:
                return  # An open microphone is not authority to act on background speech.
            plain = command.rstrip(".!?").strip().lower()
            if confidence >= .55 and plain == "stop":
                self.stop()
                self._emergency_stop()
                return
            if confidence >= .65 and plain == "listen":
                self._engine.quiet()
                self._speaking = False
                self._cooldown = self._clock() + 1.0
                self._event("interrupted")
                return
            if self._speaking or self._blocked_utterance or self._clock() < self._cooldown:
                return
            self._last_heard = self._clock()
            if confidence < .72:
                self._event("unclear", "I wasn't sure what you said. Please try again.")
                return
            if len(command) > 18000:
                self._event("unclear", "That was too long for one command. Please use a shorter request.")
                return
            self._event("transcript", command)

    def completed(self, token):
        with self._lock:
            if self._active and token == self._epoch:
                self._speaking = False
                self._cooldown = self._clock() + 1.0

    def failed(self, token):
        with self._lock:
            if token == self._epoch:
                self.stop("The microphone stopped. Check the device and enable voice again.")

    def speak(self, text, voice_id):
        with self._lock:
            if voice_id != self._epoch or not self._active or not self._authorize() or not isinstance(text, str) or not 0 < len(text) <= 800:
                return {"accepted": False}
            if self._speaking:
                return {"accepted": False}  # Never build an acknowledgement backlog.
            self._speaking = True
            self._blocked_utterance = True
            self._last_heard = self._clock()
            try:
                self._engine.speak(text)
                return {"accepted": True}
            except Exception:
                self.stop("Spoken replies are unavailable. Your result is still on screen.")
                return {"accepted": False}

    def poll(self):
        with self._lock:
            if self._active:
                if not self._authorize():
                    self.stop("Local permission ended. Microphone off.")
                elif self._clock() - self._last_heard >= 120:
                    self.stop("Voice paused after two quiet minutes. Enable it when you are ready.")
            events, self._events = self._events, []
            return {"voice_id": self._epoch, "active": self._active, "starting": self._starting, "speaking": self._speaking,
                    "level": self._level, "message": self._message, "language": self._language, "events": events}

    def watch(self):
        with self._lock:
            if self._active and (not self._authorize() or self._clock() - self._last_heard >= 120):
                self.stop("Voice paused. Enable it when you are ready.")
