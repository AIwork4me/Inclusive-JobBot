# Security policy

## Scope

Inclusive JobBot runs a local language model and lets it propose actions on
business data. The security goal is that a wrong or manipulated model output
can never become a wrong business action.

- The model only proposes. Tool names, arguments, permissions, business rules
  and human confirmation are enforced by deterministic code.
- Business writes and approvals fail closed.
- The runtime is local: no cloud model, no API key, no external agent service.
  The inference server listens on loopback only.
- The agent runtime starts with file access, shell execution, sub-agents and
  MCP disabled and allows only the tools of the active job skill.

Not in scope for this repository: the host operating system, GPU drivers and
the upstream inference engine, which are qualified and pinned but not
developed here.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub private
vulnerability reporting on this repository ("Security" tab, "Report a
vulnerability"). Include the affected commit, a reproduction and the impact.
You can expect an initial response within five working days.

## Evidence

Security qualification results, including prompt-injection, tool-argument
injection and unauthorized-action tests, are published under `evidence/` and
summarized in the security report. A result that has not been run is reported
as `NOT_RUN`, never as passed.
