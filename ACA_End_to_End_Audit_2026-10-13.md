# Adversarial Contingency Auctions (ACA): End-to-End Repository Audit

**Audit date:** 13 October 2026  
**Repository snapshot:** `daff2be` on branch `fix/audit-repairs`  
**Scope:** implementation, planning/execution consistency, experiments and sweep orchestration, statistical result generation, provenance/claim ledgers, preregistration, test evidence, manuscript/PDF, and demo UI.

## Executive verdict

The update is a meaningful improvement over a repository that only had claims and historical outputs. There are real repairs: recursive recourse-tree construction and valuation, population locking, clearer negative-result reporting, process-safer logging primitives, a versioned result model, an explicit v6 preregistration, and a better-scoped statement of the theorem's assumptions. The targeted regression suite run for this audit passed 31 tests.

**However, the repository is not yet ready for an unconditional confirmatory claim or a submission that presents the new recursive planner as empirically validated.** The most important remaining problems are not cosmetic: (1) sweep resumability can mix or skip configurations and cannot run the registered v6 seeds as listed; (2) the new recourse tree is valued recursively but flattened before execution, so the executed policy can diverge from the policy whose cost is estimated; (3) v5 and primary data predate the recursive-tree repair; (4) the advertised ACA+ pruning threshold does not prune the planner's candidate risks, and pruning semantics themselves can erase modeled risk; (5) planning-time type-specific hazard estimates are called with default state, collapsing important hypotheses; (6) the claim ledger mostly records expected verdicts rather than re-computing empirical claims; and (7) paper-number generation and statistical inference are not consistently tied to the registered cluster-level analysis.

The manuscript is visually legible, but its headline is currently stronger than the held-out evidence supports. On the exploratory nominal grid, ACA is ahead of CBBA+LR on completion by about 2.14 percentage points. In held-out v5, CBBA+LR is ahead of ACA on completion and welfare and has fewer conflicts. The README acknowledges this; the abstract/main discussion must make it equally explicit. The v6 protocol itself states that the full 50-seed confirmatory execution remains outstanding.

### Current decision by area

| Area | Verdict | Why |
|---|---|---|
| Targeted regression tests | **Pass, limited scope** | 31 repair-focused tests passed. This is not a full-suite pass. |
| Population locking | **Improved** | Locked subsets and matching unit tests reduce population mixing. |
| Recursive recourse construction/value | **Improved, not end-to-end validated** | The tree builder and recursive value have tests; executor still consumes a flattened edge map. |
| Experiment runner | **Blocker** | Cache identity, global log reuse, output filtering, config grid iteration, and seed selection are unsafe for a confirmatory run. |
| v6 protocol readiness | **Not ready to execute as preregistered** | No machine-readable v6 config/seed list or exact-seed runner path; registered seeds do not reproduce from the test generator; numeric pruning threshold is unspecified. |
| Existing data as evidence for fixed algorithm | **Insufficient** | Raw/core data and held-out v5 logs predate the recursive-tree repair. |
| Statistical pipeline | **Needs correction** | Main tables use cell-level calculations in places where cluster-level statistics are declared; macros use inconsistent p-value fields. |
| Claim ledger | **Not genuinely executable yet** | Empirical claim evaluation returns a predeclared expected verdict rather than deriving whether the numeric claim is true. |
| Provenance artifacts | **Partly good, test isolation flaw** | Untouched ZIP ledger matches its manifest; a test rewrites the tracked artifact with different line endings and can make a later manifest test fail. |
| Manuscript/PDF | **Major content revision needed** | Exploratory-versus-held-out contradiction is not prominent enough; v6 is pending; conditionally scoped theorem needs disciplined presentation. |
| Double-blind anonymity | **Fails if anonymous review is required** | `paper.tex` sets `\anonymousfalse` and PDF exposes author/affiliation/email. |
| Demo UI | **Needs source-of-truth repair** | It displays v6 protocol status beside v5 results, and some result numbers are hardcoded in the UI source. |

---

## 1. What is genuinely fixed or improved

### 1.1 Population locking

`experiments/population.py` now establishes named populations rather than encouraging every table to filter raw runs independently. The main nominal core is reported as 10,500 method-cell rows across 750 independent instances and 250 `graph_family × seed` clusters; the held-out v5 population is 3,600 rows across 450 instances and eight methods. The targeted population tests passed.

This is the correct direction because a matched-method comparison must use the same eligible instances for each compared method. **Still required:** route every published table, macro, and significance calculation through the same locked population and persist the selected row/instance IDs and their hash alongside each table.

### 1.2 Recursive recourse tree

`acalib/agents/contingency.py` now includes `RecourseTreeNode`, `_build_tree_recursive`, and recursive `compute_tree_expected_cost`. The focused test for depth/branching passed, and the toy tests distinguish depth-one from depth-two values. That addresses the earlier problem where increasing tree depth did not cause the expected recursive planning/value calculation.

This verifies tree construction and its simplified valuation, not that runtime execution follows the same branch policy. That distinction is the most consequential remaining algorithmic gap; see P0-2 below.

### 1.3 Blocked-path handling and oracle-belief guard

