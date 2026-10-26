"""
Writes docs/LIBRARY.md: the hand-written introduction below followed by an API reference generated from the
docstrings of the public library modules (python docs/make_library_reference.py). Run it after changing the
library so the reference never drifts from the code.
"""
import inspect
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # the repo root, so the script works without an installed creapy

# module -> one-line role; order = order in the document
MODULES = [
    ('creapy', "top level: loading tables, building datasets, re-exports of everything below"),
    ('creapy.gaze.base', "StimulusGaze: what FixationData and SaccadeData share (subsets, AOIs, smoothing)"),
    ('creapy.gaze.fixation', "FixationData: heatmaps, scanpaths, AOIs, descriptives, scanpath similarity"),
    ('creapy.gaze.saccade', "SaccadeData: saccade scanpaths, HeatMatch heatmaps and similarity, rose diagrams"),
    ('creapy.gaze.convert', "fixation table <-> saccade table"),
    ('creapy.aoi.aoi', "AOI geometry (rectangles, polygons, JSON records)"),
    ('creapy.aoi.sequence', "AOI sequences: scarf plot, transition matrix, first-fixation order"),
    ('creapy.stats.descriptives', "per-participant table, coefficient K, group comparison, group boxplot"),
    ('creapy.stats.timeseries', "smoothed curves of a measure over viewing time, per group"),
    ('creapy.stats.recurrence', "recurrence plots and RQA (Anderson et al. 2013), cross-recurrence"),
    ('creapy.stats.spectrum', "Lomb–Scargle periodograms and Morlet scalograms"),
    ('creapy.similarity.heatmatch_result', "pairwise similarity results: matrix, boxplot, permutation test, viewer map, overview"),
    ('creapy.similarity.scanpath', "MultiMatch, ScanMatch and cross-recurrence between two scanpaths"),
    ('creapy.formats.table', "reading CSV/TSV/Excel robustly"),
    ('creapy.formats.detect', "format detection and column-mapping guesses"),
    ('creapy.formats.tobii', "Tobii Pro Lab exports (Data, event-based metrics, AOI-based metrics)"),
    ('creapy.misc.utils', "natural sorting, image loading, time units, finding stimulus images"),
    ('creapy.misc.contours', "figure-free contour paths for heatmaps"),
    ('creapy.examples', "the synthetic example dataset"),
]

INTRO = """# The creapy library

creapy has two faces, as announced at DHd 2026: **`creapy.io`**, the desktop app for art historians and other
researchers who do not program (maximal ease of use), and **`creapy`**, the Python library underneath it (maximal
analytical depth and flexibility). Everything the app shows is a library call. The app adds only what a window
needs: file dialogs, sliders, the worker thread, project files, the session log.

This document is for the second audience: people who know some Python and want more than the app offers, say their
own figure layouts, statistics beyond the built-in tests, batch processing of many datasets, or a notebook that
documents an analysis. `tutorial.ipynb` in the repository walks through the same material on the example dataset;
`demo_similarity.ipynb` covers the similarity workflow in depth.

## Install

```bash
pip install creapy          # once on PyPI (planned with the public release); until then:
pip install "creapy @ git+https://github.com/xysLong/creapy.git"
pip install "creapy[gui]"   # adds PySide6 for the desktop app
```

The library needs no Qt: numpy, pandas, scipy, matplotlib, shapely, scikit-learn, Pillow, openpyxl and
[heatmatch](https://pypi.org/project/heatmatch/) (PyPI). Python 3.10 or newer.

## Design rules (what "flexible" means here)

- **Every plot takes a matplotlib `ax`** (or creates one when `ax=None`) and returns what it drew or computed:
  the heatmap array, the matrix, the curves. Compose your own figures with `plt.subplots`.
- **Every table is a pandas DataFrame** with plain column names: `participant_table`, `aoi_metrics`,
  `participant_rqa`, `participant_periodogram`, `score_overview`, `group_comparison` ... Feed them to seaborn,
  statsmodels, pingouin, R via `to_csv`.
- **Datasets are per stimulus**: a `FixationData` and a `SaccadeData` (one derived from the other). `.subset(
  subjects=..., t_range=...)` returns a new dataset for a participant selection or time window in seconds; the GUI's
  Show bar is nothing else.
- **Groups are a dict** `participant -> group name`. Pass it to `matshow`, `show_boxplot`, `permutation_test`,
  `group_comparison`, `show_group_boxplot`, `split_by_group`.
- **Coordinates are image pixels, y down**; times in seconds relative to the trial start; durations in the unit of
  the table (`fix.dur_unit`). Participants are weighted equally in every aggregate (`weights_simple`).
- **Slow computations are cached on the dataset** (heatmaps per bandwidth, orientation fields per sigma,
  similarity results per parameter set) and accept `progress` / `verbose` where they take long.

## Quickstart

```python
import creapy, matplotlib.pyplot as plt

df, mapping = creapy.load_fixations("fixation_report.csv")      # EyeLink report, Tobii export or any table
datasets = creapy.datasets_by_stimulus(df, mapping)             # {stimulus -> (FixationData, SaccadeData)}
fix, sac = datasets["painting.png"]
grouping = {p: ("expert" if p.startswith("E") else "novice") for p in fix.subjects}

fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 5))
fix.make_heatmap(ax0, bw_method=0.1, cmap="inferno")
fix.subset(t_range=(0, 3)).visualize_scanpath(ax1, subjects=fix.subjects[:3])

df_stats = creapy.participant_table(fix, sac)                   # one row per participant, incl. coefficient K
print(creapy.group_comparison(df_stats, grouping))
creapy.show_group_boxplot(df_stats, "coefficient_K", grouping)
creapy.show_measure_curve(fix, sac, "fixation_duration", sigma=2)   # the Time Series view
mm = fix.compute_scanpath_similarity("multimatch")
print(mm.score_overview(grouping)); mm.permutation_test(grouping)
```

## What the app shows, as library calls

| View in creapy.io | Library |
|---|---|
| Fixation Heatmap | `fix.make_heatmap(ax, bw_method, cmap, ...)`; shared scale: `fix.heatmap_max(...)` → `vmax` |
| Fixation Scanpath | `fix.visualize_scanpath(ax, subjects=...)` |
| Saccade Scanpath | `sac.visualize_scanpaths(ax, ...)` |
| Saccade Heatmap | `sac.make_heatmap(ax, sigma, orientation, ...)` (HeatMatch) |
| Saccade Directions | `sac.make_rose_plot(ax=polar_ax, ...)`, `sac.get_circular_weighted_stats()` |
| Areas of Interest | `creapy.AOI.rectangle/polygon`, `fix.set_top_down_aoi`, `fix.set_bottom_up_aoi`, `fix.aoi_metrics()`, `creapy.show_scarf_plot`, `creapy.transition_matrix`, `creapy.first_fixation_order` |
| Time Series | `creapy.show_measure_curve(fix, sac, measure)`, `creapy.split_by_group`, `fix.make_aoi_percentage_curve`; periodogram `creapy.participant_periodogram` + `show_periodogram` + `dominant_period`; scalogram `resample_regular` + `morlet_scalogram` + `show_scalogram` |
| Saccade Similarity | `sac.compute_heatmatch_similarity(sigma)` → `.matshow / .show_boxplot / .permutation_test / .show_multidimensional_scaling`; over time: `sac.compute_heatmatch_similarity_profile(...)` → `.show_profile` |
| Scanpath Comparison | `fix.compute_scanpath_similarity("multimatch" / "scanmatch" / "cross_recurrence")` → same methods + `.score_overview / .show_score_overview` |
| Recurrence | `creapy.show_recurrence_plot`, `creapy.participant_rqa`, `creapy.cross_recurrence_table`, `creapy.show_group_boxplot` |
| Statistics | `creapy.participant_table`, `creapy.group_comparison`, `fix.aoi_metrics()`, `creapy.show_group_boxplot` |
| Show bar (participant / group / time window) | `fix.subset(subjects=..., t_range=...)`, same for `sac` |
| Compare Side by Side / Export for All Stimuli | a `for` loop over `datasets.items()` and `plt.subplots(...)` |
| Import dialog | `creapy.load_fixations(path, mapping)`, `creapy.load_saccades`, `creapy.guess_mapping`, the Tobii loaders |

## API reference

Generated from the docstrings by `docs/make_library_reference.py`; `help(obj)` in Python shows the same text.
"""


