# RUNLOG.md

**Append-only.** Never edit or delete an earlier entry — including a wrong one. If a
conclusion is retracted, append the retraction; do not rewrite history. This file is the
most valuable artefact in the repo and the reason the results can be trusted.

Every entry: what you intended, the **exact command**, what came out, what it cost, and
what you concluded. Failures and dead ends are the highest-value content here — they stop
the next session at 3am from retrying something already known to be broken.

Template:

```
## YYYY-MM-DD HH:MM AEDT -- <short title>
Gate: G_  |  Arm: A/B  |  T-__h
Intent:
Command:
Result:
Cost: __ GPU-min / __ credits
Conclusion:
Next:
```

---

## 2026-11-21 ~22:00 AEDT -- repo handoff prepared
Gate: pre-G0  |  Arm: -  |  T-66h

Intent: stand up the repo and planning docs for the Beyond Binding Round 1 sprint.

Result: docs written. Key findings from reading the brief and verifying sources:

- **Deadline is T-66h, not weeks.** Mon 23 Nov 23:59 ET = Tue 24 Nov 15:59 AEDT.
  Confirmed live via GenScript's own announcement, same date and deadline.
- **Format gap.** The challenge needs paired VH/VL IgG. All five prior campaigns on this
  box produced single-chain minibinders. The proven 4-pillar stack does not transfer:
  RFdiffusion base checkpoints are not antibody-finetuned, and AF2 initial-guess assumes a
  single-chain binder. **RFantibody is the right tool and is not installed.**
- **Target verified.** UniProt P24394: signal 1-25, ECD topological domain **26-232**
  (exactly matches the brief), TM 233-256, disulfides 34-44 and 74-86.
  **N-glycosylation at N53, N98, N128, N134, N176, N209 -- all six inside the ECD.**
  Six glycans on a 207-residue domain materially constrains epitope choice.
- **Better structure than the one the brief cites.** The brief sources its image from
  **3BPN** (3.02 A, ternary IL-4/IL-4Ra/IL-13Ra1, NAG modelled on chain B). **1IAR**
  is a 2.30 A binary IL-4/IL-4Ra complex, chain B = 207 aa, matching the ECD exactly.
  Using 1IAR chain B as the design target, 3BPN chain B as cross-check.
  Note 1IAR chain B carries **M1F and C182A** -- C182 is an unpaired Cys in the WT ECD.
- **Geodesic "tokens" are credits.** 1,000 = the Plus tier *weekly* allowance, resets
  00:00 UTC on an assigned day, **does not roll over**. Cost varies by model and input
  size and is quoted before submitting. **Failed or cancelled runs are still charged.**
  Top-up is **$0.01/credit, min $5** -- i.e. ~$10 per 1,000. Entirely separate currency
  from Claude Code tokens (LLM inference, buys no protein compute) and from GenScript
  service credits (pre-applied, just verify the order total reads 0.00 USD).
- **Open gate G0:** the public NovaDDE writeup shows antibody CDR design with a **VHH**
  example (`h-NbBCII10` framework). A VHH cannot be submitted -- the template requires
  both a heavy and a light chain. **Paired VH/VL support must be confirmed before any
  credits are spent.**

Scripts written and tested: `qc_liabilities.py` (self-test passes, 6 synthetic cases),
`build_submission.py` (validation guard rails confirmed to refuse on row-count mismatch),
`00_verify_env.sh` (countdown + fail-loud checks confirmed).

Conclusion: fallback rung **F0** assumed (both arms live) pending gate G0.

Next:
1. **User:** test the GenScript challenge login. Confirm the Geodesic account email
   matches the challenge-registration email.
2. **User:** Geodesic Settings -> Usage -- note the credit reset day. A reset inside the
   sprint window is +1,000 free credits.
3. **G0:** confirm whether NovaDDE supports paired VH/VL. If VHH-only, Arm B is dead ->
   rung F2.
4. **Step 0 of `docs/SETUP_RFANTIBODY.md`:** probe the RFantibody weight-download host
   reachability from the VM *before* spending any of the 3-hour install time box. The
   weights come from an institutional host, not GitHub or PyPI, and only RCSB/PyPI/GitHub
   are verified reachable.

---

## 2026-11-21 ~23:00 AEDT -- handoff finalised, decisions locked
Gate: pre-G0  |  Arm: -  |  T-65h

Intent: convert the planning pack into a docs-only Claude Code handoff and close the open
questions from the first pass.

