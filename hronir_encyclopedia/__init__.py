"""Hr\u00f6nir Encyclopedia package."""

__all__ = ["__version__", "get_narrative_graph", "is_narrative_consistent"]
__version__ = "0.1.0"

from .graph_logic import get_narrative_graph, is_narrative_consistent
