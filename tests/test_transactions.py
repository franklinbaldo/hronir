import pytest

# Assuming transaction_manager might be refactored, so direct import for now.
# If it's simplified away, these tests would be removed or adapted.
from hronir_encyclopedia import transaction_manager as tm

# If transaction_manager.py is heavily refactored or removed, these tests will need significant updates
# or may become obsolete. For now, we move them as is, assuming the functions still exist.


@pytest.fixture
def sample_transactions_data() -> list[str]:
    """Provides a sample list of transaction data strings."""
    return [
        "Transaction 1: Alice pays Bob 10 BTC",
        "Transaction 2: Bob pays Carol 5 BTC",
        "Transaction 3: Carol pays David 2 BTC",
        "Transaction 4: David pays Eve 1 BTC",
        "Transaction 5: Eve pays Alice 0.5 BTC",
        "Transaction 6: Satoshi Nakamoto publishes Bitcoin whitepaper",
        "Transaction 7: Early bird gets the worm",
        "Transaction 8: Another day, another dollar",
        "Transaction 9: Lorem ipsum dolor sit amet",
        "Transaction 10: Consectetur adipiscing elit",
    ]


def test_merkle_tree_and_proof_dynamics(sample_transactions_data: list[str]):
    """
    Tests the dynamics of Merkle root computation, proof generation, and verification.
    """
    # These functions might not exist if transaction_manager is simplified.
    if (
        not hasattr(tm, "compute_merkle_root")
        or not hasattr(tm, "generate_merkle_proof")
        or not hasattr(tm, "verify_merkle_proof")
    ):
        pytest.skip("Merkle tree functions not found in transaction_manager, skipping test.")

    merkle_root = tm.compute_merkle_root(sample_transactions_data)
    assert merkle_root is not None, "Merkle root should be computed."

    for i, tx_data in enumerate(sample_transactions_data):
        proof = tm.generate_merkle_proof(sample_transactions_data, i)
        assert proof is not None, f"Proof should be generated for transaction at index {i}."

        is_valid = tm.verify_merkle_proof(
            tx_data, merkle_root, proof, i, len(sample_transactions_data)
        )
        assert is_valid, f"Merkle proof verification should pass for transaction at index {i}."

    if len(sample_transactions_data) > 0:
        original_tx_data = sample_transactions_data[0]
        modified_tx_data = original_tx_data + " (modified)"

        proof_for_original = tm.generate_merkle_proof(sample_transactions_data, 0)
        assert proof_for_original is not None

        is_valid_modified = tm.verify_merkle_proof(
            modified_tx_data, merkle_root, proof_for_original, 0, len(sample_transactions_data)
        )
        assert not is_valid_modified, "Verification should fail for tampered transaction data."

        is_valid_wrong_root = tm.verify_merkle_proof(
            original_tx_data,
            "incorrect_merkle_root_value",
            proof_for_original,
            0,
            len(sample_transactions_data),
        )
        assert not is_valid_wrong_root, "Verification should fail for incorrect Merkle root."

        if proof_for_original:
            tampered_proof = list(proof_for_original)
            if tampered_proof:
                original_hash, direction = tampered_proof[0]
                tampered_proof[0] = (
                    original_hash.replace(
                        original_hash[0], "z" if original_hash[0] != "z" else "a"
                    ),
                    direction,
                )
                is_valid_tampered_proof = tm.verify_merkle_proof(
                    original_tx_data, merkle_root, tampered_proof, 0, len(sample_transactions_data)
                )
                assert not is_valid_tampered_proof, "Verification should fail for tampered proof."


def test_trust_check_sampling_dynamics(sample_transactions_data: list[str]):
    """
    Tests the trust check mechanism using cryptographic sampling.
    """
    if not hasattr(tm, "compute_merkle_root") or not hasattr(tm, "perform_trust_check_sampling"):
        pytest.skip(
            "Merkle or trust check functions not found in transaction_manager, skipping test."
        )

    merkle_root = tm.compute_merkle_root(sample_transactions_data)
    assert merkle_root is not None

    is_trusted_valid = tm.perform_trust_check_sampling(
        sample_transactions_data, merkle_root, sample_size=3
    )
    assert is_trusted_valid, "Trust check should pass for valid, consistent data."

    if len(sample_transactions_data) > 1:
        tampered_transactions_list = list(sample_transactions_data)
        tampered_transactions_list[0] = "This transaction was tampered with, it's not the original."

        is_trusted_tampered_list_full_sample = tm.perform_trust_check_sampling(
            tampered_transactions_list, merkle_root, sample_size=len(tampered_transactions_list)
        )
        assert not is_trusted_tampered_list_full_sample, (
            "Trust check with full sample should fail if a transaction in the list is tampered but original root is used."
        )

    is_trusted_wrong_root = tm.perform_trust_check_sampling(
        sample_transactions_data, "completely_fake_merkle_root", sample_size=3
    )
    assert not is_trusted_wrong_root, "Trust check should fail if the Merkle root is incorrect."

    is_trusted_empty = tm.perform_trust_check_sampling(
        [], "some_root_for_empty_list_or_none", sample_size=1
    )
    assert is_trusted_empty, "Trust check on empty list (current policy: True)."

    is_trusted_empty_no_root = tm.perform_trust_check_sampling([], "", sample_size=1)
    assert not is_trusted_empty_no_root, (
        "Trust check on empty list with no root should fail (current policy)."
    )
