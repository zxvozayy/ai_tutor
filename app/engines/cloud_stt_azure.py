# app/engines/cloud_stt_azure.py
import os, threading
from typing import Callable, Optional, Literal

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

import azure.cognitiveservices.speech as speechsdk

Mode = Literal["auto", "tr-TR", "en-US"]

class AzureSTTEngine:
    """
    Azure Speech continuous STT + (optional) Pronunciation Assessment for EN only.
    start(cb), stop(), set_mode("auto"|"tr-TR"|"en-US")
    Callback signature: cb(text: str, is_final: bool, words: list|None)
      - When PA is enabled (en-US), 'words' includes per-word scores and the
        result includes an extra property 'pa' with aggregated scores.
    """

    def __init__(self):
        key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        if not key or not region:
            raise RuntimeError("AZURE_SPEECH_KEY / AZURE_SPEECH_REGION missing in .env")

        # default mode: Auto Turkish/English recognition, no scoring
        self._mode: Mode = "auto"

        self._speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        # Punctuation / “true text”
        self._speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "TrueText"
        )

        # Audio from default microphone
        self._audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)

        # Build recognizer (language set in _apply_mode)
        self._recognizer: Optional[speechsdk.SpeechRecognizer] = None
        self._cb: Optional[Callable] = None
        self._running = False

        self._build_recognizer()  # with default mode

    # ---------------- public API ----------------
    def set_mode(self, mode: Mode):
        """Switch among 'auto', 'tr-TR', 'en-US'. Rebuilds recognizer safely."""
        if mode not in ("auto", "tr-TR", "en-US"):
            return
        self._mode = mode
        rebuild_while_running = self._running
        if rebuild_while_running:
            self.stop()
        self._build_recognizer()
        if rebuild_while_running:
            self.start(self._cb)

    def start(self, callback: Callable[[str, bool, list], None]):
        if self._running:
            return
        self._cb = callback
        self._running = True
        def _run():
            self._recognizer.start_continuous_recognition()
        threading.Thread(target=_run, daemon=True).start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        def _stop():
            self._recognizer.stop_continuous_recognition()
        threading.Thread(target=_stop, daemon=True).start()

    # ---------------- internals ----------------
    def _build_recognizer(self):
        # Create a new recognizer for current mode
        cfg = self._speech_config
        # Reset language-related properties
        # Mode → language
        if self._mode == "tr-TR":
            cfg.speech_recognition_language = "tr-TR"
            # language ID off in fixed-language mode
            cfg.set_property(speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, "None")
        elif self._mode == "en-US":
            cfg.speech_recognition_language = "en-US"
            cfg.set_property(speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, "None")
        else:  # auto detect between Turkish and English
            # Use 2-locale LID (language identification)
            cfg.set_property(speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode, "Continuous")
            lid_cfg = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(languages=["tr-TR","en-US"])

        # Build recognizer
        if self._mode == "auto":
            self._recognizer = speechsdk.SpeechRecognizer(
                speech_config=cfg,
                auto_detect_source_language_config=lid_cfg,
                audio_config=self._audio_config
            )
        else:
            self._recognizer = speechsdk.SpeechRecognizer(
                speech_config=cfg,
                audio_config=self._audio_config
            )

        # Attach events
        self._recognizer.recognizing.connect(self._on_partial)
        self._recognizer.recognized.connect(self._on_final)
        self._recognizer.canceled.connect(self._on_canceled)
        self._recognizer.session_started.connect(lambda evt: print("[AzureSTT] session started"))
        self._recognizer.session_stopped.connect(lambda evt: print("[AzureSTT] session stopped"))

        # Apply Pronunciation Assessment only in en-US mode
        if self._mode == "en-US":
            # Unscripted (no reference text), phoneme-level, 0–100 scale
            self._pa_config = speechsdk.PronunciationAssessmentConfig(
                reference_text="",  # unscripted speaking scenario
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=False,
            )
            # Prosody only available for en-US; safe to enable here.
            try:
                self._pa_config.enable_prosody_assessment()
            except Exception:
                pass
            self._pa_config.apply_to(self._recognizer)
        else:
            self._pa_config = None

    # --------------- Azure events -> unified callback ---------------
    def _on_partial(self, evt: speechsdk.SpeechRecognitionEventArgs):
        if not self._cb: return
        txt = (evt.result.text or "").strip()
        if not txt:
            return
        # Prepend a tag so UI can show live text nicely if needed
        # (We *don't* send PA on partials.)
        self._cb(txt, False, [])

    def _on_final(self, evt: speechsdk.SpeechRecognitionEventArgs):
        if not self._cb: return
        res = evt.result
        if res.reason != speechsdk.ResultReason.RecognizedSpeech:
            return

        txt = (res.text or "").strip()
        if not txt:
            return

        # If PA is active (en-US), collect scores
        words = []
        if self._pa_config is not None:
            try:
                # SDK object for overall / word-level scores
                pa = speechsdk.PronunciationAssessmentResult(res)
                # Per-word result list is available via the JSON payload
                raw_json = res.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
                # Minimal payload for UI: overall scores in a dict (attached to words)
                words = [{
                    "_pa_overall": {
                        "accuracy": pa.accuracy_score,
                        "fluency": pa.fluency_score,
                        "completeness": pa.completeness_score,
                        "prosody": getattr(pa, "prosody_score", None),
                        "pronunciation": pa.pronunciation_score
                    }
                }]
            except Exception as e:
                print("[AzureSTT] PA parse error:", e)

        self._cb(txt, True, words)

    def _on_canceled(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        print(f"[AzureSTT] canceled: reason={evt.reason} details={evt.error_details}")
