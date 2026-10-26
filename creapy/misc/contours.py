import numpy as np
import contourpy
import matplotlib.path as mpath
import matplotlib.ticker as ticker

# Filled-contour paths WITHOUT a matplotlib figure. `ax.contourf(...).get_paths()` needs a pyplot figure, which
# (a) is not safe from a worker thread and (b) costs ~50 ms per call; contourpy (matplotlib's own contouring
# engine) gives the same polygons directly. The level selection replicates ContourSet._autolev for an integer
# `levels` argument, so the default heatmap looks exactly as before (the study's sigma/colormap stimuli must
# not change). Explicit levels allow a colour scale shared across stimuli, groups and time windows.


def contour_levels(zmin, zmax, num_levels):
    """
    The level boundaries matplotlib would pick for contourf(..., levels=num_levels): MaxNLocator ticks
    trimmed to the data range. Returns a 1-D array of increasing values.
    """
    # matplotlib's choice for contourf(..., levels=num_levels): MaxNLocator(N + 1) ticks trimmed to the data range
    lev = ticker.MaxNLocator(num_levels + 1, min_n_ticks=1).tick_values(zmin, zmax)
    under = np.nonzero(lev < zmin)[0]
    i0 = under[-1] if len(under) else 0
    over = np.nonzero(lev > zmax)[0]
    i1 = over[0] + 1 if len(over) else len(lev)
    if i1 - i0 < 3:
        i0, i1 = 0, len(lev)
    return lev[i0:i1]


def filled_contour_paths(xx, yy, zz, levels):
    """
    Filled-contour polygons without a figure: one matplotlib Path per interval [levels[i], levels[i+1]] (an
    empty Path where nothing falls into the interval), like QuadContourSet.get_paths(). xx, yy, zz are the
    grid arrays, levels an increasing sequence of at least two values. Safe to call from a worker thread.
    """
    # One matplotlib Path per interval [levels[i], levels[i+1]] (possibly empty), like QuadContourSet.get_paths()
    levels = np.asarray(levels, dtype=float)
    assert len(levels) >= 2
    zz = np.asarray(zz, dtype=float)
    lowers = levels[:-1].copy()
    if zz.min() >= lowers[0]:
        lowers[0] -= 1  # include the minimum in the lowest interval (as matplotlib does)
    uppers = levels[1:]
    cg = contourpy.contour_generator(xx, yy, zz, name='mpl2014', corner_mask=True,
                                     fill_type=contourpy.FillType.OuterCode)
    paths = []
    for lower, upper in zip(lowers, uppers):
        vertices, codes = cg.filled(lower, upper)
        if len(vertices):
            paths.append(mpath.Path(np.concatenate(vertices), np.concatenate(codes)))
        else:
            paths.append(mpath.Path(np.zeros((0, 2))))
    return paths


if __name__ == '__main__':
    pass
