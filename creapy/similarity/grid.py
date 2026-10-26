import numpy as np
import pandas as pd
import itertools
import shapely
from typing import List
from tqdm import tqdm
from creapy.similarity.grid_result import PairwiseSimilarityResult

class Grid:
    """
    Square n x n grid over a stimulus of height x width pixels (cell edges rounded to whole pixels). cells is the
    list of shapely cell polygons in row-major order. Base class of FixationGrid.
    """

    def __init__(self, height, width, n):
        v_grid = np.linspace(0, height, n + 1).round().astype(int)
        h_grid = np.linspace(0, width, n + 1).round().astype(int)
        xx, yy = np.meshgrid(h_grid, v_grid)
        self.n = n
        self.all_cell_index = pd.Series(index=range(n * n), dtype=object)
        self.cells: List[shapely.geometry.Polygon] = []
        for i, j in itertools.product(range(n), repeat=2):
            x0, y0, x1, y1 = xx[i, j], yy[i, j], xx[i + 1, j + 1], yy[i + 1, j + 1]
            cell = shapely.geometry.Polygon([[x0, y0], [x0, y1], [x1, y1], [x1, y0]])
            self.cells.append(cell)

    def actually_compute_pairwise_similarities(self, df_inverse_matched, callback, include_self=False):
        """
        Run callback(cell_values_1, cell_values_2) for every pair of subjects in df_inverse_matched (columns subject,
        cell, cell_values) and collect the per-cell similarity arrays in a PairwiseSimilarityResult. include_self=True
        also compares each subject with itself. Used by FixationGrid; rarely called directly.
        """
        combinator = itertools.combinations_with_replacement if include_self else itertools.combinations
        grouped_by_subject = df_inverse_matched.groupby('subject')
        combinations = list(combinator(grouped_by_subject, 2))
        mapping = {}
        for (s1, df1), (s2, df2) in tqdm(combinations, desc='computing pairwise similarities'):
            assert (df1.cell.values == df2.cell.values).all()  # type: ignore
            similarities_in_grid = callback(df1.cell_values, df2.cell_values)
            mapping[tuple(sorted([s1, s2]))] = similarities_in_grid
        return PairwiseSimilarityResult(mapping=mapping, subjects=list(grouped_by_subject.groups.keys()),
                                        cells=self.cells)