"""Real-data checks against the WOQ exports on the lab share: skipped when the share is not mounted."""
import os
import pytest
import numpy as np

SHARE = "/Volumes/crea/Kooperationen/2022-2026 MUG/2025-04_MUG_WOQ"
EVENT_FILE = f"{SHARE}/05_Tobii Pro Lab Mapping/03_Data General Paper/Raum 1 c1 Metrics_Event-based.tsv"
SNAPSHOTS = f"{SHARE}/01_Exhibition Documentation/Final_Fotos für Tobii/c1"



def share_readable():
    # os.path.exists says True on a stale network mount; only an actual read tells
    try:
        with open(EVENT_FILE, 'rb') as f:
            return bool(f.read(1))
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not share_readable(), reason="lab share not mounted")


def test_woq_event_export_loads_into_datasets():
    import creapy
    from creapy.misc.utils import find_images
    df, mapping = creapy.load_fixations(EVENT_FILE)
    assert mapping['normalized_xy'] and mapping['trial_col'] == 'trial'
    assert df['participant'].nunique() > 100 and df['stimulus'].nunique() == 8
    images = find_images(SNAPSHOTS)
    stim = 'c1_r1_w1_a'
    assert stim in images
    fix, sac = creapy.build_pair(df[df['stimulus'] == stim], images[stim], mapping)
    assert fix.width == 2400 and fix.scale < 0.3  # 8192 px snapshot downscaled
    assert fix.fix_x.between(0, fix.width).all() and fix.fix_y.between(0, fix.height).all()
    assert fix.time_unit == 'ms' and fix.dur_unit == 'ms' and fix.pupil_col == 'pupil'
    assert sac.n_subjects() <= fix.n_subjects() and len(sac.df) > 0
    assert sac.sac_x0.between(0, fix.width).all()
    stats = creapy.participant_table(fix, sac)
    assert stats['coefficient_K'].notna().mean() > 0.9
