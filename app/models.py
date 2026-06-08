"""
AlloGator - model registry.

Defines the protein language models the web app can run. These are the four
models compared in the paper (Kannan et al., Cell Systems):

  * ESM-1b      - 650M-parameter ESM protein language model (default).
  * ESM-2 650M  - 650M-parameter ESM-2 protein language model.
  * ProtT5      - T5-encoder protein language model.
  * ESM++       - open re-implementation of ESM-C (~600M).

Each model is loaded lazily and on demand (see prediction.py / backends.py),
so the container only pays the memory cost of a model once it is selected.
This module is intentionally dependency-free (no torch / esm / transformers
import) so it can be imported anywhere cheaply.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ModelSpec:
    key: str                 # stable id used by the API / UI
    name: str                # human-readable name
    backend: str             # "esm" | "prott5" | "esmpp"
    source: str              # esm factory name OR HuggingFace repo id
    params: str              # approximate parameter count, for display
    approx_ram_gb: float     # rough resident size once loaded (fp32, CPU)
    num_layers: int = 0      # last-layer index for esm backend (0 = use all)
    # Restrict attention averaging to a contiguous block of transformer layers,
    # given 1-indexed inclusive (e.g. (28, 32) = layers 28-32). None = all layers.
    layer_range: Optional[Tuple[int, int]] = None
    recommended: bool = False
    blurb: str = ""          # one-line trade-off summary for the UI
    aliases: List[str] = field(default_factory=list)

    def to_public(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "backend": self.backend,
            "params": self.params,
            "approx_ram_gb": self.approx_ram_gb,
            "recommended": self.recommended,
            "blurb": self.blurb,
        }


_REGISTRY: "Dict[str, ModelSpec]" = {}


def _register(spec: ModelSpec) -> None:
    _REGISTRY[spec.key] = spec
    for alias in spec.aliases:
        _REGISTRY[alias] = spec


# Order matters: the UI shows models in this order, recommended first.
_register(ModelSpec(
    key="esm1b",
    name="ESM-1b",
    backend="esm",
    source="esm1b_t33_650M_UR50S",
    params="650M",
    approx_ram_gb=2.6,
    num_layers=33,
    recommended=True,
    aliases=["esm-1b", "esm1b_t33_650M_UR50S"],
))

# Same ESM-1b weights, but averaging attention over only the last three
# transformer layers (31-33) instead of all 33. Offered as a separate,
# selectable option; the all-layer ESM-1b above remains the default.
_register(ModelSpec(
    key="esm1b_late",
    name="ESM-1b (layers 31-33)",
    backend="esm",
    source="esm1b_t33_650M_UR50S",
    params="650M",
    approx_ram_gb=2.6,
    num_layers=33,
    layer_range=(31, 33),
    aliases=["esm1b-late", "esm1b_31_33"],
))

# ESM-1b is the recommended default. ESM-2 650M and ProtT5-XL are also offered
# as selectable alternatives. All three lazy-download their weights on first use
# and follow the same idle-unload pattern (see prediction.py), so only the
# selected model is resident at a time. ProtT5 requires the HuggingFace stack
# (transformers, sentencepiece, protobuf) in requirements.txt.
_register(ModelSpec(
    key="esm2_650m",
    name="ESM-2 (650M)",
    backend="esm",
    source="esm2_t33_650M_UR50D",
    params="650M",
    approx_ram_gb=2.6,
    num_layers=33,
    aliases=["esm2", "esm-2", "esm2_t33_650M_UR50D"],
))

_register(ModelSpec(
    key="prott5",
    name="ProtT5-XL",
    backend="prott5",
    source="Rostlab/prot_t5_xl_half_uniref50-enc",
    params="~3B",
    approx_ram_gb=3.0,
    aliases=["prot_t5", "prot-t5", "prott5_xl"],
))

# ESM++ (ESM-C) remains disabled for the live deployment. Re-enabling it also
# requires re-adding the `einops` dep to requirements.txt for its backend.
#
# _register(ModelSpec(
#     key="esmpp",
#     name="ESM++ (ESM-C)",
#     backend="esmpp",
#     source="Synthyra/ESMplusplus_large",
#     params="~600M",
#     approx_ram_gb=2.4,
#     aliases=["esm++", "esmc", "esm-c", "esmplusplus"],
# ))


DEFAULT_MODEL_KEY = "esm1b"


def get_spec(key: Optional[str]) -> ModelSpec:
    """Resolve a model key (or alias) to a ModelSpec, defaulting to ESM-1b."""
    if not key:
        return _REGISTRY[DEFAULT_MODEL_KEY]
    spec = _REGISTRY.get(key) or _REGISTRY.get(key.lower())
    if spec is None:
        valid = ", ".join(k for k, s in _REGISTRY.items() if s.key == k)
        raise ValueError(f"Unknown model '{key}'. Choose one of: {valid}.")
    return spec


def list_public_models() -> List[dict]:
    """Public, de-duplicated model list for the API/UI, in registry order."""
    seen = set()
    out = []
    for spec in _REGISTRY.values():
        if spec.key in seen:
            continue
        seen.add(spec.key)
        out.append(spec.to_public())
    return out
