"""Build a signed, sparse connectivity matrix from the FlyWire edge list."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
import pyarrow.feather as feather
import scipy.sparse as sp

from . import data

# Standard connectome-simulation approximation: sign each neuron's *outgoing*
# synapses by its predicted neurotransmitter. Acetylcholine is the main
# excitatory transmitter in the fly brain; GABA is inhibitory; glutamate is
# usually inhibitory in Drosophila (via the GluCl-alpha channel). The
# monoamines are neuromodulatory -- they don't fit a fast +/- weight at all,
# so we leave them at zero rather than pretend otherwise.
SIGNS = {
    "acetylcholine": +1.0,
    "glutamate": -1.0,
    "gaba": -1.0,
    "dopamine": 0.0,
    "serotonin": 0.0,
    "octopamine": 0.0,
}

CACHE_VERSION = 2


@dataclass
class Connectome:
    W: sp.csr_matrix          # [post, pre] signed weights
    ids: np.ndarray           # int64 root ids, sorted; index == matrix index
    meta: dict                # column name -> list, aligned to `ids`
    n: int

    def col(self, name: str) -> np.ndarray:
        return np.asarray(self.meta[name], dtype=object)

    def where(self, **kw) -> np.ndarray:
        """Indices of neurons matching all given column==value constraints."""
        mask = np.ones(self.n, dtype=bool)
        for k, v in kw.items():
            vals = self.col(k)
            if callable(v):
                mask &= np.array([bool(v(x)) for x in vals])
            elif isinstance(v, (list, tuple, set)):
                wanted = set(v)
                mask &= np.array([x in wanted for x in vals])
            else:
                mask &= vals == v
        return np.flatnonzero(mask)


def _cache_path() -> Path:
    return data.data_dir() / f"connectome_cache_v{CACHE_VERSION}.npz"


def load(rebuild: bool = False) -> Connectome:
    paths = data.ensure_all()
    cache = _cache_path()

    meta_tbl = feather.read_table(paths["meta"])
    meta = meta_tbl.to_pydict()
    ids = np.asarray(
        pc.cast(meta_tbl.column("fafb_783_id"), "int64").to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    order = np.argsort(ids)
    ids = ids[order]
    meta = {k: [v[i] for i in order] for k, v in meta.items()}
    n = len(ids)

    if cache.exists() and not rebuild:
        z = np.load(cache)
        if z["n"] == n:
            W = sp.csr_matrix((z["data"], z["indices"], z["indptr"]), shape=(n, n))
            return Connectome(W=W, ids=ids, meta=meta, n=n)

    print("  building connectivity matrix (one-time, ~30s) ...", file=sys.stderr)
    et = feather.read_table(paths["edges"])
    pre = pc.cast(et.column("pre"), "int64").to_numpy(zero_copy_only=False).astype(np.int64)
    post = pc.cast(et.column("post"), "int64").to_numpy(zero_copy_only=False).astype(np.int64)
    # `norm` = this connection's share of the postsynaptic neuron's total input,
    # so weights arriving at a neuron are already sensibly scaled.
    norm = et.column("norm").to_numpy(zero_copy_only=False).astype(np.float32)

    pre_i = np.searchsorted(ids, pre)
    post_i = np.searchsorted(ids, post)
    ok = (
        (pre_i < n) & (post_i < n)
        & (ids[np.clip(pre_i, 0, n - 1)] == pre)
        & (ids[np.clip(post_i, 0, n - 1)] == post)
    )
    dropped = int((~ok).sum())
    if dropped:
        print(f"    dropped {dropped:,} edges with endpoints absent from metadata",
              file=sys.stderr)
    pre_i, post_i, norm = pre_i[ok], post_i[ok], norm[ok]

    nt = meta["neurotransmitter_predicted"]
    sign = np.array([SIGNS.get(x, 0.0) for x in nt], dtype=np.float32)
    w = norm * sign[pre_i]

    keep = w != 0
    W = sp.csr_matrix(
        (w[keep], (post_i[keep], pre_i[keep])), shape=(n, n), dtype=np.float32
    )
    W.sum_duplicates()
    np.savez_compressed(
        cache, data=W.data, indices=W.indices, indptr=W.indptr, n=np.int64(n)
    )
    print(f"    {W.nnz:,} signed edges over {n:,} neurons", file=sys.stderr)
    return Connectome(W=W, ids=ids, meta=meta, n=n)
