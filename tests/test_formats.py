import numpy as np
import pandas as pd
import pytest

import creapy
from creapy.formats import read_table, detect_format, guess_mapping, FIXATION_FIELDS, SACCADE_FIELDS
from creapy.formats.detect import validate_mapping
from creapy.formats.tobii import load_prolab_data_export, load_prolab_event_export, load_prolab_export
from tests.conftest import make_prolab_export, make_prolab_event_export


def test_read_table_sniffs_semicolon_and_decimal_comma(tmp_path):
    path = tmp_path / "german.csv"
    path.write_text("subject;image;x;y;t;dur\nvp1;a.png;12,5;7,25;0;200\nvp1;a.png;.;3;300;180\n", encoding='utf-8')
    df = read_table(str(path))
    assert list(df.columns) == ['subject', 'image', 'x', 'y', 't', 'dur']
    assert df['x'].dtype.kind == 'f' and df['x'].iloc[0] == 12.5
    assert np.isnan(df['x'].iloc[1])  # EyeLink '.' -> NaN


def test_read_table_tab_and_excel(tmp_path, fixation_table):
    tsv = tmp_path / "t.tsv"
    fixation_table.to_csv(tsv, sep='\t', index=False)
    xlsx = tmp_path / "t.xlsx"
    fixation_table.to_excel(xlsx, index=False)
    assert read_table(str(tsv)).shape == fixation_table.shape
    assert read_table(str(xlsx)).shape == fixation_table.shape


def test_detect_and_guess_eyelink(fixation_table):
    assert detect_format(fixation_table.columns) == 'eyelink_fixation'
    mapping = guess_mapping(fixation_table, FIXATION_FIELDS)
    assert mapping['fix_x_col'] == 'CURRENT_FIX_X'
    assert mapping['fix_t_col'] == 'CURRENT_FIX_START'
    assert mapping['stim_col'] == 'image'  # image-like values win over name hints
    assert mapping['trial_col'] == 'TRIAL_INDEX'
    assert mapping['pupil_col'] == 'CURRENT_FIX_PUPIL'
    assert validate_mapping(fixation_table, mapping, FIXATION_FIELDS) == []


def test_guess_saccade_report():
    df = pd.DataFrame({'CURRENT_SAC_START_X': [1.], 'CURRENT_SAC_START_Y': [1.], 'CURRENT_SAC_END_X': [2.],
                       'CURRENT_SAC_END_Y': [2.], 'IMAGE': ['a.png'], 'CURRENT_SAC_START_TIME': [0.],
                       'CURRENT_SAC_AMPLITUDE': [3.], 'subject': ['s1']})
    assert detect_format(df.columns) == 'eyelink_saccade'
    mapping = guess_mapping(df, SACCADE_FIELDS)
    assert mapping['sac_x0_col'] == 'CURRENT_SAC_START_X' and mapping['sac_y1_col'] == 'CURRENT_SAC_END_Y'
    assert mapping['subj_index_col'] == 'subject' and mapping['stim_col'] == 'IMAGE'


def test_validate_mapping_reports_problems(fixation_table):
    mapping = guess_mapping(fixation_table, FIXATION_FIELDS)
    mapping['fix_x_col'] = 'image'  # text column where numbers are needed
    problems = validate_mapping(fixation_table, mapping, FIXATION_FIELDS)
    assert any('no numbers' in p for p in problems)


@pytest.mark.parametrize("unit_suffix,decimal_comma,microseconds", [(True, False, False), (False, False, False),
                                                                    (True, True, False), (True, False, True)])
