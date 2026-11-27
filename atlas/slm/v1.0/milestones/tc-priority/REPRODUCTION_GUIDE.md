# Reproduce the priority milestone

From the repository root in a fresh clone, set `PYTHONPATH` to the root, `src`, and `benchmarks/tool_calling/runner` using the OS path separator.

```sh
python -m benchmarks.slm10.tc_priority_milestone
```

The replay verifies each portable seal and reconstructs the figures without loading model weights. Use `--write` to regenerate the deliverables. The evidence manifest lists each selected seal and its capture-source commit.
