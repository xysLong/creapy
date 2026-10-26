import os
import sys
import numpy as np
import pandas as pd
import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def example_csv():
    from creapy.examples import example_dataset
    return example_dataset()


@pytest.fixture
def small_image(tmp_path):
    path = tmp_path / "stim.png"
    Image.new('RGB', (400, 300), (120, 130, 140)).save(path)
    return str(path)


@pytest.fixture
def gray_image(tmp_path):
    # a grayscale PNG: matplotlib's imread returns a 2-D array for these, which used to break the loader
    path = tmp_path / "gray.png"
    Image.new('L', (400, 300), 128).save(path)
    return str(path)


@pytest.fixture
def fixation_table(small_image):
    # three participants, two of them with two trials on the same image; times in ms, EyeLink-style '.' missing
    rng = np.random.default_rng(0)
    ls = []
    for subj in ['vp1', 'vp2', 'vp10']:
        for trial in ([1, 2] if subj != 'vp10' else [1]):
            t = 0.
            for k in range(25):
                dur = float(rng.integers(80, 400))
                ls.append({'RECORDING_SESSION_LABEL': subj, 'TRIAL_INDEX': trial, 'image': small_image,
                           'CURRENT_FIX_START': t, 'CURRENT_FIX_DURATION': dur,
                           'CURRENT_FIX_X': float(rng.uniform(0, 400)), 'CURRENT_FIX_Y': float(rng.uniform(0, 300)),
                           'CURRENT_FIX_PUPIL': float(rng.normal(800, 30))})
                t += dur + 40
    df = pd.DataFrame.from_records(ls)
    df.loc[3, 'CURRENT_FIX_X'] = np.nan  # one missing coordinate
    return df.sample(frac=1., random_state=1).reset_index(drop=True)  # shuffled on purpose


@pytest.fixture
def fixation_mapping():
    return {'stim_col': 'image', 'subj_index_col': 'RECORDING_SESSION_LABEL', 'fix_t_col': 'CURRENT_FIX_START',
            'fix_dur_col': 'CURRENT_FIX_DURATION', 'fix_x_col': 'CURRENT_FIX_X', 'fix_y_col': 'CURRENT_FIX_Y',
            'trial_col': 'TRIAL_INDEX', 'pupil_col': 'CURRENT_FIX_PUPIL'}


def make_prolab_export(path, snapshots=False, unit_suffix=True, decimal_comma=False, microseconds=False,
                       scene_camera=False):
    # A tiny Tobii Pro Lab Data-export look-alike: 2 recordings x 3 fixations x 5 samples each, 10 ms sampling
    ls = []
    for rec_idx, participant in enumerate(['Visitor 01', 'Visitor 02']):
        t = 100_000 * rec_idx
        event_index = 0
        for fix in range(3):
            event_index += 1
            x, y = 100 + 50 * fix + 10 * rec_idx, 80 + 30 * fix
            for sample in range(5):
                row = {'Recording timestamp': t, 'Participant name': participant,
                       'Recording name': f'Rec{rec_idx + 1}', 'Condition': 'c1' if rec_idx == 0 else 'c2',
                       'Eye movement type': 'Fixation', 'Eye movement type index': event_index,
                       'Gaze event duration': 50}
                if snapshots:
                    snap = 'Wall_A' if fix < 2 else 'Wall_B'
                    for name in ['Wall_A', 'Wall_B']:
                        hit = name == snap
                        row[f'Mapped eye movement type [{name}]'] = 'Fixation' if hit else 'Unclassified'
                        row[f'Mapped eye movement type index [{name}]'] = event_index if hit else ''
                        row[f'Mapped fixation X [{name}]'] = x if hit else ''
                        row[f'Mapped fixation Y [{name}]'] = y if hit else ''
                    if scene_camera:
                        row.update({'Fixation point X': 500 + fix, 'Fixation point Y': 400,
                                    'Recording media name': 'scenevideo.mp4'})
                else:
                    row.update({'Fixation point X': x, 'Fixation point Y': y, 'Presented Media name': 'painting.png'})
                ls.append(row)
                t += 10
            # a saccade sample between fixations
            ls.append({'Recording timestamp': t, 'Participant name': participant, 'Recording name': f'Rec{rec_idx + 1}',
                       'Condition': 'c1' if rec_idx == 0 else 'c2', 'Eye movement type': 'Saccade',
                       'Eye movement type index': event_index, 'Gaze event duration': 30})
            t += 30
    df = pd.DataFrame.from_records(ls)
    if microseconds:
        df['Recording timestamp'] = df['Recording timestamp'] * 1000
    if unit_suffix:
        ts_unit = 'µs' if microseconds else 'ms'
        df = df.rename(columns={'Recording timestamp': f'Recording timestamp [{ts_unit}]',
                                'Gaze event duration': 'Gaze event duration [ms]',
                                'Fixation point X': 'Fixation point X [MCS px]',
                                'Fixation point Y': 'Fixation point Y [MCS px]'})
    if decimal_comma:
        df.to_csv(path, sep='\t', index=False, decimal=',')
    else:
        df.to_csv(path, sep='\t', index=False)
    return path


def make_prolab_event_export(path):
    # The event-based metrics export as the WOQ files have it: Fixation/Saccade/Glance rows, normalised positions,
    # decimal commas, times restarting per interval
    ls = []
    for participant in ['WOQ_c1_p001', 'WOQ_c1_p002']:
        for media in ['c1_r1_w1_a', 'c1_r1_w2_a']:
            for interval in [1, 2]:
                t = 0
                for k in range(3 if interval == 1 else 0):
                    ls.append({'Recording': participant, 'Participant': participant, 'Condition': 'c1',
                               'TOI': media, 'Interval': interval, 'Media': media, 'Ungrouped': 'Painting',
                               'Event_type': 'Fixation', 'Validity': 'Whole', 'EventIndex': k + 1,
                               'Start': t, 'Stop': t + 200, 'Duration': 200, 'AOI': 'Boy_c1',
                               'Hit_proportion': 1.0, 'FixationPointX': 0.125 + 0.1 * k, 'FixationPointY': 0.25,
                               'Average_pupil_diameter': 3.5, 'Saccade_direction': None, 'Saccade_amplitude': None})
                    ls.append({'Recording': participant, 'Participant': participant, 'Condition': 'c1',
                               'TOI': media, 'Interval': interval, 'Media': media, 'Event_type': 'Saccade',
                               'Validity': 'Whole', 'EventIndex': k + 1, 'Start': t + 200, 'Stop': t + 240,
                               'Duration': 40, 'Saccade_direction': 90.0, 'Saccade_amplitude': 5.5})
                    t += 240
                if interval == 2:
                    # the second interval holds a glance and one fixation with an empty position -> dropped
                    ls.append({'Recording': participant, 'Participant': participant, 'Condition': 'c1',
                               'TOI': media, 'Interval': interval, 'Media': media, 'Event_type': 'Glance',
                               'Validity': 'Whole', 'EventIndex': 1, 'Start': 0, 'Stop': 900, 'Duration': 900})
    df = pd.DataFrame.from_records(ls)
    df.to_csv(path, sep='\t', index=False, decimal=',')
    return path