Decisions taken by the user:

- **RFantibody is the primary local arm.** Disk headroom confirmed on the second disk
  (`/mnt/comp5data`, ~977 GB). Install via **`uv`**, not Docker: Docker's data-root is on
  the 99%-full root disk, and relocating it mid-sprint orphans the existing
  `rosettacommons/rfdiffusion` image for no benefit. Scratch discipline still applies --
  root has ~25 GB and `uv`'s caches default there.
- **Epitope allocation: split.** ~12 at the IL-4/IL-13 competitive site (E1), ~5 + ~3 at
  two alternate glycan-masked patches (E2/E3). Hedges epitope-level failure.
- **No Python in the handoff.** The agent authors every module from the specs; `scripts/`
  ships empty. `CLAUDE.md` section 10 is the module-to-spec map. Nothing was lost -- the
  liability screen, novelty screen, ranking and submission builder were already fully
  specified in `RANKING_AND_QC.md` sections 2-6 and `SUBMISSION.md` sections 1-2.
- `KICKOFF_PROMPT.md` added: stateless, re-pasted each session, state carried by this log
  and `config/sprint.yaml`.

Verified against the live challenge hub this session:

- **Design format is IgG1**, stated specifically on the hub -- not "IgG1 or IgG4" as the
  batch-template dropdown implies. `CH Type` is therefore **locked to Human IgG1** for all
  20. Removes an ambiguity that was previously a judgement call.
- Target restated identically on the hub: UniProt **P24394-1**, **AA26-232**, up to 20
  designs per participant. No contradiction with the brief.
- **No deadline extension or change.** The hub states no new date. Deadline stands at
  Mon 23 Nov 23:59 ET / Tue 24 Nov 15:59 AEDT.

**GenScript service credits clarified -- there is nothing to manage.** They are a coupon
pre-loaded on the *challenge-specific* GenScript account that auto-applies at checkout and
zeroes the order (20 x $152.50 = $3,050, plus the Carterra LSA assay, plus the 100ug
Fc-tagged antigen; Item Count 22). Three operational consequences only: log in with the
challenge account from the official e-mail and not a personal one, verify the total reads
0.00 USD before confirming, and do not deviate from the scoped order (format, count,
assay, antigen) or the coupon may not apply. Nothing to conserve -- submit all 20.
Documented in `CHALLENGE_SPEC.md` section 9b. Distinct from Geodesic credits, which are a
real metered budget.

Conclusion: handoff complete. Fallback rung **F0** assumed pending gate G0.

Next, in order (cheapest hard blockers first):
1. **Agent, 2 min:** probe the RFantibody weight-download host reachability from the VM
   (`SETUP_RFANTIBODY.md` Step 0). Institutional host, not GitHub/PyPI; only RCSB, PyPI and
   GitHub are verified reachable. A block here kills the local arm -> rung F1.
2. **Agent:** scratch + `env.sh` with `uv` caches redirected, then install, then patch the
   three known-bad weight paths, then target prep, then the 2-design pilot. 3-hour time
   box, hard abort at G1.
3. **User:** test the challenge-specific GenScript login.
4. **User:** confirm the Geodesic account email matches the challenge-registration email,
   and note the credit reset day under Settings -> Usage. A reset inside the sprint is
   +1,000 free credits.
5. **User, gate G0:** confirm whether NovaDDE supports paired VH/VL. The public example is
   a VHH, which cannot be submitted -- the template requires both chains. VHH-only -> Arm B
   is dead -> rung F2.

---

## 2026-11-21 12:28–12:40 UTC (23:28 AEDT) — OVERNIGHT SESSION START. Weight host probe + RFantibody install
Gate: G1 (in progress)  |  Rung: F0  |  T-64.5h

**Mode:** unattended overnight run per `OVERNIGHT_ADDENDUM.md`. User asleep until ~08:00
AEDT. All ambiguity resolved by the agent and logged here. Zero Geodesic credits spent;
Arm B left `not_started` per the addendum.

### Action 1 — RFantibody weight host reachability (SETUP_RFANTIBODY.md Step 0). PASS.

