import pandas as pd
from pathlib import Path
from hronir_encyclopedia import graph_logic


def test_is_narrative_consistent(tmp_path: Path):
    fork_dir = tmp_path / "forking_path"
    fork_dir.mkdir()
    df = pd.DataFrame([
        {"position": 0, "prev_uuid": "", "uuid": "A", "fork_uuid": "fA"},
        {"position": 1, "prev_uuid": "A", "uuid": "B", "fork_uuid": "fB"},
        {"position": 2, "prev_uuid": "B", "uuid": "C", "fork_uuid": "fC"},
    ])
    df.to_csv(fork_dir / "path.csv", index=False)
    assert graph_logic.is_narrative_consistent(fork_dir)

    df_cycle = pd.DataFrame([
        {"position": 3, "prev_uuid": "C", "uuid": "A", "fork_uuid": "fX"},
    ])
    df_cycle.to_csv(fork_dir / "cycle.csv", index=False)
    assert not graph_logic.is_narrative_consistent(fork_dir)