The path-finding repair uses a graph view that removes blocked edges and returns no route when no route remains. The belief model's oracle setup explicitly rejects an unsupported fourth hypothesis rather than silently converting it to a uniform distribution. Relevant targeted tests passed. These are good defensive behaviors and should remain regression-protected.

### 1.4 Lipschitz bound and missing marginal handling

The Lipschitz-related code was changed toward a range-based bound over tree outcomes, and missing hazard entries in the bound path are explicitly reported. This is preferable to silently treating incomplete inputs as valid. However, the expected-cost evaluator still has its own `0.15` fallback for a missing edge marginal, so the interface is not consistently fail-closed yet.

### 1.5 Logging and result-model structure

`acalib/data/logger.py` adds an atomic JSONL writer with a lock, flush/fsync, and a record digest return value. A versioned `results/result_model_v1.json` ties several derived summaries to hashes of raw data inputs. In the audited snapshot, the result model's listed hashes match its intended CSV/SITL/map inputs.

The writer's record hash is currently discarded by the caller and is not persisted/checked by the integrity verifier, so the implementation does not yet deliver the end-to-end per-record SHA-256 chain implied by the protocol. Also make lock-acquisition failure fatal rather than silently continuing unprotected.

### 1.6 More honest evidence tiers and limitations

The README and some claim documentation now preserve negative results: exploratory ACA/ACA+ gains did not replicate in held-out v5; CBBA+LR had better held-out completion/welfare and fewer conflicts; type inference is not demonstrated as an empirical improvement. The theorem is described as conditional, and the perception work is scoped as an open-loop synthetic demo rather than physical-robot validation. Those are valuable and should not be weakened during revision.

### 1.7 Layout review

The bundled manuscript PDF renders as a readable two-column, nine-page technical paper. No obvious gross clipping, broken glyphs, or obviously overflowing tables were visible in the rendered pages inspected. The critical PDF issues are about claims and anonymity rather than basic layout.

---

## 2. P0: blockers before a new confirmatory run or strong algorithmic claims

### P0-1. The sweep runner does not safely isolate a configuration or resume key

**Relevant files:** `experiments/run_sweep.py` (notably `check_git_clean`, `compute_trial_hash`, config/seed handling, `completed_keys` construction, and output export).

The runner's comments promise resumability on `(config_hash, seed, method, adversary, regime)`, but the actual completed key omits important experimental factors, including node/robot/task counts, communication parameters, maximum steps, contingency depth, estimator/model settings, allocator hyperparameters, and config/code identity. `compute_trial_hash()` uses an MD5 over a condition dictionary and truncates the digest to 12 hex characters; that does not make the cache key a complete experiment specification.

Additional unsafe behavior:

- Runs write to global `results/runs.jsonl` and `results/traces` irrespective of `--output`. The requested output export reads all records in the shared JSONL rather than only the current requested config/seed subset. A new run can therefore mix old and new experiments or export stale records.
- If a requested condition appears already complete under the incomplete key, the runner can skip it even when meaningful configuration values differ.
- Cache parsing catches broad exceptions and continues, which can leave a partially loaded cache without a hard error.
- `get_git_commit_hash()` can yield `unknown`, and the dirty-tree check can treat an inability to inspect Git as clean. Confirmatory mode must fail closed when commit or cleanliness cannot be established.
- When a seed count is supplied, the runner uses `range(1, N+1)` rather than accepting the exact registered seed identities.
- YAML `fleet_sizes` and `task_counts` are read as lists, but only their first elements are used (`n_robots = fleet_sizes[0]`, likewise tasks), despite the grid config declaring several values.
- There is no machine-readable `protocol_v6.yaml`, and the runner does not support the exact seed-list interface the preregistration requires.
- Per-record digest returned from `AtomicJsonlWriter.append()` is ignored; the verifier primarily compares trial-hash sets rather than verifying the content hash of each record.
- The runner builds trial tuples without passing per-method `allocator_kwargs` in a way that ensures registered ACA+ parameters are actually used.

**Required fix:** make an immutable protocol config the single source for all factors, exact seed IDs, method-specific parameters, analysis population, and output paths. Derive a canonical SHA-256 config hash from normalized config plus code/protocol identity. Use a full trial key that includes that hash and seed/method/scenario identifiers. Write every run to a protocol-specific isolated directory. Resume only from the exact same protocol hash. Filter exports to exactly the requested run. Store a canonical per-record hash and verify it. Fail closed on dirty/unknown Git state, malformed log records, or hash mismatch. Iterate every declared grid factor or reject grid-valued config in single-cell mode.

**Acceptance tests:**

1. Changing only `comm_range`, `p_drop`, `n_robots`, depth, or allocator threshold changes the config/trial identity.
2. Running two configs into separate output locations leaves each output with only its own records; rerunning one config resumes only its matching trials.
3. A malformed JSONL line or mismatched record hash halts strict validation instead of silently creating a partial resume set.
4. A dirty tree, missing Git metadata, or `unknown` commit prevents a confirmatory run.
5. Given the v6 seed list, the runner executes those exact seeds (not 1–50), and the run metadata contains the seed list/hash and every resolved hyperparameter.
6. A multi-valued config either visits all combinations or is explicitly rejected rather than silently choosing index zero.

