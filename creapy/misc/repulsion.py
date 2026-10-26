import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def boxes_overlap(x10, y10, x11, y11, x20, y20, x21, y21):
    """
    True if the axis-aligned boxes (x10, y10)-(x11, y11) and (x20, y20)-(x21, y21) overlap or touch.
    """
    return not (x11 < x20 or x10 > x21 or y11 < y20 or y10 > y21)


def resolve_overlaps(df, max_iter=100, step=0.5, attenuation=0.01):
    """
    Resolve overlaps between rectangular insets by gently pushing them apart, up to max_iter rounds.
    df needs exactly the columns x, y, width, height (in that order) and a 0..n-1 index. Returns a copy
    with the columns x_original, y_original, x_repulsed, y_repulsed, width, height.
    """
    df_repulsion = df.copy(deep=True)
    for i_iter in range(max_iter):
        # draw_rectangles(df_repulsion, i_iter=i_iter)
        moved = False
        momentum = []
        for i, j in itertools.combinations(range(len(df_repulsion)), 2):
            xi, yi, wi, hi = df_repulsion.loc[i]
            xj, yj, wj, hj = df_repulsion.loc[j]
            if boxes_overlap(xi, yi, xi + wi, yi + hi, xj, yj, xj + wj, yj + hj):
                moved = True

                # Calculate overlap in x and y
                dx = min(xi + wi, xj + wj) - max(xi, xj) + 1
                dy = min(yi + hi, yj + hj) - max(yi, yj) + 1
                if dx > 0 and dy > 0:
                    delta = np.array([xi - xj, yi - yj])
                    if np.linalg.norm(delta) < 1e-5:
                        delta = np.random.rand(2) - 0.5
                    direction = delta / np.linalg.norm(delta)

                    # Push each by half the overlap plus small margin
                    shift = direction * np.array([dx, dy]) * (0.5 + step * (1 - attenuation) ** i_iter)
                    # ax.arrow(xi + 0.5 * wi, yi + 0.5 * hj, dx=shift[0], dy=shift[1])
                    momentum.extend([(i, shift), (j, -shift)])
        for idx, shift in momentum:
            df_repulsion.loc[idx, ['x', 'y']] += shift

        if not moved:
            break
    df_repulsion.insert(0, 'x_original', df['x'])
    df_repulsion.insert(1, 'y_original', df['y'])
    df_repulsion.rename(columns={'x': 'x_repulsed', 'y': 'y_repulsed'}, inplace=True)
    return df_repulsion


def draw_rectangles(df_repulsion, i_iter='final'):
    """
    Debug plot of a rectangle table (columns x, y, width, height): every rectangle labelled with its index,
    `i_iter` as the title. Shows the figure.
    """
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    for idx, row in df_repulsion.iterrows():
        x, y, w, h = row['x'], row['y'], row['width'], row['height']
        rect = patches.Rectangle((x, y), w, h, facecolor='none', edgecolor='black')
        ax.add_patch(rect)
        ax.text(x + 0.5 * w, y + 0.5 * h, idx, ha='center', va='center')
    buffer = 10  # optional buffer around rectangles
    xmin = df_repulsion['x'].min()
    xmax = (df_repulsion['x'] + df_repulsion['width']).max()
    ymin = df_repulsion['y'].min()
    ymax = (df_repulsion['y'] + df_repulsion['height']).max()
    ax.set_xlim(xmin - buffer, xmax + buffer)
    ax.set_ylim(ymin - buffer, ymax + buffer)
    ax.set_aspect('equal')
    ax.set_title(str(i_iter))
    fig.tight_layout()
    plt.show()

def draw_final_rectangles(df_repulsion):
    """
    Plot the output of resolve_overlaps: the pushed rectangles labelled with their index and a line from each
    original to its repulsed position. Shows the figure.
    """
    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    for idx, row in df_repulsion.iterrows():
        x_original, y_original, x_repulsed, y_repulsed, w, h = row
        rect = patches.Rectangle((x_repulsed, y_repulsed), w, h, facecolor='none', edgecolor='black')
        ax.add_patch(rect)
        ax.text(x_repulsed + 0.5 * w, y_repulsed + 0.5 * h, idx, ha='center', va='center')
        ax.plot([x_original, x_repulsed], [y_original, y_repulsed], color='black')
    buffer = 10  # optional buffer around rectangles
    xmin = df_repulsion['x_repulsed'].min()
    xmax = (df_repulsion['x_repulsed'] + df_repulsion['width']).max()
    ymin = df_repulsion['y_repulsed'].min()
    ymax = (df_repulsion['y_repulsed'] + df_repulsion['height']).max()
    ax.set_xlim(xmin - buffer, xmax + buffer)
    ax.set_ylim(ymin - buffer, ymax + buffer)
    ax.set_aspect('equal')
    fig.tight_layout()
    plt.show()

def generate_random_rectangles(n, x_range=(0, 100), y_range=(0, 100),
                               width_range=(1, 20), height_range=(1, 20)):
    """Generate a DataFrame with n random rectangles."""
    x = np.random.uniform(x_range[0], x_range[1], n)
    y = np.random.uniform(y_range[0], y_range[1], n)
    width = np.random.uniform(width_range[0], width_range[1], n)
    height = np.random.uniform(height_range[0], height_range[1], n)

    df = pd.DataFrame({
        'x': x,
        'y': y,
        'width': width,
        'height': height
    })
    return df


if __name__ == '__main__':
    df_ = generate_random_rectangles(50)
    df_repulsed = resolve_overlaps(df_)
    draw_final_rectangles(df_repulsed)