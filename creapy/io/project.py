import json
import os
import creapy
from creapy.aoi.aoi import AOI
from creapy.misc.utils import natural_sorted


PROJECT_SUFFIX = ".creapy.json"
PROJECT_VERSION = 2
SEARCH_DEPTH = 4   # how deep relocate() looks for a missing file below the project folder


def save_project(path, state):
    """Write the project; files inside the project's folder are stored with relative paths, so the folder can move."""
    state = to_portable(state, os.path.dirname(os.path.abspath(path)))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dict(state, creapy_version=creapy.__version__, project_version=PROJECT_VERSION), f, indent=2,
                  ensure_ascii=False, default=str)


def load_project(path):
    with open(path, encoding='utf-8') as f:
        state = json.load(f)
    assert state.get('project_version', 1) <= PROJECT_VERSION, "This project file was written by a newer creapy."
    return state


def portable_path(path, project_dir):
    """A path inside project_dir as a relative posix path; anything else unchanged."""
    if not path:
        return path
    full = os.path.abspath(str(path))
    base = os.path.abspath(project_dir)
    try:
        if os.path.commonpath([full, base]) == base:
            return os.path.relpath(full, base).replace(os.sep, '/')
    except ValueError:   # different drives on Windows
        pass
    return path


def to_portable(state, project_dir):
    """Copy of a project state with every file path inside project_dir made relative (see portable_path)."""
    state = dict(state)
    for key in ('source_path', 'image_folder', 'intervals_path'):
        state[key] = portable_path(state.get(key), project_dir)
    if state.get('attributes'):
        state['attributes'] = dict(state['attributes'], path=portable_path(state['attributes'].get('path'), project_dir))
    state['stimuli'] = [dict(e, path=portable_path(e['path'], project_dir)) for e in state.get('stimuli', [])]
    state['aois'] = [dict(e, stimulus=portable_path(e['stimulus'], project_dir)) for e in state.get('aois', [])]
    state['aoi_inactive'] = {portable_path(k, project_dir): v for k, v in (state.get('aoi_inactive') or {}).items()}
    compare = state.get('compare')
    if compare and compare.get('kind') == 'stimuli':
        state['compare'] = dict(compare, items=[portable_path(p, project_dir) for p in compare['items']])
    return state


def aois_to_records(aois_by_path, sizes):
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
    """The file a project entry points to: as written, relative to the project folder, or found by name below it."""
    if not path:
        return None
    path = str(path)
    if not os.path.isabs(path):
        candidate = os.path.normpath(os.path.join(project_dir, path.replace('/', os.sep)))
        if os.path.exists(candidate):
            return candidate
    elif os.path.exists(path):
        return path
    name = os.path.basename(path.replace('\\', '/'))
    candidate = os.path.join(project_dir, name)
    if os.path.exists(candidate):
        return candidate
    return find_below(project_dir, name)


def find_below(folder, name, max_depth=SEARCH_DEPTH):
    """First file or folder called `name` (case-insensitive) below `folder`, or None."""
    if not folder or not os.path.isdir(folder):
        return None
    base_depth = folder.rstrip(os.sep).count(os.sep)
    wanted = name.lower()
    for root, dirs, files in os.walk(folder):
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for entry in sorted(dirs) + sorted(files):
            if entry.lower() == wanted:
                return os.path.join(root, entry)
    return None


def find_projects(folder, max_depth=SEARCH_DEPTH):
    """Every project file (*.creapy.json) in a bundle folder, subfolders included, in natural order."""
    found = []
    base_depth = folder.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(folder):
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        found += [os.path.join(root, f) for f in files if f.endswith(PROJECT_SUFFIX)]
    return natural_sorted(found)


def project_title(path):
    """The project's name as shown to the user: the file name without the suffix."""
    name = os.path.basename(path)
    return name[:-len(PROJECT_SUFFIX)] if name.endswith(PROJECT_SUFFIX) else name
