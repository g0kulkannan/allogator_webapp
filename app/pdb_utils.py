"""
PDB download and B-factor annotation utilities.

Used to produce structure files whose B-factor column carries the AlloGator
score, so users can color a structure by predicted allosteric coupling in
PyMOL / ChimeraX / Mol* with a single command.
"""

from typing import Dict, List, Optional, Tuple

import requests


def download_pdb(pdb_code: str) -> Optional[str]:
    """
    Fetch a PDB file. Tries PDBrenum (UniProt-renumbered, matching the paper's
    convention) first, then falls back to RCSB.
    """
    pdb_code = pdb_code.lower().strip()

    pdbrenum_url = (
        f"https://dunbrack3.fccc.edu/PDBrenum/output_PDB/{pdb_code}_renum.pdb"
    )
    try:
        r = requests.get(pdbrenum_url, timeout=30)
        if r.status_code == 200 and r.text.strip():
            return r.text
    except requests.RequestException:
        pass

    rcsb_url = f"https://files.rcsb.org/download/{pdb_code.upper()}.pdb"
    try:
        r = requests.get(rcsb_url, timeout=30)
        if r.status_code == 200 and r.text.strip():
            return r.text
    except requests.RequestException:
        pass

    return None


def normalize_scores(values: List[float], lo: float = 0.0, hi: float = 100.0) -> List[float]:
    """Linearly rescale values into [lo, hi]. Constant input maps to the midpoint."""
    if not values:
        return values
    vmin, vmax = min(values), max(values)
    if vmax == vmin:
        return [(lo + hi) / 2.0] * len(values)
    return [lo + (v - vmin) / (vmax - vmin) * (hi - lo) for v in values]


def modify_bfactor(
    pdb_content: str,
    residue_scores: Dict[int, float],
    chain: Optional[str] = None,
) -> str:
    """
    Replace the B-factor column of each ATOM/HETATM record with the score for
    that residue (0 where no score exists). Fixed-width PDB columns:
    chain = col 22 (0-idx 21), residue number = cols 23-26, B-factor = cols 61-66.
    """
    out = []
    for line in pdb_content.split("\n"):
        if line.startswith(("ATOM", "HETATM")):
            try:
                res_num = int(line[22:26].strip())
                chain_id = line[21]
                if chain is not None and chain_id != chain:
                    out.append(line)
                    continue
                score = residue_scores.get(res_num, 0.0)
                out.append(line[:60] + f"{score:6.2f}" + line[66:])
            except (ValueError, IndexError):
                out.append(line)
        else:
            out.append(line)
    return "\n".join(out)


def get_colored_pdbs(
    pdb_code: str,
    scores: List[Dict],
    active_residues: Optional[List[int]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Download a structure and return (original, raw-score-colored, rank-colored)
    PDB strings. Active-site residues, if given, are written as B-factor = 100
    in the rank file so they remain visible as the anchor.
    """
    pdb_content = download_pdb(pdb_code)
    if pdb_content is None:
        return None, None, None

    raw_scores = {s["residue"]: s["raw_score"] for s in scores}
    rank_scores = {s["residue"]: s["rank_score"] for s in scores}

    normalized = normalize_scores(list(raw_scores.values()), 0, 100)
    raw_norm = {res: nv for res, nv in zip(raw_scores.keys(), normalized)}

    if active_residues:
        for ar in active_residues:
            rank_scores.setdefault(ar, 100.0)

    pdb_raw = modify_bfactor(pdb_content, raw_norm)
    pdb_rank = modify_bfactor(pdb_content, rank_scores)
    return pdb_content, pdb_raw, pdb_rank
