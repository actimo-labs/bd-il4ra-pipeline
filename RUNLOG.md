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
