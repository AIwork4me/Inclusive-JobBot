# LFM3-1.7B JobBot NanoAgent LoRA training plan

Design status is DRAFT. Training readiness and paid training are NOT_RUN.
The target is `LFM3-1.7B-JobBot-NanoAgent-LoRA`. An independently qualified
transfer result and training environment release are entry gates.

## Data and authority

Author synthetic Document Review, Customer Service and Product Data Management
families around typed read, draft, decision and verification tools. Each
world has a public instruction, versioned business rules and tool schemas,
a resettable initial state, explicit grants and a persisted audit log.
The expected state and executable witness are provided by a separately
authored oracle. The serving policy cannot reach the oracle.

Partition by workflow family, source template and world lineage before any
rollout. Keep a screening split, a training pool and a separate qualification
holdout. Quarantine paraphrases and variants sharing business rules or oracle
fixtures. Keep the frozen TC-V3, MULTITOOL-V2, AGENTIC-PLAN-V2 and JOB-V2
holdouts outside the training and difficulty-screening inputs. An independent
reviewer verifies split lineage, near duplicates and witness correctness
before dataset release.

For every environment, execute a known-correct witness twice from clean state.
Require the requested output, persisted state and authority trace to agree.
Reject missing approvals, stale approvals, wrong business identities and
unverified writes. Probe wrong answers, absent actions, tamper attempts,
duplicates, timeout, retry and illegitimate completion. Keep transport faults
and development grader defects distinct from model outcomes. Use an isolated
local sandbox with synthetic fixtures and deny external tool access.

## Difficulty and reward

On development data, run the frozen unadapted policy with eight distinct
seeds per task under the intended NanoAgent trajectory budget. Retain
always-correct and always-wrong tasks for evaluation. Prioritize feasible
mixed-outcome groups for GRPO. Record the selection denominator, failure
reason and group success counts by family and difficulty.

A trajectory earns efficiency credit only after passing business facts,
scope, authority, action coverage, final state and termination. For safe
correct rollouts, set the initial candidate reward to
`1 + lambda * max(0, 1 - calls / budget)`, with development candidates
lambda equal to 0 and 0.1, and the budget fixed by task stratum before
screening. All other outcomes receive zero efficiency credit. A failure to
honor the authority contract invalidates the trajectory, even if the final
answer is textually correct. Score required clarification and escalation as
correct only where the independent oracle requires them. Measure tool
proposals, actual executions, model requests and interaction turns
independently. Reward verifiers cannot grant permissions or authorize writes.

## Local pilot and checkpoint export

Pin a high-precision base revision, tokenizer, template, NanoAgent commit,
tool manifest, trainer stack, hardware and sandbox image. Start with a small
single-checkpoint PEFT experiment at rank 32 and alpha 64 on the base's verified
linear modules. Keep eight rollouts and seed/family assignments explicit.
Measure end-to-end rollout time, prefill/decode time, sandbox idle time,
trainer step time, peak host/device memory, dtype, optimizer state, stale
rollouts and useful groups. Begin with an inference and one-step gradient
smoke. Compare a clean reload against the same adapter before reporting
training feasibility.

TRL AsyncGRPO uses a serving worker, a trainer and versioned rollout
weights. Check the exact LFM3 model class, vLLM support, AMD kernels, trainable
module coverage, adapter swapping and checkpoint compatibility under the
same stack. The workstation has 128 GiB installed unified memory, shared with
the OS. AMD lists Ryzen gfx1151 support and documents platform-specific
framework limits. The full local vLLM/TRL pipeline remains unverified. If a
local combination fails, capture the exact error and a minimal control.
Evaluate an approved Linux Radeon W7900 or Radeon Cloud environment as a
separate engineering track if the project authorizes it. Record machine,
price, time and memory from the actual pilot before any larger training
decision.
[TRL AsyncGRPO](https://huggingface.co/docs/trl/en/async_grpo_trainer) ·
[AMD Ryzen Windows matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/windows/windows_compatibility.html)

Export PEFT config and hashes, rank/alpha, optimizer/inference dtype, training
and evaluation manifest digests, trainer state, base identity and conversion
provenance. Confirm dynamic GGUF values against the PEFT export and compare
high-precision merged equivalence before quantizing. Retain only the metadata
and checksums in Git.

## Candidate A/B registration

A uses the original LFM3 weights with the same deployed NanoAgent code,
tool policy, SOP state, precision, task worlds and seeds. B enables the new
JobBot adapter at its preregistered scale, with all pairing inputs identical.
Use blind outcome review and reset each world before a run. Run both in
counterbalanced order across family and difficulty. The primary endpoint is
first-pass qualified scoped completion. Secondary outcomes include exact
persisted business state, approved execution, termination, strict D25 and
quality-constrained cost. Safety is a separate fail-closed gate.

Use exact paired McNemar and paired effect intervals, family-clustered
bootstrap and a multiplicity correction for secondary comparisons.
Sample size, acceptance floor, allowed exclusions and the non-inferiority
margin must be frozen from independent development evidence before the
reviewer sees qualification results. Record the number of independent
business cases and the lower confidence bound for any greater-than-99%
claim. After passing the primary and safety gates, report full-cohort cost
and joint-success efficiency with failures and retries visible. Keep the
adapted-weight effect identifiable before testing SOP or runtime interactions.
