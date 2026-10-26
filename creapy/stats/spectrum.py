import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal as sp_signal
from creapy.gaze.base import StimulusGaze

# Spectral analysis of oculomotor time series: is there a rhythm in how a viewer looks?
# One sample per fixation (fixation duration, saccade amplitude, pupil size ...) at the fixation onset,
# i.e. an IRREGULARLY sampled series -> Lomb–Scargle periodogram. For the time-resolved picture the series is
# first smoothed onto a regular grid and run through a complex Morlet wavelet (scalogram).


# --- periodogram ------------------------------------------------------------------------------------------------

def lomb_scargle(t, v, freqs):
    """
    Normalised Lomb-Scargle periodogram of an irregularly sampled series: t in seconds, v the values at those
    times, freqs in Hz. Returns the power at each frequency as the fraction of variance explained (0..1); all
    NaN with fewer than four valid samples or a constant series.
    """
    # Normalised Lomb–Scargle power at the given frequencies (Hz) of an irregularly sampled series.
    # Power is the fraction of variance explained by a sinusoid at that frequency (0..1), so curves of
    # participants with different fixation counts and value ranges are comparable.
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    assert len(t) == len(v)
    ok = np.isfinite(t) & np.isfinite(v)
    if ok.sum() < 4 or np.ptp(t[ok]) <= 0 or np.std(v[ok]) <= 0:
        return np.full(len(freqs), np.nan)
    t, v = t[ok], v[ok] - v[ok].mean()  # lombscargle assumes a zero-mean series
    # scipy wants angular frequencies; normalize=True divides by the total variance (scipy >= 1.4)
    return sp_signal.lombscargle(t, v, 2 * np.pi * freqs, normalize=True)


def default_frequencies(t_span, n=200):
    """
    Log-spaced grid of n frequencies in Hz from 2 / t_span (two cycles per viewing) up to 2 Hz, for a viewing of
    t_span seconds (must be longer than 1 s).
    """
    # Log-spaced frequency grid for a viewing of t_span seconds.
    # Lower end 2 / t_span: a rhythm must complete at least two cycles during the viewing to be called one
    # (one cycle is indistinguishable from a trend). Upper end 2 Hz: viewers make ~3 fixations/s, so the mean
    # sampling rate is ~3 Hz and the (pseudo-)Nyquist limit lies around 1.5 Hz; 2 Hz leaves some margin
    # because irregular sampling has no hard Nyquist limit. Log spacing because a period of 2 s vs 3 s matters
    # as much as 10 s vs 15 s.
    assert t_span > 1., f"Viewing time of {t_span:.2f} s is too short for a periodogram"
    f_min = 2. / t_span
    f_max = 2.
    assert f_min < f_max
    return np.geomspace(f_min, f_max, n)


def participant_periodogram(fix, values=None, freqs=None):
    """
    Lomb-Scargle periodogram per participant. values is a per-fixation series aligned with fix.df (default
    fixation duration), freqs in Hz (default default_frequencies of the median viewing span). Returns a
    DataFrame indexed by frequency_hz with one normalised-power column per participant; several trials of one
    participant are averaged.
    """
    # One Lomb–Scargle periodogram per participant; with several trials per participant (fix.trial_col) the
    # trial periodograms are averaged. values: per-fixation series aligned with fix.df (default: fixation
    # duration). Returns a DataFrame indexed by frequency_hz with one power column per participant.
    if values is None:
        values = fix.fix_dur
    values = np.asarray(values, dtype=float)
    assert len(values) == len(fix.df)
    t = fix.t.to_numpy()
    keys = [fix.subj_index_col] + ([fix.trial_col] if fix.trial_col else [])
    positions = pd.Series(np.arange(len(fix.df)), index=fix.df.index)
    if freqs is None:
        # per-viewing span, so a participant who left early does not pull the lower end up
        spans = [np.ptp(t[positions[df_.index]]) for _, df_ in fix.df.groupby(keys, sort=False)]
        freqs = default_frequencies(float(np.median(spans)))
    freqs = np.asarray(freqs, dtype=float)

    powers = {}  # subj -> list of power arrays (one per trial)
    for key, df_ in fix.df.groupby(keys, sort=False):
        subj = key[0] if isinstance(key, tuple) else key
        idx = positions[df_.index].to_numpy()
        powers.setdefault(subj, []).append(lomb_scargle(t[idx], values[idx], freqs))
    with np.errstate(invalid='ignore'):
        # all-NaN trials (too few fixations) would warn in nanmean
        df_power = pd.DataFrame({subj: np.nanmean(np.vstack(powers[subj]), axis=0)
                                 for subj in fix.subjects if subj in powers},
                                index=pd.Index(freqs, name='frequency_hz'))
    return df_power