### P0-2. The tree whose expected cost is evaluated is not the tree the executor follows

**Relevant files:** `acalib/agents/contingency.py`, `acalib/agents/executor.py`.

The planner now builds a recursive tree and `compute_tree_expected_cost()` evaluates it recursively, but `_collect_flat_detours()` flattens branch-specific decisions to `flat_dict[edge] = child.path`. That map has no parent/branch context. If the same edge occurs in two different decision contexts with different contingency branches, one mapping overwrites the other. In addition, the recursive collection sees both edge keys and canonical aliases, which can trigger duplicate traversal.

`LocalRecourseExecutor.step_execution()` consumes `current_plan.detours` by current edge; it does not traverse the recursive `.tree`. The planner may therefore price a richer contingent policy than the robot can execute. The executor also moves to `EXHAUSTED_NEEDS_REPLAN` when the next edge in a chosen detour is blocked, even though a deeper branch may have been planned. In that case, the claimed advantage of the depth-two tree can be lost at execution time.

**Required fix:** represent executable contingencies with stable node/branch IDs and make the executor maintain a tree cursor or explicit observation-to-child transition. Do not use an edge-only map as the authoritative policy when contexts can differ. The valuation code and execution code should consume the same immutable policy object.

**Acceptance tests:**

- Construct a tree where the same edge appears in two branches with different continuations and show the executor takes the branch appropriate to the encountered state.
- Test a blockage two levels deep with no replanning/messages, if that is the intended benefit, and compare actual cost with the tree's predicted cost.
- For sampled policies, simulate branch outcomes and confirm empirical mean cost agrees with the tree's analytic cost within a predeclared Monte Carlo tolerance.
- Ensure both tree and executor reject malformed/missing branches deterministically.

### P0-3. Existing experiment results do not validate the newly repaired recursive algorithm

The key raw sweep records identify commit `72c1a431…` (8 October). The held-out v5 records identify commit `9fa21c08…` (11 October). The recursive-tree repair appears later in the current audit chain. Inspection of the held-out commit's `acalib/agents/contingency.py` confirms the current recursive helper/value path was not present there.

The result-model build summarizes these historic CSVs; it does not generate data under the repaired code. The v6 preregistration states that the full 50-seed execution remains outstanding (approximately 40 CPU-hours; only a five-development-seed dry run is mentioned). So current tables cannot be used as empirical proof that the new recursive planner improved outcomes.

This is not a criticism of fixing code after an experiment; it is a boundary on what the old experiment establishes. The old results can remain as historical v5 evidence with their original limitations, but must not be silently relabeled as evidence for the current algorithm.

**Required fix:** after resolving P0-1, P0-2, P0-4 and P0-5, execute the preregistered v6 protocol from a clean, immutable commit. Preserve complete raw JSONL, environment lock, resolved configs, seeds, per-record hashes, and commands. Build the analysis from those new files, not by overwriting the historical v5 outputs.

**Acceptance test:** every confirmatory result row resolves to one immutable run record with matching code commit, protocol/config hash, seed, method parameters, and source-record digest; the new recursive policy code is demonstrably the code executed.

### P0-4. ACA+ pruning is a no-op in the held-out run, and active pruning semantics can erase risk

**Relevant files:** `experiments/run_heldout_eval.py`, `acalib/agents/contingency.py`, `acalib/alloc/aca.py`, `docs/PAPER_CLAIMS.md`, `tools/verify_findings_checklist.py`.

The held-out evaluation sets `aca_plus` `prune_threshold=0.06`, while the planner's risky-edge threshold is 0.12. Candidate risk edges are already admitted only at or above the planner threshold; 0.06 therefore cannot prune any such edge. The v5 ACA+ variant is functionally not pruned, despite manuscript/claim language that attributes its behavior to pruning negligible-risk branches.

There is a second, latent issue if the threshold is corrected: `prune_recourse_tree()` removes risky edges beneath the pruning threshold, and `compute_tree_expected_cost()` can then return the current node cost when no active risks remain. That can treat an incompletely protected/possibly blocked path as deterministic and drop its failure/exhaustion probability or cost. `_collect_leaf_costs()` has a related danger if the dropped risk branch is treated as nonexistent. Also, `_compute_lipschitz_L_j()` calculates a local pruned `active_plan`, while the bid/bundle scoring and cache retain/use the unpruned `recourse_plan.expected_cost`. Bound and scored/executed policy can diverge.

**Required fix:** define the semantics of threshold-pruned branches before tuning a threshold. Pruning must specify what happens when that edge is actually blocked (e.g., explicit recovery/replan/failure leaf and its cost), rather than pretending the event has zero probability. Use the same pruned policy object in the bound, bid, cache, and executor. Fix the v6 preregistration to specify a numerical threshold and method-specific values. Update or remove statements that claim v5 demonstrated pruning.

**Acceptance tests:**

