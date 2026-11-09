import os
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WIDTH, HEIGHT = 1600, 1200
SEED = 2026
SHIPPED = ("demo_fixations.csv", "demo_picture_A.png", "demo_picture_B.png")


def example_folder():
    """Folder holding the example files."""
    if all(os.path.exists(os.path.join(HERE, name)) for name in SHIPPED):
        return HERE
    folder = os.path.join(os.path.expanduser("~"), ".creapy", "example")
    os.makedirs(folder, exist_ok=True)
    return folder


def example_dataset():
    """Path of the example fixation CSV (demo_fixations.csv); pictures and table are generated on first call."""
    folder = example_folder()
    csv_path = os.path.join(folder, "demo_fixations.csv")
    if not os.path.exists(csv_path):
        make_example(folder)
    return csv_path


def draw_picture_a(path):
    """Paint synthetic picture A."""
    img = Image.new('RGB', (WIDTH, HEIGHT), (214, 203, 182))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, WIDTH, HEIGHT], fill=(96, 112, 84))
    d.rectangle([0, 0, WIDTH, 760], fill=(176, 196, 214))
    d.ellipse([520, 260, 860, 700], fill=(150, 72, 60))
    d.ellipse([610, 140, 770, 300], fill=(222, 186, 150))
    d.ellipse([1180, 160, 1300, 280], fill=(250, 232, 120))
    d.polygon([(1000, 760), (1250, 460), (1500, 760)], fill=(92, 84, 110))
    d.rectangle([120, 820, 420, 1120], fill=(70, 60, 50))
    img.save(path)


def draw_picture_b(path):
    """Paint synthetic picture B."""
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
    """Simulate one viewer on one picture: a list of dicts with t_start (ms), dur (ms), x, y (px) and pupil."""
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
        dur = float(np.exp(rng.normal(np.log(260 if focal else 190), 0.35)))
        dur = dur * (0.8 if k < 3 else 1.0)
        ls.append({'t_start': round(t * 1000, 1), 'dur': round(dur, 1), 'x': round(xy[0], 1), 'y': round(xy[1], 1),
                   'pupil': round(float(rng.normal(900 if focal else 850, 40)), 1)})
        t += (dur + rng.uniform(25, 60)) / 1000.
        k += 1
    return ls


def make_example(folder):
    """Write the whole example (two pictures, fixation table, README) into `folder`."""
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