def mean_periodogram(df_power):
    """
    Mean normalised power over the participant columns of a participant_periodogram() table, ignoring NaN;
    a Series named mean_power.
    """
    # Mean power over participants (NaN-aware)
    m = df_power.mean(axis=1, skipna=True)
    m.name = 'mean_power'
    return m


def dominant_period(df_power):
    """
    Strongest rhythm per participant from a participant_periodogram() table: DataFrame with columns participant,
    peak_frequency_hz, peak_period_s (seconds per cycle) and peak_power; all NaN when the periodogram is empty.
    """
    # The strongest rhythm per participant: peak frequency, its period (s per cycle) and the power there
    freqs = df_power.index.to_numpy(dtype=float)
    ls = []
    for subj in df_power.columns:
        power = df_power[subj].to_numpy(dtype=float)
        if np.all(~np.isfinite(power)):
            ls.append({'participant': subj, 'peak_frequency_hz': np.nan, 'peak_period_s': np.nan,
                       'peak_power': np.nan})
            continue
        i = int(np.nanargmax(power))
        ls.append({'participant': subj, 'peak_frequency_hz': float(freqs[i]),
                   'peak_period_s': float(1. / freqs[i]), 'peak_power': float(power[i])})
    return pd.DataFrame.from_records(ls)


# --- scalogram --------------------------------------------------------------------------------------------------

