"""
A small SYNTHETIC example dataset so the GUI and the notebooks can be tried without any participant data:
two generated pictures, twelve invented viewers in two groups ('expert' / 'layperson'), 30 s each.
The gaze is simulated from a handful of attractors per picture: it shows what the views do, nothing about people.
The files ship with the package; when they are missing they are generated into a per-user folder, never into
the installed package.
"""
import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WIDTH, HEIGHT = 1600, 1200
SEED = 2026
SHIPPED = ("demo_fixations.csv", "demo_picture_A.png", "demo_picture_B.png")


def example_folder():
    """
    Folder holding the example files: the copy shipped with the package, or, when that copy is incomplete,
    ~/.creapy/example, where they are generated. Nothing is written into the installed package.
    """
    if all(os.path.exists(os.path.join(HERE, name)) for name in SHIPPED):
        return HERE
    folder = os.path.join(os.path.expanduser("~"), ".creapy", "example")
    os.makedirs(folder, exist_ok=True)
    return folder


def example_dataset():
    """
    Path of the example fixation CSV (demo_fixations.csv); pictures and table are generated on first call.
    """
    # Returns the path of the fixation CSV, generating everything on first call
    folder = example_folder()
    csv_path = os.path.join(folder, "demo_fixations.csv")
    if not os.path.exists(csv_path):
        make_example(folder)
    return csv_path


def draw_picture_a(path):
    """
    Paint synthetic picture A (a figure left of centre, a small bright object top right, a horizon line) at
    1600 x 1200 px and save it to `path`.
    """
    # "Composition A": a large figure left of centre, a small bright object top right, a horizon line
    img = Image.new('RGB', (WIDTH, HEIGHT), (214, 203, 182))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, WIDTH, HEIGHT], fill=(96, 112, 84))
    d.rectangle([0, 0, WIDTH, 760], fill=(176, 196, 214))
    d.ellipse([520, 260, 860, 700], fill=(150, 72, 60))          # body
    d.ellipse([610, 140, 770, 300], fill=(222, 186, 150))        # head
    d.ellipse([1180, 160, 1300, 280], fill=(250, 232, 120))      # small bright object
    d.polygon([(1000, 760), (1250, 460), (1500, 760)], fill=(92, 84, 110))  # distant hill
    d.rectangle([120, 820, 420, 1120], fill=(70, 60, 50))        # dark block bottom left
    img.save(path)


def draw_picture_b(path):
    """
    Paint synthetic picture B (two figures facing each other, a diagonal, scattered detail) at 1600 x 1200 px
    and save it to `path`.
    """
    # "Composition B": two figures facing each other, a diagonal, scattered detail
    img = Image.new('RGB', (WIDTH, HEIGHT), (58, 52, 60))
    d = ImageDraw.Draw(img)
    d.polygon([(0, HEIGHT), (WIDTH, 0), (WIDTH, 220), (0, HEIGHT - 220)], fill=(110, 96, 88))
    d.ellipse([260, 380, 520, 720], fill=(190, 150, 110))
    d.ellipse([320, 250, 460, 390], fill=(230, 200, 170))
    d.ellipse([1080, 400, 1340, 740], fill=(110, 130, 180))
    d.ellipse([1140, 270, 1280, 410], fill=(230, 200, 170))
    rng = np.random.default_rng(SEED)
    for _ in range(40):
        x, y = rng.uniform(600, 1000), rng.uniform(820, 1150)
        d.ellipse([x, y, x + 24, y + 24], fill=(240, 220, 90))
    d.rectangle([700, 60, 900, 200], fill=(200, 70, 60))
    img.save(path)


