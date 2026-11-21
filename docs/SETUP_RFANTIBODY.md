# SETUP_RFANTIBODY.md — install runbook (critical path)

**Time box: 3 hours. Hard abort at gate G1 (Sun 08:00 AEDT, T−56h).**

RFantibody has **never been installed on this box.** Treat this as a timed, abortable
task with a fallback, not an assumption. Append every command and every error to
`RUNLOG.md` as you go — if this fails, the log is what tells the next session whether to
retry or fall back.

Repo: `https://github.com/RosettaCommons/RFantibody`

Three components, which map onto our pipeline stages:

| Component | Weights | Role |
|---|---|---|
| Antibody-finetuned RFdiffusion | `RFdiffusion_Ab.pt` | CDR backbone design against the target, framework fixed |
| ProteinMPNN (interface mode) | `ProteinMPNN_v48_noise_0.2.pt` | CDR sequence design |
| RF2 (antibody) | `RF2_ab.pt` | Structure prediction + **the filter** |

---

## Step 0 — Reachability check. DO THIS FIRST. (2 minutes)

`include/download_weights.sh` pulls from an institutional host (IPD/UW), **not** from
GitHub or PyPI. The VM's verified-reachable hosts are RCSB, PyPI and GitHub. If the
weights host is unreachable, **the entire local arm is dead** and you need to know that in
minute two, not hour two.

```bash
cd /tmp
curl -sS -o /dev/null -w '%{http_code}\n' https://github.com/RosettaCommons/RFantibody
# inspect the script to find the real weight URLs, then HEAD each host:
git clone --depth 1 https://github.com/RosettaCommons/RFantibody /tmp/rfab-probe
grep -Eo 'https?://[^ "'"'"']+' /tmp/rfab-probe/include/download_weights.sh
# for each distinct host:
curl -sSI --max-time 20 <WEIGHT_URL> | head -1
```

**If the weight host is blocked:** do not burn the time box on workarounds. Record it,
switch to fallback rung **F1** (Geodesic-only) in `PIPELINE.md` §5, and tell the user —
extending the VM's egress allowlist is their call, not something to attempt silently.

---

## Step 1 — Disk discipline before you install anything

Root has **~25 GB free (99% full)**. A careless install will fill it and take the box
down mid-sprint. `uv` defaults put its cache *and* its downloaded Python interpreters on
root, and torch CUDA wheels are multi-GB.

**Export these before touching `uv`, and put them in a sourceable env file so every later
session inherits them:**

```bash
mkdir -p /mnt/comp5data/bd-il4r/{rfantibody,weights,uv-cache,uv-python,out}
cat > /mnt/comp5data/bd-il4r/env.sh <<'ENVEOF'
export BDIL4R=/mnt/comp5data/bd-il4r
export UV_CACHE_DIR=$BDIL4R/uv-cache
export UV_PYTHON_INSTALL_DIR=$BDIL4R/uv-python
export PIP_CACHE_DIR=$BDIL4R/uv-cache/pip
export TORCH_HOME=$BDIL4R/torch-home
export HF_HOME=$BDIL4R/hf-home
ENVEOF
source /mnt/comp5data/bd-il4r/env.sh
df -h / /mnt/comp5data      # record both before and after
```

**Do not use the Docker install path.** Docker's data-root lives on `/`, and an
RFantibody image build (CUDA base + torch) will very plausibly exhaust 25 GB. Relocating
Docker's data-root mid-sprint is a worse risk than the local install. The existing
`rosettacommons/rfdiffusion` image (12.24 GB reclaimable, which we want to **keep**) is
already on root.

---

## Step 2 — Clone and fetch weights (to scratch)

```bash
source /mnt/comp5data/bd-il4r/env.sh
cd $BDIL4R
git clone https://github.com/RosettaCommons/RFantibody.git rfantibody
cd rfantibody
git rev-parse HEAD                      # <-- record this commit in RUNLOG.md
bash include/download_weights.sh        # -> ./weights/
ls -la weights/ && du -sh weights/
```

Assert all three expected files are present and non-trivially sized:
`RFdiffusion_Ab.pt`, `ProteinMPNN_v48_noise_0.2.pt`, `RF2_ab.pt`.

If the clone lands on root by accident, move it before proceeding. Check `df -h /`.

---

