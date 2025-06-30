import json
import uuid
from pathlib import Path
import logging
import os # <--- Added import os

import pandas as pd
from pydantic import ValidationError

from .models import Path as PathModel
from .models import Transaction, Vote

UUID_NAMESPACE = uuid.NAMESPACE_URL
logger = logging.getLogger(__name__)

class PandasDataManager:
    """Pure pandas-based data manager for CSV operations."""

    _instance = None
    EXPECTED_PATH_COLUMNS = ["path_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"]
    EXPECTED_VOTE_COLUMNS = ["uuid", "position", "voter", "winner", "loser"]


    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        path_csv_dir=None,
        ratings_csv_dir=None,
        transactions_json_dir=None,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return

        _path_csv_dir_str = os.getenv("HRONIR_NARRATIVE_PATHS_DIR", "narrative_paths")
        _ratings_csv_dir_str = os.getenv("HRONIR_RATINGS_DIR", "ratings")
        _transactions_json_dir_str = os.getenv("HRONIR_TRANSACTIONS_DIR", "data/transactions")

        self.path_csv_dir = Path(path_csv_dir if path_csv_dir is not None else _path_csv_dir_str)
        self.ratings_csv_dir = Path(ratings_csv_dir if ratings_csv_dir is not None else _ratings_csv_dir_str)
        self.transactions_json_dir = Path(transactions_json_dir if transactions_json_dir is not None else _transactions_json_dir_str)

        self.path_csv_dir.mkdir(parents=True, exist_ok=True)
        self.ratings_csv_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_json_dir.mkdir(parents=True, exist_ok=True)

        self._paths_df: pd.DataFrame | None = None
        self._votes_df: pd.DataFrame | None = None
        self._transactions: dict[str, Transaction] = {}
        self._initialized = False
        logger.debug(f"PandasDataManager initialized with paths: {self.path_csv_dir}, {self.ratings_csv_dir}, {self.transactions_json_dir}")


    def _clear_data_files_and_reset_dfs(self):
        logger.info("Clearing data files and resetting DataFrames.")

        if self.path_csv_dir.exists():
            for f_path in self.path_csv_dir.glob("narrative_paths_position_*.csv"):
                try:
                    f_path.unlink()
                    logger.debug(f"Deleted path CSV: {f_path}")
                except OSError as e:
                    logger.error(f"Error deleting path CSV {f_path}: {e}")

        votes_file = self.ratings_csv_dir / "votes.csv"
        if votes_file.exists():
            try:
                votes_file.unlink()
                logger.debug(f"Deleted votes CSV: {votes_file}")
            except OSError as e:
                logger.error(f"Error deleting votes CSV {votes_file}: {e}")

        self._paths_df = pd.DataFrame(columns=self.EXPECTED_PATH_COLUMNS)
        self._votes_df = pd.DataFrame(columns=self.EXPECTED_VOTE_COLUMNS)
        self._transactions = {}

    def load_all_data(self, clear_existing_data: bool = False):
        if clear_existing_data:
            self._clear_data_files_and_reset_dfs()

        self._load_paths_from_csv()
        self._load_votes_from_csv()
        self._load_transactions_from_json()
        self._initialized = True
        logger.info("All data loaded into PandasDataManager.")

    def _load_paths_from_csv(self):
        all_path_dfs = []
        if not self.path_csv_dir.exists():
            logger.warning(f"Path CSV directory not found: {self.path_csv_dir}")
            self.path_csv_dir.mkdir(parents=True, exist_ok=True)

        for file_path in self.path_csv_dir.glob("narrative_paths_position_*.csv"):
            try:
                if file_path.stat().st_size > 0:
                    dtype_map = {
                        "position": int, "path_uuid": str, "prev_uuid": str,
                        "uuid": str, "status": str, "mandate_id": str
                    }
                    df = pd.read_csv(file_path, dtype=dtype_map, keep_default_na=False, na_values=[''])
                    all_path_dfs.append(df)
                else:
                    logger.debug(f"Skipping empty path CSV: {file_path}")
            except pd.errors.EmptyDataError:
                logger.warning(f"Pandas EmptyDataError for {file_path}, skipping.")
            except Exception as e:
                logger.error(f"Error loading path data from {file_path}: {e}")

        if all_path_dfs:
            self._paths_df = pd.concat(all_path_dfs, ignore_index=True)
            for col in self.EXPECTED_PATH_COLUMNS:
                if col not in self._paths_df.columns:
                    if col == "position": self._paths_df[col] = -1
                    else: self._paths_df[col] = ""
            for col in ["prev_uuid", "mandate_id"]:
                if col in self._paths_df.columns:
                     self._paths_df[col] = self._paths_df[col].replace({"": None})
        else:
            self._paths_df = pd.DataFrame(columns=self.EXPECTED_PATH_COLUMNS)
        logger.debug(f"Loaded {len(self._paths_df) if self._paths_df is not None else 0} paths.")


    def _load_votes_from_csv(self):
        votes_file = self.ratings_csv_dir / "votes.csv"
        if votes_file.exists() and votes_file.stat().st_size > 0:
            try:
                dtype_map = {
                    "uuid": str, "position": int, "voter": str, "winner": str, "loser": str
                }
                self._votes_df = pd.read_csv(votes_file, dtype=dtype_map, keep_default_na=False, na_values=[''])
            except pd.errors.EmptyDataError:
                logger.warning(f"Votes CSV {votes_file} is empty, initializing empty DataFrame.")
                self._votes_df = pd.DataFrame(columns=self.EXPECTED_VOTE_COLUMNS)
            except Exception as e:
                logger.error(f"Error loading votes from {votes_file}: {e}")
                self._votes_df = pd.DataFrame(columns=self.EXPECTED_VOTE_COLUMNS)
        else:
            logger.info(f"Votes CSV not found or empty: {votes_file}. Initializing empty DataFrame.")
            self._votes_df = pd.DataFrame(columns=self.EXPECTED_VOTE_COLUMNS)
        logger.debug(f"Loaded {len(self._votes_df) if self._votes_df is not None else 0} votes.")

    def _load_transactions_from_json(self):
        self._transactions = {}
        if not self.transactions_json_dir.exists():
            logger.warning(f"Transactions directory not found: {self.transactions_json_dir}")
            self.transactions_json_dir.mkdir(parents=True, exist_ok=True)
            return

        for json_file in self.transactions_json_dir.glob("*.json"):
            try:
                transaction_data = json.loads(json_file.read_text())
                transaction_model = Transaction(**transaction_data)
                self._transactions[str(transaction_model.uuid)] = transaction_model
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(f"Error loading transaction {json_file.name}: {e}")
        logger.debug(f"Loaded {len(self._transactions)} transactions.")

    def save_all_data(self):
        logger.info("Saving all Pandas data...")
        self.save_paths_to_csv()
        self.save_votes_to_csv()
        self._save_transactions_to_json()
        logger.info("All Pandas data saved.")

    def save_paths_to_csv(self):
        if self._paths_df is None:
            logger.warning("Paths DataFrame is None. Cannot save paths to CSV.")
            return

        self.path_csv_dir.mkdir(parents=True, exist_ok=True)

        if "position" not in self._paths_df.columns and not self._paths_df.empty:
            logger.error("Critical: 'position' column missing in paths_df. Saving all paths to undifferentiated CSV.")
            output_file = self.path_csv_dir / "narrative_paths_all_undifferentiated.csv"
            try:
                self._paths_df.to_csv(output_file, index=False)
                logger.info(f"Saved all paths (due to missing position column) to {output_file}")
            except Exception as e:
                logger.error(f"Error saving undifferentiated paths to {output_file}: {e}")
            return
        elif self._paths_df.empty:
             logger.info("Paths DataFrame is empty. No paths to save.")
             for old_file in self.path_csv_dir.glob("narrative_paths_position_*.csv"):
                 old_file.write_text(",".join(self.EXPECTED_PATH_COLUMNS) + "\n")
             return

        df_to_save = self._paths_df.copy()
        for col in self.EXPECTED_PATH_COLUMNS:
            if col not in df_to_save.columns:
                df_to_save[col] = None if col in ["prev_uuid", "mandate_id"] else ""

        for col in ["prev_uuid", "mandate_id"]:
            if col in df_to_save.columns:
                 df_to_save[col] = df_to_save[col].fillna("")

        for col in df_to_save.columns:
            if df_to_save[col].dtype == 'object':
                df_to_save[col] = df_to_save[col].astype(str).fillna("")

        grouped = df_to_save.groupby("position")
        existing_files = set(self.path_csv_dir.glob("narrative_paths_position_*.csv"))

        for position_val, group_df in grouped:
            output_file = self.path_csv_dir / f"narrative_paths_position_{int(position_val):03d}.csv"
            try:
                ordered_group_df = group_df.reindex(columns=self.EXPECTED_PATH_COLUMNS, fill_value="")
                ordered_group_df.to_csv(output_file, index=False)
                logger.info(f"Saved {len(ordered_group_df)} paths for position {position_val} to {output_file}")
                if output_file in existing_files:
                    existing_files.remove(output_file)
            except Exception as e:
                logger.error(f"Error saving paths for position {position_val} to {output_file}: {e}")

        for old_file in existing_files:
            logger.info(f"Position formerly in {old_file.name} no longer has paths. Writing header-only file.")
            old_file.write_text(",".join(self.EXPECTED_PATH_COLUMNS) + "\n")

    def save_votes_to_csv(self):
        if self._votes_df is None:
            logger.warning("Votes DataFrame is None. Cannot save votes to CSV.")
            return

        self.ratings_csv_dir.mkdir(parents=True, exist_ok=True)
        votes_file = self.ratings_csv_dir / "votes.csv"

        if self._votes_df.empty:
            logger.info("Votes DataFrame is empty. Writing header-only CSV.")
            votes_file.write_text(",".join(self.EXPECTED_VOTE_COLUMNS) + "\n")
        else:
            df_to_save = self._votes_df.copy()
            for col in self.EXPECTED_VOTE_COLUMNS:
                if col not in df_to_save.columns:
                     df_to_save[col] = ""

            for col in df_to_save.columns:
                 df_to_save[col] = df_to_save[col].astype(str).fillna("")

            try:
                ordered_df = df_to_save.reindex(columns=self.EXPECTED_VOTE_COLUMNS, fill_value="")
                ordered_df.to_csv(votes_file, index=False)
                logger.info(f"Saved {len(ordered_df)} votes to {votes_file}")
            except Exception as e:
                logger.error(f"Error saving votes to {votes_file}: {e}")

    def _save_transactions_to_json(self):
        if not self._transactions:
            logger.info("No transactions in memory to save.")
            return

        self.transactions_json_dir.mkdir(parents=True, exist_ok=True)
        for tx_uuid_str, transaction_model in self._transactions.items():
            file_path = self.transactions_json_dir / f"{tx_uuid_str}.json"
            try:
                file_path.write_text(transaction_model.model_dump_json(indent=2))
                logger.debug(f"Saved transaction {tx_uuid_str} to {file_path}")
            except Exception as e:
                logger.error(f"Error saving transaction {tx_uuid_str} to {file_path}: {e}")

    def get_all_paths(self) -> list[PathModel]:
        if self._paths_df is None or self._paths_df.empty:
            return []

        path_models = []
        for _, row in self._paths_df.iterrows():
            try:
                row_dict = row.to_dict()
                for key in ["prev_uuid", "mandate_id"]:
                    if key in row_dict and pd.isna(row_dict[key]):
                        row_dict[key] = None
                path_models.append(PathModel(**row_dict))
            except ValidationError as e:
                logger.warning(f"Validation error for path data {row.to_dict()}: {e}")
        return path_models

    def get_paths_by_position(self, position: int) -> list[PathModel]:
        if self._paths_df is None or self._paths_df.empty or "position" not in self._paths_df.columns:
            return []

        position_df = self._paths_df[self._paths_df["position"] == position]
        path_models = []
        for _, row in position_df.iterrows():
            try:
                row_dict = row.to_dict()
                for key in ["prev_uuid", "mandate_id"]:
                    if key in row_dict and pd.isna(row_dict[key]):
                        row_dict[key] = None
                path_models.append(PathModel(**row_dict))
            except ValidationError as e:
                logger.warning(f"Validation error for path data at position {position} {row.to_dict()}: {e}")
        return path_models

    def add_path(self, path: PathModel):
        if self._paths_df is None:
            self._paths_df = pd.DataFrame(columns=self.EXPECTED_PATH_COLUMNS)

        path_dict = path.model_dump(mode='json')
        for key in ["prev_uuid", "mandate_id"]:
            if path_dict[key] is None:
                path_dict[key] = ""

        new_row_df = pd.DataFrame([path_dict])

        if self._paths_df.empty:
            self._paths_df = new_row_df
        else:
            self._paths_df = pd.concat([self._paths_df, new_row_df], ignore_index=True)

    def update_path_status(
        self,
        path_uuid: str,
        status: str,
        mandate_id: str | None = None,
        set_mandate_explicitly: bool = False
    ):
        """Update path status and optionally mandate_id."""
        if self._paths_df is None or self._paths_df.empty:
            logger.warning(f"Paths DataFrame is empty or None. Cannot update status for {path_uuid}.")
            print(f"DEBUG PANDAS_DM: update_path_status CALLED for {path_uuid} to {status} BUT DF IS EMPTY/NONE")
            return

        print(f"DEBUG PANDAS_DM: update_path_status CALLED for {path_uuid} to {status}. set_mandate_explicitly={set_mandate_explicitly}, mandate_id='{mandate_id}'")
        mask = self._paths_df["path_uuid"] == str(path_uuid)
        if mask.any():
            path_idx = self._paths_df[mask].index
            self._paths_df.loc[path_idx, "status"] = status
            logger.info(f"PandasDM: Updated status of path {path_uuid} to {status}.")
            print(f"DEBUG PANDAS_DM: Successfully updated status for {path_uuid} to {status} in DF.")
            if set_mandate_explicitly:
                new_mandate_val = mandate_id if mandate_id is not None else ""
                self._paths_df.loc[path_idx, "mandate_id"] = new_mandate_val
                logger.info(f"PandasDM: Set mandate_id for path {path_uuid} to '{new_mandate_val}'.")
                print(f"DEBUG PANDAS_DM: Successfully updated mandate_id for {path_uuid} to '{new_mandate_val}' in DF.")
        else:
            logger.warning(f"PandasDM: Path with UUID {path_uuid} not found. Cannot update status.")
            print(f"DEBUG PANDAS_DM: Path {path_uuid} NOT FOUND in DF for status update.")

    def get_all_votes(self) -> list[Vote]:
        if self._votes_df is None or self._votes_df.empty:
            return []
        vote_models = []
        for _, row in self._votes_df.iterrows():
            try:
                vote_models.append(Vote(**row.to_dict()))
            except ValidationError as e:
                 logger.warning(f"Validation error for vote data {row.to_dict()}: {e}")
        return vote_models

    def add_vote(self, vote: Vote):
        if self._votes_df is None:
            self._votes_df = pd.DataFrame(columns=self.EXPECTED_VOTE_COLUMNS)

        vote_dict = vote.model_dump(mode='json')
        new_row_df = pd.DataFrame([vote_dict])

        if self._votes_df.empty:
            self._votes_df = new_row_df
        else:
            self._votes_df = pd.concat([self._votes_df, new_row_df], ignore_index=True)

    def get_votes_by_position(self, position: int) -> list[Vote]:
        if self._votes_df is None or self._votes_df.empty or "position" not in self._votes_df.columns:
            return []

        position_df = self._votes_df[self._votes_df["position"] == position]
        vote_models = []
        for _, row in position_df.iterrows():
            try:
                vote_models.append(Vote(**row.to_dict()))
            except ValidationError as e:
                logger.warning(f"Validation error for vote data at pos {position} {row.to_dict()}: {e}")
        return vote_models

    def get_all_transactions(self) -> list[Transaction]:
        return list(self._transactions.values())

    def add_transaction(self, transaction: Transaction):
        self._transactions[str(transaction.uuid)] = transaction

    def get_transaction(self, tx_uuid: str) -> Transaction | None:
        return self._transactions.get(str(tx_uuid))

    def initialize_if_needed(self):
        if not self._initialized:
            self.load_all_data()

    def clear_in_memory_data(self):
        self._clear_data_files_and_reset_dfs()
        self._initialized = False

    def __enter__(self):
        self.initialize_if_needed()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save_all_data()
