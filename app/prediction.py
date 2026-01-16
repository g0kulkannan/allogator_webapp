"""
AlloGator - ESM1b-based allosteric site prediction scoring.

Kannan et al., 2024 bioRxiv
https://www.biorxiv.org/content/10.1101/2024.10.03.616547v1
"""

import os
import numpy as np
import torch
import esm
from typing import List, Tuple, Dict
from scipy.stats import rankdata

# Global model cache
_model = None
_alphabet = None
_batch_converter = None


def get_device():
    """Get the best available device (CUDA > CPU)."""
    if torch.cuda.is_available():
        return torch.device('cuda')
    return torch.device('cpu')


def load_model():
    """Load ESM1b model (cached singleton)."""
    global _model, _alphabet, _batch_converter

    if _model is None:
        print("Loading ESM1b model...")
        _model, _alphabet = esm.pretrained.esm1b_t33_650M_UR50S()
        device = get_device()
        _model = _model.to(device)
        _model.eval()
        _batch_converter = _alphabet.get_batch_converter()
        print(f"Model loaded on {device}")

    return _model, _alphabet, _batch_converter


def compute_attention_scores(
    sequence: str,
    active_residues: List[int]
) -> Dict:
    """
    Compute attention-based allosteric site prediction scores.

    Args:
        sequence: Protein amino acid sequence
        active_residues: List of active site residue numbers (1-indexed)

    Returns:
        Dictionary with:
        - scores: List of dicts with residue, amino_acid, raw_score, rank_score
        - active_residues: The input active residues
        - sequence_length: Length of the sequence
    """
    model, alphabet, batch_converter = load_model()
    device = get_device()

    # Prepare data for ESM
    data = [("protein", sequence)]
    batch_labels, batch_strs, batch_tokens = batch_converter(data)
    batch_tokens = batch_tokens.to(device)

    # Run inference
    with torch.no_grad():
        results = model(batch_tokens, repr_layers=[33], return_contacts=True)

    # Get attention matrix
    attentions = results['attentions']
    basis = attentions[0].cpu().numpy()

    # Average over heads and layers
    attentions_sum = np.mean(np.mean(basis, axis=1), axis=0)

    # Remove start/end tokens
    final_attention = attentions_sum[1:-1, 1:-1]

    # Convert active_residues to set for faster lookup
    actres_set = set(active_residues)

    # Calculate scores for each residue
    scores = []

    for resi in range(len(sequence)):
        residue_num = resi + 1  # Convert to 1-indexed

        # Skip active site residues
        if residue_num in actres_set:
            continue

        # Skip residues adjacent to active site (within +/-1)
        if any(abs(residue_num - ar) < 2 for ar in active_residues):
            continue

        # Sum attention from this residue to all active site residues
        raw_score = 0.0
        for ar in active_residues:
            if ar - 1 < len(final_attention) and resi < len(final_attention):
                raw_score += final_attention[ar - 1, resi]

        scores.append({
            'residue': residue_num,
            'amino_acid': sequence[resi],
            'raw_score': float(raw_score)
        })

    # Calculate rank scores (percentile ranks, higher = better)
    if scores:
        raw_scores = [s['raw_score'] for s in scores]
        ranks = rankdata(raw_scores, method='average')
        percentile_ranks = (ranks / len(ranks)) * 100

        for i, s in enumerate(scores):
            s['rank_score'] = float(percentile_ranks[i])

    return {
        'scores': scores,
        'active_residues': active_residues,
        'sequence_length': len(sequence)
    }


def scores_to_csv(scores: List[Dict]) -> str:
    """Convert scores to CSV format string."""
    lines = ["residue,amino_acid,raw_score,rank_score"]
    for s in scores:
        lines.append(f"{s['residue']},{s['amino_acid']},{s['raw_score']:.6f},{s['rank_score']:.2f}")
    return "\n".join(lines)
