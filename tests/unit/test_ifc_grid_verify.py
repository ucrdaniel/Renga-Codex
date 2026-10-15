"""Independent narrow IFC-export fixtures; no Renga or user fixture required."""
from copy import deepcopy

import pytest

from renga_codex_bridge.ifc_grid_verify import (
    GridExportVerificationError, decode_step_string, verify_exported_grid,
)


def grid():
    return {"x": [{"name": "1", "position_mm": 0}],
            "y": [{"name": "A", "position_mm": 0}],
            "bounds_mm": [-1000, -1000, 7000, 7000]}


def exported():
    # Authored independently of the seed generator. The second unassigned
    # metre unit reproduces Renga exports that use it for a derived material
    # property; only the project's unit assignment determines coordinates.
    return """ISO-10303-21;
HEADER;
FILE_NAME('literal;with,comma','',(),(),'','','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCCARTESIANPOINT((0.,0.,0.));
#2=IFCDIRECTION((0.,0.,1.));
#3=IFCDIRECTION((1.,0.,0.));
#4=IFCAXIS2PLACEMENT3D(#1,#2,#3);
#5=IFCGEOMETRICREPRESENTATIONCONTEXT('Model','Model',3,0.000001,#4,$);
#6=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);
#7=IFCUNITASSIGNMENT((#6));
#8=IFCPROJECT('own',$,'Own project',$,$,$,$,(#5),#7);
#9=IFCLOCALPLACEMENT($,#4);
#11=IFCCARTESIANPOINT((0.,0.,0.));
#12=IFCAXIS2PLACEMENT3D(#11,#2,#3);
#14=IFCLOCALPLACEMENT(#9,#12);
#20=IFCCARTESIANPOINTLIST2D(((0.,-1000.),(0.,7000.)));
#21=IFCINDEXEDPOLYCURVE(#20,$,$);
#22=IFCGRIDAXIS('1',#21,.T.);
#23=IFCCARTESIANPOINTLIST2D(((-1000.,0.),(7000.,0.)));
#24=IFCINDEXEDPOLYCURVE(#23,$,.F.);
#25=IFCGRIDAXIS('A',#24,.F.);
#30=IFCGRID('grid',$,$,$,$,#14,$,(#25),(#22),$,$);
#40=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
ENDSEC;
END-ISO-10303-21;
"""


def test_correct_native_export_subset_matches_and_reports_provenance_boundary():
    requested = grid()
    before = deepcopy(requested)
    result = verify_exported_grid(exported(), requested)
    assert requested == before
    assert result["status"] == "passed"
    assert result["axis_count"] == 2
    assert result["axes"][0]["endpoints_mm"] == [[0, -1000], [0, 7000]]
    assert result["direct_axis_com_geometry_getter"] is False
    assert result["export_provenance_verified_by_this_reader"] is False


def test_endpoints_can_be_reversed_independently_of_same_sense():
    text = exported().replace("((0.,-1000.),(0.,7000.))", "((0.,7000.),(0.,-1000.))")
    assert verify_exported_grid(text, grid())["status"] == "passed"


def test_translations_are_resolved_across_placement_chain():
    text = exported().replace("#11=IFCCARTESIANPOINT((0.,0.,0.))", "#11=IFCCARTESIANPOINT((100.,200.,0.))")
    text = text.replace("((0.,-1000.),(0.,7000.))", "((-100.,-1200.),(-100.,6800.))")
    text = text.replace("((-1000.,0.),(7000.,0.))", "((-1100.,-200.),(6900.,-200.))")
    assert verify_exported_grid(text, grid())["axes"][0]["endpoints_mm"] == [[0, -1000], [0, 7000]]


def test_polyline_variant_checks_real_2d_point_references():
    text = exported().replace("#21=IFCINDEXEDPOLYCURVE(#20,$,$)", "#21=IFCPOLYLINE((#50,#51))")
    text = text.replace("#40=", "#50=IFCCARTESIANPOINT((0.,-1000.));\n#51=IFCCARTESIANPOINT((0.,7000.));\n#40=")
    assert verify_exported_grid(text, grid())["status"] == "passed"


@pytest.mark.parametrize("literal,expected", [
    ("'O''Brien;A'", "O'Brien;A"),
    (r"'\X2\04100411\X0\'", "АБ"),
    (r"'\X4\0001F600\X0\'", "😀"),
    (r"'\X2\D83DDE00\X0\'", "😀"),
    (r"'slash\X2\005C\X0\'", "slash\\"),
])
def test_step_label_decoding(literal, expected):
    assert decode_step_string(literal) == expected


