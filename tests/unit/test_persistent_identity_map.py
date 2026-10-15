"""Identity verification must bind each native name to its own persistent UUID."""
import pytest

from renga_codex_bridge.level_projects import identity_map


FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"


def rows():
    return [{"name": "Этаж 1", "uuid": FIRST}, {"name": "Этаж 2", "uuid": SECOND}]


def test_maps_names_to_persistent_ids_instead_of_only_comparing_id_set():
    original = rows()
    swapped = [{"name": "Этаж 1", "uuid": SECOND}, {"name": "Этаж 2", "uuid": FIRST}]
    assert {row["uuid"] for row in original} == {row["uuid"] for row in swapped}
    assert identity_map(original) != identity_map(swapped)


def test_inventory_order_and_local_numeric_ids_do_not_change_persistent_mapping():
    original = rows()
    reordered = [dict(original[1], id=8000), dict(original[0], id=9000)]
    assert identity_map(original) == identity_map(reordered)
    assert identity_map(original) == {"Этаж 1": FIRST, "Этаж 2": SECOND}


@pytest.mark.parametrize("bad_uuid", [None, "", "not-a-uuid", "11111111", 42,
                                      "00000000-0000-0000-0000-000000000000"])
def test_rejects_invalid_or_nil_native_identity(bad_uuid):
    with pytest.raises(RuntimeError, match="persistent identity"):
        identity_map([{"name": "Native", "uuid": bad_uuid}])


@pytest.mark.parametrize("duplicate", [FIRST, "{" + FIRST + "}"])
def test_duplicate_uuid_is_rejected_even_when_names_differ(duplicate):
    with pytest.raises(RuntimeError, match="Duplicate"):
        identity_map([{"name": "1", "uuid": FIRST}, {"name": "A", "uuid": duplicate}])


def test_empty_axis_inventory_has_empty_map_for_no_grid_bootstrap():
    assert identity_map([]) == {}
