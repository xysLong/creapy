import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal as sp_signal
from creapy.gaze.base import StimulusGaze


def lomb_scargle(t, v, freqs):
    """Normalised Lomb-Scargle periodogram of an irregularly sampled series: t in seconds."""
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    assert len(t) == len(v)
    ok = np.isfinite(t) & np.isfinite(v)
    if ok.sum() < 4 or np.ptp(t[ok]) <= 0 or np.std(v[ok]) <= 0:
        return np.full(len(freqs), np.nan)
    t, v = t[ok], v[ok] - v[ok].mean()
    return sp_signal.lombscargle(t, v, 2 * np.pi * freqs, normalize=True)


def default_frequencies(t_span, n=200):
    """Log-spaced grid of n frequencies in Hz from 2 / t_span (two cycles per viewing) up to 2 Hz."""
    assert t_span > 1., f"Viewing time of {t_span:.2f} s is too short for a periodogram"
    f_min = 2. / t_span
    f_max = 2.
    assert f_min < f_max
    return np.geomspace(f_min, f_max, n)


def participant_periodogram(fix, values=None, freqs=None):
    """Lomb-Scargle periodogram per participant."""
    if values is None:
        values = fix.fix_dur
    values = np.asarray(values, dtype=float)
    assert len(values) == len(fix.df)
    t = fix.t.to_numpy()
    keys = [fix.subj_index_col] + ([fix.trial_col] if fix.trial_col else [])
    positions = pd.Series(np.arange(len(fix.df)), index=fix.df.index)
    if freqs is None:
        spans = [np.ptp(t[positions[df_.index]]) for _, df_ in fix.df.groupby(keys, sort=False)]
        freqs = default_frequencies(float(np.median(spans)))
    freqs = np.asarray(freqs, dtype=float)

    powers = {}
    for key, df_ in fix.df.groupby(keys, sort=False):
        subj = key[0] if isinstance(key, tuple) else key
        idx = positions[df_.index].to_numpy()
        powers.setdefault(subj, []).append(lomb_scargle(t[idx], values[idx], freqs))
    with np.errstate(invalid='ignore'):
        df_power = pd.DataFrame({subj: np.nanmean(np.vstack(powers[subj]), axis=0)
                                 for subj in fix.subjects if subj in powers},
                                index=pd.Index(freqs, name='frequency_hz'))
    return df_power


def mean_periodogram(df_power):
    """Mean normalised power over the participant columns of a participant_periodogram() table, ignoring NaN."""
    m = df_power.mean(axis=1, skipna=True)
    m.name = 'mean_power'
    return m


def dominant_period(df_power):
    """Strongest rhythm per participant from a participant_periodogram() table."""
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


def resample_regular(t, v, step=0.05, sigma=0.3, weights=None):
    """Put an irregular series (t in seconds, v) onto a regular grid by Gaussian smoothing."""
    t = np.asarray(t, dtype=float)
    v = np.asarray(v, dtype=float)
    weights = np.ones(len(t)) if weights is None else np.asarray(weights, dtype=float)
    ok = np.isfinite(t) & np.isfinite(v)
    t, v, weights = t[ok], v[ok], weights[ok]
    assert len(t) >= 2
    t_new = np.arange(t.min(), t.max() + step, step)
    m, _ = StimulusGaze.gaussian_smooth_irregular(t_new, t, v, weights_subj=weights, sigma=sigma)
    if np.isnan(m).any():
        good = np.isfinite(m)
        m = np.interp(t_new, t_new[good], m[good])
    return t_new, m


def morlet_scalogram(t_new, v_new, freqs, w0=6.):
    """Wavelet power of a REGULARLY sampled series (from resample_regular) with a complex Morlet wavelet."""
    t_new = np.asarray(t_new, dtype=float)
    v = np.asarray(v_new, dtype=float)
    freqs = np.asarray(freqs, dtype=float)
    assert len(t_new) == len(v) and len(v) >= 4
    dt = float(t_new[1] - t_new[0])
    assert np.allclose(np.diff(t_new), dt), "morlet_scalogram needs a regular time grid (see resample_regular)"
    v = v - np.nanmean(v)
    v = np.where(np.isfinite(v), v, 0.)
    n = len(v)
    n_fft = int(2 ** np.ceil(np.log2(2 * n)))
    v_hat = np.fft.fft(v, n_fft)
    omega = 2 * np.pi * np.fft.fftfreq(n_fft, dt)
    scales = w0 / (2 * np.pi * freqs)
    s_omega = scales[:, None] * omega[None, :]
    psi_hat = np.pi ** -0.25 * np.sqrt(2 * np.pi * scales[:, None] / dt) * np.exp(-0.5 * (s_omega - w0) ** 2)
    psi_hat[:, omega <= 0] = 0.
    coeffs = np.fft.ifft(v_hat[None, :] * np.conj(psi_hat), axis=1)[:, :n]
    return np.abs(coeffs) ** 2


def _inverse(x):
    with np.errstate(divide='ignore'):
        return 1. / np.asarray(x, dtype=float)


def show_periodogram(ax, df_power, freqs_or_index=None, color=None, label=None, individual_alpha=0.15):
    """Plot a participant_periodogram() table on ax: one thin curve per participant, the mean in bold."""
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
        sec = ax.secondary_xaxis('top', functions=(_inverse, _inverse))
        sec.set_xlabel('period (s per cycle)')
        ax._creapy_period_axis = True  # type: ignore
    if label is not None:
        ax.legend()


def show_scalogram(ax, t_new, freqs, power, cmap='magma'):
    """Time x frequency map of wavelet power on ax (pcolormesh, log frequency axis): t_new in seconds."""
    mesh = ax.pcolormesh(np.asarray(t_new, dtype=float), np.asarray(freqs, dtype=float), np.asarray(power, dtype=float),
                         shading='auto', cmap=cmap)
    ax.set_yscale('log')
    ax.set_xlabel('viewing time (s)')
    ax.set_ylabel('frequency (Hz)')
    return mesh


if __name__ == '__main__':
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