- A test input contains at least one candidate edge that is actually removed at the registered threshold.
- The cost/leaf set continues to account for the removed edge's failure probability and prescribed recovery behavior.
- The exact same plan hash is used for bound, score, cache, and execution.
- The v5 paper and documentation are explicitly labeled as not having tested active pruning if its threshold was below the planner's threshold.

### P0-5. Type-specific hazard prediction is called without relevant state

**Relevant files:** `acalib/agents/belief.py`, `acalib/agents/robot.py`, `acalib/alloc/aca.py`.

The hazard model differentiates behavior based on fleet/edge interaction and targeted interdiction state. But planning-time calls use `get_edge_marginals()` with no fleet state. That default makes `edge_robot_count=0`, and the call into `get_hazard_under_type()` also uses default `is_targeted_by_interdiction=False`. In this mode, the reactive and budgeted-interdiction estimates collapse to a baseline around 0.05 rather than representing their distinct state-dependent hazards. The Lipschitz calculation calls the same default path. This weakens the very type-specific marginal estimates the belief-aware planner depends on.

Additionally, perception/sensing's reactive feature definition (“at either endpoint”) does not perfectly match the simulator's edge/traversal-state rule. Even if the posterior update is correct for its own feature, a model trained on different event semantics may be miscalibrated for the simulator.

**Required fix:** define a shared event/state representation for simulator hazards, estimator updates, planning marginals, and Lipschitz bounds. Pass the actual relevant fleet state and target indicators into planning; avoid default state as if it were a calibrated estimate. Document precisely what information is available at decision time, and estimate calibration on held-out scenarios.

**Acceptance tests:**

- With otherwise equal inputs, construct reactive, budgeted-interdiction, and static hypotheses and show their predicted hazard changes appropriately with robot positions/targeting.
- Verify the planner and simulator use compatible event definitions.
- Report held-out calibration (e.g., reliability bins/Brier score or calibration curve) before claiming belief-aware hazard accuracy.

### P0-6. “Exact recursive expected cost” is exact only for a simplified independence model

`compute_tree_expected_cost()` multiplies fixed edge-level probabilities such as `(1 - p_i)` and evaluates a branching model that effectively assumes the relevant edge hazard events are independent with fixed marginal probabilities. The simulator's adversary can have persistent blockage and state-dependent/reactive behavior. Under those conditions, multiplying static marginals is not automatically the exact expected cost of the full simulator.

There is also a residual fallback of `0.15` when an edge marginal is absent, even though other parts of the repair effort aim to fail on missing probabilities. A silent fallback can turn an incomplete model into a seemingly successful computed value.

**Required fix:** either (a) limit the exactness claim to the explicitly defined independent Bernoulli model and prove/evaluate only that model, or (b) derive the tree value from the correct state-transition distribution, including correlations/persistent adversary state. Remove the unregistered `0.15` fallback and reject missing probabilities.

**Acceptance tests:** compare analytic tree cost to enumerated state-transition outcomes on all small cases; test correlated/persistent blocking separately to make clear where the independence approximation stops being exact.

---

## 3. P1: major research, analysis, or submission issues

### P1-1. The paper's headline is not reconciled with the held-out negative result

The exploratory core shows an ACA vs CBBA+LR completion difference of approximately +2.14 percentage points for ACA. The held-out v5 benchmark shows the opposite pattern:

| Metric | ACA | CBBA+LR | Held-out direction |
|---|---:|---:|---|
| Completion | 92.40% | 94.67% | CBBA+LR higher |
| Net welfare | 937.44 | 958.92 | CBBA+LR higher |
| Total conflicts | 39.66 | 25.48 | CBBA+LR fewer |

The README discloses the reversal, but the manuscript abstract and main discussion still use language that the exploratory result “confirms” the positive claim. That is too strong without prominently disclosing that it did not replicate. The paper should distinguish: exploratory mechanism evidence; held-out v5 confirmatory evidence (including the reversal); and the future v6 test of the repaired algorithm.

**Required fix:** rewrite abstract, contribution bullets, results discussion, and conclusion so that the v5 outcome is not relegated to a secondary caveat. Present the trade-off and negative finding honestly. Identify what claim, if any, is actually supported by held-out evidence, with matched population and correct cluster-level uncertainty. Do not claim v6 confirmation before the run is complete.

### P1-2. Reported statistical inference is inconsistent with the declared cluster-aware analysis

`tools/build_result_model.py` computes cell-level and cluster-level p-values and interval variants. But `experiments/make_tables.py::generate_main_results_table()` calculates ordinary bootstrap intervals over pooled per-instance values and raw paired Wilcoxon tests on cell rows instead of using the declared cluster-aware statistic. `tools/generate_numbers_from_model.py` then draws some headline claims from cell-level fields even when the protocol says cluster-level inference is primary.

Examples found in the generated-model/macros path:

