import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from sklearn import manifold
from tqdm import tqdm
from creapy.misc.utils import natural_sorted, natural_key


class PairwiseSimilarityResult:
    """
    Pairwise similarity scores between all subjects viewing one stimulus: any measure that yields one number
    per subject pair (HeatMatch s_loc/s_dir, MultiMatch, ScanMatch, cross-recurrence ...). The matrix, group
    boxplot, permutation test and viewer map work for every score column.
    """

    def __init__(self, df_sim, scores=None):
        # One row per unordered subject pair, diagonal included: subject_a, subject_b, <score columns>
        assert list(df_sim)[:2] == ['subject_a', 'subject_b']
        self.scores = list(scores) if scores is not None else [c for c in df_sim.columns[2:]]
        assert self.scores and all(c in df_sim.columns for c in self.scores)
        self.df_sim = df_sim
        self.subjects = natural_sorted(set(df_sim['subject_a']) | set(df_sim['subject_b']))
        self._permutation_cache = {}  # (which, grouping items, n_permutations, seed) -> result dict

    def default_score(self):
        """The score column used when `which` is not given (s_dir for HeatMatch, the first column otherwise)."""
        return self.scores[0]

    def matrix(self, which=None, grouping=None):
        """
        Symmetric participant x participant DataFrame of one score; with a grouping (participant -> group) the rows
        and columns are ordered group by group, so same-group pairs form blocks along the diagonal.
        """
        if which is None:
            which = self.default_score()
        assert which in self.scores, f"Unknown score {which}; available: {self.scores}"
        labels, _ = self.__labels_and_groups(grouping)
        mirrored = self.df_sim.rename(columns={'subject_a': 'subject_b', 'subject_b': 'subject_a'})
        df_ = pd.concat([self.df_sim, mirrored]).drop_duplicates(subset=['subject_a', 'subject_b'])
        matrix = df_.pivot(index='subject_a', columns='subject_b', values=which)
        return matrix.loc[labels, labels]

    def __labels_and_groups(self, grouping):
        if grouping is None:
            return list(self.subjects), None
        assert all(subj in self.subjects for subj in grouping)
        group_names = natural_sorted(set(grouping.values()))
        groups = {name: natural_sorted(subj for subj, name_ in grouping.items() if name_ == name) for name in group_names}
        labels = [subj for name in group_names for subj in groups[name]]
        return labels, groups

    def matshow(self, which=None, grouping=None, ax=None, cmap='viridis', group_color='black'):
        """
        The similarity matrix as an image with a colour bar; with a grouping, group blocks are framed and labelled.
        Above 40 participants only every tenth name is written. Returns the matrix DataFrame.
        """
        matrix = self.matrix(which=which, grouping=grouping)
        _, groups = self.__labels_and_groups(grouping)
        labels = matrix.index
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 10))
        im = ax.matshow(matrix, cmap=cmap)
        n = len(labels)
        if n <= 40:
            ax.set_xticks(range(n))
            ax.set_yticks(range(n))
            ax.set_xticklabels(labels, rotation=90, fontsize=8 if n > 25 else None)
            ax.set_yticklabels(labels, fontsize=8 if n > 25 else None)
        else:
            # with 100+ participants the names would overprint: label every tenth
            step = 10 if n <= 200 else 25
            ax.set_xticks(range(0, n, step))
            ax.set_yticks(range(0, n, step))
            ax.set_xticklabels([labels[i] for i in range(0, n, step)], rotation=90, fontsize=7)
            ax.set_yticklabels([labels[i] for i in range(0, n, step)], fontsize=7)
        ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        if groups is not None:
            # bracket geometry scales with the matrix size (the old fixed -2 offsets vanish at n = 157)
            d = max(2., 0.03 * n)
            w0 = -0.5
            for group_name, group in groups.items():
                group_size = len(group)
                w1 = w0 + group_size
                ax.add_patch(Rectangle((w0, w0), height=group_size, width=group_size,
                                       facecolor='none', edgecolor=group_color, linewidth=1))
                ax.text((w0 + w1) / 2, -d, group_name, ha='center', va='center', fontweight='bold')
                ax.text(-1.25 * d, (w0 + w1) / 2, group_name, ha='center', va='center', fontweight='bold',
                        rotation=90 if n > 40 else 0)
                ax.add_line(Line2D([w0 + 0.1, w0 + 0.1, w1 - 0.1, w1 - 0.1],
                                   [-0.7 * d, -0.9 * d, -0.9 * d, -0.7 * d],
                                   lw=2, color=group_color, clip_on=False))
                ax.add_line(Line2D([-0.8 * d, -d, -d, -0.8 * d],
                                   [w0 + 0.1, w0 + 0.1, w1 - 0.1, w1 - 0.1],
                                   lw=2, color=group_color, clip_on=False))
                w0 = w1
        if show:
            ax.figure.tight_layout()
            plt.show()
        return matrix

    def show_boxplot(self, grouping, which=None, ax=None):
        """
        Boxplots of the pairwise scores within each group and between each pair of groups ('A/B'); grouping maps
        participant -> group. The within-vs-between question is tested by permutation_test.
        """
        which = which or self.default_score()
        matrix = self.matrix(which=which, grouping=grouping)
        _, groups = self.__labels_and_groups(grouping)
        data = []
        labels = []
        # Within-group similarities
        for group_name, group in groups.items():
            data.append([matrix.loc[s1, s2] for s1, s2 in itertools.combinations(group, 2)])
            labels.append(group_name)
        # Between-group similarities
        for (name_1, group_1), (name_2, group_2) in itertools.combinations(groups.items(), 2):
            data.append([matrix.loc[s1, s2] for s1, s2 in itertools.product(group_1, group_2)])
            labels.append(f"{name_1}/{name_2}")
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(figsize=(5, 5))
        ax.boxplot(data, tick_labels=labels, patch_artist=True)
        ax.set_ylabel(which)
        if show:
            ax.figure.tight_layout()
            plt.show()

    def permutation_test(self, grouping, which=None, n_permutations=10_000, seed=0, verbose=True):
        """
        One-sided permutation test: are participants more similar within their group than between groups?
        Statistic = mean within-group score - mean between-group score, group labels shuffled under the null.
        Returns a dict with which, within_mean, between_mean, observed, p_value, n_permutations (cached per call).
        """
        which = which or self.default_score()
        # One-sided permutation test: are subjects more similar within their group than between groups?
        # Statistic: mean(within-group sims) - mean(between-group sims); group labels shuffled under the null.
        key = (which, tuple(sorted(grouping.items())), n_permutations, seed)
        if key in self._permutation_cache:
            return self._permutation_cache[key]
        matrix = self.matrix(which=which, grouping=grouping)
        labels = np.array([grouping[subj] for subj in matrix.index])
        assert len(set(labels)) >= 2, "The permutation test needs at least two groups!"
        iu, ju = np.triu_indices(len(labels), k=1)  # unordered pairs, self-similarities excluded
        sims = matrix.to_numpy()[iu, ju]

        def statistic(labels_):
            within = labels_[iu] == labels_[ju]
            return sims[within].mean() - sims[~within].mean()

        within = labels[iu] == labels[ju]
        assert within.any(), "The permutation test needs at least one group with two or more subjects!"
        observed = statistic(labels)
        rng = np.random.default_rng(seed)
        null_stats = np.array([statistic(rng.permutation(labels))
                               for _ in tqdm(range(n_permutations), desc="Permutation test",
                                             disable=not verbose)])
        p_value = (np.sum(null_stats >= observed) + 1) / (n_permutations + 1)
        self._permutation_cache[key] = {'which': which,
                                        'within_mean': sims[within].mean(),
                                        'between_mean': sims[~within].mean(),
                                        'observed': observed,
                                        'p_value': p_value,
                                        'n_permutations': n_permutations}
        return self._permutation_cache[key]

    def score_overview(self, grouping=None):
        """
        Mean score over all unordered participant pairs, one row per score column: columns 'measure', 'all pairs'
        and, with a grouping (participant -> group) of two or more groups, 'within groups' and 'between groups'.
        For MultiMatch this is the five-dimension summary of the GUI's Measure overview.
        """
        iu, ju = np.triu_indices(len(self.subjects), k=1)
        ls = []
        for score in self.scores:
            matrix = self.matrix(which=score)
            vals = matrix.to_numpy()[iu, ju]
            row = {'measure': score, 'all pairs': float(np.nanmean(vals))}
            if grouping and len(set(grouping.values())) >= 2:
                labels = np.array([grouping.get(s) for s in matrix.index], dtype=object)
                known = (labels[iu] != None) & (labels[ju] != None)  # noqa: E711
                same = known & (labels[iu] == labels[ju])
                diff = known & (labels[iu] != labels[ju])
                row['within groups'] = float(np.nanmean(vals[same])) if same.any() else np.nan
                row['between groups'] = float(np.nanmean(vals[diff])) if diff.any() else np.nan
            ls.append(row)
        return pd.DataFrame.from_records(ls)

    def show_score_overview(self, grouping=None, ax=None, strip_prefix='mm_'):
        """
        Grouped bar chart of score_overview(): one group of bars per score (all pairs / within / between groups),
        y from 0 to 1. strip_prefix is removed from the tick labels ('mm_vector' -> 'vector'). Returns the table.
        """
        df_over = self.score_overview(grouping=grouping)
        cols = [c for c in df_over.columns if c != 'measure']
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(1, 1, figsize=(7, 4))
        x = np.arange(len(df_over))
        w = 0.8 / len(cols)
        for i, c in enumerate(cols):
            ax.bar(x + (i - (len(cols) - 1) / 2) * w, df_over[c], width=w, label=c)
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace(strip_prefix, '') if strip_prefix else m for m in df_over['measure']])
        ax.set_ylim(0, 1)
        ax.set_ylabel("similarity (1 = identical)")
        if len(cols) > 1:
            ax.legend()
        if show:
            ax.figure.tight_layout()
            plt.show()
        return df_over

    def show_multidimensional_scaling(self, grouping=None, which=None, ax=None):
        """
        Viewer map: each participant as a point in two dimensions (spectral embedding of the similarity matrix),
        coloured by group when a grouping is given. Near points = similar viewing; the axes carry no unit.
        """
        matrix = self.matrix(which=which, grouping=grouping)
        matrix = matrix.fillna(0.)
        # SpectralEmbedding expects an affinity (= similarity) matrix, so the scores are passed directly
        # TSNE(n_components=2, perplexity=5, init='random', metric='precomputed')
        # MDS(n_components=2, metric=True, n_init=1, dissimilarity='precomputed')
        # Isomap(metric='precomputed')
        model = manifold.SpectralEmbedding(affinity='precomputed')
        dim_reduced = model.fit_transform(matrix.to_numpy())
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(figsize=(5, 5))
        if grouping is not None:
            groups = [grouping[subj] for subj in matrix.index]
            cmap = {name: i for i, name in enumerate(sorted(set(groups)))}
            c = [cmap[name] for name in groups]
        else:
            c = None
        ax.scatter(dim_reduced[:, 0], dim_reduced[:, 1], c=c, s=50)
        if show:
            ax.figure.tight_layout()
            plt.show()


