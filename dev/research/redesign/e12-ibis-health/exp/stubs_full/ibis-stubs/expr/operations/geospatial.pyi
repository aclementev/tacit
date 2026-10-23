import abc
import ibis.expr.datatypes as dt
from ibis.expr.operations.core import Binary, Unary, Value
from ibis.expr.operations.reductions import Filterable, Reduction

__all__ = ['GeoSpatialBinOp', 'GeoSpatialUnOp', 'GeoDistance', 'GeoContains', 'GeoContainsProperly', 'GeoCovers', 'GeoCoveredBy', 'GeoCrosses', 'GeoDisjoint', 'GeoEquals', 'GeoGeometryN', 'GeoGeometryType', 'GeoIntersects', 'GeoIsValid', 'GeoLineLocatePoint', 'GeoLineMerge', 'GeoLineSubstring', 'GeoOrderingEquals', 'GeoOverlaps', 'GeoTouches', 'GeoUnaryUnion', 'GeoUnion', 'GeoArea', 'GeoPerimeter', 'GeoLength', 'GeoMaxDistance', 'GeoX', 'GeoY', 'GeoXMin', 'GeoXMax', 'GeoYMin', 'GeoYMax', 'GeoStartPoint', 'GeoEndPoint', 'GeoPoint', 'GeoPointN', 'GeoNPoints', 'GeoNRings', 'GeoSRID', 'GeoSetSRID', 'GeoBuffer', 'GeoCentroid', 'GeoDFullyWithin', 'GeoDWithin', 'GeoEnvelope', 'GeoAzimuth', 'GeoWithin', 'GeoIntersection', 'GeoDifference', 'GeoSimplify', 'GeoTransform', 'GeoConvert', 'GeoAsBinary', 'GeoAsEWKB', 'GeoAsEWKT', 'GeoAsText', 'GeoFlipCoordinates']

class GeoSpatialBinOp(Binary, metaclass=abc.ABCMeta):
    left: Value[dt.GeoSpatial]
    right: Value[dt.GeoSpatial]

class GeoSpatialUnOp(Unary, metaclass=abc.ABCMeta):
    arg: Value[dt.GeoSpatial]

class GeoDistance(GeoSpatialBinOp):
    dtype = ...

class GeoContains(GeoSpatialBinOp):
    dtype = ...

class GeoContainsProperly(GeoSpatialBinOp):
    dtype = ...

class GeoCovers(GeoSpatialBinOp):
    dtype = ...

class GeoCoveredBy(GeoSpatialBinOp):
    dtype = ...

class GeoCrosses(GeoSpatialBinOp):
    dtype = ...

class GeoDisjoint(GeoSpatialBinOp):
    dtype = ...

class GeoEquals(GeoSpatialBinOp):
    dtype = ...

class GeoGeometryN(GeoSpatialUnOp):
    n: Value[dt.Integer]
    dtype = ...

class GeoGeometryType(GeoSpatialUnOp):
    dtype = ...

class GeoIntersects(GeoSpatialBinOp):
    dtype = ...

class GeoIsValid(GeoSpatialUnOp):
    dtype = ...

class GeoLineLocatePoint(GeoSpatialBinOp):
    left: Value[dt.LineString]
    right: Value[dt.Point]
    dtype = ...

class GeoLineMerge(GeoSpatialUnOp):
    dtype = ...

class GeoLineSubstring(GeoSpatialUnOp):
    arg: Value[dt.LineString]
    start: Value[dt.Floating]
    end: Value[dt.Floating]
    dtype = ...

class GeoOrderingEquals(GeoSpatialBinOp):
    dtype = ...

class GeoOverlaps(GeoSpatialBinOp):
    dtype = ...

class GeoTouches(GeoSpatialBinOp):
    dtype = ...

class GeoUnaryUnion(Filterable, Reduction):
    arg: Value[dt.GeoSpatial]
    dtype = ...

class GeoUnion(GeoSpatialBinOp):
    dtype = ...

class GeoArea(GeoSpatialUnOp):
    dtype = ...

class GeoPerimeter(GeoSpatialUnOp):
    dtype = ...

class GeoLength(GeoSpatialUnOp):
    dtype = ...

class GeoMaxDistance(GeoSpatialBinOp):
    dtype = ...

class GeoX(GeoSpatialUnOp):
    dtype = ...

class GeoY(GeoSpatialUnOp):
    dtype = ...

class GeoXMin(GeoSpatialUnOp):
    dtype = ...

class GeoXMax(GeoSpatialUnOp):
    dtype = ...

class GeoYMin(GeoSpatialUnOp):
    dtype = ...

class GeoYMax(GeoSpatialUnOp):
    dtype = ...

class GeoStartPoint(GeoSpatialUnOp):
    dtype = ...

class GeoEndPoint(GeoSpatialUnOp):
    dtype = ...

class GeoPoint(GeoSpatialBinOp):
    left: Value[dt.Numeric]
    right: Value[dt.Numeric]
    dtype = ...

class GeoPointN(GeoSpatialUnOp):
    n: Value[dt.Integer]
    dtype = ...

class GeoNPoints(GeoSpatialUnOp):
    dtype = ...

class GeoNRings(GeoSpatialUnOp):
    dtype = ...

class GeoSRID(GeoSpatialUnOp):
    dtype = ...

class GeoSetSRID(GeoSpatialUnOp):
    srid: Value[dt.Integer]
    dtype = ...

class GeoBuffer(GeoSpatialUnOp):
    radius: Value[dt.Floating]
    dtype = ...

class GeoCentroid(GeoSpatialUnOp):
    dtype = ...

class GeoDFullyWithin(GeoSpatialBinOp):
    distance: Value[dt.Floating]
    dtype = ...

class GeoDWithin(GeoSpatialBinOp):
    distance: Value[dt.Floating]
    dtype = ...

class GeoEnvelope(GeoSpatialUnOp):
    dtype = ...

class GeoAzimuth(GeoSpatialBinOp):
    left: Value[dt.Point]
    right: Value[dt.Point]
    dtype = ...

class GeoWithin(GeoSpatialBinOp):
    dtype = ...

class GeoIntersection(GeoSpatialBinOp):
    dtype = ...

class GeoDifference(GeoSpatialBinOp):
    dtype = ...

class GeoSimplify(GeoSpatialUnOp):
    tolerance: Value[dt.Floating]
    preserve_collapsed: Value[dt.Boolean]
    dtype = ...

class GeoTransform(GeoSpatialUnOp):
    srid: Value[dt.Integer]
    dtype = ...

class GeoConvert(GeoSpatialUnOp):
    source: str
    target: str
    dtype = ...

class GeoAsBinary(GeoSpatialUnOp):
    dtype = ...

class GeoAsEWKB(GeoSpatialUnOp):
    dtype = ...

class GeoAsEWKT(GeoSpatialUnOp):
    dtype = ...

class GeoAsText(GeoSpatialUnOp):
    dtype = ...

class GeoFlipCoordinates(GeoSpatialUnOp):
    dtype = ...
