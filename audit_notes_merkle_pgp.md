Security Audit: Merkle Trees & PGP Signatures (Pivot Plan v2.0)
Files Reviewed: transaction_manager.py, duckdb_storage.py
Plan Document: docs/pivot_plan_v2.md

Date: 2024-07-27

Overall Status:
- The concepts of Merkle trees for snapshot integrity & anti-Sybil measures, and PGP signatures for snapshot authenticity are well-defined in pivot_plan_v2.md.
- Current implementations in transaction_manager.py and duckdb_storage.py DO NOT yet include these security features. Implementation is pending.

Key Findings & Recommendations:

1.  Missing Implementations:
    -   No code for Merkle tree generation/validation (for snapshot integrity or anti-Sybil trust protocol) exists in the reviewed files.
    -   No code for PGP signing/verification of snapshots/manifests exists.
    -   Action: These are high-priority features for v2.0 and need full implementation.

2.  Proposed Location of Logic:
    -   SnapshotManifest (Merkle root, PGP signature): Logic for creation, signing, and Merkle root calculation should be part of snapshot generation, likely orchestrated by transaction_manager.py or a dedicated snapshot/conflict module.
    -   MerkleTrustProtocol (anti-Sybil): Should be a new module/class, interacting with DuckDB for local data and used during network discovery/sync operations.

3.  PGP Key Management:
    -   Plan mentions PGP keys in GitHub Actions secrets. This is good for automation.
    -   Need clear strategy for local CLI usage (e.g., GPG agent integration).
    -   Action: Document and implement secure PGP private key handling for both automated and local environments. Consider key rotation policies.

4.  Merkle Tree Details:
    -   Snapshot Integrity: Clearly define what data elements form the leaves of the snapshot's Merkle tree (e.g., hashes of individual tables, sorted rows, or sharded files). Ensure determinism.
    -   Trust Protocol: Hashing sorted hrönir UUIDs as planned seems reasonable.
    -   Action: Finalize and document the specifics of Merkle tree construction for both use cases.

5.  Verification Steps:
    -   PGP signature on SnapshotManifest must be verified upon fetching/receiving it.
    -   Snapshot Merkle root should be verified against downloaded data.
    -   Action: Integrate these verification steps into `hronir sync`, `discover`, and any snapshot processing workflows.

6.  Dependencies:
    -   PGP operations will likely require `python-gnupg` or `pgpy`.
    -   Action: Add necessary cryptographic libraries to `pyproject.toml`.

7.  Security of Manifest:
    -   The SnapshotManifest itself (containing sequence numbers, Merkle roots, PGP signature) becomes a critical piece of data. Its integrity and authenticity are paramount. The PGP signature on the manifest is key here.

End of Audit Notes.