class HeatMatchSimilarityResult(PairwiseSimilarityResult):
    """Pairwise HeatMatch similarity scores (Long et al. 2026): s_loc and s_dir (the default)."""

    def __init__(self, df_sim):
        assert list(df_sim) == ['subject_a', 'subject_b', 's_loc', 's_dir']
        super().__init__(df_sim, scores=['s_dir', 's_loc'])


class HeatMatchSimilarityProfile:
    """Sliding-window HeatMatch similarity: pairwise scores per time window (viewer synchrony over time)."""

    def __init__(self, df_profile, window):
        # One row per time window and unordered subject pair: t_center, subject_a, subject_b, s_loc, s_dir
        assert list(df_profile) == ['t_center', 'subject_a', 'subject_b', 's_loc', 's_dir']
        self.df_profile = df_profile
        self.window = window

    def curves(self, which='s_dir', grouping=None):
        """
        {label: DataFrame indexed by window centre (s) with columns mean, std}: one curve 'all pairs' without a
        grouping, otherwise one per group (within) and one per group pair 'A/B' (between).
        """
        # {label: df with t_center index and mean/std columns}: 'all pairs' without grouping,
        # else one curve per group (within) and per group pair (between), like show_boxplot
        assert which in ['s_loc', 's_dir']
        df_ = self.df_profile.copy()
        if grouping is None:
            df_['label'] = 'all pairs'
        else:
            ls = []
            for a, b in zip(df_['subject_a'].map(grouping), df_['subject_b'].map(grouping)):
                if pd.isna(a) or pd.isna(b):
                    ls.append(None)  # subject not in the grouping -> pair excluded
                elif a == b:
                    ls.append(a)
                else:
                    ls.append('/'.join(sorted([a, b])))
            df_['label'] = ls
            df_ = df_[df_['label'].notna()]
        curves = {}
        for label, df_label in df_.groupby('label'):
            grouped = df_label.groupby('t_center')[which]
            curves[label] = pd.DataFrame({'mean': grouped.mean(), 'std': grouped.std()})
        return curves

    def show_profile(self, which='s_dir', grouping=None, ax=None, n_std=0.05):
        """
        Similarity over viewing time: the curves of curves() with a band of ± n_std standard deviations.
        Returns the curves dict.
        """
        curves = self.curves(which=which, grouping=grouping)
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(figsize=(5, 5))
        for label, df_curve in curves.items():
            line, = ax.plot(df_curve.index, df_curve['mean'], label=label)
            if 0. < n_std <= 1.:
                ax.fill_between(df_curve.index, df_curve['mean'] - n_std * df_curve['std'],
                                df_curve['mean'] + n_std * df_curve['std'],
                                color=line.get_color(), alpha=0.1)
        ax.set_xlabel("Time (window centers)")
        ax.set_ylabel(which)
        if len(curves) > 1:
            ax.legend()
        if show:
            ax.figure.tight_layout()
            plt.show()
        return curves


if __name__ == '__main__':
    pass
