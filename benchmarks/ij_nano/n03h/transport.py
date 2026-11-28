"""Physical chat-protocol transport for the 48H campaign.

Reuses the qualified N02R ``ServerSession`` (same pinned llama.cpp
b12359 Vulkan engine, same launch flags, netstat socket-PID ownership,
GPU offload evidence). The canonical chat renderer below is FROZEN for
the whole campaign: prompt bytes are a pure function of the frozen
public payloads, so the renderer digest is part of the experiment
identity. The ACTUAL provider request is captured per trial (the
65,535-vs-768 effective-limit mismatch stays a permanent regression
control: configured values are never trusted alone).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
import urllib.request

from benchmarks.ij_nano.n02r.controller_v2 import ServerSession, post_json

ROOT = pathlib.Path(__file__).resolve().parents[3]

# frozen sampling identity (matches the qualified N02R decoding identity)
SAMPLING = {"temperature": 0, "seed": 42, "max_tokens": 1024}
CONTEXT_FLAGS = ["-c", "8192", "-ngl", "99", "--jinja",
                 "--cache-reuse", "256", "--metrics"]
REQUEST_TIMEOUT_S = 600


def render_chat_user_content(case: dict) -> str:
    """Canonical, deterministic chat rendering of a public payload.

    Payload keys keep their frozen insertion order; ``instruction``
    always renders last as the task line. Catalogs render as
    ``- id: description`` lines. This function is campaign-frozen; its
    source digest is recorded in every run manifest."""
    pp = case.get("public_payload") or {}
    lines: list[str] = []
    for key, value in pp.items():
        if key == "instruction":
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"- {k}: {v}")
        elif isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"- {item}")
        else:
            lines.append(f"{key}: {value}")
    instruction = pp.get("instruction")
    if instruction:
        lines.append("")
        lines.append(f"Task: {instruction}")
    return "\n".join(lines)


def renderer_digest() -> str:
    src = pathlib.Path(__file__).read_bytes()
    return hashlib.sha256(src).hexdigest()


class ChatTransport:
    """One llama-server per model (fixed configuration, isolated
    process). ``submit`` renders the canonical prompt, POSTs the actual
    request, and returns (content, telemetry)."""

    def __init__(self, model_alias: str, weights_path: pathlib.Path,
                 port: int, workdir: pathlib.Path,
                 lora_file: pathlib.Path | None = None):
        self.alias = model_alias
        self.lora_file = lora_file
        flags = list(CONTEXT_FLAGS)
        if lora_file is not None:
            # fixed-adapter isolated server process (order section 4.2)
            flags += ["--lora", str(lora_file)]
        self.session = ServerSession(
            backend="vulkan", model=str(weights_path), alias=model_alias,
            port=port, workdir=workdir, profile_flags=flags)
        self.base = f"http://127.0.0.1:{port}"
        self.started = False

    def start(self, deadline_s: float = 600.0) -> dict:
        self.session.start()
        health = self.session.wait_ready(time.time() + deadline_s)
        self.started = True
        return {"health": health,
                "offload": self.session.offload_line(),
                "lora_active": bool(self.lora_file),
                "template_fingerprint":
                    self.session.template_fingerprint(self.base)}

    def stop(self) -> None:
        self.session.stop()
        self.started = False

    def submit(self, case: dict) -> tuple[str, dict]:
        content = render_chat_user_content(case)
        request = {
            "messages": [{"role": "user", "content": content}],
            "temperature": SAMPLING["temperature"],
            "seed": SAMPLING["seed"],
            "max_tokens": SAMPLING["max_tokens"],
            "cache_prompt": True,
        }
        t0 = time.perf_counter()
        j = post_json(self.base, "/v1/chat/completions", request,
                      timeout=REQUEST_TIMEOUT_S)
        latency_s = time.perf_counter() - t0
        choice = (j.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = j.get("usage") or {}
        telemetry = {
            "actual_provider_request": {
                "temperature": request["temperature"],
                "seed": request["seed"],
                "max_tokens": request["max_tokens"],
                "cache_prompt": request["cache_prompt"],
                "n_ctx": 8192,
            },
            "prompt_sha256": hashlib.sha256(
                content.encode("utf-8")).hexdigest(),
            "prompt_chars": len(content),
            "completion_tokens": usage.get("completion_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "finish_reason": choice.get("finish_reason"),
            "latency_s": round(latency_s, 3),
            "ttft_s": None,   # not captured on non-streaming endpoint
        }
        return message.get("content") or "", telemetry
