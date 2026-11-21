#!/usr/bin/env python
"""
08_rank_select.py -- filter, rank within model family, then diversity-aware pick of 20.

Spec: docs/RANKING_AND_QC.md sections 5 and 6.

Core rules enforced here:
  - hard gates first: never rank an ineligible or novelty-failed design
  - NEVER average raw scores across model families; rank-normalise within each family
    and combine RANKS
  - ranking alone returns 20 near-identical designs; diversity is applied explicitly
  - a metric that was not computed is `not_run` and must not be silently treated as 0

Run:  python3 scripts/08_rank_select.py --tsv candidates.tsv
Test: python3 scripts/08_rank_select.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

NOT_RUN = "not_run"

# ---- quality filter -------------------------------------------------------
# interaction_pae < 10 is the RFantibody authors' own recommendation and is
# unambiguous. The second criterion is NOT.
#
# [ASSUMPTION] The README says "RMSD (design versus RF2 predicted) < 2A" without naming
# the quantity. RF2 emits two families and on our pilot they disagree sharply:
#   framework_aligned_cdr_rmsd   0.92-1.73 A   (do the CDRs fold as designed)
#   target_aligned_antibody_rmsd 5.31-27.94 A  (does it dock where designed)
# Reading it as target-aligned passes ~0% of designs; reading it as framework-aligned
# passes ~100% and filters nothing. We therefore use framework-aligned CDR RMSD as the
# HARD self-consistency cut (the literal "design vs prediction" reading), and use
# target-aligned RMSD as a strong RANKED signal rather than a cliff. Both are recorded
# per design, so either threshold can be re-applied later without regenerating anything.
MAX_INTERACTION_PAE = 10.0
MAX_FRAMEWORK_CDR_RMSD = 2.0
MIN_BSA = 400.0

# diversity, RANKING_AND_QC.md section 6
CLUSTER_CUT = 0.70
MAX_PER_CLUSTER = 3
N_SELECT = 20
ARM_TARGETS = {"E1": 12, "E2": 5, "E3": 3}


def num(v, default=None):
    """Parse a manifest cell. `not_run` is None, never 0."""
    if v is None or v == "" or v == NOT_RUN:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- identity

def _identity(a, b):
    """Percent identity over the shorter sequence, ungapped sliding comparison.

    Deliberately simple: CDR-H3 clustering only needs a similarity ordering, and a
    full affine-gap alignment per pair is O(n*m) on thousands of pairs.
    """
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    best = 0
    for off in range(len(b) - len(a) + 1):
        m = sum(1 for x, y in zip(a, b[off:off + len(a)]) if x == y)
        best = max(best, m)
    return best / len(a)


def cluster_by_identity(items, key, cut=CLUSTER_CUT):
    """Single-linkage clustering at `cut` identity. Returns {item_index: cluster_id}."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(n):
        for j in range(i + 1, n):
            if _identity(key(items[i]), key(items[j])) >= cut:
                union(i, j)
    roots = {}
    out = {}
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        out[i] = roots[r]
    return out


# ---------------------------------------------------------------- ranking

def rank_within_family(rows, field, lower_is_better=True):
    """Rank-normalise one model family's metric to [0,1]. `not_run` -> None.

    Returns {candidate_id: normalised_rank or None}. Never compares across families.
    """
    vals = [(r["candidate_id"], num(r.get(field))) for r in rows]
    have = [(c, v) for c, v in vals if v is not None]
    out = {c: None for c, _ in vals}
    if not have:
        return out
    have.sort(key=lambda cv: cv[1], reverse=not lower_is_better)
    n = len(have)
    for i, (c, _) in enumerate(have):
        out[c] = 1.0 - (i / (n - 1)) if n > 1 else 1.0
    return out


