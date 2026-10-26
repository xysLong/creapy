import json
import os
import creapy
from creapy.aoi.aoi import AOI

# A creapy project file (.creapy.json) remembers everything the user typed in by hand: where the table and the
# images are, the column mapping, the groups, the areas of interest, the current view, so a session can be
# resumed without redoing the import dialog. It holds no gaze data: the table is re-read from its original path.

PROJECT_SUFFIX = ".creapy.json"
PROJECT_VERSION = 1


def save_project(path, state):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dict(state, creapy_version=creapy.__version__, project_version=PROJECT_VERSION), f, indent=2,
                  ensure_ascii=False, default=str)


def load_project(path):
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    assert state.get('project_version', 1) <= PROJECT_VERSION, "This project file was written by a newer creapy."
    return state


def aois_to_records(aois_by_path, sizes):
    # {stimulus path: {name: AOI}} -> JSON-able list; sizes: path -> (width, height) of the image array the AOIs
    # were drawn on, so a later session can warn when the image changed
    ls = []
    for path, aois in aois_by_path.items():
        if not aois:
            continue
        width, height = sizes.get(path, (None, None))
        ls.append({'stimulus': path, 'width': width, 'height': height, 'aois': [aoi.to_record() for aoi in aois.values()]})
    return ls


def aois_from_records(records):
    aois_by_path = {}
    for entry in records:
        aois_by_path[entry['stimulus']] = {rec['name']: AOI.from_record(rec) for rec in entry['aois']}
    return aois_by_path


def relocate(path, project_dir):
    # Files referenced by a project may have moved with it: try the stored path, then the project folder
    if path and os.path.exists(path):
        return path
    if path:
        candidate = os.path.join(project_dir, os.path.basename(path))
        if os.path.exists(candidate):
            return candidate
    return None
