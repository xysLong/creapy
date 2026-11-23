import os
import re
import numpy as np
from PIL import Image


def natural_key(value):
    """Sort key that orders embedded numbers numerically ('vp2' before 'vp11'); letters compare lower-case."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', str(value))]


def natural_sorted(values):
    """sorted() with natural_key, so 'vp2' comes before 'vp11'."""
    return sorted(values, key=natural_key)


MAX_IMAGE_SIDE = 2400


def load_stimulus_image(path, max_side=MAX_IMAGE_SIDE):
    """Any image Pillow can open -> (uint8 RGB array, scale)."""
    with Image.open(path) as img:
        width, height = img.size
        scale = min(1., max_side / max(width, height)) if max_side else 1.
        if scale < 1.:
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            if img.format == 'JPEG':
                img.draft('RGB', target)
            img = img.convert('RGB').resize(target, Image.LANCZOS)
            array = np.asarray(img)
            scale_x, scale_y = array.shape[1] / width, array.shape[0] / height
            return array, (scale_x + scale_y) / 2
        return np.asarray(img.convert('RGB')), 1.


def seconds_from_table_time(t):
    """Convert a time column to seconds and report the unit it came in: values above 600,000 are taken as µs."""
    t_max = np.nanmax(t)
    if t_max > 6e5:
        return t / 1e6, 'us'
    if t_max > 600:
        return t / 1e3, 'ms'
    return t, 's'


IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.gif', '.webp')


def find_images(folder, max_depth=3):
    """Dict lower-case file name and stem -> full path for every image in a folder, subfolders included."""
    found = {}
    base_depth = folder.rstrip(os.sep).count(os.sep)
    for root, dirs, files in os.walk(folder):
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        for name in sorted(files):
            if name.lower().endswith(IMAGE_EXTENSIONS):
                full = os.path.join(root, name)
                found.setdefault(name.lower(), full)
                found.setdefault(os.path.splitext(name)[0].lower(), full)
    return found


if __name__ == '__main__':
    pass


CONDITION_TOKEN = r'(?<![A-Za-z0-9])c\d+(?![A-Za-z0-9])'


def condition_token(name, pattern=CONDITION_TOKEN):
    """The condition token in a stimulus name ('c1_r1_w2.jpg' -> 'c1', 'Boy_c2' -> 'c2'), or None."""
    found = re.findall(pattern, os.path.splitext(os.path.basename(str(name)))[0])
    return found[0] if len(set(found)) == 1 else None


def grouping_from_stimulus_names(subj_to_names, pattern=CONDITION_TOKEN):
    """participant -> condition token read off the names of the stimuli that participant looked at.

    For museum studies whose snapshots are condition-specific (c1_..., c2_...) this derives each visitor's condition
    without a condition column. Pass one name per fixation (repetitions allowed): the most frequent token wins, so a
    stray fixation mapped onto the other condition's snapshot does not unseat it; a tie leaves the participant out.
    Returns None when fewer than two tokens occur."""
    grouping = {}
    for subj, names in subj_to_names.items():
        counts = {}
        for name in names:
            token = condition_token(name, pattern)
            if token is not None:
                counts[token] = counts.get(token, 0) + 1
        if not counts:
            continue
        best = max(counts.values())
        winners = [token for token, n in counts.items() if n == best]
        if len(winners) == 1:
            grouping[subj] = winners[0]
    return grouping if len(set(grouping.values())) >= 2 else None


def grouping_from_participant_names(subjects, pattern=CONDITION_TOKEN):
    """participant -> condition token in the participant's own name ('M_c1_p01' -> 'c1'), or None."""
    grouping = {subj: condition_token(subj, pattern) for subj in subjects}
    grouping = {subj: token for subj, token in grouping.items() if token is not None}
    return grouping if len(set(grouping.values())) >= 2 else None