- Core ACA vs CBBA+LR: cell-adjusted p is about `4.46e-05`, while cluster-adjusted p is about `0.00402`. Both are below 0.05, but the manuscript's “p < .001” strength comes from the cell-level field, not the declared cluster-level inference.
- CBBA-PR+LR macro reads `cell_p_raw` while manuscript labels the value as Holm-adjusted. The result model's adjusted value differs (adjusted p is 1.0 for that contrast; raw p is about 0.321).
- Held-out no-margin contrast is generated from `cell_p_raw` (about 0.0082) even though surrounding text says the difference was not significant after family-wise correction. Its adjusted cell p is about 0.0412 and its cluster-adjusted p about 0.3033. The reported p-value and the statement are not drawn from the same estimator/correction path.
- Contrast records in `result_model_v1.json` do not contain the confidence intervals for contrasts, while interval endpoints are hardcoded in the number generator.

**Required fix:** decide which unit of analysis and estimator the protocol declares primary (currently cluster by `graph_family × seed`), compute all primary tables/macros using that same estimator, and report cell-level sensitivity as a clearly secondary result if desired. Store contrast intervals and adjusted p-values in the model. Do not manually label a raw p-value as adjusted. Recompute all claims after selecting the official method.

**Acceptance tests:**

- A test reproduces each published contrast and p-value directly from the locked population and verifies the corresponding macro.
- Every manuscript p-value has metadata specifying estimator, unit, test, multiple-comparison family, and correction.
- Cell-level and cluster-level results cannot be substituted for each other by a `.get()` fallback.

### P1-3. Number generator contradicts its own “zero hardcoded empirical fallbacks” claim

`tools/generate_numbers_from_model.py` says all empirical numbers map to `result_model_v1.json`, but its code still contains literal numbers and `.get(..., default)` fallbacks for counts, p-values, effect sizes, CI endpoints, theorem summaries, and other figures. `aeSeedsCount` is explicitly written as `15`, yet the core `results/raw_results.csv` contains 50 unique seed IDs (1–50) and the main population has 750 independent instances across five graph families and three adversary scenarios. The manuscript says the instance count is “15 seeds × 5 graph families,” so both the macro and its explanatory arithmetic need reconciliation.

The linter checking `paper.tex` prose does not prove that the macro generator is source-backed: the problematic numbers are introduced in the generated macro file path. Some fallback values are only used when a model field is missing, which makes the output particularly dangerous because the build can still succeed and appear complete.

**Required fix:** make a required schema for every macro; missing fields must fail the build. Derive seed counts, trial counts, CIs, effect sizes, and all empirical figures from the result model or protocol config. Store the model field/source path per macro. For counts that deliberately describe a different subset, define and name that subset explicitly rather than hardcoding a likely-looking number.

### P1-4. The registered v6 seed list does not match the seed-generation test

`protocols/prereg-v6.md` says the 50 confirmatory seeds were generated by `np.random.default_rng(20261013)`, and then lists a specific seed sequence. `tests/test_prereg_v6_seeds.py` independently uses `rng.choice(np.arange(50000, 60000), size=n_seeds*2, replace=False)`, takes the first 50, and sorts them. That generated list does not equal the listed preregistered list. The test checks that its own generated list lies in range and is disjoint from old seeds; it does not parse the list in the preregistration and compare against the asserted generation method.

The supplied list is in a disjoint range, which is useful, but its exact derivation is not reproducible from the method/test that claims to verify it. The protocol also gives only `τ > τ_planner`, not a numerical pruning threshold, and there is no machine-readable `protocol_v6.yaml` to pass exact seeds/hyperparameters to the runner. The `prereg-v6` Git tag is lightweight rather than a signed annotated tag; that does not invalidate the document, but a stable commit hash and timestamped record are better practice for preregistration provenance.

**Required fix:** decide whether the written seed list or the generated list is authoritative, freeze the actual exact 50-seed sequence in a machine-readable protocol file, record the derivation/hash, and make the test parse and compare the exact list. Record development seeds separately. Fix the exact ACA+ threshold, all method parameters, seed list, population, and statistical estimand before confirmatory execution. Any post-freeze changes must become a new protocol version, not silently overwrite v6.

### P1-5. Claim ledger currently behaves more like a claim registry than a statistical verifier

`experiments/claims.py::EmpiricalClaim.evaluate()` checks that the source file exists, reads it, evaluates a population filter, and then returns `verdict=self.expected_verdict`. It does not independently compute the named effect estimate, confidence interval, test, correction, or compare the computed figure to the quoted claim. A nonempty filtered data frame can therefore support an expected `PASS` even when the numeric statement is wrong.

`tools/build_claim_ledger_v2.py` hardcodes claim wording, estimators, intervals/tests/corrections, and expected verdicts. One concrete mismatch: `CLAIM-09-V2` describes a SITL completion/rank issue but points at `results/raw_results.csv` rather than the SITL result source and filters methods in the regular sweep. More broadly, `tools/build_all_results.py` Step 6 calls the legacy static `tools.claim_ledger.write_claim_ledger()` and does not regenerate/validate the V2 ledger as the authoritative artifact. Legacy filters include `comm_regime == 'nominal' & n_robots == 8 & n_tasks == 30`, which are known to be empty against the current raw table per the finding notes; the pipeline's status validation can nevertheless pass because it doesn't execute those filters and calculations.

