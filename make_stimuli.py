#!/usr/bin/env python3
"""
Build the degraded stimuli for the PSY 3200 disambiguation experiment.

Students do NOT need to run this: the generated stimuli are already in
stimuli/twotone/ and stimuli/sws/. It is here so the stimuli are reproducible
and so you can see exactly how they were made.

Visual: two-tone ("Mooney") images
    original photo -> grayscale -> centre-crop to square -> 512x512
    -> Gaussian blur (sigma = BLUR_SIGMA px)
    -> subtract BG_WEIGHT x a heavily blurred copy (sigma = BG_SIGMA px), so
       each pixel is partly compared with its surroundings rather than with
       the whole photo; this keeps object shapes in dark or bright regions
    -> threshold at the median
    Result: ~50% black / 50% white, the same image on every presentation.

Auditory: sine-wave speech (SWS; Remez et al., 1981, Science)
    clear sentence -> track the first three formants (Praat Burg algorithm)
    -> replace each formant with one sinusoid that follows its frequency
       and amplitude -> sum the three tones.
    Result: three whistles with no harmonics, no voicing, no noise.

Requires: numpy scipy pillow praat-parselmouth soundfile
    pip install numpy scipy pillow praat-parselmouth soundfile
"""
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image
from scipy.ndimage import gaussian_filter, median_filter, uniform_filter1d
from scipy.signal import stft
import parselmouth

ROOT = Path(__file__).parent
ORIG_IMG = ROOT / "stimuli" / "images"
ORIG_SPEECH = ROOT / "stimuli" / "sounds"
OUT_IMG_ORIG = ROOT / "stimuli" / "images_clear"
OUT_IMG_2T = ROOT / "stimuli" / "twotone"
OUT_SPEECH_CLEAR = ROOT / "stimuli" / "speech_clear"
OUT_SWS = ROOT / "stimuli" / "sws"

# 12 images, matching the 12 sentences. Excluded: 11 (identifiable real
# person, and face recognition engages different processing), 13 and 15
# (iconic / near-unrecognisable even with the original). 16 kept as a spare.
IMAGE_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14]
SPEECH_IDS = list(range(1, 13))   # sentences 13-16 in the old repo were buzz tones

SIZE = 512
BLUR_SIGMA = 3.0     # fine detail kept; 6 was too hard to recognise even after the original
BG_SIGMA = 40.0      # scale of the local background
BG_WEIGHT = 0.5      # 0 = global threshold, 1 = fully local (looks like texture)

# Per-image (BLUR_SIGMA, BG_WEIGHT) overrides, tuned by eye: more blur and a
# more global threshold make an image harder; less blur and a more local
# threshold make it easier.
IMAGE_PARAMS = {
    "img06": (2.0, 0.75),   # crowd: too hard at the default
    "img10": (8.0, 0.0),    # opera tiers: too easy
    "img11": (2.0, 0.75),   # concert hall: too hard
    "img12": (6.0, 0.0),    # arch: too easy
}
SR = 22050
N_FORMANTS = 3


# ----------------------------------------------------------------- images
def square_gray(path: Path) -> Image.Image:
    im = Image.open(path).convert("L")
    s = min(im.size)
    left, top = (im.width - s) // 2, (im.height - s) // 2
    return im.crop((left, top, left + s, top + s)).resize((SIZE, SIZE), Image.LANCZOS)


def two_tone(gray: Image.Image, sigma: float = BLUR_SIGMA,
             bg_sigma: float = BG_SIGMA, bg_weight: float = BG_WEIGHT) -> Image.Image:
    g = np.asarray(gray, dtype=float)
    x = gaussian_filter(g, sigma) - bg_weight * gaussian_filter(g, bg_sigma)
    return Image.fromarray(((x > np.median(x)) * 255).astype(np.uint8))


def make_images() -> None:
    OUT_IMG_ORIG.mkdir(parents=True, exist_ok=True)
    OUT_IMG_2T.mkdir(parents=True, exist_ok=True)
    for k, img_id in enumerate(IMAGE_IDS, start=1):
        g = square_gray(ORIG_IMG / f"{img_id}.jpg")
        g.save(OUT_IMG_ORIG / f"img{k:02d}.png")
        sigma, weight = IMAGE_PARAMS.get(f"img{k:02d}", (BLUR_SIGMA, BG_WEIGHT))
        t = two_tone(g, sigma=sigma, bg_weight=weight)
        t.save(OUT_IMG_2T / f"img{k:02d}.png")
        print(f"img{k:02d}  <- images/{img_id}.jpg   white={np.asarray(t).mean()/255:.2f}")