def signature(obj):
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def doc(obj):
    # one paragraph per docstring: the docstrings' line breaks would break a Markdown list item
    d = inspect.getdoc(obj)
    return " ".join(d.split()) if d else "*(no docstring)*"


def members_of(module_name):
    module = importlib.import_module(module_name)
    functions, classes = [], []
    for name, obj in vars(module).items():
        if name.startswith('_'):
            continue
        if module_name == 'creapy':
            if not (inspect.isfunction(obj) and obj.__module__ == module_name):
                continue
        elif getattr(obj, '__module__', None) != module_name:
            continue
        if inspect.isfunction(obj):
            functions.append((name, obj))
        elif inspect.isclass(obj):
            classes.append((name, obj))
    return functions, classes


def method_entries(cls):
    ls = []
    for name, member in vars(cls).items():
        if name.startswith('_'):
            continue
        if isinstance(member, (staticmethod, classmethod)):
            ls.append((name, member.__func__, "static" if isinstance(member, staticmethod) else "class"))
        elif inspect.isfunction(member):
            ls.append((name, member, ""))
    return ls


def main():
    out = [INTRO]
    for module_name, role in MODULES:
        functions, classes = members_of(module_name)
        if not functions and not classes:
            continue
        out.append(f"\n### `{module_name}`\n\n{role}\n")
        for name, cls in classes:
            out.append(f"\n#### class `{name}`\n\n{doc(cls)}\n")
            init = vars(cls).get('__init__')
            if init is not None:
                out.append(f"\n- `{name}{signature(init).replace('(self, ', '(').replace('(self)', '()')}`"
                           + (f": {doc(init)}" if inspect.getdoc(init) else ""))
            for mname, fn, kind in method_entries(cls):
                sig = signature(fn)
                if kind == "":
                    sig = sig.replace('(self, ', '(').replace('(self)', '()')
                elif kind == "class":
                    sig = sig.replace('(cls, ', '(').replace('(cls)', '()')
                out.append(f"- `.{mname}{sig}`" + (" *(static)*" if kind == "static" else "")
                           + f": {doc(fn)}")
            out.append("")
        for name, fn in functions:
            out.append(f"- `{name}{signature(fn)}`: {doc(fn)}")
    text = "\n".join(out).rstrip() + "\n"
    path = os.path.join(HERE, "LIBRARY.md")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    n_missing = text.count("*(no docstring)*")
    print(f"wrote {path} ({len(text.splitlines())} lines, {n_missing} entries without docstring)")


if __name__ == '__main__':
    main()
