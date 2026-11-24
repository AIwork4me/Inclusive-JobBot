# Third-party notices

Original code in this repository is licensed under Apache-2.0 (see `LICENSE`).
The components below keep their own licenses. This file is generated from
installed package metadata by `scripts/tools/third_party_notices.py`; where a
package's metadata does not state a license, the table says so instead of
guessing.

## Models and inference engine

| Component | License | Source |
|---|---|---|
| llama.cpp (ggml-org/llama.cpp, build b12359) | MIT | https://github.com/ggml-org/llama.cpp |
| MiniCPM5-2B model weights (OpenBMB, from ModelScope) | Apache-2.0 (statement in the upstream model card) | https://modelscope.cn/models/OpenBMB/MiniCPM5-2B |
| Ollama (optional baseline, not distributed) | MIT | https://github.com/ollama/ollama |
| ROCm runtime wheels, rocm[libraries] 10.0.0 (downloaded by install_rocm_runtime.ps1, not distributed) | not stated in the wheel metadata; AMD's terms apply | https://stable.repo.amd.com/rocm/whl-next/ |

## Python packages in the project environment

| Package | License | Homepage |
|---|---|---|
| absl-py 2.5.1 | Apache-2.0 | https://github.com/abseil/abseil-py |
| annotated-types 0.8.0 | MIT | https://github.com/annotated-types/annotated-types |
| anyio 4.16.0 | MIT | https://github.com/agronholm/anyio |
| attrs 26.1.0 | MIT | https://tidelift.com/subscription/pkg/pypi-attrs?utm_source=pypi-attrs&utm_medium=pypi |
| certifi 2026.11.20 | MPL-2.0 | https://github.com/certifi/python-certifi |
| cffi 2.1.1 | MIT-0 | https://github.com/python-cffi/cffi |
| charset-normalizer 3.5.3 | MIT |  |
| click 8.5.1 | BSD-3-Clause | https://github.com/pallets/click/ |
| colorama 0.4.6 | BSD License | https://github.com/tartley/colorama |
| cryptography 50.0.2 | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography |
| distro 1.9.0 | Apache License, Version 2.0 |  |
| filelock 4.3.1 | MIT | https://github.com/tox-dev/filelock |
| gguf 0.19.0 | MIT License | https://ggml.ai |
| google-antigravity 0.1.24 | Apache-2.0 | https://github.com/Google-Antigravity/antigravity-sdk-python |
| google-auth 2.63.1 | Apache 2.0 |  |
| google-genai 3.6.1 | Apache-2.0 | https://github.com/googleapis/python-genai |
| h11 0.16.0 | MIT |  |
| httpcore2 2.16.2 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| httpx2 2.16.2 | BSD-3-Clause | https://github.com/pydantic/httpx2 |
| idna 3.20 | BSD-3-Clause | https://github.com/kjd/idna |
| iniconfig 2.3.1 | MIT | https://github.com/pytest-dev/iniconfig |
| jsonschema 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema |
| jsonschema-specifications 2025.9.1 | MIT | https://github.com/python-jsonschema/jsonschema-specifications |
| mcp 2.3.0 | MIT | https://modelcontextprotocol.io |
| mcp-types 2.3.0 | MIT | https://modelcontextprotocol.io |
| modelscope 1.40.3 | Apache-2.0 | https://github.com/modelscope/modelscope |
| modelscope-hub 0.7.1 | Apache-2.0 |  |
| numpy 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | https://numpy.org |
| opentelemetry-api 1.45.2 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| packaging 26.4 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| pluggy 1.7.0 | MIT | https://github.com/pytest-dev/pluggy |
| protobuf 7.36.2 | 3-Clause BSD License |  |
| pyasn1 0.6.5 | BSD-2-Clause | https://github.com/pyasn1/pyasn1 |
| pyasn1_modules 0.4.2 | BSD | https://github.com/pyasn1/pyasn1-modules |
| pycparser 3.12 | BSD-3-Clause | https://github.com/eliben/pycparser |
| pydantic 2.14.4 | MIT | https://github.com/pydantic/pydantic |
| pydantic_core 2.50.5 | MIT | https://github.com/pydantic |
| Pygments 2.21.0 | BSD-2-Clause | https://pygments.org |
| PyJWT 2.15.1 | MIT | https://github.com/jpadilla/pyjwt |
| pytest 9.2.0 | MIT | https://docs.pytest.org/en/latest/ |
| python-multipart 0.0.34 | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pywin32 312 | PSF | https://github.com/mhammond/pywin32 |
| PyYAML 6.0.4 | MIT | http://lists.sourceforge.net/lists/listinfo/yaml-core |
| referencing 0.37.0 | MIT | https://github.com/python-jsonschema/referencing |
| requests 2.34.2 | Apache-2.0 | https://github.com/psf/requests |
| rpds-py 2026.9.1 | MIT | https://github.com/crate-py/rpds |
| sniffio 1.3.1 | MIT OR Apache-2.0 | https://github.com/python-trio/sniffio |
| sse-starlette 3.7.1 | BSD-3-Clause | https://github.com/sysid/sse-starlette |
| starlette 1.10.0 | BSD-3-Clause | https://github.com/Kludex/starlette |
| tenacity 9.1.4 | Apache 2.0 |  |
| tqdm 4.70.1 | MPL-2.0 AND MIT | https://tqdm.github.io |
| truststore 0.10.5 | MIT | https://github.com/sethmlarson/truststore |
| typing-inspection 0.4.5 | MIT | https://github.com/pydantic/typing-inspection |
| typing_extensions 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| urllib3 2.8.0 | MIT |  |
| uvicorn 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ |
| websockets 17.4 | BSD-3-Clause | https://github.com/python-websockets/websockets |

Model weights and engine binaries are downloaded by scripts at install time
and are not part of this repository.
