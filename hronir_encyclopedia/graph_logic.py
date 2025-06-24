import networkx as nx

from . import storage  # To access DataManager
from .models import Fork

ROOT_NODE = "__ROOT__"


def get_narrative_graph() -> nx.DiGraph:
    """Build a directed graph from Fork entries using pandas data manager."""
    G = nx.DiGraph()
    G.add_node(ROOT_NODE)
    
    data_manager = storage.DataManager()
    data_manager.initialize_and_load()
    
    all_forks = data_manager.get_all_forks()
    for fork in all_forks:
        # Handle prev_uuid, cur_uuid, and fork_uuid as strings
        prev_uuid_str = str(fork.prev_uuid) if fork.prev_uuid else None
        cur_uuid_str = str(fork.uuid)
        fork_uuid_str = str(fork.fork_uuid)
        
        if prev_uuid_str:
            G.add_edge(prev_uuid_str, cur_uuid_str, fork_uuid=fork_uuid_str)
        else:
            # If prev_uuid is None or empty, connect from ROOT_NODE
            G.add_edge(ROOT_NODE, cur_uuid_str, fork_uuid=fork_uuid_str)
    
    return G


def is_narrative_consistent() -> bool:
    """Return True if the narrative graph contains no cycles."""
    G = get_narrative_graph()
    return nx.is_directed_acyclic_graph(G)
