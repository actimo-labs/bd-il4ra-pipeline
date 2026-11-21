# TARGET_PREP.md — IL-4Rα ECD preparation and epitope strategy

Stage 1 of the pipeline. Everything downstream inherits the errors made here, and target
prep bugs are the hardest class to detect later. Assert, do not eyeball.

---

## 1. Construct definition

| Field | Value | Source |
|---|---|---|
| UniProt | **P24394-1** (IL4R_HUMAN) | Brief |
| Signal peptide | 1–25 | UniProt |
| ECD / extracellular topological domain | **26–232** (207 residues) | UniProt, matches brief exactly |
| Transmembrane | 233–256 | UniProt |
| Disulfides | **34–44**, **74–86** | UniProt |
| N-glycosylation sequons | **N53, N98, N128, N134, N176, N209** | UniProt |

**Domain architecture.** The ECD is a cytokine receptor homology module: two
fibronectin-III-like subdomains (D1, N-terminal; D2, C-terminal) with the IL-4 binding
site formed at the inter-domain region. Epitopes must sit on D1 or D2 surface.

### Fetch and assert — do not trust this document for sequence

Numbering conventions differ between UniProt and PDB. Derive, then assert:

```bash
# UniProt is NOT on the VM allowlist in all sessions; RCSB is (verified 200).
# Prefer deriving the ECD from structure, and cross-check length.
mkdir -p /mnt/comp5data/bd-il4r/target/raw
cd /mnt/comp5data/bd-il4r/target/raw
wget https://files.rcsb.org/download/1IAR.pdb
wget https://files.rcsb.org/download/3BPN.pdb
```

Mandatory assertions in `scripts/` before any design run:

- ECD sequence length == **207**
- All six sequon positions, in whatever numbering you adopt, are `N-X-[ST]` with `X != P`
- Both annotated disulfide pairs are present as Cys
- The numbering map `{uniprot_resnum -> pdb_resnum -> cropped_resnum}` is written to disk
  as a file, not held in a variable. Every hotspot list references **one** of these
  explicitly and says which.

**Trap (cost a prior campaign a round):** hotspots must name the target chain's residue
numbers **after** cropping and renumbering. Assert the identity of each hotspot residue
(expected one-letter code at that index) before launching.

---

## 2. Glycan masking — the single most important target-prep decision

Six N-glycosylation sequons sit inside a 207-residue domain. The assay antigen is
"Human IL-4 R alpha / CD124 Protein, **Fc Tag**, low endotoxin (MALS verified)" — a
mammalian-expressed Fc fusion, so **assume all six sequons are occupied by glycans in the
experiment**, even though a crystal structure may model none of them.

3BPN models NAG on chain B at two sites. 1IAR models the protein essentially bare. **The
absence of a glycan in a PDB file is a crystallography artefact, not biology.**

A designed antibody whose epitope overlaps an occupied glycan will produce a beautiful
computational model and **zero LSA signal.** This is the most likely silent failure mode
in this entire campaign.

### Rule

1. Build a per-residue glycan-exclusion mask: every residue whose Cβ lies within
   **12 Å** of the Cβ of any sequon Asn (N53, N98, N128, N134, N176, N209) is
   **excluded from epitope selection**.
2. 12 Å is a deliberate conservative default — a single GlcNAc is ~8 Å and real
   complex N-glycans sweep much further. Record the radius used in `config/sprint.yaml`.
   If masking removes so much surface that no viable epitope remains, **reduce to 10 Å and
   log the decision in RUNLOG.md** rather than silently relaxing it.
3. Write the mask to `target/glycan_mask.json` and have every epitope definition
   assert zero intersection with it.

### Also exclude

- **Membrane-proximal surface.** Residues near the C-terminal end of the ECD (~approaching
  232) are occluded in the Fc fusion and on the real receptor. Exclude the last ~10–15
  residues' surface neighbourhood.
- **The Fc-fusion junction.** The Fc tag is appended at the ECD C-terminus. Same region
  as above; this is a second, independent reason to avoid it.
- **Free cysteine.** The ECD has four Cys in two annotated disulfides (34–44, 74–86).
  1IAR's IL-4Rα chain carries a **C182A** mutation — that position is an unpaired Cys in
  the wild-type ECD, mutated out for crystallisation. Decide explicitly whether your
  working model has A or C at 182, record it, and avoid building an interface against a
  position whose identity differs between your model and the real antigen.

---

## 3. Structure sources

| PDB | Resolution | Method | Contents | Use |
|---|---|---|---|---|
| **1IAR** | **2.30 Å** | X-ray | Binary **IL-4 (chain A) / IL-4Rα (chain B, 207 aa)**. Chain B carries **M1F, C182A** | **Primary coordinate source.** Highest resolution, cleanest, chain B length matches the ECD exactly |
| **3BPN** | 3.02 Å | X-ray | **Ternary** IL-4 (A) / IL-4Rα (B, 205 aa) / IL-13Rα1 (C). NAG glycans modelled on chain B | Cross-check; type II complex context; the structure the brief itself cites |

Use **1IAR chain B** as the design target and **3BPN chain B** as an independent check
(superpose; if the chosen epitope's backbone differs materially between them, that patch
is conformationally uncertain — deprioritise it).

**Do not** use an IL-4Rα structure in complex with a known antibody as the *design*
target coordinate source, to keep a clean provenance story for the novelty claim. Such
structures are legitimate for epitope reconnaissance and for the novelty reference set.

---

## 4. HLT formatting for RFantibody