def test_unicode_labels_and_doubled_apostrophes_match_exact_request():
    text = exported()
    text = text.replace("IFCGRIDAXIS('1'", "IFCGRIDAXIS('O''Brien;A'")
    text = text.replace("IFCGRIDAXIS('A'", r"IFCGRIDAXIS('\X2\0410\X0\'")
    request = grid()
    request["x"][0]["name"] = "O'Brien;A"
    request["y"][0]["name"] = "А"
    assert verify_exported_grid(text, request)["axis_count"] == 2


@pytest.mark.parametrize("literal", ["A", "'A'B'", r"'\S\A'", r"'\X2\0\X0\'",
                                     r"'\X2\ZZZZ\X0\'", r"'\X2\D800\X0\'",
                                     r"'\X4\00110000\X0\'", r"'\X2\0085\X0\'",
                                     r"'\X2\0041'", "'A\nB'"])
def test_unknown_malformed_or_control_string_encodings_rejected(literal):
    with pytest.raises(GridExportVerificationError):
        decode_step_string(literal)


@pytest.mark.parametrize("old,new", [
    (".MILLI.,.METRE.", "$,.METRE."),
    ("IFCUNITASSIGNMENT((#6))", "IFCUNITASSIGNMENT((#6,#40))"),
    ("#6=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)", "#6=IFCCONVERSIONBASEDUNIT($,.LENGTHUNIT.,'mm',$)"),
    ("IFCGRIDAXIS('A'", "IFCGRIDAXIS('1'"),
    ("IFCGRIDAXIS('A'", "IFCGRIDAXIS('unexpected'"),
    ("((0.,-1000.),(0.,7000.))", "((0.,-1000.),(0.,6999.))"),
    ("((0.,-1000.),(0.,7000.))", "((1.,-1000.),(1.,7000.))"),
    ("((0.,-1000.),(0.,7000.))", "((0.,-1000.,0.),(0.,7000.,0.))"),
    ("((0.,-1000.),(0.,7000.))", "((0.,-1000.),(0.,1000.),(0.,7000.))"),
    ("IFCINDEXEDPOLYCURVE(#20,$,$)", "IFCCIRCLE(#20,1.)"),
    ("IFCINDEXEDPOLYCURVE(#20,$,$)", "IFCINDEXEDPOLYCURVE(#20,(IFCARCINDEX((1,2,3))),$)"),
    ("IFCINDEXEDPOLYCURVE(#20,$,$)", "IFCINDEXEDPOLYCURVE(#20,$,.T.)"),
    ("IFCLOCALPLACEMENT(#9,#12)", "IFCLOCALPLACEMENT(#14,#12)"),
    ("#11=IFCCARTESIANPOINT((0.,0.,0.))", "#11=IFCCARTESIANPOINT((0.,0.,3000.))"),
    ("#12=IFCAXIS2PLACEMENT3D(#11,#2,#3)", "#12=IFCAXIS2PLACEMENT3D(#11,#2,#2)"),
    ("IFCLOCALPLACEMENT(#9,#12)", "IFCLOCALPLACEMENT(#404,#12)"),
    ("(#25),(#22),$,$", "(#25),(#22,#22),$,$"),
    ("(#25),(#22),$,$", "(),(#22),$,$"),
    ("(#25),(#22),$,$", "(#25),(#22),(#25),$"),
    ("FILE_SCHEMA(('IFC4'))", "FILE_SCHEMA(('IFC2X3'))"),
    ("END-ISO-10303-21;", ""),
    ("(#5),#7", "(),#7"),
])
def test_fail_closed_for_wrong_values_units_geometry_and_transforms(old, new):
    assert old in exported()
    with pytest.raises(GridExportVerificationError):
        verify_exported_grid(exported().replace(old, new), grid())


def test_unassigned_extra_axis_is_not_ignored():
    text = exported().replace("#40=", "#41=IFCGRIDAXIS('Extra',#21,.T.);\n#40=")
    with pytest.raises(GridExportVerificationError, match="Unassigned"):
        verify_exported_grid(text, grid())


def test_missing_requested_axis_is_rejected_even_if_other_axes_are_valid():
    requested = grid()
    requested["x"].append({"name": "2", "position_mm": 3000})
    with pytest.raises(GridExportVerificationError, match="missing"):
        verify_exported_grid(exported(), requested)


def test_submicrometre_tolerance_has_no_relative_error_shortcut():
    text = exported().replace("7000.))", "7000.0000001))")
    assert verify_exported_grid(text, grid())["status"] == "passed"
    with pytest.raises(GridExportVerificationError):
        verify_exported_grid(text.replace("7000.0000001", "7000.00001"), grid())
