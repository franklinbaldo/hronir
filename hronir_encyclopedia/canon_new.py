import math
from typing import Any

from .models import Path as PathModel
from .storage import DataManager


def get_all_paths_graph(dm: DataManager) -> dict[str, list[PathModel]]:
    """
    Retrieves all paths and builds an adjacency list (parent_uuid -> list of child paths).
    parent_uuid is the hrönir UUID of the predecessor.
    """
    paths = dm.get_all_paths()
    graph: dict[str, list[PathModel]] = {}

    for path in paths:
        # Normalize parent UUID (handle None/empty for root)
        parent = str(path.prev_uuid) if path.prev_uuid else "root"
        if parent not in graph:
            graph[parent] = []
        graph[parent].append(path)

    return graph


def calculate_canonical_path(dm: DataManager) -> list[dict[str, Any]]:
    """
    Calculates the canonical path using Quadratic Influence.
    Returns a list of dicts with {'position': int, 'path_uuid': str, 'hrönir_uuid': str}.
    """
    paths = dm.get_all_paths()

    if not paths:
        return []

    # Map hrönir_uuid -> Path object (to find the path that introduced a hrönir)
    hronir_to_path: dict[str, PathModel] = {}
    for p in paths:
        hronir_to_path[str(p.uuid)] = p

    # Adjacency list: predecessor_hronir_uuid -> List[PathModel]
    # Key "root" for position 0 (where prev_uuid is None)
    graph: dict[str, list[PathModel]] = {}
    for p in paths:
        prev = str(p.prev_uuid) if p.prev_uuid else "root"
        if prev not in graph:
            graph[prev] = []
        graph[prev].append(p)

    # Calculate influence for every hrönir
    # Influence(H) = 1 + sqrt(count(children of H))
    influence_map: dict[str, float] = {}

    # We calculate influence for every hrönir known (those introduced by paths).
    for h_uuid in hronir_to_path.keys():
        children = graph.get(h_uuid, [])
        influence_map[h_uuid] = 1.0 + math.sqrt(len(children))

    # Traverse from root
    canonical_chain = []
    current_predecessor = "root"

    while True:
        candidates = graph.get(current_predecessor, [])
        if not candidates:
            break

        best_candidate = None
        best_score = -1.0

        # Determine the winner among candidates
        # Score(Candidate) = Sum( Influence(Child) ) for all Child of Candidate
        for candidate in candidates:
            candidate_hronir = str(candidate.uuid)

            # Children of this candidate
            children_paths = graph.get(candidate_hronir, [])

            score = 0.0
            # If a candidate has no children, its score is 0 based on children.
            # However, we need a base score or just rely on influence being 1.0 (from empty children).
            # If influence_map calculation assumes 1.0 + sqrt(0) = 1.0, then a leaf has influence 1.0.
            # But here we are summing influence of children.
            # If no children, sum is 0.
            # If all candidates are leaves (frontier), all scores are 0.
            # We need a tie-breaker or base score.
            # Let's say Score = Sum(Influence(Children)). If 0, use 0.

            for child_path in children_paths:
                child_hronir = str(child_path.uuid)
                weight = influence_map.get(child_hronir, 1.0)
                score += weight

            # Apply tie-breaking logic
            is_better = False
            if best_candidate is None:
                is_better = True
            elif score > best_score:
                is_better = True
            elif score == best_score:
                # Tie-breaker 1: Raw count of children (popularity)
                if len(children_paths) > len(graph.get(str(best_candidate.uuid), [])):
                    is_better = True
                elif len(children_paths) == len(graph.get(str(best_candidate.uuid), [])):
                    # Tie-breaker 2: Deterministic UUID string comparison (lexicographical asc)
                    # Or consistent creation order if available (timestamp?) - Path doesn't have timestamp.
                    # UUID is random but stable.
                    if str(candidate.path_uuid) < str(best_candidate.path_uuid):
                        is_better = True

            if is_better:
                best_score = score
                best_candidate = candidate

        if best_candidate:
            canonical_chain.append(
                {
                    "position": best_candidate.position,
                    "path_uuid": str(best_candidate.path_uuid),
                    "hrönir_uuid": str(best_candidate.uuid),
                }
            )
            current_predecessor = str(best_candidate.uuid)
        else:
            break

    return canonical_chain


def get_candidates_with_scores(
    dm: DataManager, position: int, predecessor_uuid: str | None = None
) -> list[dict[str, Any]]:
    """
    Returns candidates for a given position/predecessor with their scores.
    Useful for 'ranking' command.
    """
    paths = dm.get_all_paths()
    hronir_to_path = {str(p.uuid): p for p in paths}

    # Build graph
    graph: dict[str, list[PathModel]] = {}
    for p in paths:
        prev = str(p.prev_uuid) if p.prev_uuid else "root"
        if prev not in graph:
            graph[prev] = []
        graph[prev].append(p)

    # Calculate influence map
    influence_map: dict[str, float] = {}
    for h_uuid in hronir_to_path.keys():
        children = graph.get(h_uuid, [])
        influence_map[h_uuid] = 1.0 + math.sqrt(len(children))

    # Determine target predecessor.
    target_predecessor = predecessor_uuid

    if not target_predecessor:
        if position == 0:
            target_predecessor = "root"
        else:
            # Infer from canonical path
            canonical_chain = calculate_canonical_path(dm)
            # Find entry for position - 1
            prev_entry = next((e for e in canonical_chain if e["position"] == position - 1), None)
            if prev_entry:
                target_predecessor = prev_entry["hrönir_uuid"]
            else:
                # Cannot determine predecessor
                return []

    # If predecessor is not "root" and not in graph, check if it exists as a hrönir
    # (it might be a leaf node, so it won't be a key in graph if we iterate keys, but here we used prev_uuid as keys).
    # Wait, graph keys are PARENTS. So if predecessor is a valid parent, it should be in graph if it has children.
    # If it has no children, candidates list is empty.

    candidates = graph.get(target_predecessor, [])

    results = []
    for candidate in candidates:
        candidate_hronir = str(candidate.uuid)
        children_paths = graph.get(candidate_hronir, [])

        score = 0.0
        for child_path in children_paths:
            child_hronir = str(child_path.uuid)
            weight = influence_map.get(child_hronir, 1.0)
            score += weight

        results.append(
            {
                "path_uuid": str(candidate.path_uuid),
                "hrönir_uuid": str(candidate.uuid),
                "score": score,
                "continuations": len(children_paths),
            }
        )

    # Sort by score (desc), continuations (desc), path_uuid (asc)
    results.sort(key=lambda x: (-x["score"], -x["continuations"], x["path_uuid"]))

    return results
