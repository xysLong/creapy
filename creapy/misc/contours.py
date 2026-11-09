import numpy as np
import contourpy
import matplotlib.path as mpath
import matplotlib.ticker as ticker


def contour_levels(zmin, zmax, num_levels):
    """The level boundaries matplotlib would pick for contourf(..., levels=num_levels)."""
    lev = ticker.MaxNLocator(num_levels + 1, min_n_ticks=1).tick_values(zmin, zmax)
    under = np.nonzero(lev < zmin)[0]
    i0 = under[-1] if len(under) else 0
    over = np.nonzero(lev > zmax)[0]
    i1 = over[0] + 1 if len(over) else len(lev)
    if i1 - i0 < 3:
        i0, i1 = 0, len(lev)
    return lev[i0:i1]


def filled_contour_paths(xx, yy, zz, levels):
    """Filled-contour polygons without a figure: one matplotlib Path per interval [levels[i], levels[i+1]]."""
    levels = np.asarray(levels, dtype=float)
    assert len(levels) >= 2
    zz = np.asarray(zz, dtype=float)
    lowers = levels[:-1].copy()
    if zz.min() >= lowers[0]:
        lowers[0] -= 1
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