RFantibody's antibody-finetuned RFdiffusion requires **HLT-remarked PDBs**: heavy chain
as `H`, light chain as `L`, target as `T`, with CDR loops marked by REMARK lines.

Two inputs:

1. **Framework Fv** — VH+VL only, constant domains trimmed off, chains relabelled H and L.
2. **Target** — the cropped IL-4Rα epitope shell, chain relabelled T.

RFantibody ships a util for the conversion. **Use the shipped converter, do not hand-roll
chain relabelling.** After conversion, assert: exactly three chains present, chain IDs are
exactly `H`/`L`/`T`, and the CDR REMARK lines exist and point at the loops you intend to
diffuse.

### Target cropping

Reuse the hotspot-centred shell-crop pattern from `02_crop_target.py` in the prior
campaigns. Crop to the epitope neighbourhood rather than feeding the whole ECD — it
reduces compute and stops the model from drifting to an off-target patch. Keep the crop
large enough that the epitope's structural context is intact (a shell of ~12–15 Å beyond
the hotspot set is the prior-campaign default).

Write the crop's renumbering map to disk. See §1.

---

## 5. Framework selection

RFantibody designs **CDRs onto a fixed framework**, which is exactly the novelty model the
brief expects ("standardized framework and constant regions are expected"). The framework
is therefore a free, high-leverage diversity axis.

Run **two** frameworks:

| Framework | Rationale | Risk |
|---|---|---|
| **hu-4D5-8 Fv** (trastuzumab-derived, humanized) | RFantibody's own validated/example framework. Highest chance the generative model behaves as published. | Humanized murine origin — slightly weaker humanness story for Round 2 |
| **Human germline Fv** (e.g. IGHV3-23 / IGKV1-39 pairing) | Best humanness and developability profile for Round 2; very common, well-behaved, high-expressing | Not the framework RFantibody was demonstrated on — treat as the experimental arm |

Both are permitted: neither is an IL-4Rα binder, and the brief explicitly expects
standardised frameworks. **Record which framework each design used in the manifest.**
Framework diversity is cheap insurance; do not spend sprint hours building more than two.

If the germline arm produces visibly worse RF2 metrics in the pilot, drop it and put the
slots into hu-4D5-8. Decide this at gate G2, on data, and log it.

---

## 6. Epitope allocation — the agreed split

20 slots, split to hedge epitope-level failure. Target allocation:

| Arm | Slots | Epitope | Rationale |
|---|---|---|---|
| **E1 — IL-4/IL-13 competitive site** | **~12** | The IL-4 contact surface on IL-4Rα | Functionally meaningful (blocks type 2 signalling), the best-characterised patch on this target, and demonstrably antibody-druggable. Strongest Round 2 narrative. |
| **E2 — alternate patch A** | **~5** | Best-scoring non-E1, non-glycan-masked patch | Independent shot. If E1 designs badly or is glycan-shadowed, this saves the submission. |
| **E3 — alternate patch B** | **~3** | Second-best alternate | Cheap tail diversity |

These are targets, not quotas. Final counts follow QC and ranking — an arm that produces
nothing credible forfeits its slots to arms that did. Record the realised split.

### Defining E1 — compute it, do not hardcode it

```
E1 = { residues of 1IAR chain B with any heavy atom within 5.0 Å
       of any heavy atom of 1IAR chain A (IL-4) }
     MINUS glycan_mask
     MINUS membrane_proximal_mask
```

Then pick 3–5 hotspots from E1 for RFdiffusion: prefer residues with high side-chain SASA
in the *unbound* receptor, central to the patch rather than at its rim, and hydrophobic or
mixed-character rather than fully polar. Cross-check the patch exists in 3BPN chain B too.

**Literature anchor, labelled:** a published patent for a different (not ours, not to be
used as a scaffold) anti-IL-4R antibody reports an epitope at **L39, F41, L42, L43, D72,
Y74** on the IL-4Rα ECD. This is **third-party patent text, numbering convention
unverified by us** — treat it only as evidence that this region is antibody-accessible,
and verify independently against the structure before using it to steer anything.

### Defining E2/E3 — patch scoring

Score all surface patches on the ECD after masking, rank on:

- Solvent accessibility and patch area (needs enough surface to bury an Fv paratope —
  roughly ≥600 Å² of burialable area)
- Hydrophobic content — fully polar, charged patches are poor de novo design targets
- Local backbone rigidity / low B-factor; agreement between 1IAR and 3BPN
- Convexity/concavity — moderately concave patches suit CDR loops
- Distance from E1 — require E2/E3 centroids to be well separated from E1 so the arms are
  genuinely independent, not three views of the same surface

Record the scoring table. Pick E2/E3 at gate G1 and freeze them.

---

## 7. Deliverables of this stage

Written to `/mnt/comp5data/bd-il4r/target/`:

```
raw/1IAR.pdb, raw/3BPN.pdb       # untouched downloads
il4ra_ecd.pdb                    # cleaned chain B, documented numbering
numbering_map.json               # uniprot <-> pdb <-> cropped
glycan_mask.json                 # masked residues + radius used
epitopes/E1.json, E2.json, E3.json   # residue sets + hotspots + provenance
crops/E1_target_HLT.pdb, ...     # HLT-formatted, chain T
frameworks/hu4D5-8_Fv_HLT.pdb, germline_Fv_HLT.pdb
patch_scoring.tsv                # the full ranked table, including rejected patches
```

Plus a short `target/README.md` recording every judgement call made here — which
structure, which numbering, which mask radius, why E2/E3 were chosen over the
runners-up. Round 1 may require us to explain our methodology by e-mail.
