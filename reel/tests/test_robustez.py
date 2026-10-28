"""Regression tests for the two resilience findings of the native review (lineage review-a520253b1e437b18)."""
import numpy as np
import pytest
import soundfile as sf

from reelkit import narration, render


class FakeNarrator:
    calls = 0

    def __init__(self, ref_wav, ref_text, model):
        pass

    def say(self, text, seed):
        FakeNarrator.calls += 1
        return np.full(24000, 0.1, np.float32), 24000

    def close(self):
        pass


class FailingTranscriber:
    def text(self, audio):
        raise MemoryError("Whisper could not load")

    def words(self, audio, prompt=""):
        return []

    def close(self):
        pass


class EchoTranscriber:
    heard = ""

    def text(self, audio):
        return EchoTranscriber.heard

    def words(self, audio, prompt=""):
        return []

    def close(self):
        pass


def test_synthesized_scenes_survive_a_failure_before_the_wer_check(tmp_path, monkeypatch):
    ref = tmp_path / "ref.wav"
    sf.write(ref, np.zeros(2400, np.float32), 24000)
    monkeypatch.setattr(narration, "Narrator", FakeNarrator)
    monkeypatch.setattr(narration, "resample", lambda audio, sr, target: audio)
    monkeypatch.setattr(narration, "trim_silence", lambda audio, sr: audio)
    frases = ["uno dos tres", "cuatro cinco seis"]

    monkeypatch.setattr(narration, "Transcriber", FailingTranscriber)
    with pytest.raises(MemoryError):
        narration.narrate(frases, ref, "ref", tmp_path / "cache", log=lambda *_: None)
    assert FakeNarrator.calls == 2

    monkeypatch.setattr(narration, "Transcriber", EchoTranscriber)
    EchoTranscriber.heard = "uno dos tres"
    scenes = narration.narrate(frases[:1], ref, "ref", tmp_path / "cache", log=lambda *_: None)
    assert FakeNarrator.calls == 2          # nothing synthesized again
    assert scenes[0].wer == 0


class DeadPipe:
    def write(self, data):
        raise BrokenPipeError

    def close(self):
        raise BrokenPipeError


class DeadFfmpeg:
    returncode = 1

    def __init__(self, cmd, stdin=None, stderr=None):
        self.cmd = cmd
        self.stdin = DeadPipe()
        self.stderr = self

    def read(self):
        return b"Unknown encoder 'libx264'"

    def wait(self):
        return 1


class TinyRenderer:
    fps = 30
    frame_count = 3

    def frame(self, t):
        return np.zeros((2, 2, 3), np.uint8)


def test_encode_reports_why_ffmpeg_failed_and_keeps_the_previous_reel(tmp_path, monkeypatch):
    out = tmp_path / "reel.mp4"
    out.write_bytes(b"previous good reel")
    monkeypatch.setattr(render.subprocess, "Popen", DeadFfmpeg)
    with pytest.raises(RuntimeError, match="Unknown encoder"):
        render.encode(TinyRenderer(), out, log=lambda *_: None)
    assert out.read_bytes() == b"previous good reel"
