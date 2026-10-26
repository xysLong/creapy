import os
import re
import numpy as np
from PIL import Image


def natural_key(value):
    """
    Sort key that orders embedded numbers numerically ('vp2' before 'vp11'); letters compare lower-case.
    """
    # 'vp2' < 'vp11': split digits out so numbers compare as numbers
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', str(value))]


def natural_sorted(values):
    """
    sorted() with natural_key, so 'vp2' comes before 'vp11'.
    """
    return sorted(values, key=natural_key)


MAX_IMAGE_SIDE = 2400  # museum snapshots arrive as 8k-pixel JPEGs (35 MB each); the GUI never needs more


def load_stimulus_image(path, max_side=MAX_IMAGE_SIDE):
    """
    Any image Pillow can open -> (uint8 RGB array, scale). Grayscale, palette, CMYK, 16-bit and RGBA all land
    here (matplotlib's imread returns 2-D arrays for grayscale PNGs and floats for PNGs, which broke
    `h, w, _ = shape`). Images longer than max_side are downscaled; `scale` (<= 1) is what the ORIGINAL
    pixel coordinates have to be multiplied by to land on the returned array. JPEGs use Pillow's draft mode,
    so an 8192 x 5464 snapshot decodes in a fraction of a second instead of ~130 MB of RAM.
    """
    with Image.open(path) as img:
        width, height = img.size
        scale = min(1., max_side / max(width, height)) if max_side else 1.
        if scale < 1.:
            target = (max(1, round(width * scale)), max(1, round(height * scale)))
            if img.format == 'JPEG':
                img.draft('RGB', target)  # decode at a reduced size (power-of-two DCT scaling)
            img = img.convert('RGB').resize(target, Image.LANCZOS)
            array = np.asarray(img)
            # draft() may land on a slightly different size than requested: use the real one
            scale_x, scale_y = array.shape[1] / width, array.shape[0] / height
            return array, (scale_x + scale_y) / 2
        return np.asarray(img.convert('RGB')), 1.


def seconds_from_table_time(t):
    """
    Convert a time column to seconds and report the unit it came in: values above 600,000 are taken as µs
    ('us'), above 600 as ms, otherwise seconds. Returns (t_in_seconds, unit). Assumes no trial lasts longer
    than 10 minutes.
    """
    # Time columns arrive in s (EyeLink reports after preprocessing), ms (raw EyeLink/Tobii) or µs (Tobii).
    # No static-viewing trial lasts 10 minutes, so values past 600 are ms and past 600,000 are µs.
    t_max = np.nanmax(t)
    if t_max > 6e5:
        return t / 1e6, 'us'
    if t_max > 600:
        return t / 1e3, 'ms'
    return t, 's'



IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.gif', '.webp')


def find_images(folder, max_depth=3):
    """
    Dict lower-case file name AND lower-case stem -> full path for every image (png, jpg, bmp, tif, gif, webp)
    under `folder`, descending at most max_depth subfolder levels and skipping hidden folders. A name found
    twice keeps the shallower hit. Tobii snapshot names therefore match with or without extension.
    """
    # {lower-case file name AND stem -> path} for every image under `folder` (subfolders included, e.g. the
    # WOQ snapshots in "Wandansichten/Raum 1"); a name that exists twice keeps the shallower hit
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