**Required fix:** use a single source registry that contains each claim's source artifact, row population, estimand, estimator, interval/test, correction family, expected direction, tolerance, and evidence tier. Recompute each number from the locked raw data; fail on empty populations, mismatches, or changed results; and report FAIL/INCONCLUSIVE distinctly. Make V2 the generated source of truth and either retire legacy ledgers or make them generated read-only views. Add a test for every claim, not merely nonempty filters and SHA string length.

### P1-6. UI protocol label and results are not a coherent source of truth

`acalib/demo/ui/layout.py` displays “Protocol: prereg-v6” / “Audit Status: Verified Deterministic” alongside a hash associated with the held-out v5 CSV. `acalib/demo/ui/tabs.py` says the held-out figures are from `results/confirmatory/heldout_v5_summary.csv`, but values are hardcoded in a literal `heldout_data` list. The view can therefore drift from the CSV after a rebuild, while its badge presents the prereg-v6 protocol as if those numbers were v6 outputs.

**Required fix:** use distinct labels: “Protocol v6 registered — execution pending” and “Displayed results: protocol v5 — [data hash]”. Load rows from the validated result model/summary rather than literals, and have the UI show the data/model hash actually used. Remove “verified” from the badge unless it describes a specific machine-checked state that is visible and current.

### P1-7. Claim-level theorem evidence is absent from the core hash chain

`results/per_claim_evaluations.jsonl` has 5,700 parseable top-level records, all tied to the old `72c1a…` code commit. Across nested claims, it has 106,214 claims, 57,334 marked `claimed_safe`, and 12,087 in the `tv_le_eta`/assumption-adhered subset. The adhered subset has zero conflicts, whereas the broader claimed-safe set has 330 conflicts. Thus the evidence supports a **conditional** claim over the adhered subset, not a fleet-wide or every-claimed-safe guarantee; only about 21.1% of claimed-safe claims fall into the checked adherence subset.

But `results/per_claim_evaluations.jsonl` is missing from `results/build_provenance.json`'s artifact list, absent from `result_model_v1.json` input hashes and `repro/input_hashes.json`, and marked `MISSING` in `CLAIM_SOURCE_MATRIX.csv`. Several theorem-specific macros are hardcoded. The numbers happen to be consistent with the file, but the build will not detect drift in that source.

**Required fix:** hash and identify this JSONL as a first-class input; compute adherence rate, conflict count, and confidence bound from it; store those values in the result model with the source commit; and have the theorem claim ledger verify them. Make the limited adherence fraction and conditional scope prominent in paper text.

### P1-8. Historical v5 JSONL is incomplete and should stay explicitly classified as such

`python tools/verify_log_integrity.py --historical-v5` reports a 3,600-row CSV and 3,600 unique CSV hashes, but the JSONL has 3,541 lines, 3,491 valid records, 50 malformed records, and 109 CSV hashes absent from the JSONL. The tool intentionally classifies this as `DECLARED-INCOMPLETE / HISTORICAL IRRECOVERABLE` rather than fabricating missing rows; that is the correct decision.

Do not call this a fully trace-verified run. Summary-level CSV comparisons can still be reported with the caveat and provenance available, but the next confirmatory run needs complete logs and must be rejected by strict verification if any record is malformed or absent.

### P1-9. Double-blind review setting is disabled

`paper.tex:54` sets `\anonymousfalse`. The rendered PDF shows the author name, institutional affiliation, and email footnote. If the target venue requires double-anonymous review, this PDF is not submission-ready. Set the venue-appropriate anonymous mode and also check PDF metadata, acknowledgments, supplementary material, repository/URL self-identification, and any author-identifying artifact paths.

### P1-10. Supporting paper/docs have stale or contradictory status language

- `docs/PAPER_CLAIMS.md` retains language that v5 ACA+ confirmed “pruning low-probability branches,” despite the threshold mismatch described under P0-4.
- `RESULTS_VERDICT.md` still refers to an earlier preregistration version in its heading.
- `PROGRESS.md` says “In Progress - Section 2 Setup” even while later items and deliverables indicate substantially more work has been completed.
- The v6 UI badge is inconsistent with v5 displayed data.

These documents should be updated only after the actual code/data state is fixed, not simply marked complete because a helper/test has been added. The finding checklist should be reviewed by behavior and evidence, not by file/commit existence.

---

## 4. P2: additional quality and reproducibility concerns

### 4.1 Test side effect: ledger-generation test modifies a tracked artifact

**Correction to initial investigation:** the untouched ZIP's `audit/CLAIM_LEDGER_V2.csv` matches the hash and byte size recorded in `results/build_provenance.json`. `tests/test_build_manifest.py::test_build_manifest_hashes_match_artifacts` passes when the original file is restored. The observed mismatch appears after `tests/test_claim_ledger.py` calls `build_claim_ledger_v2("audit/CLAIM_LEDGER_V2.csv")`, rewriting the tracked CSV with LF line endings. The file changes from 4,812 to 4,802 bytes, so a later manifest test fails. This is test-order contamination/newline instability, not evidence that the initial archive's manifest was broken.

**Fix:** write generated outputs to `tmp_path` in the unit test. Make newline handling deterministic and test the exact serialized bytes if cross-platform byte identity is part of provenance. Tests should not mutate tracked source artifacts.