Intent: the weights come from an institutional host (IPD/UW), not GitHub/PyPI. Only RCSB,
PyPI and GitHub were verified reachable from this box. A block here kills the local arm.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://github.com/RosettaCommons/RFantibody   # 200
git clone --depth 1 https://github.com/RosettaCommons/RFantibody /tmp/rfab-probe
grep -Eo 'https?://[^ "'"'"']+' include/download_weights.sh
curl -sSI --max-time 25 https://files.ipd.uw.edu/pub/RFantibody/<each>.pt | head -1
```

Result — **all weight hosts reachable**:

| URL | HTTP | content-length |
|---|---|---|
| `files.ipd.uw.edu/pub/RFantibody/RFdiffusion_Ab.pt` | **200** | 483,452,922 |
| `files.ipd.uw.edu/pub/RFantibody/RF2_ab.pt` | **200** | 294,759,918 |
| `files.ipd.uw.edu/pub/RFantibody/ProteinMPNN_v48_noise_0.2.pt` | **200** | 6,681,301 |
| `zenodo.org/records/17488258/...RFab_noframework...pt` (RF2 **TCR**) | **200** | 882,991,901 |

**Conclusion: the local arm is alive. Rung stays F0 (Arm A live; Arm B deferred, not dead).**
No egress-allowlist decision needed from the user. That parked item is moot for Arm A.

**Decision (agent, logged for reversal):** skipped the 883 MB Zenodo **RF2 TCR** weight.
`grep -rn` over `src/`, `scripts/` shows it is referenced **nowhere** in the codebase —
only `include/download_weights.sh` fetches it. It is for TCR design, not antibody design.
Saves 883 MB and ~2 min. Reversible: re-run the wget line if an RF2 config ever asks for it.
Downloaded the other three directly rather than via `download_weights.sh` (the script's
`&&` chain would have forced the TCR download too).

### Action 2 — scratch + env file (Step 1). DONE.

`/mnt/comp5data/bd-il4r/env.sh` written and is the sourceable env for every later session:
`BDIL4R`, `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `PIP_CACHE_DIR`, `TORCH_HOME`,
`HF_HOME`, `XDG_CACHE_HOME` all redirected to scratch; `PATH` += `~/.local/bin`;
`DGLBACKEND=pytorch` (silences a DGL backend warning on every import).

Disk, before and after the whole install:

```
BEFORE  /dev/sda1 2.0T 1.9T  25G 99% /          /dev/sdb 984G 6.9G 977G 1% /mnt/comp5data
AFTER   /dev/sda1 2.0T 1.9T  25G 99% /          /dev/sdb 984G  14G 970G 2% /mnt/comp5data
```

**Root did not move.** The cache redirection worked; ~7 GB landed on scratch as intended.

### Action 3 — install (Steps 2–3). DONE in ~6 min against a 3-hour time box.

- RFantibody commit SHA: **`efe4b9040f051edc229e9318ead586ff76236c9b`**
- `uv` 0.13.9 installed to `~/.local/bin`; `uv cache dir` confirmed `=/mnt/comp5data/bd-il4r/uv-cache`
- `uv sync`: **24.4 s**. Resolved torch **2.3.1+cu118**, torchvision 0.18.1+cu118,
  torchaudio 2.3.1+cu118, triton 2.3.1, numpy 1.x, dgl **2.4.0+cu118**, hydra-core,
  biotite, e3nn, pandas 2.3.3. venv at `$BDIL4R/rfantibody/.venv` (on scratch).

**CUDA verification — the silent-CPU-fallback check:**

```
torch 2.3.1+cu118
cuda_available True          <-- REQUIRED. confirmed, not inferred
device NVIDIA A100-SXM4-80GB
dgl 2.4.0+cu118
matmul ok True               <-- real GPU tensor op executed
```

**Correction to `SETUP_RFANTIBODY.md` Step 3 — the DGL warning is now stale.** The doc
says DGL "must come from CUDA-enabled wheels, and it is the most common install failure
in this stack", implying a separate manual step. At commit `efe4b90` that is **already
fixed upstream**: `pyproject.toml` pins dgl to a wheel hosted on the RFantibody GitHub
releases page (`deps-dgl-2.4.0/dgl-2.4.0+cu118-cp310-cp310-manylinux1_x86_64.whl`),
because the original dgl.ai host went away. `uv sync` handles it with no manual step.
No action needed; flagging so nobody hunts for a problem that no longer exists.

### Known-bad paths confirmed present (Step 4) — to patch before first run

`grep` confirms both documented traps are real at this commit:

```
src/rfantibody/rf2/config/base.yaml:18:  model_weights: /home/weights/RF2_ab.pt
scripts/proteinmpnn_interface_design.py:45: ... '/home/weights/ProteinMPNN_v48_noise_0.2.pt'
```

