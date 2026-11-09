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
