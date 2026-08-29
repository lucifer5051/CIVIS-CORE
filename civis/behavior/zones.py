from typing import List, Optional, Tuple
from civis.behavior.models import LineTripwire, Point2D, PolygonZone


def point_in_polygon(point: Point2D, polygon: List[Point2D]) -> bool:
    """Ray-casting algorithm to test if point is inside a polygon."""
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1x, p1y = polygon[0].x, polygon[0].y
    for i in range(n + 1):
        p2x, p2y = polygon[i % n].x, polygon[i % n].y
        if point.y > min(p1y, p2y):
            if point.y <= max(p1y, p2y):
                if point.x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (point.y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or point.x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def _ccw(A: Point2D, B: Point2D, C: Point2D) -> bool:
    return (C.y - A.y) * (B.x - A.x) > (B.y - A.y) * (C.x - A.x)


def line_intersects(A: Point2D, B: Point2D, C: Point2D, D: Point2D) -> bool:
    """Tests if line segment AB intersects line segment CD."""
    return _ccw(A, C, D) != _ccw(B, C, D) and _ccw(A, B, C) != _ccw(A, B, D)


class ZoneEvaluator:
    """Evaluates polygon zone containment and tripwire crossings."""

    def __init__(self, zones: List[PolygonZone], tripwires: List[LineTripwire]) -> None:
        self.zones = zones
        self.tripwires = tripwires

    def get_containing_zones(self, point: Point2D) -> List[str]:
        containing = []
        for zone in self.zones:
            if point_in_polygon(point, zone.polygon):
                containing.append(zone.zone_id)
        return containing

    def check_tripwire_crossing(self, p_prev: Point2D, p_curr: Point2D) -> List[LineTripwire]:
        crossed = []
        for tripwire in self.tripwires:
            if line_intersects(p_prev, p_curr, tripwire.p1, tripwire.p2):
                crossed.append(tripwire)
        return crossed
