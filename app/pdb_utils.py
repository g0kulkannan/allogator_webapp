"""
PDB download and B-factor modification utilities.
"""

import requests
from typing import List, Dict, Optional, Tuple
import numpy as np


def download_pdb(pdb_code: str) -> Optional[str]:
    """
    Download PDB file from PDBrenum (renumbered) or fallback to RCSB.

    Args:
        pdb_code: 4-character PDB code

    Returns:
        PDB file content as string, or None if download fails
    """
    pdb_code = pdb_code.lower().strip()

    # Try PDBrenum first (renumbered PDB)
    pdbrenum_url = f"http://dunbrack3.fccc.edu/PDBrenum/output_PDB/{pdb_code}_renum.pdb"
    try:
        response = requests.get(pdbrenum_url, timeout=30)
        if response.status_code == 200 and response.text.strip():
            return response.text
    except requests.RequestException:
        pass

    # Fallback to RCSB PDB
    rcsb_url = f"https://files.rcsb.org/download/{pdb_code.upper()}.pdb"
    try:
        response = requests.get(rcsb_url, timeout=30)
        if response.status_code == 200:
            return response.text
    except requests.RequestException:
        pass

    return None


def normalize_scores(scores: List[float], min_val: float = 0, max_val: float = 100) -> List[float]:
    """Normalize scores to a given range."""
    if not scores:
        return scores

    score_min = min(scores)
    score_max = max(scores)

    if score_max == score_min:
        return [50.0] * len(scores)

    normalized = []
    for s in scores:
        norm = (s - score_min) / (score_max - score_min)
        normalized.append(min_val + norm * (max_val - min_val))

    return normalized


def modify_bfactor(
    pdb_content: str,
    residue_scores: Dict[int, float],
    chain: str = None
) -> str:
    """
    Modify B-factor column in PDB file with scores.

    Args:
        pdb_content: Original PDB file content
        residue_scores: Dict mapping residue number to score (0-100 range)
        chain: Optional chain ID to modify (if None, modifies all chains)

    Returns:
        Modified PDB content with B-factors replaced by scores
    """
    lines = pdb_content.split('\n')
    modified_lines = []

    for line in lines:
        if line.startswith('ATOM') or line.startswith('HETATM'):
            # PDB format: columns are fixed width
            # Residue number: columns 23-26 (1-indexed)
            # Chain ID: column 22 (1-indexed)
            # B-factor: columns 61-66 (1-indexed)

            try:
                res_num = int(line[22:26].strip())
                chain_id = line[21]

                # Check if we should modify this residue
                if chain is not None and chain_id != chain:
                    modified_lines.append(line)
                    continue

                if res_num in residue_scores:
                    score = residue_scores[res_num]
                    # Format B-factor as 6 characters, right-justified with 2 decimal places
                    bfactor_str = f"{score:6.2f}"
                    # Replace B-factor column (columns 61-66, 0-indexed: 60-66)
                    new_line = line[:60] + bfactor_str + line[66:]
                    modified_lines.append(new_line)
                else:
                    # Set B-factor to 0 for residues without scores
                    new_line = line[:60] + "  0.00" + line[66:]
                    modified_lines.append(new_line)
            except (ValueError, IndexError):
                modified_lines.append(line)
        else:
            modified_lines.append(line)

    return '\n'.join(modified_lines)


def get_colored_pdbs(
    pdb_code: str,
    scores: List[Dict]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Download PDB and create colored versions based on scores.

    Args:
        pdb_code: 4-character PDB code
        scores: List of score dicts with 'residue', 'raw_score', 'rank_score'

    Returns:
        Tuple of (original_pdb, raw_score_pdb, rank_score_pdb)
        Any can be None if processing fails
    """
    # Download PDB
    pdb_content = download_pdb(pdb_code)
    if pdb_content is None:
        return None, None, None

    # Create residue -> score mappings
    raw_scores = {s['residue']: s['raw_score'] for s in scores}
    rank_scores = {s['residue']: s['rank_score'] for s in scores}

    # Normalize raw scores to 0-100 range for B-factor visualization
    raw_values = list(raw_scores.values())
    normalized_raw = normalize_scores(raw_values, 0, 100)
    raw_scores_normalized = {
        res: norm for res, norm in zip(raw_scores.keys(), normalized_raw)
    }

    # Create colored PDB files
    pdb_raw = modify_bfactor(pdb_content, raw_scores_normalized)
    pdb_rank = modify_bfactor(pdb_content, rank_scores)

    return pdb_content, pdb_raw, pdb_rank
