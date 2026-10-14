"""Curve inspection regression tests; fake typed objects never activate COM."""

from types import SimpleNamespace

import pytest

from renga_codex_bridge.model import curve_points


class Segment:
    def __init__(self, begin, end):
        self.begin = SimpleNamespace(X=begin[0], Y=begin[1])
        self.end = SimpleNamespace(X=end[0], Y=end[1])

    def GetBeginPoint(self):
        return self.begin

    def GetEndPoint(self):
        return self.end


class PolyCurve:
    def __init__(self, points):
        self.segments = [Segment(a, b) for a, b in zip(points, points[1:])]

    def GetInterfaceByName(self, name):
        assert name == "IPolyCurve2D"
        return self

    def QueryInterface(self, interface):
        return self

    def GetSegmentCount(self):
        return len(self.segments)

    def GetSegment(self, index):
        return self.segments[index]


def fake_context(curve):
    baseline = SimpleNamespace(GetBaseline=lambda: curve)
    obj = SimpleNamespace(ObjectTypeS="WALL", QueryInterface=lambda interface: baseline)
    session = SimpleNamespace(
        sdk=SimpleNamespace(types={"Room": "ROOM"}),
        r=SimpleNamespace(IBaseline2DObject=object(), IPolyCurve2D=object()),
    )
    return session, obj


def test_open_polycurve_includes_final_endpoint_of_u_shaped_stair():
    points = [[10, 20], [10, 3020], [2010, 3020], [2010, 20]]
    session, obj = fake_context(PolyCurve(points))
    assert curve_points(session, obj) == points


def test_closed_polycurve_does_not_repeat_first_point_at_end():
    points = [[0, 0], [6000, 0], [6000, 4000], [0, 4000], [0, 0]]
    session, obj = fake_context(PolyCurve(points))
    assert curve_points(session, obj) == points[:-1]


def test_native_curve_without_polycurve_interface_reads_both_line_endpoints():
    session, obj = fake_context(Segment((120, 250), (5870, 250)))
    assert curve_points(session, obj) == [[120, 250], [5870, 250]]


@pytest.mark.parametrize("end", [(0, 0), (0.0000005, -0.0000005)])
def test_closed_polycurve_closure_uses_native_coordinate_tolerance(end):
    session, obj = fake_context(PolyCurve([(0, 0), (5, 0), (5, 5), end]))
    assert curve_points(session, obj) == [[0, 0], [5, 0], [5, 5]]
