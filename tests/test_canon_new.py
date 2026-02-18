import uuid
from unittest.mock import MagicMock

import pytest

from hronir_encyclopedia.canon_new import calculate_canonical_path
from hronir_encyclopedia.models import Path as PathModel

NAMESPACE = uuid.NAMESPACE_URL

def to_uuid5(val):
    if not val:
        return None
    return str(uuid.uuid5(NAMESPACE, val))

# Helper to create paths easily
def create_path(path_key, position, prev_key, hronir_key):
    return PathModel(
        path_uuid=to_uuid5(path_key),
        position=position,
        prev_uuid=to_uuid5(prev_key),
        uuid=to_uuid5(hronir_key),
        status="PENDING"
    )

@pytest.fixture
def mock_dm():
    dm = MagicMock()
    return dm

def test_simple_chain(mock_dm):
    # Root -> A -> B
    paths = [
        create_path("p0", 0, None, "a"),
        create_path("p1", 1, "a", "b")
    ]
    mock_dm.get_all_paths.return_value = paths

    canon = calculate_canonical_path(mock_dm)

    assert len(canon) == 2
    assert canon[0]['hrönir_uuid'] == to_uuid5("a")
    assert canon[1]['hrönir_uuid'] == to_uuid5("b")

def test_fork_simple_majority(mock_dm):
    # Root -> A
    # A -> B (0 children)
    # A -> C (2 children D, E)

    # C should win over B because C has children (Influence > 1) and B has none (Influence 1).
    # Wait, my logic: Influence(Child) = 1 + sqrt(count).
    # B has 0 children. Influence(B) = 1.
    # C has 2 children (D, E). Influence(C) = 1 + sqrt(2) ≈ 2.41.
    # Score(A) depends on B and C? No, Score(A) depends on ITS children.
    # A is the winner at pos 0.
    # Candidates for Pos 1 are children of A: B and C.
    # We compare Score(B) and Score(C).
    # Score(B) = Sum(Influence(children of B)).
    # B has 0 children. Sum = 0.
    # Score(C) = Sum(Influence(children of C)).
    # Children of C are D, E.
    # D is leaf. Influence(D) = 1.
    # E is leaf. Influence(E) = 1.
    # Score(C) = 1 + 1 = 2.
    # C wins (2 > 0).

    paths = [
        create_path("p0", 0, None, "a"),
        create_path("p1_b", 1, "a", "b"),
        create_path("p1_c", 1, "a", "c"),
        create_path("p2_d", 2, "c", "d"),
        create_path("p2_e", 2, "c", "e"),
    ]
    mock_dm.get_all_paths.return_value = paths

    canon = calculate_canonical_path(mock_dm)

    # Expect A -> C -> D/E
    # D vs E at pos 2. Both score 0. Tie.
    # Tie-breaker: len(children) -> 0 vs 0.
    # Tie-breaker: path_uuid. "p2_d" vs "p2_e".
    # uuid5("p2_d") vs uuid5("p2_e").
    # We need to know which is smaller.

    assert len(canon) == 3
    assert canon[0]['hrönir_uuid'] == to_uuid5("a")
    assert canon[1]['hrönir_uuid'] == to_uuid5("c")

    winner_pos2 = canon[2]['hrönir_uuid']
    assert winner_pos2 in [to_uuid5("d"), to_uuid5("e")]

def test_quadratic_influence(mock_dm):
    # Root -> A
    # A -> B (10 leaf children)
    # A -> C (4 leaf children)

    # Score(B) = 10 * 1 = 10.
    # Score(C) = 4 * 1 = 4.
    # B wins.

    paths = [create_path("p0", 0, None, "a")]

    # B branch
    paths.append(create_path("p1_b", 1, "a", "b"))
    for i in range(10):
        paths.append(create_path(f"p2_b_{i}", 2, "b", f"leaf_b_{i}"))

    # C branch
    paths.append(create_path("p1_c", 1, "a", "c"))
    for i in range(4):
        paths.append(create_path(f"p2_c_{i}", 2, "c", f"leaf_c_{i}"))

    mock_dm.get_all_paths.return_value = paths

    canon = calculate_canonical_path(mock_dm)

    assert canon[1]['hrönir_uuid'] == to_uuid5("b")