## Step 3 — Environment via `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc          # or restart the shell
cd $BDIL4R/rfantibody
uv sync                   # creates .venv, pulls Python 3.10 + torch (CUDA 11.8 wheels)
```

Then the **Deep Graph Library** step the README calls out separately — DGL must come from
CUDA-enabled wheels, and it is the most common install failure in this stack. Follow the
repo's current instruction verbatim; do not improvise a version.

**CUDA note:** the box has driver 550.90.07 / CUDA 12.4. RFantibody's torch is built
against **CUDA 11.8**. That is fine — the driver is backward compatible — but it means
**this venv is independent of every existing conda env.** Do not try to make it share
`boltz`'s torch 2.14.1+cu126 or `mpnn`'s 2.5.1+cu121. And under no circumstances touch
`af2ig`, whose jax 0.4.20 pins are load-bearing and fragile.

Verify:

```bash
cd $BDIL4R/rfantibody
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
uv run rfdiffusion --help          # should print RFdiffusion help
```

`torch.cuda.is_available()` **must** print `True`. A silent CPU fallback is the exact
failure that turned a 10 s/design screen into something unusable in a prior campaign.
Check it explicitly; never infer it from a run "looking like it started".

---

## Step 4 — Patch the known-bad default paths BEFORE the first run

These are documented upstream issues. Fixing them now costs 5 minutes; discovering them
costs an hour each, and the RF2 one fails at the *end* of a pipeline run.

| File | Problem | Fix |
|---|---|---|
| `src/rfantibody/rf2/config/base.yaml` (may be `.yml`) | `model_weights` points at a path that does not exist → **RF2 stage fails at the end of the run** | Set to the absolute path of your `RF2_ab.pt` |
| `scripts/proteinmpnn_interface_design.py` (~line 45) | hardcoded `/home/weights/ProteinMPNN_v48_noise_0.2.pt` (a Docker-internal path) | Set to your real weights path |
| `src/rfantibody/rfdiffusion/inference/model_runners.py` (~line 75) | default checkpoint name may be `base_complex_finetuned_BFF_9.pt` | Either set to `RFdiffusion_Ab.pt` or always pass `inference.ckpt_override_path` explicitly |

Line numbers are indicative — **grep, do not trust them**:

```bash
grep -rn "weights/" src/rfantibody/rf2/config/ scripts/ | grep -v Binary
grep -rn "base_complex_finetuned\|RFdiffusion_Ab" src/rfantibody/rfdiffusion/inference/model_runners.py
```

Prefer **passing paths explicitly on the command line** over editing files, where the
option exists — it keeps the repo clean and makes the run self-documenting in RUNLOG.
`git diff` whatever you did have to edit, and paste it into RUNLOG.md.

---

## Step 5 — Two-design pilot (the G1 gate)

Do not launch production. Run **2 designs end to end** and look at the output.

```bash
source /mnt/comp5data/bd-il4r/env.sh
cd $BDIL4R/rfantibody
mkdir -p $BDIL4R/out/pilot

# Stage 1: CDR backbone design. Note the trajectory flag.
uv run rfdiffusion \
  --config-name antibody \
  antibody.target_pdb=$BDIL4R/target/crops/E1_target_HLT.pdb \
  antibody.framework_pdb=$BDIL4R/target/frameworks/hu4D5-8_Fv_HLT.pdb \
  inference.ckpt_override_path=$BDIL4R/rfantibody/weights/RFdiffusion_Ab.pt \
  inference.num_designs=2 \
  inference.output_prefix=$BDIL4R/out/pilot/e1 \
  inference.write_trajectory=False
```

**Disable trajectory output.** A prior campaign leaked ~6 GB of trajectory dumps
unnoticed, on a box that now has 25 GB of root headroom. Confirm the exact flag name
against `--help` for this version; if the flag differs, find it — do not skip it.

Then ProteinMPNN over the designed CDRs, then RF2. Time each stage with `/usr/bin/time -v`
and record **seconds per design** for all three. These numbers size the whole campaign at
gate G2.

### Pilot acceptance criteria — all must hold

- [ ] Three chains in the output, IDs exactly `H`, `L`, `T`
- [ ] The diffused regions are the **CDR loops**, not framework. Open it in PyMOL (`viz` env) and look.
- [ ] CDR loops contact the **intended epitope residues**, not a different patch
- [ ] RF2 produced a scorefile with non-null interface metrics
- [ ] **Interface metrics are computed on (H+L) vs T, not globally.** Global ipTM on an Fv is ~0.9 from the H↔L interface alone and tells you nothing about antigen binding. If the shipped scorefile only reports global ipTM, you must compute the H+L vs T interface yourself.
- [ ] `torch.cuda.is_available()` was True and GPU utilisation was non-zero during the run
- [ ] Measured s/design recorded in RUNLOG.md for each of the three stages

If any box is unticked at **Sun 08:00 AEDT**, abort to fallback rung F1.

---

## Step 6 — Production

Only after G1 passes and G2 sizing is done.

- Run in **tmux**. Never a bare foreground shell. The session will drop.
- Checkpoint and make the stage resumable. Write per-design outputs, not one big blob.
- All output under `$BDIL4R/out/`, never under `/`.
- Watch `df -h /` and `df -h /mnt/comp5data` on a timer. Abort on root dropping below 10 GB.
- Keep raw outputs separate from processed metrics. Never overwrite a raw result.
- Reserve GPU time for the **deep-resample round** on surviving backbones
  (`PIPELINE.md` §3) — historically ~27× the hit rate of more geometry at a fifth of
  the cost. This is the highest-value use of the back half of the GPU budget.

---

## Step 7 — Record in RUNLOG.md

Non-negotiable, whether this succeeded or failed:

- RFantibody commit SHA
- `uv.lock` / resolved torch + DGL versions
- Every file patched, with the diff
- Measured s/design for each stage
- Which pilot acceptance boxes passed, which failed, and what you did about it
- `df -h` before and after

If RFantibody failed, the log must say **why**, precisely enough that nobody retries the
same dead end at 3am.