def simulate_viewer(rng, attractors, weights, n_fix, focal, t_total=30.):
    """
    Simulate one viewer on one picture: a list of dicts with t_start (ms), dur (ms), x, y (px) and pupil,
    up to n_fix fixations or t_total seconds. `attractors` are (x, y, spread) tuples drawn with `weights`;
    the first three fixations stay central; focal viewers fixate longer.
    """
    # Attractors: list of (x, y, spread). focal viewers stay longer and jump less; early viewing is central.
    ls = []
    t = 0.05
    xy = np.array([WIDTH / 2, HEIGHT / 2], dtype=float)
    k = 0
    while t < t_total and k < n_fix:
        if k < 3:
            target = np.array([WIDTH / 2, HEIGHT / 2]) + rng.normal(0, 90, 2)
        else:
            idx = rng.choice(len(attractors), p=weights)
            ax, ay, spread = attractors[idx]
            target = np.array([ax, ay]) + rng.normal(0, spread, 2)
        xy = target if rng.random() > 0.3 else xy + rng.normal(0, 40, 2)
        xy = np.clip(xy, [10, 10], [WIDTH - 10, HEIGHT - 10])
        dur = float(np.exp(rng.normal(np.log(260 if focal else 190), 0.35)))  # ms, lognormal
        dur = dur * (0.8 if k < 3 else 1.0)
        ls.append({'t_start': round(t * 1000, 1), 'dur': round(dur, 1), 'x': round(xy[0], 1), 'y': round(xy[1], 1),
                   'pupil': round(float(rng.normal(900 if focal else 850, 40)), 1)})
        t += (dur + rng.uniform(25, 60)) / 1000.
        k += 1
    return ls


def make_example(folder):
    """
    Write the whole example into `folder`: demo_picture_A.png, demo_picture_B.png, demo_fixations.csv and a
    README.md. Returns the fixation DataFrame with the columns participant, group, age, trial, image,
    t_start (ms), dur (ms), x, y (px), pupil.
    """
    img_a = os.path.join(folder, "demo_picture_A.png")
    img_b = os.path.join(folder, "demo_picture_B.png")
    draw_picture_a(img_a)
    draw_picture_b(img_b)
    rng = np.random.default_rng(SEED)
    pictures = {
        'demo_picture_A.png': [(690, 220, 60), (690, 480, 110), (1240, 220, 40), (270, 970, 90), (1250, 620, 120)],
        'demo_picture_B.png': [(390, 320, 55), (1210, 340, 55), (390, 550, 90), (1210, 570, 90), (800, 980, 130),
                               (800, 130, 50)],
    }
    # experts: more weight on the compositional elements (figures' heads, the diagonal), fewer long fixations;
    # laypersons: pulled towards the bright object / scattered detail
    weights = {
        ('demo_picture_A.png', 'expert'): [0.32, 0.25, 0.08, 0.15, 0.20],
        ('demo_picture_A.png', 'layperson'): [0.25, 0.20, 0.30, 0.10, 0.15],
        ('demo_picture_B.png', 'expert'): [0.24, 0.24, 0.12, 0.12, 0.08, 0.20],
        ('demo_picture_B.png', 'layperson'): [0.18, 0.18, 0.12, 0.12, 0.30, 0.10],
    }
    ls = []
    for i in range(12):
        group = 'expert' if i < 6 else 'layperson'
        participant = f"P{i + 1:02d}"
        for trial, (picture, attractors) in enumerate(pictures.items(), start=1):
            focal = group == 'expert'
            n_fix = int(rng.integers(70, 110))
            for row in simulate_viewer(rng, attractors, weights[(picture, group)], n_fix, focal):
                row.update({'participant': participant, 'group': group, 'trial': trial, 'image': picture,
                            'age': int(25 + i * 2)})
                ls.append(row)
    df = pd.DataFrame.from_records(ls)[['participant', 'group', 'age', 'trial', 'image', 't_start', 'dur', 'x', 'y',
                                        'pupil']]
    df.to_csv(os.path.join(folder, "demo_fixations.csv"), index=False)
    with open(os.path.join(folder, "README.md"), 'w', encoding='utf-8') as f:
        f.write("# creapy example dataset (synthetic)\n\n"
                "Generated by `creapy.examples.make_example`: twelve invented viewers (six 'expert', six "
                "'layperson'), two generated pictures (1600 x 1200 px), 30 s of simulated viewing each.\n\n"
                "`demo_fixations.csv`: one row per fixation with participant, group, age, trial, image, t_start (ms), "
                "dur (ms), x, y (px), pupil (arbitrary).\n\nNo real eye-tracking data is involved.\n")
    return df


if __name__ == '__main__':
    print(example_dataset())