def test_tobii_screen_export(tmp_path, unit_suffix, decimal_comma, microseconds):
    path = make_prolab_export(str(tmp_path / "export.tsv"), unit_suffix=unit_suffix, decimal_comma=decimal_comma,
                              microseconds=microseconds)
    df_raw = read_table(path)
    assert detect_format(df_raw.columns) == 'tobii_data_export'
    df, mapping = load_prolab_data_export(path)
    assert len(df) == 6  # 2 recordings x 3 fixations, samples collapsed
    assert set(df['participant']) == {'Visitor 01', 'Visitor 02'}
    assert (df['stimulus'] == 'painting.png').all()
    assert mapping['fix_x_col'] == 'x' and mapping['subj_index_col'] == 'participant'
    # timestamps in ms regardless of the export unit; fixations 80 ms apart (5 samples + saccade)
    first = df[df['participant'] == 'Visitor 01'].sort_values('t')
    assert np.allclose(np.diff(first['t']), 80.)
    assert (df['dur'] == 50).all()
    assert set(df['condition']) == {'c1', 'c2'}


def test_tobii_snapshot_export(tmp_path):
    path = make_prolab_export(str(tmp_path / "glasses.tsv"), snapshots=True)
    df, mapping = load_prolab_data_export(path)
    assert set(df['stimulus']) == {'Wall_A', 'Wall_B'}
    assert df['snapshot_mapped'].all()
    assert len(df[df['stimulus'] == 'Wall_A']) == 4 and len(df[df['stimulus'] == 'Wall_B']) == 2


def test_tobii_metrics_export_is_refused():
    df = pd.DataFrame({'Participant': ['a'], 'TOI': ['x'], 'AOI': ['y'], 'Total_duration_of_whole_fixations': [1.]})
    assert detect_format(df.columns) == 'tobii_metrics_export'
    with pytest.raises(ValueError, match="metrics"):
        load_prolab_data_export(df)


def test_load_fixations_routes_tobii(tmp_path):
    path = make_prolab_export(str(tmp_path / "export.tsv"))
    df, mapping = creapy.load_fixations(path)
    assert mapping['fix_t_col'] == 't' and len(df) == 6


def test_tobii_event_export(tmp_path):
    path = make_prolab_event_export(str(tmp_path / "Raum 1 c1 Metrics_Event-based.tsv"))
    df_raw = read_table(path)
    assert detect_format(df_raw.columns) == 'tobii_event_export'
    df, mapping = load_prolab_export(path)
    assert mapping['normalized_xy'] is True and mapping['trial_col'] == 'trial' and mapping['pupil_col'] == 'pupil'
    assert set(df['stimulus']) == {'c1_r1_w1_a', 'c1_r1_w2_a'}
    assert len(df) == 2 * 2 * 3  # 2 participants x 2 media x 3 fixations; saccade/glance rows dropped
    assert df['x'].between(0, 1).all() and (df['dur'] > 0).all()
    assert set(df['trial']) == {1}  # interval 2 holds only a glance in the synthetic file
    # decimal commas survived
    assert np.isclose(df.loc[0, 'x'], 0.125)
    # FixationData scales to the image and treats intervals as trials
    from PIL import Image
    img = tmp_path / "c1_r1_w1_a.jpg"
    Image.new('RGB', (800, 600), (90, 90, 90)).save(img)
    import creapy
    df_w1 = df[df['stimulus'] == 'c1_r1_w1_a']
    fix, sac = creapy.build_pair(df_w1, str(img), mapping)
    assert fix.width == 800 and np.isclose(fix.fix_x.min(), 0.125 * 800)
    assert fix.time_unit == 'ms' and fix.dur_unit == 'ms'
    assert len(sac.df) == 2 * 2  # 2 participants x (3 fixations -> 2 saccades); saccades never bridge intervals


def test_tobii_data_export_drops_scene_camera_rows(tmp_path):
    # glasses export: snapshot columns present, no 'Presented Media name' -> the scene-camera fixation points
    # must not become a 'screen' stimulus
    path = make_prolab_export(str(tmp_path / "glasses.tsv"), snapshots=True, scene_camera=True)
    df, _ = load_prolab_data_export(path)
    assert set(df['stimulus']) == {'Wall_A', 'Wall_B'}
