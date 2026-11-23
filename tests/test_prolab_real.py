import os
import pytest
import numpy as np

EVENT_FILE = os.environ.get('CREAPY_TEST_EVENT_EXPORT', '')
SNAPSHOTS = os.environ.get('CREAPY_TEST_SNAPSHOTS', '')


def export_readable():
    try:
        with open(EVENT_FILE, 'rb') as f:
            return bool(f.read(1)) and os.path.isdir(SNAPSHOTS)
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not export_readable(),
                                reason="set CREAPY_TEST_EVENT_EXPORT and CREAPY_TEST_SNAPSHOTS to a real export")


def test_event_export_loads_into_datasets():
    import creapy
    from creapy.misc.utils import find_images
    df, mapping = creapy.load_fixations(EVENT_FILE)
    assert mapping['normalized_xy'] and mapping['trial_col'] == 'trial'
    assert df['participant'].nunique() > 1 and df['stimulus'].nunique() >= 1
    images = find_images(SNAPSHOTS)
    stim = next(s for s in df['stimulus'].unique() if s in images)
    fix, sac = creapy.build_pair(df[df['stimulus'] == stim], images[stim], mapping)
    assert fix.width <= 2400
    assert fix.fix_x.between(0, fix.width).all() and fix.fix_y.between(0, fix.height).all()
    assert fix.time_unit == 'ms' and fix.dur_unit == 'ms' and fix.pupil_col == 'pupil'
    assert sac.n_subjects() <= fix.n_subjects() and len(sac.df) > 0
    assert sac.sac_x0.between(0, fix.width).all()
    stats = creapy.participant_table(fix, sac)
    assert stats['coefficient_K'].notna().mean() > 0.9
