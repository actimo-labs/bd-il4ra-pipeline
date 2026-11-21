#!/usr/bin/env python
"""
09_boltz_crosscheck.py -- orthogonal Boltz-2 co-fold of Fv + IL-4Ralpha.

Spec: docs/PIPELINE.md section S3.

This is a SECOND OPINION from a different model family, not the primary filter.
Agreement between RF2 and Boltz-2 is the strongest computational evidence available to
us; disagreement is informative and is recorded, not hidden.

Two things this must get right:

1. `msa: empty`. The MSA server at 10.148.0.19:8080 is dead and the host is gone
   (CLAUDE.md s6 trap 7). Every prior campaign ran single-sequence mode. Do not try to
   revive it.
2. **Chain-pair scoring.** Boltz emits `pair_chains_iptm`, a per-chain-pair matrix.
   Global `iptm` on an Fv is dominated by the H<->L interface and is meaningless. We
   read the H-T and L-T entries and ignore H-L except as a reported negative control.

5 diffusion samples: between-seed Spearman rho was +0.239 at 1 sample and +0.846 at 5
in a prior campaign, at 2.41x the cost. Single-sample margins are noise.

Run:  conda run -n boltz python scripts/09_boltz_crosscheck.py --manifest candidates.tsv
Test: conda run -n boltz python scripts/09_boltz_crosscheck.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

BDIL4R = Path(os.environ.get("BDIL4R", "/mnt/comp5data/bd-il4r"))
TARGET = BDIL4R / "target"
OUT = BDIL4R / "out" / "boltz"
NOT_RUN = "not_run"

DIFFUSION_SAMPLES = 5
RECYCLING_STEPS = 3


def ecd_sequence():
    nm = json.loads((TARGET / "numbering_map.json").read_text())
    return nm["sequence_seqres"]


def write_yaml(path, vh, vl, target_seq):
    """Boltz-2 input. msa: empty on every chain -- single-sequence mode."""
    y = [
        "version: 1",
        "sequences:",
        "  - protein:",
        "      id: H",
        f"      sequence: {vh}",
        "      msa: empty",
        "  - protein:",
        "      id: L",
        f"      sequence: {vl}",
        "      msa: empty",
        "  - protein:",
        "      id: T",
        f"      sequence: {target_seq}",
        "      msa: empty",
        "",
    ]
    Path(path).write_text("\n".join(y))
    return path


def parse_confidence(d):
    """Pull the (H+L) vs T chain-pair metrics out of a Boltz confidence JSON.

    Returns a dict. Raises if the chain-pair matrix is absent -- we will not silently
    fall back to global ipTM, which on an Fv is ~the H<->L interface.
    """
    pair = d.get("pair_chains_iptm")
    if not pair:
        raise KeyError(
            "no pair_chains_iptm in the Boltz confidence output. Refusing to fall back "
            "to global ipTM: on an Fv that is dominated by the H<->L interface and says "
            "nothing about antigen binding.")

    def get(a, b):
        try:
            return float(pair[str(a)][str(b)])
        except (KeyError, TypeError, ValueError):
            return None

    # Boltz indexes chains in input order: H=0, L=1, T=2
    ht, lt, hl = get(0, 2), get(1, 2), get(0, 1)
    vals = [v for v in (ht, lt) if v is not None]
    return {
        "iptm_H_T": ht,
        "iptm_L_T": lt,
        "iptm_HL_vs_T_mean": (sum(vals) / len(vals)) if vals else None,
        "iptm_HL_vs_T_max": max(vals) if vals else None,
        "iptm_H_L_NEGATIVE_CONTROL": hl,
        "global_iptm_DO_NOT_RANK_ON_THIS": d.get("iptm"),
        "complex_plddt": d.get("complex_plddt"),
        "ptm": d.get("ptm"),
    }


def run_one(cid, vh, vl, target_seq, workdir, samples=DIFFUSION_SAMPLES, timeout=1800):
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    yml = workdir / f"{cid}.yaml"
    write_yaml(yml, vh, vl, target_seq)
    cmd = [
        os.path.expanduser("~/miniforge3/envs/boltz/bin/boltz"), "predict", str(yml),
        "--out_dir", str(workdir),
        "--diffusion_samples", str(samples),
        "--recycling_steps", str(RECYCLING_STEPS),
        "--output_format", "pdb",
        "--override",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    confs = sorted(workdir.glob(f"boltz_results_{cid}/predictions/{cid}/confidence_*.json"))
    if not confs:
        return {"candidate_id": cid, "error": "no confidence json",
                "stderr": r.stderr[-800:], "rc": r.returncode}
    per_sample = []
    for c in confs:
        try:
            per_sample.append(parse_confidence(json.loads(c.read_text())))
        except KeyError as e:
            return {"candidate_id": cid, "error": str(e)}
    vals = [p["iptm_HL_vs_T_mean"] for p in per_sample if p["iptm_HL_vs_T_mean"] is not None]
    return {
        "candidate_id": cid,
        "n_samples": len(per_sample),
        "boltz2_iface_mean5": round(statistics.mean(vals), 4) if vals else None,
        "boltz2_iface_sd5": round(statistics.pstdev(vals), 4) if len(vals) > 1 else None,
        "boltz2_iface_max": round(max(vals), 4) if vals else None,
        "per_sample": per_sample,
    }


def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    import tempfile
    d = Path(tempfile.mkdtemp())
    p = write_yaml(d / "t.yaml", "EVQL", "DIQM", "FKVL")
    txt = Path(p).read_text()
    check("yaml declares three chains H, L, T",
          "id: H" in txt and "id: L" in txt and "id: T" in txt)
    check("yaml sets msa: empty on EVERY chain (the MSA server is dead)",
          txt.count("msa: empty") == 3)
    check("yaml carries the sequences", "EVQL" in txt and "FKVL" in txt)

    # chain-pair parsing: H=0, L=1, T=2
    conf = {"pair_chains_iptm": {"0": {"0": 0.9, "1": 0.88, "2": 0.42},
                                 "1": {"0": 0.88, "1": 0.9, "2": 0.36},
                                 "2": {"0": 0.42, "1": 0.36, "2": 0.9}},
            "iptm": 0.85, "complex_plddt": 0.8, "ptm": 0.7}
    r = parse_confidence(conf)
    check("parses H-T chain pair", abs(r["iptm_H_T"] - 0.42) < 1e-9)
    check("parses L-T chain pair", abs(r["iptm_L_T"] - 0.36) < 1e-9)
    check("(H+L) vs T mean is the mean of H-T and L-T",
          abs(r["iptm_HL_vs_T_mean"] - 0.39) < 1e-9)
    check("H-L is captured only as a NEGATIVE CONTROL",
          abs(r["iptm_H_L_NEGATIVE_CONTROL"] - 0.88) < 1e-9)
    check("global ipTM is kept but named so it cannot be ranked on by accident",
          "global_iptm_DO_NOT_RANK_ON_THIS" in r)
    check("the interface metric is NOT the global ipTM",
          r["iptm_HL_vs_T_mean"] != r["global_iptm_DO_NOT_RANK_ON_THIS"])
    check("global ipTM (0.85) would have looked good while the true interface (0.39) "
          "is poor -- the trap, demonstrated",
          r["global_iptm_DO_NOT_RANK_ON_THIS"] > 0.8 and r["iptm_HL_vs_T_mean"] < 0.5)

    raised = False
    try:
        parse_confidence({"iptm": 0.9})
    except KeyError:
        raised = True
    check("missing pair_chains_iptm RAISES rather than falling back to global ipTM",
          raised)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--manifest", default="candidates.tsv")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--samples", type=int, default=DIFFUSION_SAMPLES)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--vh"), ap.add_argument("--vl"), ap.add_argument("--cid", default="adhoc")
    a = ap.parse_args()

    if a.self_test:
        print("09_boltz_crosscheck.py self-test (synthetic confidence JSON)")
        sys.exit(0 if self_test() else 1)

    tgt = ecd_sequence()
    print(f"[boltz] target = IL-4Ralpha ECD, {len(tgt)} aa, msa=empty, "
          f"{a.samples} diffusion samples")

    if a.vh and a.vl:
        import time
        t0 = time.time()
        r = run_one(a.cid, a.vh, a.vl, tgt, a.out, a.samples)
        print(json.dumps(r, indent=2)[:2000])
        print(f"[boltz] {time.time()-t0:.1f} s for 1 complex x {a.samples} samples")
        return

    rows = [r for r in csv.DictReader(open(a.manifest), delimiter="\t")
            if r.get("eligibility_status") == "pass"
            and r.get("novelty_status") != "fail"]
    try:
        rows.sort(key=lambda r: float(r.get("rf2_iface_hl_vs_t", 1e9)))
    except ValueError:
        pass
    if a.limit:
        rows = rows[:a.limit]
    print(f"[boltz] {len(rows)} candidates to cross-check")

    res = []
    outp = Path(a.out) / "boltz_results.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    for i, r in enumerate(rows, 1):
        import time
        t0 = time.time()
        x = run_one(r["candidate_id"], r["vh_seq"], r["vl_seq"], tgt, a.out, a.samples)
        x["elapsed_s"] = round(time.time() - t0, 1)
        res.append(x)
        outp.write_text(json.dumps(res, indent=2))     # checkpoint every design
        print(f"  [{i}/{len(rows)}] {r['candidate_id']}  "
              f"iface={x.get('boltz2_iface_mean5')}  sd={x.get('boltz2_iface_sd5')}  "
              f"{x['elapsed_s']}s")
    print(f"[write] {outp}")


if __name__ == "__main__":
    main()
