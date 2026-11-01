"""Background music sits 18 dB or more under the narration."""
import numpy as np

from reelkit.audio import mix_music


def _rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)


def test_music_sits_at_least_18_db_under_the_voice_while_it_speaks():
    sr = 8000
    rng = np.random.default_rng(0)
    voice = np.zeros(9 * sr, np.float32)
    voice[int(0.5 * sr):3 * sr] = 0.3 * rng.standard_normal(int(2.5 * sr))
    voice[4 * sr:6 * sr] = 0.3 * rng.standard_normal(2 * sr)
    t = np.arange(9 * sr) / sr
    music = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

    result = mix_music(voice, music, sr, under_db=19.0)

    speaking = voice != 0
    gap = _rms_db(voice[speaking]) - _rms_db(result.music[speaking])
    assert 18.0 <= gap <= 21.0
    np.testing.assert_allclose(result.mix, voice + result.music, atol=1e-6)