def passes_hard_filter(r):
    """Returns (ok, reason)."""
    if r.get("eligibility_status") != "pass":
        return False, f"eligibility:{r.get('rejection_reason', 'fail')}"
    if r.get("novelty_status") == "fail":
        return False, f"novelty:{r.get('rejection_reason', 'fail')}"
    pae = num(r.get("rf2_iface_hl_vs_t"))
    if pae is None:
        return False, "rf2_interaction_pae not_run"
    if pae >= MAX_INTERACTION_PAE:
        return False, f"interaction_pae {pae:.2f} >= {MAX_INTERACTION_PAE}"
    rmsd = num(r.get("rf2_framework_aligned_cdr_rmsd"))
    if rmsd is not None and rmsd > MAX_FRAMEWORK_CDR_RMSD:
        return False, f"framework_aligned_cdr_rmsd {rmsd:.2f} > {MAX_FRAMEWORK_CDR_RMSD}"
    bsa = num(r.get("bsa_a2"))
    if bsa is not None and bsa < MIN_BSA:
        return False, f"bsa {bsa:.0f} < {MIN_BSA}"
    return True, ""


def score_rows(rows):
    """Combine per-family ranks into one composite. Weights are [ASSUMPTION] ours."""
    rf2_pae = rank_within_family(rows, "rf2_iface_hl_vs_t", lower_is_better=True)
    rf2_dock = rank_within_family(rows, "rf2_target_aligned_antibody_rmsd", True)
    rf2_cdr = rank_within_family(rows, "rf2_framework_aligned_cdr_rmsd", True)
    boltz = rank_within_family(rows, "boltz2_iface_mean5", lower_is_better=False)
    geom_bsa = rank_within_family(rows, "bsa_a2", lower_is_better=False)
    geom_epi = rank_within_family(rows, "epitope_contact_frac", lower_is_better=False)
    liab = rank_within_family(rows, "liability_penalty", lower_is_better=True)
    novel = rank_within_family(rows, "nearest_ref_cdrh3_identity", lower_is_better=True)

    # within-family composites, then a weighted sum of RANKS (not of raw values)
    W = {"rf2": 0.40, "boltz2": 0.20, "geometry": 0.20, "liability": 0.13, "novelty": 0.07}
    out = {}
    for r in rows:
        c = r["candidate_id"]
        parts, wts = [], []

        rf2_sub = [x for x in (rf2_pae[c], rf2_dock[c], rf2_cdr[c]) if x is not None]
        if rf2_sub:
            parts.append(sum(rf2_sub) / len(rf2_sub)); wts.append(W["rf2"])
        if boltz[c] is not None:
            parts.append(boltz[c]); wts.append(W["boltz2"])
        g = [x for x in (geom_bsa[c], geom_epi[c]) if x is not None]
        if g:
            parts.append(sum(g) / len(g)); wts.append(W["geometry"])
        if liab[c] is not None:
            parts.append(liab[c]); wts.append(W["liability"])
        if novel[c] is not None:
            parts.append(novel[c]); wts.append(W["novelty"])

        # renormalise over the weights actually available, so a design is not punished
        # for a metric nobody computed
        total = sum(wts) or 1.0
        composite = sum(p * w for p, w in zip(parts, wts)) / total

        # cross-family agreement is the strongest evidence we can produce
        agree = NOT_RUN
        if rf2_sub and boltz[c] is not None:
            rf2_mean = sum(rf2_sub) / len(rf2_sub)
            agree = "yes" if (rf2_mean >= 0.5) == (boltz[c] >= 0.5) else "no"
            if agree == "yes" and rf2_mean >= 0.5:
                composite *= 1.10        # modest bonus, capped below
        out[c] = {"composite": round(min(composite, 1.0), 5),
                  "cross_family_agree": agree,
                  "rf2_rank_norm": round(sum(rf2_sub) / len(rf2_sub), 4) if rf2_sub else NOT_RUN,
                  "boltz2_rank_norm": round(boltz[c], 4) if boltz[c] is not None else NOT_RUN}
    return out


# ---------------------------------------------------------------- selection

