# OVERNIGHT_ADDENDUM.md

Paste this **after** `KICKOFF_PROMPT.md` when starting an unattended run. It changes only
one thing: what the agent may decide on its own while nobody is awake to ask.

---

## Overnight mode

You are running unattended in tmux. The user is asleep and **will not answer questions
until morning.** A question you ask now costs the whole night.

**Take the most reasonable reading of anything ambiguous, state at the top of your work
which reading you took, and carry on.** Log the decision in `RUNLOG.md` so it can be
reversed in the morning. Do not stop to confirm. Do not idle.

### Overnight objective

**Pass gate G1 and get production launched.** Concretely, by morning:

1. RFantibody installed and verified, or **cleanly aborted** with the reason recorded
2. Target prepped: numbering map, glycan mask, E1 frozen, HLT inputs built
3. The 2-design pilot run, acceptance criteria evaluated, **seconds per design measured**
   for all three stages
4. If the pilot passed: production sized against remaining GPU hours and **launched in
   tmux**, E2/E3 frozen, framework arms decided
5. `RUNLOG.md` and `config/sprint.yaml` current enough that the user can read them over
   coffee and know exactly where things stand

### Decide on your own — do not wait for permission

- Every install, dependency and debugging choice
- Patching RFantibody's known-bad weight paths
- Epitope scoring parameters, patch ranking, which patches become E2/E3
- Relaxing the glycan mask radius from 12 Å to 10 Å **if and only if** masking leaves no
  viable epitope — and log it loudly
- Framework arm decision at G2 (drop the germline arm if its pilot metrics are clearly
  worse)
- Run sizing, batch sizes, seeds, how many MPNN draws per backbone
- Declaring a fallback rung and moving to it
- Writing, testing and committing any module in `scripts/`
- Killing your own run if it is thrashing, and recording why

### Park until morning — do not do these alone

| Parked | Why |
|---|---|
| **Extending the VM's egress allowlist** | Not yours or mine to change |
| **Spending money on Geodesic credits** | The user's money |
| **Any Geodesic run at all** | Gate G0 is unresolved — paired VH/VL support is unconfirmed, and failed runs are charged. **Spend zero credits overnight.** |
| **Anything touching Dr. G or the submission** | Human-in-the-loop, and the deadline is still ~65h out |
| **`git push`** | Commit locally all night; the user decides about the remote |
| **Ordering anything, emailing anyone** | External actions |

**Assume Arm B is unavailable tonight and run RFantibody-only.** That is not the fallback
rung F2 — it is a timing fact. Leave `arms.B_geodesic.status` as `not_started` and
`paired_vh_vl_supported: unknown` in `config/sprint.yaml`. Do not write off Arm B.

If you hit a parked decision, write it in `RUNLOG.md` under a clear
`## BLOCKED — needs user` heading, then **keep working on everything that does not depend
on it.**

### If RFantibody aborts at G1

Do not thrash. Do not keep retrying the same failure past the time box.

1. Record precisely why, with the commands and errors, so nobody retries the dead end
2. Set `fallback_rung` in `config/sprint.yaml`
3. Then spend the remaining night on work that is useful under **every** rung: target
   prep, epitope definition and scoring, the liability screen, the novelty reference set
   and screen, the ranking and selection module, the submission builder. **All of that is
   generator-agnostic and all of it has to exist regardless.** None of it needs a GPU.
4. Write a `## MORNING BRIEF` section at the end of `RUNLOG.md`: what works, what does
   not, what the user must decide, and the single highest-value next action

Do that last step **whatever** happens overnight, success or failure. It is the handover.

## Commits

Committing is **authorised and expected**. Local commits only — no push.

Commit after each of these, not in one batch at the end:

- A gate passes, or a fallback rung changes
- A module is written **and its self-test passes**
- A measurement lands in `RUNLOG.md`
- Target prep produces a frozen artefact (numbering map, glycan mask, an epitope JSON)
- Any patch to RFantibody's source — commit the diff into the repo as a record even
  though the install lives on scratch
- Before launching any long GPU run, so there is a known-good point to return to

**Your first commit is the baseline.** Before doing anything else, commit the handoff
docs as they stand (`docs: handoff baseline`) so every later diff is attributable. Confirm
`.gitignore` is in place first.

Message format:

```
<stage>: <what changed>

- what you did
- what it measured or produced, with numbers
- anything still broken

Gate: G1 | Rung: F0 | T-54h
```

Rules:

- **Never commit bulk artefacts.** `.gitignore` covers weights, PDBs, checkpoints, venvs,
  trajectories. Bulk lives on `/mnt/comp5data/bd-il4r/`. If `git status` shows something
  large, fix `.gitignore` rather than force-adding it.
- **Never commit credentials**, the challenge account details, or Geodesic tokens.
- `RUNLOG.md` is append-only. If you retract a conclusion, append the retraction — never
  rewrite or delete an earlier entry, including a wrong one.
- Commit `candidates.tsv`. It is small and it is the audit trail.

## A trap specific to running in tmux

**A permission prompt with nobody watching stalls the entire night.** Before detaching,
make sure your session is configured to run without interactive approval for the work it
needs to do, and confirm it by watching one real tool call succeed.

Second: **assume the session can still drop.** Every long stage goes in its own tmux
window, checkpointed and resumable. A stage that cannot resume from where it died is a
stage that has to be re-run, and you do not have the hours for that.

Third: **watch the disk.** Root is 99% full. Keep a monitor running and **abort any run if
root drops below 10 GB** — a full root disk on a shared box is a worse problem than a
missed gate.