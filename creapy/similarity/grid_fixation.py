import numpy as np
import pandas as pd

from creapy.similarity.grid import Grid

class FixationGrid(Grid):
    """
    Grid-based fixation similarity: the stimulus is split into n x n cells and two participants are compared
    cell by cell on how much fixation weight they put there. Usually reached through
    FixationData.compute_grid_based_fixation_similarity.
    """

    def __init__(self, height, width, n):
        super().__init__(height, width, n)

    def compute_pairwise_similarities(self, df_matchable, include_self=False):
        """
        Pairwise fixation similarity for every pair of subjects. df_matchable has exactly the columns subject, point
        (shapely points in pixels) and weight (summing to 1 per subject, e.g. duration shares). Per cell the score
        is min / max of the two subjects' summed weights (NaN where neither fixated); returns a
        PairwiseSimilarityResult. include_self=True also compares each subject with itself.
        """
        assert list(df_matchable) == ['subject', 'point', 'weight']
        df_inverse_matched = self.__match_with_fixation_points(df_matchable)
        callback = FixationGrid.__compute_fixation_similarities_in_grid
        return self.actually_compute_pairwise_similarities(df_inverse_matched, callback=callback, include_self=include_self)

    def __match_with_fixation_points(self, df_matchable):
        assert list(df_matchable) == ['subject', 'point', 'weight']
        ls = {}
        for cell_idx, cell in enumerate(self.cells):
            ls[cell_idx] = cell.contains(df_matchable['point'])
        df_temp = pd.DataFrame(ls)
        __row_sum = df_temp.sum(axis=1)
        assert (__row_sum <= 1).all()
        assert (__row_sum == 1).sum() > 0.95 * len(df_temp)  # type: ignore
        matching = df_temp.idxmax(axis=1)
        matching[~df_temp.any(axis=1)] = pd.NA
        df_matched = df_matchable.drop(columns='point', inplace=False)
        df_matched['cell'] = pd.Series(matching, dtype="Int64")

        ls = []
        for subject, df_ in df_matched.groupby('subject'):
            assert np.isclose(df_['weight'].sum(), 1.)
            df_grouped = df_.groupby("cell")["weight"].apply(np.array)
            df_inverse = df_grouped.reindex(self.all_cell_index.index).apply(
                lambda x: x if isinstance(x, np.ndarray) else np.array([])
            ).reset_index()
            df_inverse['subject'] = subject
            ls.append(df_inverse)
        df_inverse_matched = pd.concat(ls).reset_index(drop=True)[['subject', 'index', 'weight']]
        return df_inverse_matched.rename(columns={'index': 'cell', 'weight': 'cell_values'})

    @staticmethod
    def __compute_fixation_similarities_in_grid(weights_1_series, weights_2_series, method='jaccard++'):
        if method == 'jaccard++':
            w_fix_x = weights_1_series.apply(np.sum).to_numpy()
            w_fix_y = weights_2_series.apply(np.sum).to_numpy()
        elif method == 'jaccard':
            w_fix_x = weights_1_series.apply(len).to_numpy()
            w_fix_y = weights_2_series.apply(len).to_numpy()
        else:
            raise ValueError(f"Unsupported method: {method}")

        min_fix = np.minimum(w_fix_x, w_fix_y)
        max_fix = np.maximum(w_fix_x, w_fix_y)

        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            similarities_in_grid = np.where(max_fix == 0, np.nan, min_fix / max_fix)

        # overall = np.nanmean(similarity)
        return similarities_in_grid


# The legacy saccade comparison block that used to live below (SaccadeGrid, Saccades,
# SaccadesComparator, compute_grid_based_metrics, compute_metrics) was retired 2026-09-04,
# superseded by the heatmatch package (SaccadeData.compute_heatmatch_similarity).


if __name__ == '__main__':
    pass
