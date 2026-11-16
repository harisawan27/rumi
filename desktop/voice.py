"""Offline Windows speech, with explicit arming and bounded in-memory events.

No audio is persisted or sent to a service. Windows System.Speech is loaded only
when the user enables voice. The injected engine seam keeps lifecycle tests offline.
"""
import ctypes
import re
import threading
import time
from pathlib import Path
from string import ascii_uppercase


def addressed(text):
    match = re.match(r"^(?:hey\s+)?(?:rumi|roomie|roomy)[,.:!]?\s+(.+)$", text.strip(), re.I)
    return match[1].strip() if match else None


def wake_word(text):
    return bool(re.match(r"^hey\s+(?:rumi|roomie|roomy)(?:[,.!:?]|\s|$)", text.strip(), re.I))


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
            wake = GrammarBuilder()
            wake.Culture = recognizers[0].Culture
            wake.Append("Hey Rumi")
            self.recognizer.LoadGrammar(Grammar(wake))
            builder = GrammarBuilder()
            builder.Culture = recognizers[0].Culture
            builder.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
            builder.Append(Choices(Array[String]([
                "stop", "listen", "confirm", "cancel", "open Notepad", "open Explorer",
                "list files", "list my files", "read that file", "hello", "thank you",
                "what can you do", "help", "are you there", "next page",
                "previous page", "show workspace", "show companion", "read result page",
                "list windows", "inspect window", "confirm window plan", "cancel window plan",
                "enable Windows control", "pause microphone", "confirm workflow save", "cancel workflow", "choose option one", "choose option two",
                "choose option three", "choose option four", "make a resume", "confirm resume save", "cancel resume",
                "use heard request", "polish resume with Gemini", "confirm Gemini draft", "cancel Gemini draft",
                "open it in Word", "open my resume in Word", "open my last resume in Word", "open my CV in Word"] + [f"focus window {word}" for word in
                ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")])))
            self.recognizer.LoadGrammar(Grammar(builder))
            for lead, endings in (
                ("find", ["in this document and save it as a note", "in this document and save what you found as a note"]),
                ("search for", ["and save the first three links"]),
            ):
                workflow = GrammarBuilder()
                workflow.Culture = recognizers[0].Culture
                workflow.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
                workflow.Append(lead)
                workflow.AppendDictation()
                workflow.Append(Choices(Array[String](endings)))
                self.recognizer.LoadGrammar(Grammar(workflow))
            resume = GrammarBuilder()
            resume.Culture = recognizers[0].Culture
            resume.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
            resume.Append(Choices(Array[String](["make new folder in", "make a new folder in"])))
            resume.Append(Choices(Array[String](list(ascii_uppercase))))
            resume.Append("drive and make a resume for me in it")
            self.recognizer.LoadGrammar(Grammar(resume))
            for lead in ("resume name", "resume details", "resume folder named"):
                field = GrammarBuilder()
                field.Culture = recognizers[0].Culture
                field.Append(Choices(Array[String](["Rumi", "Hey Rumi"])))
                field.Append(lead)
                field.AppendDictation()
                self.recognizer.LoadGrammar(Grammar(field))
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

    def on_hypothesis(self, callback):
        self.recognizer.SpeechHypothesized += lambda sender, event: callback(str(event.Result.Text), float(event.Result.Confidence))

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
    def __init__(self, authorize, emergency_stop, factory=WindowsSpeech, clock=time.monotonic,
                 background=lambda: False, on_wake=lambda: None, on_request=lambda: None):
        self._authorize, self._emergency_stop = authorize, emergency_stop
        self._background, self._on_wake = background, on_wake
        self._on_request = on_request
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
        self._hinted = False

    def _can_listen(self):
        return self._background() or self._authorize()

    def discard_events(self):
        with self._lock:
            self._events.clear()
            self._blocked_utterance = True
            if self._speaking and self._engine:
                try:
                    self._engine.quiet()
                except Exception:
                    self.stop("Microphone paused. Enable it when you are ready.")
                self._speaking = False
                self._cooldown = self._clock() + 1.0

    def _event(self, kind, text=""):
        if len(self._events) >= 8:
            if not self._background():
                self.stop("Voice paused because the interface fell behind. Enable it again.")
                return
            self._events.pop(0)
        self._sequence += 1
        self._events.append((self._clock(), {"id": self._sequence, "kind": kind, "text": text}))

    def start(self):
        if not self._can_listen():
            return self.stop("Choose a folder or enable Windows control before starting voice.")
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
            if isinstance(engine, WindowsSpeech):
                engine.on_hypothesis(lambda text, confidence: self.hypothesis(token, text, confidence))
            with self._lock:
                if token != self._epoch or not self._can_listen():
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
                if token == self._epoch and self._can_listen():
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
                self._hinted = False
                self._blocked_utterance = self._speaking or self._clock() < self._cooldown

    def hypothesis(self, token, text, confidence):
        with self._lock:
            if (self._active and token == self._epoch and confidence >= .85 and wake_word(text)
                    and not (self._hinted or self._speaking or self._blocked_utterance)
                    and self._clock() >= self._cooldown and self._can_listen()):
                self._hinted = True
                self._on_wake()
                self._event("wake")

    def level(self, token, level):
        with self._lock:
            if self._active and token == self._epoch:
                self._level = max(0, min(100, level))

    def recognized(self, token, text, confidence):
        with self._lock:
            if not self._active or token != self._epoch:
                return
            if not self._can_listen():
                self.stop("Local permission ended. Microphone off.")
                return
            command = addressed(text)
            wake = wake_word(text)
            has_access = self._authorize()
            if not has_access and not wake:
                return
            plain = (command or "").rstrip(".!?").strip().lower()
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
            if not command and not wake:
                return
            self._last_heard = self._clock()
            if confidence < .72:
                if has_access:
                    self._event("unclear", "I wasn't sure what you said. Please try again.")
                return
            if wake:
                if not self._hinted:
                    self._on_wake()
                if not command:
                    if not self._hinted:
                        self._event("wake")
                    return
            if len(command) > 18000:
                self._event("unclear", "That was too long for one command. Please use a shorter request.")
                return
            self._event("transcript" if has_access else "wake_request", command)
            if not has_access:
                self._on_request()

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
                if not self._can_listen():
                    self.stop("Local permission ended. Microphone off.")
                elif not self._background() and self._clock() - self._last_heard >= 120:
                    self.stop("Voice paused after two quiet minutes. Enable it when you are ready.")
            events, self._events = self._events, []
            now = self._clock()
            return {"voice_id": self._epoch, "active": self._active, "starting": self._starting, "speaking": self._speaking,
                    "level": self._level, "message": self._message, "language": self._language,
                    "events": [event for when, event in events if now - when < (90 if event["kind"] == "wake_request" else 8)]}

    def activity(self):
        with self._lock:
            return {"speaking": self._speaking, "level": self._level if self._active else 0}

    def watch(self):
        with self._lock:
            if self._active and (not self._can_listen() or (not self._background() and self._clock() - self._last_heard >= 120)):
                self.stop("Voice paused. Enable it when you are ready.")
