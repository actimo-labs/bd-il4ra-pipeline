# GEODESIC.md — NovaDDE: three different currencies, one budget

---

## 1. First: you are holding three unrelated currencies. Do not conflate them.

| Currency | Where | What it buys | Amount here | Who manages it |
|---|---|---|---|---|
| **Claude Code tokens** | Your VM / Claude account | **LLM inference only** — the agent reading files, writing code, reasoning. Buys **zero** protein compute. | Effectively unlimited | Nobody. Ignore it. |
| **Geodesic NovaDDE credits** | geodesiclab.com account | **Platform compute** — each run of a generative design model, each NovaAtom folding/prediction job | **~1,000** (= the Plus tier weekly allowance) | **Actively budget this. It is the scarce one.** |
| **GenScript service credits** | Challenge GenScript account | The experimental order: 20 sequences @ $152.50, Carterra LSA assay, the antigen | Pre-applied by organisers | Nothing to do. Just verify the order total reads **0.00 USD** before confirming. |

The thing you called "1000 tokens" is **1,000 Geodesic credits**. Geodesic's own pricing
page uses "credits" and never says "tokens". They are not LLM tokens and they have nothing
to do with your Claude Code allowance. Running the A100 locally costs **zero** Geodesic
credits — that is the whole reason Arm A exists.

---

## 2. How Geodesic credits actually behave

Verified from geodesiclab.com/pricing, 21 Nov 2026:

- **Weekly allowance, not a balance.** Resets at **00:00 UTC on your assigned day** and
  **does not roll over.** 1,000/week matches the **Plus** tier ($30/mo).
- **Cost varies by model and input size**, and the **exact cost is shown before you
  submit**, including per-model costs inside a pipeline. **Always read the quote.**
- **Creating a pipeline is free.** Only accepted executions draw credits.
- **Failed or cancelled runs are still charged** if they were accepted. There is no free
  exploration. Get the parameters right before you hit submit.
- **Top-up: $0.01/credit, minimum $5, purchased credits never expire** and are consumed
  only after the weekly allowance is gone.
- Balance and next reset date: **Settings → Usage**.

### The single most useful consequence

**Credits cost one cent.** 1,000 credits ≈ **$10**. Another 5,000 ≈ **$50**.

Weigh that against the cost of a degraded submission in a competition with a $2.5M prize
pool and a hard, non-extendable deadline. **Never let a credit ceiling reduce the quality
or diversity of the 20 designs.** If you run low, top up. This is the cheapest decision in
the entire sprint — do not spend an hour optimising credit usage when $20 removes the
constraint outright.

### Two things to check in the first ten minutes

1. **Settings → Usage: when is your reset day?** If it lands inside the sprint
   (Sat 21 → Tue 24 Nov), you get a second free 1,000. That materially changes the plan.
2. **Confirm your Geodesic account email matches your challenge-registration email.**
   The brief is explicit that token delivery depends on this.

---

## 3. Gate G0 — the question that decides whether Arm B exists at all

**Does NovaDDE's antibody designer support a paired VH/VL (Fv / IgG) format, or only
VHH / nanobody?**

The public workbench writeup describes picking "an antibody format, such as VHH, and a
framework template, such as h-NbBCII10", designing CDR1-3 de novo with settable CDR
lengths. The worked example is a **VHH**.

**A VHH cannot be submitted to this challenge.** The template requires both a heavy-chain
and a light-chain sequence. A single-domain antibody has no light chain.

So, before spending a single credit, log in and establish:

- [ ] Is there a paired **VH/VL**, **Fv**, **scFv** or **IgG** format option?
- [ ] Can CDRs be designed de novo across **both** chains?
- [ ] Can you supply your **own framework template** (so the hu-4D5-8 / germline framework
      choice from `TARGET_PREP.md` §5 stays consistent across both arms)?
- [ ] Can you supply your **own target PDB and hotspot residues** (our cropped, glycan-masked
      E1/E2/E3 definitions)?
- [ ] What does one design run of your intended size **cost in credits**?

**If paired VH/VL is not supported: Arm B is dead.** Write that in `RUNLOG.md`, drop to
fallback rung **F2** in `PIPELINE.md` §5, and put everything into RFantibody. Do not try
to salvage it by submitting a VHH sequence in the VH column with an invented light chain —
that is an invalid, unpaired construct and it will not express as designed.

---

## 4. What NovaDDE gives us that is worth credits

From the public workbench description:

| Capability | Value to this campaign |
|---|---|
| **De novo CDR1-3 design** on a chosen framework template, with settable CDR lengths | This is the core generator. Directly comparable to RFantibody's role. |
| Hotspot / epitope selection | Lets us drive it with our own E1/E2/E3 definitions instead of its defaults |
| **NovaAtom** folding model (incl. "Lite" tier) | A **third** structure-prediction family, independent of RF2 and Boltz-2. Cross-family agreement is the strongest computational evidence we can assemble. |
| ipTM and **refold RMSD** filtering | Refold RMSD is a self-consistency check we would otherwise have to build |
| **OASis humanness** metrics | Free Round 2 developability evidence, and useful supporting material if GenScript asks for methodology |
| Conversational agent that picks the generative model | Convenient, but it also means **you may not know which model ran.** Record what it tells you. |

Note on the last row: the agent choosing the model is a reproducibility hazard. For every
run, record in the manifest what model was used, what version if shown, the parameters,
and the credit cost. If it will not tell you, record that it would not. **Never write a
model name into the manifest that the platform did not actually confirm.**

---

## 5. Spending plan

Sequenced so that the irreversible spending happens last, after the cheap questions are
answered.

| Phase | Action | Credits |
|---|---|---|
| **0. Recon** | Log in, check Usage/reset day, answer every G0 checkbox, read the cost quote for a representative job. Create a pipeline (free). | **0** |
| **1. Pilot** | Smallest viable run on **E1** with the hu-4D5-8 framework. Inspect output format, confirm paired VH/VL comes back, confirm sequences are extractable. | small — record actual |
| **2. Calibrate** | From the pilot's actual cost, compute credits-per-design. Decide run sizes for E1/E2/E3. **Top up now if the plan exceeds the balance.** | 0 |
| **3. Production** | Breadth first: all three epitopes × both frameworks, rather than depth on E1. Arm B's job is diversity the local arm might miss. | the bulk |
| **4. Reserve** | Hold back **~15%** for a re-run if a batch comes back malformed, or to re-fold the final 20 through NovaAtom as the third-family cross-check. | ~15% |

### Rules

- Read the credit quote **every** time before submitting. Costs scale with input size.
- Small pilot before any large run. Failed runs are charged.
- Record **every** run's cost in RUNLOG.md so a burn rate exists before it matters.
- Prefer breadth over depth here — depth on proven backbones is what the **free** local
  A100 is for.
- Export sequences as soon as a run finishes. Do not leave the only copy of a result on
  someone else's platform during a sprint.

---

## 6. Carry-over to Round 2

If we advance, Geodesic's OASis humanness and refold-RMSD outputs for the submitted 20
are directly reusable as developability evidence. **Export and commit them to this repo
for every submitted design before the deadline**, even if they are not used in Round 1
ranking. After submission, the designs are frozen and the context is gone; a run you
exported on Monday is worth far more in January than a login you have to reconstruct.

---

## 7. Support

- Platform / access / token issues: **contact@geodesiclab.com**
- Docs and help centre: https://agent.geodesiclab.com/help
- Put "Beyond Binding Challenge" in the subject line, with your name and contact email.

With a 66-hour deadline, email support **the moment** something blocks you, then keep
working the local arm while you wait. Do not sit idle on a support ticket.