### 4.2 Full-suite result was not independently reproduced in this audit

The audit directly ran the targeted regression selection and got **31 passed in 3.78 seconds**. It then ran `tests/test_build_manifest.py` on the restored, untouched artifact and got **1 passed**. An attempted broader command, `pytest -q -m 'not (sitl or ortools or ui)'`, exceeded the available 120-second run window after 29 progress dots; it did not produce a final suite summary, so this audit does **not** claim that entire suite passed.

The repository's bundled `TEST_REPORT_BEFORE_AFTER.md` reports 116 passed/5 skipped in one summary, while its included detailed test output says 115 passed/5 skipped. Resolve this one-test discrepancy from a single saved test log. Optional integration extras require additional platform/dependency setup, as acknowledged in the repo.

### 4.3 Venv and environment portability

The archive includes a large platform-specific `venv_core` bundle. That is not a portable environment lock and should not be treated as an independent reproducibility record. Prefer pinned dependency files/lock, platform declaration, setup instructions, and CI on a clean environment. Exclude the whole virtualenv from the research source archive if not needed for the recipient.

### 4.4 Atomic writer lock failure should not silently continue

The writer can continue if `fcntl.flock` fails. If correctness depends on the lock, inability to acquire it should raise, or the code should select and document a tested cross-platform locking backend. Also persist the digest that `append()` returns and have strict verification recompute it; returning a digest that is discarded offers no record-integrity guarantee by itself.

### 4.5 `--dry-run` is not completely dry

The sweep's dry-run path appears to benchmark/execute one trial before returning without a result run. That may not contaminate output, but a flag named dry-run should ideally resolve/validate configuration and show a planned workload without running the simulator. Clarify or separate `--smoke-test` and `--dry-run` behavior.

### 4.6 Cache key for graph betweenness may be too weak

A cache key built from graph family and counts such as number of nodes/edges can collide for different graph topologies with equal counts. If the cache is restricted to fixed static topologies, encode the actual topology identifier/hash so that accidental reuse is impossible.

### 4.7 Absolute machine paths and missing commit ID in provenance

`results/build_provenance.json` contains a machine-specific absolute root path and does not itself record the exact Git commit; `results/run_metadata.json` points to the old `72c1…` run code. Use portable relative paths and include commit SHA, dirty/clean state, protocol/config hash, environment lock hash, command line, seed list, input hashes, and output hashes.

---

## 5. Statistical and theorem interpretation: what can be said now

### 5.1 Exploratory vs held-out conclusions

The exploratory positive result is a real historical measurement, but it should be labeled exploratory. It cannot be presented as replicated after the held-out reversal. The held-out v5 table reports CBBA+LR at 94.67% completion vs ACA at 92.40%, welfare 958.92 vs 937.44, and 25.48 vs 39.66 total conflicts. The fact that ACA remains a contribution-worthy design idea does not erase the comparison.

### 5.2 Conditional safety claim

The evaluated claim-level records show zero observed conflicts among the 12,087 claims meeting the recorded `TV <= eta` adherence condition, but 330 conflicts among the wider set of 57,334 claims marked safe. This is compatible with a *conditional* theorem whose assumptions are verified; it is not evidence of universal safety when the condition is unmet. Any confidence bound must be recomputed using a clearly defined independent unit and an appropriately conservative method, with the claim-level file included in the provenance chain.

### 5.3 Exactness claim for tree valuation

The code's expected-cost calculation may be exact for the simplified tree model with its specified fixed, independent hazard marginals. It is not automatically exact for the persistent, stateful simulator. State the model and assumptions precisely. If dependence matters to the intended method, calculate value under the transition model or demonstrate calibration against simulator rollouts.

### 5.4 What is not established yet

The current snapshot does not establish that the repaired recursive algorithm beats a baseline; that active pruning improves performance; that type-specific belief estimates are calibrated during planning; or that v6 independently replicates the result. Those claims require a corrected runner, integrated execution, state-consistent hazards, frozen numeric parameters, and a completed strict v6 run.

---

## 6. Recommended repair sequence

Do these in this order; otherwise later experiments may need to be discarded and repeated.

### Gate 1 — Lock the executable protocol

1. Create `experiments/configs/protocol_v6.yaml` containing the exact seed list, all methods/parameters, numerical pruning threshold, topology/instance population, trial horizon, data-collection fields, and primary analysis plan.
2. Make the seed-list test parse that file and the preregistration, asserting exact equality and hash; resolve the documented RNG/list discrepancy.
3. Fix runner config identity, exact seed support, all grid factors, output isolation, strict cache parsing, and record-content hashes.
4. Fail closed on dirty or unknown Git state. Ensure resolved configuration and code commit appear on every record.

**Gate 1 passes only if:** a clean small test run can be launched twice; the second launch resumes only identical trials; a deliberately changed parameter does not resume; logs/config hashes verify exactly; and every requested seed is the seed actually executed.

### Gate 2 — Make valuation and execution use the same policy