Both are Docker-internal paths that do not exist in a `uv` local install. Third trap
(`model_runners.py` checkpoint default) still to be checked. Patching next.


### Step 4 — weight-path patches applied. All three traps resolved.

**Finding that changes the risk picture: at commit `efe4b90` the CLI entry points already
inject the correct weights path, so the two documented "known-bad path" traps cannot fire
when the pipeline is driven through `rfdiffusion` / `proteinmpnn` / `rf2`.**
`src/rfantibody/cli/inference.py` calls `PathConfig.get_weight_path(<model>)` and appends
an explicit override (lines 134, 276, 425). `PathConfig.WEIGHTS_DIR` defaults to
`PROJECT_ROOT/weights`, which is exactly where ours live, so resolution is correct:

```
rfdiffusion  .../weights/RFdiffusion_Ab.pt             exists=True  size=483452922
proteinmpnn  .../weights/ProteinMPNN_v48_noise_0.2.pt  exists=True  size=6681301
rf2          .../weights/RF2_ab.pt                     exists=True  size=294759918
```

All three sizes match the `content-length` from the Step 0 HEAD probe exactly — downloads
are complete and not truncated.

**But the injection is conditional on `default_weights.exists()`, with a silent fallthrough
to the Docker path if it is false.** That is a latent silent-failure mode, so the patches
were applied anyway as belt-and-braces:

```diff
--- a/src/rfantibody/rf2/config/base.yaml
-  model_weights: /home/weights/RF2_ab.pt
+  model_weights: /mnt/comp5data/bd-il4r/rfantibody/weights/RF2_ab.pt

--- a/scripts/proteinmpnn_interface_design.py
-default_ckpt = os.path.join( os.path.dirname(__file__), '/home/weights/ProteinMPNN_v48_noise_0.2.pt')
+default_ckpt = '/mnt/comp5data/bd-il4r/rfantibody/weights/ProteinMPNN_v48_noise_0.2.pt'
```

(The original mpnn line was doubly broken: `os.path.join` with an absolute second argument
discards the first, so `os.path.dirname(__file__)` was dead code.)

**Trap 3 confirmed real and handled differently.** `model_runners.py:70-81` falls back to
IPD-internal paths (`/net/databases/diffusion/models/hotspot_models/base_complex_finetuned_BFF_9.pt`
et al.) when `inference.ckpt_override_path` is None. Per the runbook's preferred option we
will **always pass the checkpoint explicitly** rather than edit the file. `model_runners.py:196`
prints the resolved `ckpt_path` at load time — the pilot log will be checked for it.

`--no-trajectory` confirmed as the real flag name against `rfdiffusion --help`
(maps to `inference.write_trajectory=False`). Trajectory output will be off in every run.

### Doc/code mismatch, non-blocking
README says the HLT converter is `scripts/util/chothia_to_HLT.py`; the file on disk is
`scripts/util/chothia2HLT.py`. Not on our critical path — the hu-4D5-8 framework ships
pre-converted at `scripts/examples/example_inputs/hu-4D5-8_Fv.pdb`.

### Upstream guidance captured from README (drives G2 sizing and the filter)
- **Authors' minimal filter: RF2 pAE < 10, and RMSD(design vs RF2 prediction) < 2 Å.**
  Rosetta ddG < -20 optional (Rosetta not installed; skip).
- Authors state the filter is the pipeline's main weakness and expect **~10k designs** for
  hits in the general case. We have ~24 GPU-h. This confirms `PIPELINE.md` §6's honest
  expectation of 1-3 hits and makes **diversity over depth** the correct strategy.
- Example CDR loop ranges: `H1:7,H2:6,H3:5-13,L1:8-13,L2:7,L3:9-11`.
- "RFantibody is more sensitive to exactly which hotspots are selected than vanilla
  RFdiffusion... will generally just generate an undocked antibody if a bad set of
  hotspots is given." **Undocked output is the expected symptom of bad hotspots** — this is
  the thing to look for in the pilot, not a crash.
- Authors independently flag that **sites with nearby glycans are hard** because the glycan
  orders on binding. Independent support for the 12 A glycan mask.
- Hotspot syntax is chain-prefixed target numbering, e.g. `-h "T305,T456"` -> post-crop
  chain-T numbering. This is exactly the trap in `TARGET_PREP.md` §1.

