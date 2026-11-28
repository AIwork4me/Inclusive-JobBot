# ADR-003 Purpose-built execution

Status: accepted for IJ-0.6 experiments. Qualification is pending.

MiniCPM5 proposes typed intent and fields. The versioned skill selects a deterministic dependency graph. A shared execution boundary validates wire format, schema, resource scope, workflow state and confirmation before a transaction. A business write is tied to a confirmed operation and persisted with audit evidence. The SDK can orchestrate model turns and call tools within that boundary. The inference backend can be replaced through a capability contract.

The general-agent control and all execution arms share the same authorization and transaction protections. Compare schema-only changes, deterministic sequencing, and job-specific knowledge in distinct paired arms. Include a larger model on the same workflow and a deterministic arm. Keep runtime inputs independent of the oracle. A structured delivery note is appropriate for the first slice and leaves OCR qualification separate.

Free model orchestration remains a control. A deterministic workflow is also an execution path when the input already identifies the operation and provides validated fields. The experimental question is where semantic extraction improves completion per inference call while maintaining business correctness.
