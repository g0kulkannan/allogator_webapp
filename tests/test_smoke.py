"""
Lightweight smoke tests. The model-dependent tests are skipped automatically
if torch/esm or the weights aren't available, so this runs in CI without GPUs
or large downloads.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_model_registry():
    from app import models
    pub = models.list_public_models()
    keys = {m["key"] for m in pub}
    assert keys == {"esm1b", "esm2_650m", "prott5", "esmpp"}, keys
    # exactly one recommended, and it is the default ESM-1b
    rec = [m for m in pub if m["recommended"]]
    assert len(rec) == 1 and rec[0]["key"] == "esm1b"
    assert models.DEFAULT_MODEL_KEY == "esm1b"
    assert models.get_spec(None).key == "esm1b"
    # backends are tagged
    assert models.get_spec("esm1b").backend == "esm"
    assert models.get_spec("prott5").backend == "prott5"
    assert models.get_spec("esmpp").backend == "esmpp"
    # alias resolution
    assert models.get_spec("esm-1b").key == "esm1b"
    assert models.get_spec("esm++").key == "esmpp"
    assert models.get_spec("prot_t5").key == "prott5"
    # unknown -> ValueError
    try:
        models.get_spec("not-a-model")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_active_residues():
    from app.prediction import parse_active_residues
    assert parse_active_residues("630, 708, 740") == [630, 708, 740]
    assert parse_active_residues("124-126, 130") == [124, 125, 126, 130]
    assert parse_active_residues("5-3") == [3, 4, 5]  # reversed range handled
    assert parse_active_residues(" 10 , 10 ") == [10]  # dedup + strip


def test_examples_are_consistent():
    from app.examples import EXAMPLES
    valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
    for e in EXAMPLES:
        seq = e["sequence"]
        assert set(seq) <= valid_aa, f"{e['id']} has non-AA chars"
        assert len(seq) <= 1022, f"{e['id']} exceeds ESM limit"
        for part in e["active_residues"].split(","):
            part = part.strip()
            if "-" in part:
                continue
            n = int(part)
            assert 1 <= n <= len(seq), f"{e['id']} active residue {n} out of range"


def test_csv_export_shape():
    from app.prediction import scores_to_csv
    result = {
        "model": {"name": "ESM-1b"},
        "active_residues": [10, 20],
        "sequence_length": 100,
        "scores": [
            {"residue": 5, "amino_acid": "A", "raw_score": 0.1, "rank_score": 80.0, "is_top": False},
            {"residue": 7, "amino_acid": "G", "raw_score": 0.2, "rank_score": 95.0, "is_top": True},
        ],
    }
    csv = scores_to_csv(result)
    lines = csv.strip().split("\n")
    assert lines[0].startswith("# AlloGator")
    # data sorted by rank desc -> residue 7 first
    data_rows = [l for l in lines if not l.startswith("#") and not l.startswith("residue")]
    assert data_rows[0].startswith("7,G")


if __name__ == "__main__":
    test_model_registry()
    test_parse_active_residues()
    test_examples_are_consistent()
    test_csv_export_shape()
    print("All smoke tests passed.")
