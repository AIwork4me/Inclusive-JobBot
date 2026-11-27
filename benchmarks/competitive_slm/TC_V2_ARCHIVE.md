# Archive competitive TC-V2 results

Use the statistics plan and canonical plan SHA-256 fixed before the run.
The plan's arm must pin the exact configuration digest and match the
controlled Vulkan settings. Set `thinking` to `frozen_case_requirement`
and `protocol` to `native-tool-calling`.

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$planOptions = @('--plan', $statisticsPlan, '--plan-sha256', $predeclaredPlanSha256)
python -m benchmarks.competitive_slm.tc_v2_archive export @planOptions --panel full --source $closedRun --output $newArchive
python -m benchmarks.competitive_slm.tc_v2_archive verify @planOptions --archive $newArchive --source $closedRun
python -m benchmarks.competitive_slm.tc_v2_archive combine @planOptions --archive $archiveB --archive $archiveD --output $statisticsInput
python -m benchmarks.competitive_slm.statistics analyze @planOptions --evidence $statisticsInput
```

Select the same panel the batch runner used. The exporter checks the original
run and arm configuration digests, canonical roster, exact first-attempt
journals, sealed session artifacts and SQLite digests. It confirms the
recorded physical-counter proof for passing sessions. Single-case development
diagnostics use a different run identity and are outside this archive scope.
Closed partial runs retain their full planned denominator and all four
statuses. A new snapshot of the same run requires a fresh archive folder.

| Member | Contents |
| --- | --- |
| `archive.json` | Public run identity, status totals, staged plan digest and member hashes |
| `trials.jsonl.gz` | One UTF-8 JSON line per planned trial, including paired streaming verdicts and evidence digests |
| `statistics.json.gz` | UTF-8 JSON input fragment with the exact first and repeat phases |

The export copies only allowlisted fields. It scans the UTF-8 payloads before
compression and again on readback. Keep the raw prompts, replies, generation
traces, logs, SQLite files and original run metadata in the local run folder.
The archive records their relevant proof digests. Use `verify --source` to
recheck the original evidence and reproduce the export. Archive-only
verification checks the compressed contents, status roster and statistics
mapping. It cannot reconstruct or independently replay the local evidence.

`combine` refuses mixed evidence classes and duplicate arm phases. Use its
JSON output with the statistics analyzer. Stream-only archives retain the
streaming case results in the metrics journal. The paired statistics
analyzer consumes the primary and repeat records.

Archive verification is a software result. The original evidence class and
measured run statuses remain in the export. The exporter starts no inference.
