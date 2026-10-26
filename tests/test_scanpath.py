import numpy as np
import pytest
from creapy.gaze.fixation import FixationData
from creapy.similarity.scanpath import scanmatch, multimatch, scanpath_of, scanpath_similarity_table, MM_MEASURES

W, H = 400, 300


def random_path(n=30, seed=0):
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.uniform(0, W, n), rng.uniform(0, H, n), rng.uniform(0.1, 0.5, n)])


def mirrored(path):
    path_ = path.copy()
    path_[:, 0] = W - path_[:, 0]
    return path_


def test_scanmatch_identical_is_one():
    p = random_path()
    assert np.isclose(scanmatch(p, p, W, H), 1.)
    assert np.isclose(scanmatch(p, p, W, H, temporal_bin=0.05), 1.)


def test_scanmatch_mirror_scores_lower():
    p = random_path()
    assert scanmatch(p, mirrored(p), W, H) < scanmatch(p, p, W, H)


def test_scanmatch_symmetric_and_bounded():
    p, q = random_path(seed=1), random_path(n=45, seed=2)
    s = scanmatch(p, q, W, H)
    assert np.isclose(s, scanmatch(q, p, W, H))
    assert 0. <= s <= 1.
    # gaps cost something: aligning with a penalty never scores higher
    assert scanmatch(p, q, W, H, gap=1.) <= s + 1e-12


def test_scanmatch_temporal_binning():
    p, q = random_path(seed=1), random_path(n=45, seed=2)
    s0 = scanmatch(p, q, W, H)
    s1 = scanmatch(p, q, W, H, temporal_bin=0.05)
    assert 0. <= s1 <= 1.
    assert not np.isclose(s0, s1)


def test_scanmatch_offimage_fixations_clipped():
    p = random_path()
    p[0, :2] = (-50, 1000)  # off the image, must land in a border cell without error
    assert 0. <= scanmatch(p, p, W, H) <= 1.


def test_multimatch_identical_is_one():
    p = random_path()
    sims = multimatch(p, p, W, H)
    assert list(sims) == MM_MEASURES
    for name in MM_MEASURES:
        assert np.isclose(sims[name], 1.), name


def test_multimatch_mirror_scores_lower():
    p = random_path()
    sims = multimatch(p, mirrored(p), W, H)
    # the alignment follows the vector differences, so even length and duration may drop below 1 here
    for name in ['vector', 'direction', 'position']:
        assert sims[name] < 1., name
    for name in MM_MEASURES:
        assert 0. <= sims[name] <= 1.


def test_multimatch_single_fixation_gives_nan():
    p, q = random_path(), random_path(n=1)
    sims = multimatch(p, q, W, H)
    assert all(np.isnan(sims[name]) for name in MM_MEASURES)
    assert all(np.isnan(v) for v in multimatch(q, p, W, H).values())


def test_multimatch_bounded_and_symmetric():
    p, q = random_path(seed=3), random_path(n=12, seed=4)
    sims, sims_ = multimatch(p, q, W, H), multimatch(q, p, W, H)
    for name in MM_MEASURES:
        assert 0. <= sims[name] <= 1.
        assert np.isclose(sims[name], sims_[name]), name


def test_similarity_table(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    assert fix.dur_unit == 'ms'
    path = scanpath_of(fix, 'vp1')
    assert path.shape == (int((fix.subj_index == 'vp1').sum()), 3)
    assert path[:, 2].max() < 1.  # seconds, not ms

    df_sm = scanpath_similarity_table(fix, method='scanmatch', verbose=False)
    assert list(df_sm) == ['subject_a', 'subject_b', 'scanmatch']
    assert len(df_sm) == 6  # 3 choose 2 + 3 diagonal
    diag = df_sm[df_sm['subject_a'] == df_sm['subject_b']]
    assert len(diag) == 3 and np.allclose(diag['scanmatch'], 1.)
    assert df_sm['scanmatch'].between(0, 1).all()

    df_mm = scanpath_similarity_table(fix, method='multimatch', verbose=False)
    assert list(df_mm) == ['subject_a', 'subject_b', 'mm_vector', 'mm_direction', 'mm_length', 'mm_position',
                           'mm_duration']
    assert len(df_mm) == 6
    diag = df_mm[df_mm['subject_a'] == df_mm['subject_b']]
    assert np.allclose(diag[[f"mm_{name}" for name in MM_MEASURES]], 1.)

    with pytest.raises(ValueError):
        scanpath_similarity_table(fix, method='levenshtein', verbose=False)