def resample_regular(t, v, step=0.05, sigma=0.3, weights=None):
    """
    Put an irregular series (t in seconds, v) onto a regular grid with spacing step seconds by Gaussian
    smoothing with sigma seconds (default 0.3 s, about one fixation); gaps the kernel cannot bridge are filled
    linearly. Returns (t_new, v_new). Needed before morlet_scalogram.
    """
    # Irregular (t, v) -> regular grid via the same Gaussian smoothing as the time-series curves.
    # sigma=0.3 s is about one fixation, so the curve follows the fixation-by-fixation ups and downs
    # without the step-like look of nearest-neighbour interpolation.
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    weights = np.ones(len(t)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v, weights = t[ok], v[ok], weights[ok]
    assert len(t) >= 2
    t_new = np.arange(t.min(), t.max() + step, step)
    m, _ = StimulusGaze.gaussian_smooth_irregular(t_new, t, v, weights_subj=weights, sigma=sigma)
    if np.isnan(m).any():
        # gaps wider than the kernel (blinks, lost tracking): bridge them linearly, the FFT cannot take NaN
        good = np.isfinite(m)
        m = np.interp(t_new, t_new[good], m[good])
    return t_new, m


def morlet_scalogram(t_new, v_new, freqs, w0=6.):
    """
    Wavelet power of a REGULARLY sampled series (from resample_regular) with a complex Morlet wavelet of
    parameter w0 (Torrence & Compo 1998). freqs in Hz; returns |W|^2 as an array of shape
    (len(freqs), len(t_new)), ready for show_scalogram.
    """
    # Continuous wavelet transform of a REGULARLY sampled series with a complex Morlet wavelet
    # (Torrence & Compo 1998, done in the Fourier domain: one FFT of the signal, one inverse FFT per scale).
    # scale = w0 / (2 pi f), so the wavelet's centre frequency is f. Returns |W|^2 with shape (len(freqs), len(t_new)).
    t_new = np.asarray(t_new, dtype=float)
    v = np.asarray(v_new, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    assert len(t_new) == len(v) and len(v) >= 4
    dt = float(t_new[1] - t_new[0])
    assert np.allclose(np.diff(t_new), dt), "morlet_scalogram needs a regular time grid (see resample_regular)"
    v = v - np.nanmean(v)
    v = np.where(np.isfinite(v), v, 0.)
    n = len(v)
    n_fft = int(2 ** np.ceil(np.log2(2 * n)))  # zero padding against wrap-around at the edges
    v_hat = np.fft.fft(v, n_fft)
    omega = 2 * np.pi * np.fft.fftfreq(n_fft, dt)  # angular frequencies of the FFT bins
    scales = w0 / (2 * np.pi * freqs)
    # Fourier transform of the Morlet daughter at each scale, (n_freqs, n_fft); only positive frequencies
    # (the analytic wavelet), normalised so that power is comparable across scales
    s_omega = scales[:, None] * omega[None, :]
    psi_hat = np.pi ** -0.25 * np.sqrt(2 * np.pi * scales[:, None] / dt) * np.exp(-0.5 * (s_omega - w0) ** 2)
    psi_hat[:, omega <= 0] = 0.
    coeffs = np.fft.ifft(v_hat[None, :] * np.conj(psi_hat), axis=1)[:, :n]
    return np.abs(coeffs) ** 2


# --- plotting ---------------------------------------------------------------------------------------------------

def _inverse(x):
    # 1 / x for the period axis; matplotlib probes the transform with 0, which must not warn
    with np.errstate(divide='ignore'):
        return 1. / np.asarray(x, dtype=float)


def show_periodogram(ax, df_power, freqs_or_index=None, color=None, label=None, individual_alpha=0.15):
    """
    Plot a participant_periodogram() table on ax: one thin curve per participant, the mean in bold, log
    frequency axis in Hz with the period in seconds on top. freqs_or_index overrides the table's frequency
    index; label adds a legend entry (one call per group). Returns nothing.
    """
    # Thin curves per participant, bold mean; log frequency axis with the period (s per cycle) on top
    freqs = df_power.index.to_numpy(dtype=float) if freqs_or_index is None else np.asarray(freqs_or_index, dtype=float)
    if color is None:
        color = 'C0'
    if individual_alpha > 0:
        for subj in df_power.columns:
            ax.plot(freqs, df_power[subj].to_numpy(dtype=float), color=color, alpha=individual_alpha, lw=0.8)
    ax.plot(freqs, mean_periodogram(df_power).to_numpy(dtype=float), color=color, lw=2., label=label)
    ax.set_xscale('log')
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('normalised power')
    if not getattr(ax, '_creapy_period_axis', False):
        sec = ax.secondary_xaxis('top', functions=(_inverse, _inverse))  # period = 1 / f, and back
        sec.set_xlabel('period (s per cycle)')
        ax._creapy_period_axis = True  # type: ignore
    if label is not None:
        ax.legend()


def show_scalogram(ax, t_new, freqs, power, cmap='magma'):
    """
    Time x frequency map of wavelet power on ax (pcolormesh, log frequency axis): t_new in seconds, freqs in Hz,
    power from morlet_scalogram. Returns the QuadMesh so a colorbar can be added.
    """
    # Time x frequency map of wavelet power; returns the mesh so the caller can add a colorbar
    mesh = ax.pcolormesh(np.asarray(t_new, dtype=float), np.asarray(freqs, dtype=float), np.asarray(power, dtype=float),
                         shading='auto', cmap=cmap)
    ax.set_yscale('log')
    ax.set_xlabel('viewing time (s)')
    ax.set_ylabel('frequency (Hz)')
    return mesh


if __name__ == '__main__':
    # quick smoke test: a 0.5 Hz rhythm hidden in noisy fixation durations
    rng = np.random.default_rng(0)
    t = np.cumsum(rng.uniform(0.2, 0.45, 100))
    v = 250 + 60 * np.sin(2 * np.pi * 0.5 * t) + rng.normal(0, 30, len(t))
    freqs = default_frequencies(np.ptp(t))
    df_power = pd.DataFrame({'demo': lomb_scargle(t, v, freqs)}, index=pd.Index(freqs, name='frequency_hz'))
    print(dominant_period(df_power))
    fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(6, 6))
    show_periodogram(ax0, df_power)
    t_new, v_new = resample_regular(t, v)
    show_scalogram(ax1, t_new, freqs, morlet_scalogram(t_new, v_new, freqs))
    fig.tight_layout()
    plt.show()