1. Replace edge-only detour flattening as authoritative policy with a branch-context-preserving runtime tree/cursor.
2. Make pruning semantics explicit, preserve risk/recovery leaves, and ensure bid/bound/cache/executor share the same plan object.
3. Remove unapproved `0.15` fallbacks and reconcile tree-model independence assumptions with the simulator.
4. Add integration tests for repeated edges in separate branches, multi-depth blockage, active pruning, no-route outcomes, and predicted-vs-realized cost.

**Gate 2 passes only if:** an independently inspected trace shows the executor follows the branch that the valuation model priced, including blocked second-level branches.

### Gate 3 — Correct the belief/hazard interface

1. Define a common hazard event/state contract across simulator, observation model, planner, and bound.
2. Pass actual fleet state / targeted-interdiction state into prediction.
3. Measure probability calibration on held-out scenes and disclose limitations.

**Gate 3 passes only if:** distinct hazard hypotheses yield distinguishable, defensible marginals in scenarios designed to separate them, and the assumptions are reproducible from a test fixture.

### Gate 4 — Make the statistics and claim system genuinely executable

1. Choose the registered primary cluster-level estimand and multiple-comparison family.
2. Generate all table values, CIs, effects, p-values and paper macros from one model. Remove empirical literals and `.get(... default)` fallbacks.
3. Store contrast intervals; fix raw/adjusted p-value labels and replace cell-level numbers where cluster inference is primary.
4. Turn the claim ledger into a calculation/verification engine, not an expected-verdict register; remove known-empty legacy filters or cause strict build failure.
5. Add the per-claim JSONL to all provenance/input hashes and calculate theorem macros from it.
6. Fix the test side effect by using temporary outputs.

**Gate 4 passes only if:** a clean `build_all_results` fails on a deliberately incorrect estimate, an empty population, a source hash mismatch, or a missing required model field—and passes on the checked-in data with every paper macro traceable to a source field.

### Gate 5 — Run v6 and preserve immutable evidence

1. Commit/freeze protocol and source; create a clear, immutable commit/tag and record the full commit hash and environment lock.
2. Run the exact v6 seeds with all outputs in a new protocol-specific directory. Do not overwrite v5 history.
3. Strictly verify that every CSV summary row has one valid raw source record; reject malformed/absent hashes.
4. Rebuild the result model and all manuscript tables/macros from those outputs; generate a fresh claim ledger.
5. Include deviations, failed seeds, crashes, and all negative results in the report.

**Gate 5 passes only if:** all raw records, configs, source commit, model, ledger, and manuscript metrics verify without manual intervention and can be rebuilt in a clean environment.

### Gate 6 — Revise manuscript and UI

1. Rewrite abstract/main results/conclusion to explicitly state the held-out v5 reversal and that v6 remains pending until it is complete.
2. Remove the unsupported v5 pruning result claim; scope the tree's “exact” cost statement to the correct model.
3. Correct seed/trial-count prose and source-backed macros.
4. Fix UI status labels and dynamically source its results.
5. If double-blind review applies, enable anonymous mode and inspect PDF metadata/supplements.
6. Update `PAPER_CLAIMS.md`, `RESULTS_VERDICT.md`, `PROGRESS.md`, and `FINDINGS.csv` so status reflects validated behavior, not just a code change.

---

## 7. Minimal reproducibility commands used or recommended

The targeted regression selection used in this audit was:

```bash
pytest -q \
  tests/test_audit_fixes.py \
  tests/test_contingency_tree.py \
  tests/test_claim_ledger.py \
  tests/test_population.py \
  tests/test_result_model.py \
  tests/test_log_integrity.py \
  tests/test_prereg_v6_seeds.py \
  tests/test_public_surfaces.py
```

**Observed here:** `31 passed in 3.78s`.

After restoring the original ledger bytes from the archive, this also passed:

```bash
pytest -q tests/test_build_manifest.py
```

**Observed here:** `1 passed in 0.06s`.

The broader run attempted during this audit did not finish within the 120-second run window, so no completed result is asserted for it. Run the full supported test matrix in CI/clean environment and save the raw output before using a full-suite pass claim.

Recommended strict preflight before any confirmatory run:

```bash
# Pseudocode/target commands after the runner repair:
python tools/verify_protocol.py --config experiments/configs/protocol_v6.yaml --strict
python tools/verify_log_integrity.py --protocol v6 --strict
python tools/build_all_results.py --protocol v6 --strict
python tools/lint_paper.py --strict
pytest -q
```

The exact command names for new strict protocol options must be implemented; do not copy the pseudocode as if every flag already exists.

---

## Final recommendation

**Keep the audit-repair branch and preserve the current negative findings, but do not yet label the repaired recursive ACA/ACA+ system as empirically confirmed.** The fastest safe path is not to polish more prose or launch the 40 CPU-hour job immediately. First fix the runner's protocol isolation and exact seed support, then fix planner/executor policy equivalence and pruning semantics, and ensure state-consistent hazard estimates. Only then spend compute on the v6 run.

After that run, regenerate all statistics from one cluster-aware analysis path, make the ledger actually check them, rebuild the manuscript/UI, and publish the logs/provenance. The existing code repairs and audit artifacts are a stronger foundation—but the submission-level evidence needs to follow the repaired code, not precede it.
