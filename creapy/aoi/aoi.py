import numpy as np
import functools
import matplotlib.patches as patches
import matplotlib.patheffects as pe
import matplotlib.path as mpath
from shapely import area, centroid, covers
from shapely.ops import unary_union
from shapely.geometry import Point, Polygon, LinearRing, box


class AOI:
    """
    One area of interest: a named shapely geometry in image pixels (x right, y down). Build it with
    AOI.rectangle(...) or AOI.polygon(...), or from matplotlib Paths drawn in the GUI (paths=...). Several
    disconnected parts are fine, they become one MultiPolygon.
    """

    def __init__(self, name="Unnamed", geom=None, paths=None):
        assert (geom is None) != (paths is None), "EITHER 'geom' OR 'paths' must be provided, but not both"
        self.__name = name
        self.__geom = geom if paths is None else AOI.__multiple_paths_to_single_geom(paths)
        self.__path = AOI.__single_geom_to_single_path(self.__geom)
        self.__disconnected_polygons = AOI.__extract_disconnected_polygons(self.__geom)

    @property
    def name(self):
        """The AOI's name (read-only)."""
        return self.__name

    @property
    def geom(self):
        """The shapely geometry (Polygon or MultiPolygon) in image pixels, read-only."""
        return self.__geom

    def area(self):
        """Area of the AOI in square pixels."""
        return float(area(self.__geom))

    def contains(self, points):
        """
        True for each point inside or on the boundary of the AOI. points: shapely point(s), e.g. fix.fix_points;
        returns one bool or a bool array.
        """
        return covers(self.__geom, points)

    @staticmethod
    def rectangle(name, x0, y0, x1, y1):
        """Rectangular AOI from two opposite corners (x0, y0), (x1, y1) in pixels; the corner order does not matter."""
        return AOI(name=name, geom=box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    @staticmethod
    def polygon(name, vertices):
        """
        Polygon AOI from a list of (x, y) vertices in pixels, at least three. Self-intersections are repaired
        with buffer(0).
        """
        assert len(vertices) >= 3, "A polygon AOI needs at least three corners."
        return AOI(name=name, geom=Polygon(vertices).buffer(0))

    def to_record(self):
        """Dict {'name', 'wkt'} describing the AOI as text (WKT), for saving AOI sets to JSON; see from_record."""
        # Serializable description (WKT) so AOI sets can be saved and reloaded
        return {'name': self.__name, 'wkt': self.__geom.wkt}

    @staticmethod
    def from_record(record):
        """Rebuild an AOI from a to_record() dict."""
        from shapely import wkt
        return AOI(name=record['name'], geom=wkt.loads(record['wkt']))

    def show(self, ax, color='yellow', alpha=0.4, label=True):
        """
        Draw the AOI on a matplotlib axes as a translucent patch, with its name at the centroid of the largest
        part (dashed lines connect further parts). label=False draws the patch alone.
        """
        ax.add_patch(patches.PathPatch(self.__path, facecolor=color, alpha=alpha, edgecolor=color, linewidth=1.5))
        if not label:
            return
        polygons = sorted([(area(polygon), polygon) for polygon in self.__disconnected_polygons], reverse=True)
        center = centroid(polygons[0][1])
        ax.text(center.x, center.y, self.__name, ha='center', va='center', color="black",
                path_effects=[
                    pe.Stroke(linewidth=4, foreground='white', alpha=0.7),  # halo effect
                    pe.Normal()
                ])
        for _, polygon in polygons[1:]:
            center_ = centroid(polygon)
            ax.plot([center.x, center_.x], [center.y, center_.y], color='black', alpha=0.3, linestyle='--')

    @staticmethod
    def __multiple_paths_to_single_geom(paths):
        # Generator expression to convert each path to polygons
        polygons = [AOI.__single_path_to_multiple_geoms(path) for path in paths]
        flattened_polygons = functools.reduce(lambda a, b: a + b, polygons)
        return unary_union(flattened_polygons)

    @staticmethod
    def __extract_disconnected_polygons(geom):
        """Extract individual disconnected polygons from a unary union result."""
        if geom.geom_type == 'Polygon':
            return [geom]
        elif geom.geom_type == 'MultiPolygon':
            return list(geom.geoms)
        elif geom.geom_type == 'GeometryCollection':
            return [g for g in geom.geoms if isinstance(g, Polygon)]
        else:
            return []

    @staticmethod
    def __single_path_to_multiple_geoms(path):
        """Extract individual polygons from a Path that may contain disconnected parts."""
        polys = []
        vertices = path.vertices
        codes = path.codes
        if codes is None:
            # Assume one continuous path
            if np.allclose(vertices[0], vertices[-1]):
                polys.append(Polygon(vertices))
            else:
                polys.append(LinearRing(vertices))
            return polys

        current = []
        for vert, code in zip(vertices, codes):
            if code == mpath.Path.MOVETO:
                if current:
                    ring = np.array(current)
                    if np.allclose(ring[0], ring[-1]):
                        polys.append(Polygon(ring))
                    else:
                        polys.append(LinearRing(ring))
                current = [vert]
            else:
                current.append(vert)

        # Don't forget the last one
        if current:
            ring = np.array(current)
            if np.allclose(ring[0], ring[-1]):
                polys.append(Polygon(ring))
            else:
                polys.append(LinearRing(ring))
        return polys

    @staticmethod
    def __single_geom_to_single_path(geom):
        """Convert a shapely Polygon or MultiPolygon to a matplotlib Path."""
        if geom.geom_type == 'Polygon':
            verts = np.array(geom.exterior.coords)
            codes = ([mpath.Path.MOVETO] + [mpath.Path.LINETO] * (len(verts) - 2) + [mpath.Path.CLOSEPOLY])
            return mpath.Path(verts, codes)
        elif geom.geom_type == 'MultiPolygon':
            all_verts = []
            all_codes = []
            for polygon in geom.geoms:
                verts = np.array(polygon.exterior.coords)
                codes = ([mpath.Path.MOVETO] + [mpath.Path.LINETO] * (len(verts) - 2) + [mpath.Path.CLOSEPOLY])
                all_verts.extend(verts)
                all_codes.extend(codes)
            return mpath.Path(np.array(all_verts), all_codes)
        else:
            raise ValueError(f"Unsupported geometry type: {geom.geom_type}")