# ----------------------------------------------------------------- speech
def sine_wave_speech(x: np.ndarray, sr: int, n_formants: int = N_FORMANTS) -> np.ndarray:
    snd = parselmouth.Sound(x, sampling_frequency=sr)
    f0 = snd.to_pitch().selected_array["frequency"]
    median_f0 = np.median(f0[f0 > 0]) if np.any(f0 > 0) else 120.0
    max_formant = 5000 if median_f0 < 160 else 5500          # male vs female ceiling

    step = 0.005
    fm = snd.to_formant_burg(time_step=step, max_number_of_formants=5,
                             maximum_formant=max_formant, window_length=0.025)
    times = np.arange(0, snd.duration, step)
    F = np.array([[fm.get_value_at_time(k + 1, t) for t in times] for k in range(n_formants)])

    # amplitude of each formant = spectral magnitude near its frequency
    f_axis, t_axis, Z = stft(x, sr, nperseg=int(0.025 * sr), noverlap=int(0.020 * sr))
    mag = np.abs(Z)
    A = np.zeros_like(F)
    for i, t in enumerate(times):
        col = mag[:, min(np.searchsorted(t_axis, t), mag.shape[1] - 1)]
        for k in range(n_formants):
            f = F[k, i]
            if np.isfinite(f):
                band = (f_axis > f - 150) & (f_axis < f + 150)
                A[k, i] = col[band].max() if band.any() else 0.0

    # gate silence: frames more than 35 dB below the loudest frame get zero amplitude
    frame_energy = np.array([mag[:, min(np.searchsorted(t_axis, t), mag.shape[1] - 1)].sum() for t in times])
    gate = 20 * np.log10(frame_energy + 1e-12) > 20 * np.log10(frame_energy.max()) - 35
    A *= gate

    # fill missing frequencies, smooth tracks
    for k in range(n_formants):
        f = F[k]
        good = np.isfinite(f)
        F[k] = np.interp(np.arange(len(f)), np.flatnonzero(good), f[good]) if good.any() else 500 * (k + 1)
        F[k] = median_filter(F[k], size=5)
        A[k] = uniform_filter1d(median_filter(A[k], size=3), size=3)

    # synthesise: one sinusoid per formant, frequency- and amplitude-modulated
    n = len(x)
    ts = np.arange(n) / sr
    y = np.zeros(n)
    for k in range(n_formants):
        f_s = np.interp(ts, times, F[k])
        a_s = np.interp(ts, times, A[k])
        y += a_s * np.sin(2 * np.pi * np.cumsum(f_s) / sr)

    ramp = int(0.01 * sr)
    y[:ramp] *= np.linspace(0, 1, ramp)
    y[-ramp:] *= np.linspace(1, 0, ramp)
    return y


def rms_normalise(y: np.ndarray, target_rms: float = 0.08) -> np.ndarray:
    y = y * (target_rms / (np.sqrt(np.mean(y ** 2)) + 1e-12))
    peak = np.abs(y).max()
    return y * (0.95 / peak) if peak > 0.95 else y


def make_speech() -> None:
    OUT_SPEECH_CLEAR.mkdir(parents=True, exist_ok=True)
    OUT_SWS.mkdir(parents=True, exist_ok=True)
    for k, sid in enumerate(SPEECH_IDS, start=1):
        x, sr = sf.read(ORIG_SPEECH / f"{sid}.mp3")
        assert sr == SR, f"{sid}.mp3 is {sr} Hz, expected {SR}"
        x = x.astype(float)
        sf.write(OUT_SPEECH_CLEAR / f"sent{k:02d}.wav", rms_normalise(x), SR)
        sf.write(OUT_SWS / f"sent{k:02d}.wav", rms_normalise(sine_wave_speech(x, SR)), SR)
        print(f"sent{k:02d}  <- sounds/{sid}.mp3   {len(x)/SR:.2f} s")


if __name__ == "__main__":
    make_images()
    make_speech()