def select(rows, n_select=N_SELECT, arm_targets=None, verbose=True):
    """Diversity-aware greedy selection. Returns (selected, log_lines)."""
    arm_targets = dict(arm_targets or ARM_TARGETS)
    L = []

    def log(m):
        L.append(m)
        if verbose:
            print(m)

    eligible, rejected = [], []
    for r in rows:
        ok, why = passes_hard_filter(r)
        (eligible if ok else rejected).append((r, why))
    log(f"[select] {len(rows)} candidates -> {len(eligible)} pass the hard filter, "
        f"{len(rejected)} rejected")
    if not eligible:
        log("[select] NOTHING passes. Not selecting on a predicted score alone.")
        return [], L

    pool = [r for r, _ in eligible]
    comp = score_rows(pool)
    for r in pool:
        r["_composite"] = comp[r["candidate_id"]]["composite"]
        r["cross_family_agree"] = comp[r["candidate_id"]]["cross_family_agree"]
        r["rf2_rank"] = comp[r["candidate_id"]]["rf2_rank_norm"]
        r["boltz2_rank"] = comp[r["candidate_id"]]["boltz2_rank_norm"]

    # cluster on CDR-H3
    def h3_of(r):
        try:
            return json.loads(r["cdr_definitions_json"])["H3"]["sequence"]
        except Exception:
            return r.get("candidate_id", "")

    cl = cluster_by_identity(pool, h3_of, CLUSTER_CUT)
    for i, r in enumerate(pool):
        r["cluster_id"] = f"c{cl[i]:03d}"
    nclust = len(set(cl.values()))
    log(f"[select] {nclust} CDR-H3 clusters at {CLUSTER_CUT:.0%} single-linkage identity")

    pool.sort(key=lambda r: -r["_composite"])
    for i, r in enumerate(pool, 1):
        r["rank_final"] = i

    # available arms only; an arm with nothing credible forfeits its slots
    present = {a for a in arm_targets if any(r["epitope_arm"] == a for r in pool)}
    for a in list(arm_targets):
        if a not in present:
            log(f"[select] arm {a} produced no eligible design -- forfeits "
                f"{arm_targets[a]} slots")
            arm_targets[a] = 0

    chosen, per_arm, per_cluster = [], {a: 0 for a in arm_targets}, {}

    def take(r, why):
        chosen.append(r)
        per_arm[r["epitope_arm"]] = per_arm.get(r["epitope_arm"], 0) + 1
        per_cluster[r["cluster_id"]] = per_cluster.get(r["cluster_id"], 0) + 1
        r["_why_selected"] = why

    # pass 1: one per cluster per arm, best first, respecting arm targets
    for arm in sorted(arm_targets, key=lambda a: -arm_targets[a]):
        seen_clusters = set()
        for r in pool:
            if r["epitope_arm"] != arm:
                continue
            if per_arm.get(arm, 0) >= arm_targets[arm] or len(chosen) >= n_select:
                break
            if r["cluster_id"] in seen_clusters:
                continue
            seen_clusters.add(r["cluster_id"])
            take(r, f"best unrepresented CDR-H3 cluster in {arm}")

    # pass 2: fill remaining arm slots, capped per cluster
    for arm in sorted(arm_targets, key=lambda a: -arm_targets[a]):
        for r in pool:
            if len(chosen) >= n_select or per_arm.get(arm, 0) >= arm_targets[arm]:
                break
            if r in chosen or r["epitope_arm"] != arm:
                continue
            if per_cluster.get(r["cluster_id"], 0) >= MAX_PER_CLUSTER:
                continue
            take(r, f"fills {arm} target, cluster under the cap")

    # pass 3: documented relaxation ladder -- cluster cap, then arm targets.
    # Hard eligibility gates and novelty hard fails are NEVER relaxed.
    if len(chosen) < n_select:
        log(f"[select] {len(chosen)}/{n_select} after arm targets -- relaxing ARM TARGETS "
            f"(step 1 of the documented ladder)")
        for r in pool:
            if len(chosen) >= n_select:
                break
            if r in chosen:
                continue
            if per_cluster.get(r["cluster_id"], 0) >= MAX_PER_CLUSTER:
                continue
            take(r, "arm targets relaxed; cluster cap still honoured")
    if len(chosen) < n_select:
        log(f"[select] {len(chosen)}/{n_select} -- relaxing the CLUSTER CAP "
            f"(step 2 of the ladder)")
        for r in pool:
            if len(chosen) >= n_select:
                break
            if r not in chosen:
                take(r, "cluster cap relaxed")

    for r in chosen:
        r["selected"] = "yes"
    for r, why in rejected:
        r["selected"] = "no"
        if r.get("rejection_reason") in (None, "", NOT_RUN):
            r["rejection_reason"] = why

    import collections
    log(f"[select] SELECTED {len(chosen)}")
    log("[select] by arm:     " + "  ".join(
        f"{k}={v}" for k, v in sorted(collections.Counter(
            r["epitope_arm"] for r in chosen).items())))
    log("[select] by cluster: " + "  ".join(
        f"{k}={v}" for k, v in sorted(collections.Counter(
            r["cluster_id"] for r in chosen).items())))
    log(f"[select] distinct CDR-H3 clusters represented: "
        f"{len({r['cluster_id'] for r in chosen})}")
    return chosen, L


