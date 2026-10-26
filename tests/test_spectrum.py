import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from creapy.gaze.fixation import FixationData
from creapy.stats.spectrum import (lomb_scargle, default_frequencies, participant_periodogram, mean_periodogram,
                                   dominant_period, resample_regular, morlet_scalogram, show_periodogram,
                                   show_scalogram)


def irregular_series(seed, f_hz=None, n=150):
    # fixation-like onsets (one every 0.2–0.45 s) with durations around 250 ms, optionally modulated by a sinusoid
    rng = np.random.default_rng(seed)
    t = np.cumsum(rng.uniform(0.2, 0.45, n))
    v = 250 + rng.normal(0, 30, n)
    if f_hz is not None:
        v = v + 60 * np.sin(2 * np.pi * f_hz * t)
    return t, v


def test_lomb_scargle_finds_known_rhythm():
    t, v = irregular_series(0, f_hz=0.5)
    freqs = default_frequencies(np.ptp(t))
    power = lomb_scargle(t, v, freqs)
    assert power.shape == freqs.shape and np.all(np.isfinite(power))
    assert np.all(power >= 0) and np.all(power <= 1)  # normalised: fraction of variance
    peak = freqs[np.argmax(power)]
    assert abs(peak - 0.5) < 0.05
    assert power.max() > 0.3  # the sinusoid carries most of the variance
    assert power.max() > 20 * np.median(power)


def test_lomb_scargle_white_noise_has_no_strong_peak():
    # The max/median ratio of white-noise power is ~6-12 for 200 frequencies (extreme value of chi2), so the test
    # is on the normalised power itself: no frequency explains more than a fifth of the variance
    freqs = default_frequencies(50.)
    for seed in range(5):
        t, v = irregular_series(seed)
        power = lomb_scargle(t, v, freqs)
        assert np.all(np.isfinite(power))
        assert power.max() < 0.2


def test_lomb_scargle_degenerate_input():
    freqs = default_frequencies(10.)
    assert np.all(np.isnan(lomb_scargle([0, 1, 2], [1, 2, 3], freqs)))  # fewer than 4 samples
    assert np.all(np.isnan(lomb_scargle([0, 1, 2, 3, 4], [5, 5, 5, 5, 5], freqs)))  # constant
    t, v = irregular_series(1, f_hz=0.5)
    v[::7] = np.nan
    assert np.all(np.isfinite(lomb_scargle(t, v, freqs)))  # NaNs are dropped


def test_default_frequencies():
    freqs = default_frequencies(30., n=100)
    assert len(freqs) == 100
    assert np.isclose(freqs[0], 2. / 30.) and np.isclose(freqs[-1], 2.)
    assert np.all(np.diff(freqs) > 0)
    assert np.allclose(np.diff(np.log(freqs)), np.diff(np.log(freqs))[0])  # log spacing


def test_morlet_scalogram_peaks_at_sine_frequency():
    t_new = np.arange(0, 20, 0.05)
    v_new = np.sin(2 * np.pi * 1.0 * t_new)
    freqs = np.geomspace(0.25, 4, 41)  # ten steps per octave, 1 Hz exactly on the grid
    power = morlet_scalogram(t_new, v_new, freqs)
    assert power.shape == (len(freqs), len(t_new))
    assert np.all(np.isfinite(power)) and np.all(power >= 0)
    i = int(np.argmax(power.mean(axis=1)))
    assert i == int(np.argmin(np.abs(freqs - 1.0)))


def test_resample_regular_then_scalogram():
    t, v = irregular_series(2, f_hz=0.5)
    t_new, v_new = resample_regular(t, v, step=0.05, sigma=0.3)
    assert np.allclose(np.diff(t_new), 0.05)
    assert np.all(np.isfinite(v_new))
    freqs = default_frequencies(np.ptp(t), n=60)
    power = morlet_scalogram(t_new, v_new, freqs)
    i = int(np.argmax(power.mean(axis=1)))
    assert abs(freqs[i] - 0.5) < 0.1


def test_participant_periodogram_on_fixture(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    assert fix.trial_col is not None  # the fixture has two trials for two of the participants
    df_power = participant_periodogram(fix)
    assert list(df_power.columns) == fix.subjects
    assert df_power.index.name == 'frequency_hz'
    assert np.all(np.isfinite(df_power.to_numpy())) and np.all(df_power.to_numpy() >= 0)
    m = mean_periodogram(df_power)
    assert len(m) == len(df_power) and np.all(np.isfinite(m))
    df_peaks = dominant_period(df_power)
    assert len(df_peaks) == len(fix.subjects)
    assert list(df_peaks.columns) == ['participant', 'peak_frequency_hz', 'peak_period_s', 'peak_power']
    assert np.allclose(df_peaks['peak_period_s'], 1. / df_peaks['peak_frequency_hz'])
    # another per-fixation value, own frequency grid
    freqs = default_frequencies(8., n=50)
    df_pupil = participant_periodogram(fix, values=fix.df[fix.pupil_col], freqs=freqs)
    assert df_pupil.shape == (50, len(fix.subjects))


def test_plot_helpers_run(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    df_power = participant_periodogram(fix)
    fig, (ax0, ax1) = plt.subplots(2, 1)
    show_periodogram(ax0, df_power, color='C1', label='all')
    show_periodogram(ax0, df_power, individual_alpha=0.)  # second call reuses the period axis
    t, v = irregular_series(3, f_hz=0.5)
    t_new, v_new = resample_regular(t, v)
    freqs = default_frequencies(np.ptp(t), n=40)
    mesh = show_scalogram(ax1, t_new, freqs, morlet_scalogram(t_new, v_new, freqs))
    fig.colorbar(mesh, ax=ax1)
    fig.canvas.draw()
    plt.close(fig)
