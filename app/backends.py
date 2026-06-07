"""
Model backends.

Each backend knows how to (a) load a model + tokenizer and (b) turn a single
sequence into an (L, L) attention matrix that is the mean over all heads and
all layers, with the special tokens removed so row/col i corresponds to
sequence position i (0-indexed). Downstream scoring (prediction.py) is then
identical across backends.

The recipes here mirror the paper's reference scoring scripts exactly:
  - ESM      : fair-esm, drop BOS/EOS -> attn[1:-1, 1:-1]
  - ProtT5   : T5 encoder, residues space-separated, [UZOB]->X, slice [:L,:L]
               (T5 has no BOS; a single EOS is appended)
  - ESM++    : Synthyra ESMplusplus (ESM-C), drop BOS/EOS -> attn[1:L+1, 1:L+1]

Loading is lazy: heavy libraries (torch / esm / transformers) are imported
inside the loader functions so importing this module stays cheap.
"""

import re
from typing import Tuple

import numpy as np

from .models import ModelSpec


def get_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


# ---------------------------------------------------------------------------
# A loaded backend is a small object exposing .attention(sequence) -> (L, L).
# ---------------------------------------------------------------------------
class _EsmBackend:
    def __init__(self, spec: ModelSpec):
        import esm
        import torch

        factory = getattr(esm.pretrained, spec.source)
        self.model, self.alphabet = factory()
        self.device = get_device()
        self.model = self.model.to(self.device).eval()
        self.batch_converter = self.alphabet.get_batch_converter()
        self.repr_layer = spec.num_layers
        self.layer_range = spec.layer_range  # (lo, hi) 1-indexed inclusive, or None
        self._torch = torch

    def attention(self, sequence: str) -> np.ndarray:
        torch = self._torch
        _, _, tokens = self.batch_converter([("protein", sequence)])
        tokens = tokens.to(self.device)
        with torch.no_grad():
            out = self.model(
                tokens,
                repr_layers=[self.repr_layer],
                need_head_weights=True,
                return_contacts=False,
            )
        # (batch, layers, heads, T, T) -> mean over heads then layers
        attn = out["attentions"][0].to(torch.float32).cpu().numpy()
        if self.layer_range is not None:
            lo, hi = self.layer_range  # 1-indexed inclusive
            attn = attn[lo - 1:hi]
        mean = attn.mean(axis=1).mean(axis=0)
        return mean[1:-1, 1:-1]  # drop BOS/EOS


class _ProtT5Backend:
    def __init__(self, spec: ModelSpec):
        import torch
        from transformers import T5EncoderModel, T5Tokenizer

        self.tokenizer = T5Tokenizer.from_pretrained(spec.source, do_lower_case=False)
        self.model = T5EncoderModel.from_pretrained(spec.source, output_attentions=True)
        self.device = get_device()
        self.model = self.model.to(self.device)
        if self.device.type == "cpu":
            self.model = self.model.to(torch.float32)
        self.model = self.model.eval()
        self._torch = torch

    def attention(self, sequence: str) -> np.ndarray:
        torch = self._torch
        L = len(sequence)
        spaced = " ".join(list(re.sub(r"[UZOB]", "X", sequence)))
        ids = self.tokenizer(spaced, add_special_tokens=True, padding=False,
                             return_tensors="pt")
        ids = {k: v.to(self.device) for k, v in ids.items()}
        with torch.no_grad():
            out = self.model(**ids, output_attentions=True)
            stack = torch.stack(out.attentions, dim=0)[:, 0]  # (layers, heads, T, T)
            mean = stack.mean(dim=(0, 1)).cpu().to(torch.float32).numpy()
        return mean[:L, :L]  # T5 has no BOS; trailing EOS dropped by the slice


class _EsmppBackend:
    def __init__(self, spec: ModelSpec):
        import torch
        from transformers import AutoModelForMaskedLM

        self.model = AutoModelForMaskedLM.from_pretrained(
            spec.source, trust_remote_code=True, torch_dtype=torch.float32
        )
        self.device = get_device()
        self.model = self.model.to(self.device).eval()
        self.tokenizer = self.model.tokenizer
        self._torch = torch

    def attention(self, sequence: str) -> np.ndarray:
        torch = self._torch
        L = len(sequence)
        enc = self.tokenizer([sequence], return_tensors="pt")
        enc = {k: v.to(self.device) for k, v in enc.items()}
        with torch.no_grad():
            out = self.model(**enc, output_attentions=True)
            stack = torch.stack(out.attentions, dim=0)[:, 0]  # (layers, heads, T, T)
            attn = stack[:, :, 1:L + 1, 1:L + 1]               # drop BOS/EOS
            mean = attn.mean(dim=(0, 1)).cpu().to(torch.float32).numpy()
        return mean


_BACKENDS = {
    "esm": _EsmBackend,
    "prott5": _ProtT5Backend,
    "esmpp": _EsmppBackend,
}


def build_backend(spec: ModelSpec):
    """Instantiate (and load) the backend for a given model spec."""
    try:
        cls = _BACKENDS[spec.backend]
    except KeyError:
        raise ValueError(f"Unknown backend '{spec.backend}' for model '{spec.key}'.")
    return cls(spec)


def predownload(spec: ModelSpec) -> None:
    """Fetch weights into the local cache without keeping anything resident."""
    if spec.backend == "esm":
        import esm
        getattr(esm.pretrained, spec.source)()
    elif spec.backend == "prott5":
        from transformers import T5EncoderModel, T5Tokenizer
        T5Tokenizer.from_pretrained(spec.source, do_lower_case=False)
        T5EncoderModel.from_pretrained(spec.source)
    elif spec.backend == "esmpp":
        from transformers import AutoModelForMaskedLM
        AutoModelForMaskedLM.from_pretrained(spec.source, trust_remote_code=True)
