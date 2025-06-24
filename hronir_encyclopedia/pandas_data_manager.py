import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from pydantic import ValidationError

from .models import Fork, Transaction, Vote

UUID_NAMESPACE = uuid.NAMESPACE_URL


class PandasDataManager:
    """Pure pandas-based data manager for CSV operations."""
    
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        fork_csv_dir="the_garden",
        ratings_csv_dir="ratings", 
        transactions_json_dir="data/transactions",
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
            
        self.fork_csv_dir = Path(fork_csv_dir)
        self.ratings_csv_dir = Path(ratings_csv_dir)
        self.transactions_json_dir = Path(transactions_json_dir)
        
        # In-memory dataframes
        self._forks_df: Optional[pd.DataFrame] = None
        self._votes_df: Optional[pd.DataFrame] = None
        self._transactions: Dict[str, Transaction] = {}
        
        self._initialized = False
        
    def load_all_data(self):
        """Load all data from CSV files into memory."""
        self._load_forks()
        self._load_votes()
        self._load_transactions()
        self._initialized = True
        
    def _load_forks(self):
        """Load forks from CSV files."""
        fork_files = list(self.fork_csv_dir.glob("*.csv"))
        if not fork_files:
            self._forks_df = pd.DataFrame(columns=["fork_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"])
            return
            
        dfs = []
        for file_path in fork_files:
            if file_path.stat().st_size > 0:
                df = pd.read_csv(file_path)
                dfs.append(df)
                
        if dfs:
            self._forks_df = pd.concat(dfs, ignore_index=True)
        else:
            self._forks_df = pd.DataFrame(columns=["fork_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"])
            
    def _load_votes(self):
        """Load votes from CSV file."""
        votes_file = self.ratings_csv_dir / "votes.csv"
        if votes_file.exists() and votes_file.stat().st_size > 0:
            self._votes_df = pd.read_csv(votes_file)
        else:
            self._votes_df = pd.DataFrame(columns=["uuid", "position", "voter", "winner", "loser"])
            
    def _load_transactions(self):
        """Load transactions from JSON files."""
        self._transactions = {}
        if not self.transactions_json_dir.exists():
            return
            
        for json_file in self.transactions_json_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    transaction = Transaction(**data)
                    self._transactions[str(transaction.uuid)] = transaction
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"Error loading transaction {json_file}: {e}")
                
    def save_all_data(self):
        """Save all data back to CSV files."""
        self._save_forks()
        self._save_votes()
        self._save_transactions()
        
    def _save_forks(self):
        """Save forks to CSV files grouped by position."""
        if self._forks_df is None or self._forks_df.empty:
            return
            
        self.fork_csv_dir.mkdir(exist_ok=True)
        
        # Group by position and save each to its own file
        for position, group in self._forks_df.groupby("position"):
            file_path = self.fork_csv_dir / f"forking_paths_position_{position}.csv"
            group.to_csv(file_path, index=False)
            
    def _save_votes(self):
        """Save votes to CSV file."""
        if self._votes_df is None:
            return
            
        self.ratings_csv_dir.mkdir(exist_ok=True)
        votes_file = self.ratings_csv_dir / "votes.csv"
        self._votes_df.to_csv(votes_file, index=False)
        
    def _save_transactions(self):
        """Save transactions to JSON files."""
        if not self._transactions:
            return
            
        self.transactions_json_dir.mkdir(parents=True, exist_ok=True)
        
        for tx_uuid, transaction in self._transactions.items():
            file_path = self.transactions_json_dir / f"{tx_uuid}.json"
            with open(file_path, "w") as f:
                json.dump(transaction.model_dump(), f, indent=2, default=str)
                
    # --- Fork operations ---
    def get_all_forks(self) -> List[Fork]:
        """Get all forks as Pydantic models."""
        if self._forks_df is None or self._forks_df.empty:
            return []
            
        forks = []
        for _, row in self._forks_df.iterrows():
            try:
                fork = Fork(**row.to_dict())
                forks.append(fork)
            except ValidationError as e:
                print(f"Validation error for fork {row.get('fork_uuid', 'unknown')}: {e}")
                
        return forks
        
    def get_forks_by_position(self, position: int) -> List[Fork]:
        """Get forks at a specific position."""
        if self._forks_df is None or self._forks_df.empty:
            return []
            
        position_forks = self._forks_df[self._forks_df["position"] == position]
        forks = []
        
        for _, row in position_forks.iterrows():
            try:
                fork = Fork(**row.to_dict())
                forks.append(fork)
            except ValidationError as e:
                print(f"Validation error for fork {row.get('fork_uuid', 'unknown')}: {e}")
                
        return forks
        
    def add_fork(self, fork: Fork):
        """Add a new fork."""
        if self._forks_df is None:
            self._forks_df = pd.DataFrame(columns=["fork_uuid", "position", "prev_uuid", "uuid", "status", "mandate_id"])
            
        fork_data = fork.model_dump()
        new_row = pd.DataFrame([fork_data])
        self._forks_df = pd.concat([self._forks_df, new_row], ignore_index=True)
        
    def update_fork_status(self, fork_uuid: str, status: str):
        """Update fork status."""
        if self._forks_df is None:
            return
            
        mask = self._forks_df["fork_uuid"] == fork_uuid
        if mask.any():
            self._forks_df.loc[mask, "status"] = status
            
    # --- Vote operations ---
    def get_all_votes(self) -> List[Vote]:
        """Get all votes as Pydantic models."""
        if self._votes_df is None or self._votes_df.empty:
            return []
            
        votes = []
        for _, row in self._votes_df.iterrows():
            try:
                vote = Vote(**row.to_dict())
                votes.append(vote)
            except ValidationError as e:
                print(f"Validation error for vote {row.get('uuid', 'unknown')}: {e}")
                
        return votes
        
    def add_vote(self, vote: Vote):
        """Add a new vote."""
        if self._votes_df is None:
            self._votes_df = pd.DataFrame(columns=["uuid", "position", "voter", "winner", "loser"])
            
        vote_data = vote.model_dump()
        new_row = pd.DataFrame([vote_data])
        self._votes_df = pd.concat([self._votes_df, new_row], ignore_index=True)
        
    def get_votes_by_position(self, position: int) -> List[Vote]:
        """Get votes for a specific position."""
        if self._votes_df is None or self._votes_df.empty:
            return []
            
        position_votes = self._votes_df[self._votes_df["position"] == position]
        votes = []
        
        for _, row in position_votes.iterrows():
            try:
                vote = Vote(**row.to_dict())
                votes.append(vote)
            except ValidationError as e:
                print(f"Validation error for vote {row.get('uuid', 'unknown')}: {e}")
                
        return votes
        
    # --- Transaction operations ---
    def get_all_transactions(self) -> List[Transaction]:
        """Get all transactions."""
        return list(self._transactions.values())
        
    def add_transaction(self, transaction: Transaction):
        """Add a new transaction."""
        self._transactions[str(transaction.uuid)] = transaction
        
    def get_transaction(self, tx_uuid: str) -> Optional[Transaction]:
        """Get a specific transaction."""
        return self._transactions.get(tx_uuid)
        
    # --- Utility methods ---
    def initialize_if_needed(self):
        """Initialize data manager if not already done."""
        if not self._initialized:
            self.load_all_data()
            
    def __enter__(self):
        """Context manager entry."""
        self.initialize_if_needed()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save data."""
        self.save_all_data()