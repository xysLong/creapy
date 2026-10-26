import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.offsetbox import TextArea, VPacker, AnnotationBbox
import warnings
import itertools
from sklearn import manifold

class PairwiseSimilarityResult:
    """
    Result of a grid-based fixation similarity: for every pair of subjects an array with one similarity per grid
    cell (NaN where neither looked). Offers gridshow (per-cell map on the stimulus), matshow (subject x subject
    matrix of cell means), show_boxplot (within / between groups) and show_multidimensional_scaling (2-D
    embedding). Not the HeatMatch result class of the same name in creapy.similarity.heatmatch_result.
    """

    def __init__(self, mapping, subjects, cells):
        self.__subjects = subjects
        self.__mapping = self.__fill_mapping(mapping)
        self.__cells = cells

    def __fill_mapping(self, mapping):
        for subject_a, subject_b in itertools.combinations_with_replacement(self.__subjects, 2):
            key_ab = tuple(sorted([subject_a, subject_b]))
            if subject_a != subject_b:
                key_ba = tuple(reversed(key_ab))
                if key_ab in mapping:
                    assert key_ba not in mapping
                    mapping[key_ba] = mapping[key_ab]
                else:
                    assert key_ba in mapping
                    mapping[key_ab] = mapping[key_ba]
            else:
                if key_ab in mapping:
                    assert isinstance(mapping[key_ab], np.ndarray)
                else:
                    mapping[key_ab] = np.nan
        assert len(mapping) == len(self.__subjects) ** 2
        return mapping

    def gridshow(self, path_to_stim):
        """
        Show the per-cell similarity over the stimulus image at path_to_stim in a 2 x 2 figure: a star glyph per
        cell (size = number of valid pairs, colour = mean similarity, spikiness = its standard deviation) plus three
        maps of count, mean and standard deviation with the numbers written in. Calls plt.show().
        """
        _matrix = []
        for subject_a, subject_b in itertools.combinations(self.__subjects, 2):
            array = self.__mapping[tuple(sorted([subject_a, subject_b]))]
            if isinstance(array, np.ndarray):
                _matrix.append(array)
            else:
                assert subject_a == subject_b
        matrix = np.array(_matrix)
        counts = (~np.isnan(matrix)).sum(axis=0)
        # If a cell is nan in all pairwise results, a column in "matrix" would be nan in all rows
        # Therefore, "Mean of empty slice" and "Degrees of freedom <= 0 for slice" warnings
        # But they are not important so we filter out
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            means = np.nanmean(matrix, axis=0)
            stds = np.nanstd(matrix, ddof=0, axis=0)
        assert len(means) == len(self.__cells)
        img = mpimg.imread(path_to_stim)
        fig, ((ax00, ax01), (ax10, ax11)) = plt.subplots(2, 2, figsize=(15, 15))
        self.__gridshow_1_axis(ax00, counts, means, stds, img=img, show_stats=False)
        self.__gridshow_3_axes([ax01, ax10, ax11], counts, means, stds, img=img, show_stats=True)
        fig.tight_layout()
        plt.show()
        # plt.savefig(f"./temp/{datetime.now().strftime('%Y%m%d%H%M%S')}.png", dpi=100, bbox_inches='tight')

    def __gridshow_1_axis(self, ax, counts, means, stds, img, show_stats):
        PairwiseSimilarityResult.__apply_image_axes_formatting(ax, img)
        cmap = plt.get_cmap('viridis')
        for cell_idx, (cell, n, m, s) in enumerate(zip(self.__cells, counts, means, stds)):
            n_unit = PairwiseSimilarityResult.__safe_unit_normalize(n, counts)
            xx, yy = cell.exterior.xy
            x_edge = np.max(xx) - np.min(xx)
            y_edge = np.max(yy) - np.min(yy)
            centroid = cell.centroid
            x_center, y_center = centroid.x, centroid.y
            if not np.isnan(m):
                m_unit = PairwiseSimilarityResult.__safe_unit_normalize(m, means)
                s_unit = PairwiseSimilarityResult.__safe_unit_normalize(s, stds)
                star_x, star_y = PairwiseSimilarityResult.__make_star(transition=s_unit)
                star_x *= n_unit * x_edge / 2
                star_y *= n_unit * y_edge / 2
                star_x += x_center
                star_y += y_center
                ax.fill(star_x, star_y, color=cmap(m_unit), clip_on=False, alpha=0.7)
                ax.plot(xx, yy, color='white', clip_on=False, alpha=0.5)
                if show_stats:
                    ax.text(x_center, y_center, f"$n$={n}\n$\\mu$={round(m, 3)}\n$\\sigma$={round(s, 3)}", ha='center',
                            va='center')

    def __gridshow_3_axes(self, axes, counts, means, stds, img, show_stats):
        PairwiseSimilarityResult.__apply_image_axes_formatting(axes, img)
        cmap = plt.get_cmap('viridis')
        for cell_idx, (cell, n, m, s) in enumerate(zip(self.__cells, counts, means, stds)):
            n_unit = PairwiseSimilarityResult.__safe_unit_normalize(n, counts)
            x, y = cell.exterior.xy
            x_text = np.min(x) + 0.1 * (np.max(x) - np.min(x))
            y_text = np.min(y) + 0.1 * (np.max(y) - np.min(y))
            texts = [f"$n$={n}"] if show_stats else None
            if not np.isnan(m):
                m_unit = PairwiseSimilarityResult.__safe_unit_normalize(m, means)
                s_unit = PairwiseSimilarityResult.__safe_unit_normalize(s, stds)
                axes[0].fill(x, y, alpha=0.5, facecolor=cmap(n_unit), edgecolor='white')
                axes[1].fill(x, y, alpha=0.5, facecolor=cmap(m_unit), edgecolor='white')
                axes[2].fill(x, y, alpha=0.5, facecolor=cmap(s_unit), edgecolor='white')
                if show_stats:
                    texts.append(f"$\\mu$={round(m, 3)}")
                    texts.append(f"$\\sigma$={round(s, 3)}")
            for i, (ax, title) in enumerate(zip(axes, ["Number $n$", r"Mean $\mu$", r"Standard Deviation $\sigma$"])):
                if show_stats:
                    text_areas = [TextArea(f"Cell {cell_idx}", textprops=dict(alpha=0.5))]
                    text_areas.extend([TextArea(text, textprops=dict(weight='bold') if i == j else dict(alpha=0.5))
                                       for j, text in enumerate(texts)])
                    textbox = VPacker(children=text_areas, align="left", pad=0, sep=0)
                    ab = AnnotationBbox(textbox, (x_text, y_text), xycoords='data', box_alignment=(0, 1), frameon=False)
                    ax.add_artist(ab)
                ax.set_title(title)

    @staticmethod
    def __apply_image_axes_formatting(axes, img):
        if not isinstance(axes, (list, np.ndarray)):
            axes = [axes]
        height, width = img.shape[:2]
        for ax in axes:
            ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xlim([0, width])
            ax.set_ylim([height, 0])

    @staticmethod
    def __safe_unit_normalize(value, values):
        nanmax = np.nanmax(values)
        nanmin = np.nanmin(values)
        if np.isnan(nanmax) or np.isnan(nanmin):
            return 0.5
        if nanmax > nanmin:
            return (value - nanmin) / (nanmax - nanmin)
        return 0.5

    @staticmethod
    def __make_star(transition, n_points=100, radius=1.0, zigzag_depth=1, frequency=6):
        angles = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        zigzag = np.cos(angles * frequency)
        modulation = transition * zigzag_depth * (1 - (zigzag + 1) / 2)
        modulated_radius = radius - modulation
        x = modulated_radius * np.cos(angles)
        y = modulated_radius * np.sin(angles)
        return x, y

    def matshow(self, grouping=None):
        """
        Subject x subject matrix of the mean cell similarity (viridis; the diagonal is NaN unless computed with
        include_self=True). grouping is an optional dict subject -> group name: subjects are then ordered by group
        and the groups are framed and labelled. Calls plt.show().
        """
        matrix, groups = self.__compute_similarity_matrix(grouping=grouping)
        labels = matrix.index
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.matshow(matrix, cmap='viridis')
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_yticklabels(labels)
        if groups is not None:
            w0 = -0.5
            for group_name, group in groups.items():
                group_size = len(group)
                w1 = w0 + group_size
                ax.add_patch(Rectangle((w0, w0), height=group_size, width=group_size,
                                       facecolor='none', edgecolor='black', linewidth=1))
                ax.text((w0 + w1) / 2, -2, group_name, ha='center', va='center', fontweight='bold')
                ax.text(-2.5, (w0 + w1) / 2, group_name, ha='center', va='center', fontweight='bold')
                ax.add_line(Line2D([w0 + 0.1, w0 + 0.1, w1 - 0.1, w1 - 0.1],
                                   [-1.4, -1.8, -1.8, -1.4],
                                   lw=2, color='black', clip_on=False))
                ax.add_line(Line2D([-1.6, -2, -2, -1.6],
                                   [w0 + 0.1, w0 + 0.1, w1 - 0.1, w1 - 0.1],
                                   lw=2, color='black', clip_on=False))
                w0 = w1
        fig.tight_layout()
        plt.show()

    def __compute_similarity_matrix(self, grouping=None):
        matrix = pd.Series(self.__mapping).unstack().map(
            lambda x: np.nanmean(x) if isinstance(x, np.ndarray) else np.nan)

        if grouping is not None:
            assert isinstance(grouping, dict)
            assert all(subj in self.__subjects for subj in grouping.keys())
            group_names = sorted(set(grouping.values()))
            groups = {}
            labels = []
            for group_name_1 in group_names:
                subjects = []
                for subj, group_name_2 in grouping.items():
                    if group_name_1 == group_name_2:
                        subjects.append(subj)
                groups[group_name_1] = subjects
                labels.extend(subjects)
        else:
            labels = self.__subjects
            groups = {}
        return matrix[labels].reindex(labels), groups

    def show_boxplot(self, grouping):
        """
        Boxplots of the mean cell similarity within each group and between each pair of groups. grouping is a dict
        subject -> group name. Calls plt.show().
        """
        similarity_matrix, groups = self.__compute_similarity_matrix(grouping=grouping)
        data = []
        labels = []
        # Within-Group Comparison
        for group_name, group in groups.items():
            data.append([similarity_matrix.loc[s1, s2] for s1, s2 in itertools.combinations(group, 2)])
            labels.append(group_name)
        # Between-Group Comparison
        for (group_name_1, group_1), (group_name_2, group_2) in itertools.combinations(groups.items(), 2):
            data.append([similarity_matrix.loc[s1, s2] for s1, s2 in itertools.product(group_1, group_2)])
            labels.append(f"{group_name_1}/{group_name_2}")
        fig, ax = plt.subplots(figsize=(5, 5))
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
        fig.tight_layout()
        plt.show()

    def show_multidimensional_scaling(self, grouping=None):
        """
        Scatter the subjects in 2-D by spectral embedding of the similarity matrix (sklearn SpectralEmbedding with
        the scores as affinities), coloured by group. grouping is a dict subject -> group name and is needed for the
        colours despite its default of None. Calls plt.show().
        """
        similarity_matrix, _ = self.__compute_similarity_matrix(grouping=grouping)
        empty_entries = np.argwhere(similarity_matrix.isna())
        assert all([empty_entry[0] == empty_entry[1] for empty_entry in empty_entries])
        similarity_matrix.fillna(value=1., inplace=True)
        # SpectralEmbedding expects an affinity (= similarity) matrix, so the scores are passed directly
        # (bug fixed 2026-09-04: used to convert to a dissimilarity matrix first)
        # TSNE(n_components=2, perplexity=5, init='random', metric='precomputed')
        # MDS(n_components=2, metric=True, n_init=1, dissimilarity='precomputed')
        # Isomap(metric='precomputed')
        model = manifold.SpectralEmbedding(affinity='precomputed')
        dim_reduced = model.fit_transform(similarity_matrix)
        fig, ax = plt.subplots(figsize=(5, 5))
        groups = [grouping[subj] for subj in similarity_matrix.index]
        cmap = {g: i for i, g in enumerate(sorted(set(groups)))}
        c = [cmap[g] for g in groups]
        ax.scatter(dim_reduced[:, 0], dim_reduced[:, 1], c=c, s=50)
        fig.tight_layout()
        plt.show()