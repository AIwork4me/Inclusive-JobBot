# Release intake and dispatch gate

The active inputs are MULTITOOL-V2 candidate 0.3 and AGENTIC-PLAN-V2 candidate 0.4 review v3. The intake pins both packet manifests and verifies the bytes of their referenced inputs. The older Planning packets and the 0.2 world allocation remain available for historical replays.

## First-phase Planning expectations

Use the repository's locked Python environment. Generate the blank form from the packet's public case IDs, fill all 800 case rows, then validate the returned document.

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.slm10.blind_review_receipt --phase-one-template --review-scope READ_ONLY_MECHANICAL
python -m benchmarks.slm10.blind_review_receipt --validate-phase-one '<private-phase-one.json>'
```

Use [the phase-one schema](phase-one-expectations.schema.json) to describe conditional branches. Give each branch a condition, dependencies, allowed and forbidden actions, terminal facts expressed symbolically, and authority requirements. Enter the assigned reviewer ID. Record semantic duplicate candidates using case IDs. The template has blank rows so it fails validation until completed. The first-phase document uses the case roster only and has no scenario IDs.

The canonical digest is SHA256 of compact UTF-8 JSON with sorted object keys and no appended newline. Sort expectation rows by case ID. Sort each semantic duplicate finding's case IDs and then order the findings by their canonical JSON. Other arrays retain their order. The registrar records both the exact submitted file digest and the canonical digest. Once a registrar has authenticated this receipt, the registrar may disclose the scenario supplement. Keep the receipt and the disclosure timestamps in the private review record.

Verify the signed first-phase receipt before disclosure using only the first-phase documents and the independently pinned trust registry.

```powershell
python -m benchmarks.slm10.independent_release verify-phase-one --scope READ_ONLY_MECHANICAL --trust '<private-key-registry.json>' --trust-sha256 '<owner-provided-sha256>' --bundle '<private-bundle-directory>'
```

## Authenticated review, reconciliation, and issuance

Use separate, authorized individuals for registrar, reconciler, and issuer, and assign an independent reviewer. The release caller receives the Ed25519 public-key registry and its SHA256 from the authorized release owner over a trusted channel. The trust registry has `schema_version` set to `1.0` and a record for each of `registrar`, `reconciler`, and `issuer`. Each record contains `actor_id` and `ed25519_public_key`, the lowercase hex encoding of its 32 raw bytes. Keep private keys with their custodians.

Keep the bundle private. A signed record contains `actor_id`, `payload`, and `signature` in an outer object. The signature is the lowercase hex encoding of an Ed25519 signature over the canonical JSON array `["IJ-SLM-RELEASE/<filename>/1.0", actor_id, payload]`. Dates in signed records use UTC timestamps with whole seconds and a trailing `Z`. A referenced record's SHA256 covers its exact file bytes, including any newline.

Each payload binds `suite`, `review_scope`, `packet_manifest_sha256`, and `candidate_manifest_sha256`. The bundle includes these files.

| File | Content |
|---|---|
| `phase-one.json` | Planning first-phase expectation document supplied by the reviewer. |
| `phase-one-receipt.json` | Registrar-signed Planning receipt with `reviewer_id`, `received_at`, `document_sha256`, and `expectations_sha256`. |
| `verdict.json` | Reviewer submission using the verdict schema. Unreviewed case/scenario pairs keep their `NOT_RUN` disposition. |
| `final-receipt.json` | Registrar-signed record with `reviewer_id`, `identity_and_independence_verified` set to true, `verdict_sha256`, and `received_at`. For Planning include `phase_one_receipt_sha256` and `scenario_released_at`. Disclosure must follow first-phase receipt and precede or coincide with final receipt. |
| `reconciliation.json` | Reconciler-signed record for the target `case_id` and `scenario_id` (null for MULTITOOL), with both receipt digests (first-phase null for MULTITOOL), `reconciled_at`, `partition_status`, `partition_rationale`, `status`, `rationale`, `independent_expectation_sha256`, `oracle_witness_sha256`, and `discrepancies`. |
| `issuance.json` | Issuer-signed record binding the case, scenario and both receipt digests (first-phase null for MULTITOOL), `trial_id`, `roster_sha256`, `reconciliation_sha256`, `issued_at`, `status`, exact `runtime` identities, `evaluation_contract_sha256`, `handoff_sha256`, `qualified_requirements`, and `bindings_evidence`. |

The reconciler joins the exact case and scenario with the prior expectation, candidate world or records, oracle and witness after independent intake. The expectation digest covers the canonical `independent_expectation` object. The oracle and witness digest covers the MULTITOOL oracle row or the canonical Planning object `{"world": selected_world, "witness": witness}`. Record each discrepancy with `component`, `independent_expectation`, `candidate_expectation`, `counterevidence`, and `impact`. Keep the original signed records and reissue affected content under a fresh candidate digest. A discrepancy, pending partition review, or pending independent finding blocks issuance for that case.

The signer independently verifies the supplied evidence. Each entry in `bindings_evidence` has `path` relative to the private bundle and `sha256`. Use distinct evidence for `matched_runner`, `runtime_admission`, `hardware_handoff`, and `evaluation`. Runtime includes the candidate, backend, Direct or SDK profile, Git SHA, runner SHA256, binary SHA256 and engine build, model SHA256 and revision, host and physical GPU hashes, runtime session ID and run ID. The SDK profile also requires SDK version and binary SHA256. Verification checks the runtime hardware identity against the published handoff artifact.

| Scope | Scope-specific qualification |
|---|---|
| `READ_ONLY_MECHANICAL` | Public contract, provider-tool linkage, actual call path, business facts, and read-only scope. MULTITOOL must pass the pinned callback allowlist. Planning is limited to L0–L5. |
| `STATEFUL` | D23. Planning stateful world without affirmative commit. |
| `AFFIRMATIVE_WRITE` | D23 and affirmative D24. Planning world with an affirmative commit. |
| `STRICT_END_TO_END` | Individually qualified D12, D23, affirmative D24, and D25. |

The required maps are defined by `SCOPE_REQUIREMENTS` in `benchmarks.slm10.independent_release`. Every record binds one exact scope. MULTITOOL 0.3 has a read-only candidate roster and has no stateful or affirmative-write roster.

## Dispatcher status

```powershell
$env:PYTHONPATH = 'src'
python -m benchmarks.slm10.independent_release status
python -m benchmarks.slm10.independent_release verify --suite AGENTIC-PLAN-V2 --scope READ_ONLY_MECHANICAL --trust '<private-key-registry.json>' --trust-sha256 '<owner-provided-sha256>' --bundle '<private-bundle-directory>' --trial-id '<pinned-trial-id>' --runtime '<runtime-identity.json>'
```

The repository has no authenticated independent reviews, authorized trust registry, or issued release records for either active candidate. The preflight verifies supplied private records. A successful verification still reports `formal_dispatch=BLOCKED` and `physical_execution=NOT_RUN`. Activation requires a registered matched physical dispatcher for the exact candidate and scope, with live handoff and runtime admission at launch. The formal guard rejects dispatch at this point. Historical MULTITOOL and Planning binding helpers are scoped software checks. The Planning historical helper binds candidate 0.2.

## Statistical unit for physical reports

Bind each formal slot to its authored task family and selected world before dispatch. Keep all repeats, translations, profile comparisons and shared worlds together when deriving matched quality or compensation intervals. Use the connected groups of shared task families and reused worlds as resampling units. Report the group count, coverage of complete pairs and unavailable intervals when the frozen grouping cannot support an interval. Preserve task and trial counts in addition to the independent-group denominator.
