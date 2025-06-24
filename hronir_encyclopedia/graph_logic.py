# Remove Path and pd imports if no longer directly used for CSV reading
# from pathlib import Path
import networkx as nx
from sqlalchemy.orm import Session as SQLAlchemySession

# import pandas as pd # No longer reading CSVs here
# Import for DB access
from . import storage  # To access ForkDB and get_db_session

ROOT_NODE = "__ROOT__"


def get_narrative_graph(session: SQLAlchemySession | None = None) -> nx.DiGraph:
    """Build a directed graph from ForkDB entries in the database."""
    G = nx.DiGraph()
    G.add_node(ROOT_NODE)

    close_session_locally = False
    if session is None:
        session = storage.get_db_session()
        close_session_locally = True

    try:
        all_forks = session.query(storage.ForkDB).all()
        for fork_entry in all_forks:
            # Ensure prev_uuid, cur_uuid, and fork_uuid are strings, handling None for prev_uuid
            prev_uuid_str = str(fork_entry.prev_uuid) if fork_entry.prev_uuid else None
            cur_uuid_str = str(fork_entry.uuid)
            fork_uuid_str = str(fork_entry.fork_uuid)

            if prev_uuid_str:
                G.add_edge(prev_uuid_str, cur_uuid_str, fork_uuid=fork_uuid_str)
            else:
                # If prev_uuid is None or empty (should be None from DB if root), connect from ROOT_NODE
                G.add_edge(ROOT_NODE, cur_uuid_str, fork_uuid=fork_uuid_str)
        return G
    finally:
        if close_session_locally and session is not None:
            session.close()


def is_narrative_consistent(session: SQLAlchemySession | None = None) -> bool:
    """Return True if the narrative graph (from DB) contains no cycles."""
    G = get_narrative_graph(session=session)
    return nx.is_directed_acyclic_graph(G)
