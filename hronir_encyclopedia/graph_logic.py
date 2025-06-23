from pathlib import Path

import networkx as nx
import pandas as pd

ROOT_NODE = "__ROOT__"


def get_narrative_graph(forking_path_dir: Path = Path("forking_path")) -> nx.DiGraph:
    """Read forking_path CSVs and build a directed graph."""
    G = nx.DiGraph()
    G.add_node(ROOT_NODE)
    if not forking_path_dir.is_dir():
        return G
    for csv_file in forking_path_dir.glob("*.csv"):
        if csv_file.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(csv_file, dtype=str)
        except Exception:
            continue
        for _, row in df.iterrows():
            prev_uuid = str(row.get("prev_uuid", ""))
            cur_uuid = str(row.get("uuid", ""))
            fork_uuid = str(row.get("fork_uuid", ""))
            if prev_uuid:
                G.add_edge(prev_uuid, cur_uuid, fork_uuid=fork_uuid)
            else:
                G.add_edge(ROOT_NODE, cur_uuid, fork_uuid=fork_uuid)
    return G


def is_narrative_consistent(forking_path_dir: Path = Path("forking_path")) -> bool:
    """Return True if the narrative graph contains no cycles."""
    G = get_narrative_graph(forking_path_dir)
    return nx.is_directed_acyclic_graph(G)
