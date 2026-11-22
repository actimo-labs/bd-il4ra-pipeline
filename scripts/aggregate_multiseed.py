#!/usr/bin/env python
"""
aggregate_multiseed.py -- average RF2 interaction_pae over seeds, update the manifest.

RF2 is stochastic with a spread wide enough to decide pass/fail (see
14_rf2_multiseed.sh header). This replaces the single-sample `rf2_iface_hl_vs_t`
with a multi-sample mean and records the between-seed sd, so a design whose score
swings wildly is visible as weak even when its mean looks good.

The ORIGINAL single-sample value is preserved in rf2_iface_single_sample so nothing
is lost and the before/after is auditable.

Usage: aggregate_multiseed.py <multiseed_dir> <candidates.tsv>
"""
import csv
import json
import statistics
import sys
from pathlib import Path


def scores(p):
    for line in p.read_text().splitlines():
        if line.startswith("SCORE interaction_pae:"):
            try:
                return float(line.split(":")[1])
            except ValueError:
                return None
    return None


def other(p, key):
    for line in p.read_text().splitlines():
        if line.startswith(f"SCORE {key}:"):
            try:
                return float(line.split(":")[1])
            except ValueError:
                return None
    return None


MIN_SEEDS = 3   # refuse to average fewer than this; 1-2 samples is the problem, not the fix


def main():
    allow_partial = "--allow-partial" in sys.argv
    root, man = Path(sys.argv[1]), Path(sys.argv[2])
    mapping = json.loads((root / "name_to_candidate.json").read_text())

    per = {}          # candidate_id -> list of pae
    per_rmsd = {}     # candidate_id -> list of target_aligned_antibody_rmsd
    seed_dirs = sorted(root.glob("seed_*"))
    for d in seed_dirs:
        for f in d.glob("*.pdb"):
            name = f.stem.replace("_best", "")
            cid = mapping.get(name)
            if cid is None:
                continue
            v = scores(f)
            if v is not None:
                per.setdefault(cid, []).append(v)
            rv = other(f, "target_aligned_antibody_rmsd")
            if rv is not None:
                per_rmsd.setdefault(cid, []).append(rv)

    print(f"[aggregate] {len(seed_dirs)} seed directories, {len(per)} designs with scores")
    if not per:
        sys.exit("REFUSING: no scores parsed -- nothing to aggregate")
    ns = [len(v) for v in per.values()]
    print(f"[aggregate] samples per design: min {min(ns)} median {statistics.median(ns):.0f} max {max(ns)}")

    # HARD GUARD. Running this on a partial sweep silently mixes 1-sample and n-sample
    # values into one column that ranking then gates on as if comparable -- which is the
    # exact failure this whole job exists to fix. Refuse rather than warn.
    if min(ns) < MIN_SEEDS and not allow_partial:
        short = sum(1 for n in ns if n < MIN_SEEDS)
        sys.exit(
            f"REFUSING TO AGGREGATE: {short} of {len(ns)} designs have fewer than "
            f"{MIN_SEEDS} seeds (min {min(ns)}). A partial sweep would put 1-sample and "
            f"n-sample means in the same column and rank them against each other. "
            f"Let the sweep finish, or pass --allow-partial if you genuinely want this.")

    rows = list(csv.DictReader(open(man), delimiter="\t"))
    cols = list(rows[0].keys())
    for c in ("rf2_iface_single_sample", "rf2_iface_mean", "rf2_iface_sd",
              "rf2_iface_n_seeds", "rf2_iface_max", "rf2_dock_rmsd_mean"):
        if c not in cols:
            cols.append(c)

    hit = sum(1 for r in rows if r["candidate_id"] in per)
    if hit == 0:
        sys.exit(f"REFUSING TO WRITE: multi-seed join matched 0 of {len(rows)} rows on "
                 f"full candidate_id. Sample manifest id {rows[0]['candidate_id']!r}, "
                 f"sample scored id {next(iter(per))!r}")

    moved_in, moved_out = 0, 0
    for r in rows:
        for c in cols:
            r.setdefault(c, "not_run")
        v = per.get(r["candidate_id"])
        if not v:
            continue
        mean = statistics.mean(v)
        # IDEMPOTENCE: on a second run rf2_iface_hl_vs_t already holds the mean, so
        # reading it here would overwrite the preserved original with the mean and
        # destroy the audit trail this field exists for. Only ever write it once.
        if str(r.get("rf2_iface_single_sample", "not_run")) == "not_run":
            r["rf2_iface_single_sample"] = r.get("rf2_iface_hl_vs_t")
        single = r.get("rf2_iface_single_sample")
        r["rf2_iface_mean"] = round(mean, 3)
        # sample stdev, not population: 5 seeds are a sample of RF2's output distribution
        r["rf2_iface_sd"] = round(statistics.stdev(v), 3) if len(v) > 1 else "not_run"
        r["rf2_iface_n_seeds"] = len(v)
        r["rf2_iface_max"] = round(max(v), 3)
        rv = per_rmsd.get(r["candidate_id"])
        if rv:
            r["rf2_dock_rmsd_mean"] = round(statistics.mean(rv), 2)
            # ranking reads rf2_target_aligned_antibody_rmsd -- point it at the mean too,
            # or the pae in the same 0.40 RF2 block is multi-seed while this stays single
            r["rf2_target_aligned_antibody_rmsd"] = round(statistics.mean(rv), 2)
        # the ranking reads rf2_iface_hl_vs_t -- point it at the MEAN
        try:
            s = float(single)
            if s < 10 <= mean:
                moved_out += 1
            elif s >= 10 > mean:
                moved_in += 1
        except (TypeError, ValueError):
            pass
        r["rf2_iface_hl_vs_t"] = round(mean, 3)

    with open(man, "w") as w:
        w.write("\t".join(cols) + "\n")
        for r in rows:
            w.write("\t".join(str(r.get(c, "not_run")) for c in cols) + "\n")

    print(f"[aggregate] joined {hit}/{len(rows)} rows on full candidate_id")
    print(f"[aggregate] rf2_iface_hl_vs_t now holds the {statistics.median(ns):.0f}-seed MEAN; "
          f"single-sample value preserved in rf2_iface_single_sample")
    print(f"[aggregate] designs that CROSSED the pae<10 threshold once averaged:")
    print(f"              passed single-sample but fail on the mean: {moved_out}")
    print(f"              failed single-sample but pass on the mean: {moved_in}")
    sds = [statistics.stdev(v) for v in per.values() if len(v) > 1]
    if sds:
        print(f"[aggregate] between-seed sd: median {statistics.median(sds):.2f} "
              f"max {max(sds):.2f}")


if __name__ == "__main__":
    main()