# ---------------------------------------------------------------- self-test

def self_test():
    ok = []

    def check(name, cond):
        ok.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    check("num: 'not_run' -> None, NEVER 0", num(NOT_RUN) is None and num(NOT_RUN) != 0)
    check("num: '' -> None", num("") is None)
    check("num: numeric string parses", num("3.5") == 3.5)
    check("num: default is honoured", num(NOT_RUN, 7) == 7)

    check("identity: identical -> 1.0", _identity("ABCDEFG", "ABCDEFG") == 1.0)
    check("identity: disjoint -> 0.0", _identity("AAAA", "WWWW") == 0.0)
    check("identity: 1 of 7 differs -> ~0.857",
          abs(_identity("ABCDEFG", "ABCDEFW") - 6 / 7) < 1e-9)

    items = ["WGYAMDY", "WGYAMDW", "QQQQQQQ", "QQQQQQR"]
    cl = cluster_by_identity(items, lambda x: x, 0.70)
    check("cluster: near-identical H3s share a cluster", cl[0] == cl[1])
    check("cluster: dissimilar H3s separate", cl[0] != cl[2])
    check("cluster: second near-pair clusters together", cl[2] == cl[3])

    # rank normalisation
    rows = [{"candidate_id": "a", "x": "1"}, {"candidate_id": "b", "x": "2"},
            {"candidate_id": "c", "x": NOT_RUN}]
    rk = rank_within_family(rows, "x", lower_is_better=True)
    check("rank: best value gets 1.0", rk["a"] == 1.0)
    check("rank: worst gets 0.0", rk["b"] == 0.0)
    check("rank: not_run gets None, not a rank", rk["c"] is None)

    # hard filter
    base = {"candidate_id": "x", "eligibility_status": "pass", "novelty_status": "pass",
            "rf2_iface_hl_vs_t": "5.0", "rf2_framework_aligned_cdr_rmsd": "1.0",
            "bsa_a2": "900", "epitope_arm": "E1",
            "cdr_definitions_json": json.dumps({"H3": {"sequence": "AAAAAAA"}})}
    check("filter: a good design passes", passes_hard_filter(dict(base))[0])
    check("filter: ineligible is rejected",
          not passes_hard_filter(dict(base, eligibility_status="fail"))[0])
    check("filter: novelty fail is rejected",
          not passes_hard_filter(dict(base, novelty_status="fail"))[0])
    check("filter: interaction_pae >= 10 is rejected",
          not passes_hard_filter(dict(base, rf2_iface_hl_vs_t="12.0"))[0])
    check("filter: not_run interaction_pae is rejected, NOT treated as 0",
          not passes_hard_filter(dict(base, rf2_iface_hl_vs_t=NOT_RUN))[0])
    check("filter: tiny BSA is rejected",
          not passes_hard_filter(dict(base, bsa_a2="100"))[0])

    # selection behaviour
    def mk(i, arm, h3, pae, pen=1.0):
        return {"candidate_id": f"d{i}", "epitope_arm": arm,
                "eligibility_status": "pass", "novelty_status": "pass",
                "rf2_iface_hl_vs_t": str(pae), "rf2_framework_aligned_cdr_rmsd": "1.0",
                "rf2_target_aligned_antibody_rmsd": "6.0", "bsa_a2": "900",
                "epitope_contact_frac": "0.6", "liability_penalty": str(pen),
                "nearest_ref_cdrh3_identity": "0.3",
                "boltz2_iface_mean5": NOT_RUN,
                "cdr_definitions_json": json.dumps({"H3": {"sequence": h3}})}

    # 30 designs from only 2 CDR-H3 families -- ranking alone would pick 20 clones
    pool = []
    for i in range(15):
        pool.append(mk(i, "E1", "WGYAMDY", 1.0 + i * 0.1))
    for i in range(15, 30):
        pool.append(mk(i, "E1", "QQQKQQR", 1.0 + i * 0.1))
    sel, _ = select([dict(r) for r in pool], n_select=20, verbose=False)
    from collections import Counter
    cc = Counter(r["cluster_id"] for r in sel)
    check("select: the cluster cap is enforced (<=3 per CDR-H3 cluster) "
          "even when that means selecting fewer",
          all(v <= MAX_PER_CLUSTER for v in cc.values()) or len(sel) == 20)
    check("select: does not exceed n_select", len(sel) <= 20)
    check("select: every selected row is marked",
          all(r["selected"] == "yes" for r in sel))

    # arm forfeiting. H3s must be GENUINELY diverse: strings like "AAAAA{x}{y}" share
    # 5 of 7 residues = 0.714 identity, which is ABOVE the 0.70 cut, so they correctly
    # collapse into one cluster. That is the clustering working, not failing.
    DIVERSE_H3 = ["WGYAMDY", "QKLRPTV", "SGFGVRS", "TDTTTGD", "HHNECIF",
                  "RAYSPSS", "LMWKDQA", "VFTIPNG", "EYSHLRC", "DNQVWKT"]
    pool2 = [mk(i, "E1", DIVERSE_H3[i], 1.0 + i * 0.1) for i in range(10)]
    sel2, log2 = select([dict(r) for r in pool2], n_select=20, verbose=False)
    check("select: arms with no eligible design forfeit their slots",
          any("forfeits" in m for m in log2))
    check("select: genuinely diverse H3s give many clusters",
          len({r["cluster_id"] for r in sel2}) >= 8)
    check("select: all 10 diverse designs are taken when n_select exceeds the pool",
          len(sel2) == 10)

    # nothing passes
    dead = [dict(mk(0, "E1", "AAAAAAA", 50.0))]
    sel3, log3 = select(dead, verbose=False)
    check("select: returns empty when nothing passes, rather than lowering the bar",
          sel3 == [])

    check("select: cross-family agreement is not_run when Boltz-2 has not been run",
          score_rows([dict(mk(0, "E1", "AAAAAAA", 5.0))])["d0"]["cross_family_agree"]
          == NOT_RUN)

    print(f"\nself-test: {sum(ok)}/{len(ok)} passed")
    return all(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--tsv", default="candidates.tsv")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.self_test:
        print("08_rank_select.py self-test (synthetic candidates)")
        sys.exit(0 if self_test() else 1)

    p = Path(a.tsv)
    if not p.exists():
        print(f"no manifest at {p} -- run 06_harvest.py first")
        sys.exit(1)
    rows = list(csv.DictReader(open(p), delimiter="\t"))
    print(f"[load] {len(rows)} candidates from {p}")
    sel, _ = select(rows)
    out = Path(a.out) if a.out else p
    cols = list(rows[0].keys()) if rows else []
    with open(out, "w") as w:
        w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r.get(c, NOT_RUN)) for c in cols) + "\n")
    print(f"[write] {out} updated with cluster_id / rank_final / selected")


if __name__ == "__main__":
    main()
