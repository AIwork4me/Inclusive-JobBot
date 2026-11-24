# Third-party notices

Original code in this repository is licensed under Apache-2.0 (see `LICENSE`).
The components below keep their own licenses. This file is generated from
installed package metadata by `scripts/tools/third_party_notices.py`; where a
package's metadata does not state a license, the table says so instead of
guessing.

## Models and inference engine

| Component | License | Source |
|---|---|---|
| llama.cpp (ggml-org/llama.cpp, build b12359) | lic | https://github.com/ggml-org/llama.cpp |
| MiniCPM5-2B model weights (OpenBMB, from ModelScope) | lic | https://modelscope.cn/models/OpenBMB/MiniCPM5-2B |
| Ollama (optional baseline, not distributed) | lic | https://github.com/ollama/ollama |
| ROCm runtime wheels, rocm[libraries] 10.0.0 (downloaded by install_rocm_runtime.ps1, not distributed) | lic | https://stable.repo.amd.com/rocm/whl-next/ |

## Python packages in the project environment

| Package | License | Homepage |
|---|---|---|
| absl-py 2.5.1 | lic | https://github.com/abseil/abseil-py |
| annotated-types 0.8.0 | lic | https://github.com/annotated-types/annotated-types |
| anyio 4.16.0 | lic | https://github.com/agronholm/anyio |
| attrs 26.1.0 | lic | https://tidelift.com/subscription/pkg/pypi-attrs?utm_source=pypi-attrs&utm_medium=pypi |
| certifi 2026.11.20 | lic | https://github.com/certifi/python-certifi |
| cffi 2.1.1 | lic | https://github.com/python-cffi/cffi |
| charset-normalizer 3.5.3 | lic |  |
| click 8.5.1 | lic | https://github.com/pallets/click/ |
| colorama 0.4.6 | lic | https://github.com/tartley/colorama |
| cryptography 50.0.2 | lic | https://github.com/pyca/cryptography |
| distro 1.9.0 | lic |  |
| filelock 4.3.1 | lic | https://github.com/tox-dev/filelock |
| gguf 0.19.0 | lic | https://ggml.ai |
| google-antigravity 0.1.24 | lic | https://github.com/Google-Antigravity/antigravity-sdk-python |
| google-auth 2.63.1 | lic |  |
| google-genai 3.6.1 | lic | https://github.com/googleapis/python-genai |
| h11 0.16.0 | lic |  |
| httpcore2 2.16.2 | lic | https://github.com/pydantic/httpx2 |
| httpx2 2.16.2 | lic | https://github.com/pydantic/httpx2 |
| idna 3.20 | lic | https://github.com/kjd/idna |
| jsonschema 4.26.0 | lic | https://github.com/python-jsonschema/jsonschema |
| jsonschema-specifications 2025.9.1 | lic | https://github.com/python-jsonschema/jsonschema-specifications |
| mcp 2.3.0 | lic | https://modelcontextprotocol.io |
| mcp-types 2.3.0 | lic | https://modelcontextprotocol.io |
| modelscope 1.40.3 | lic | https://github.com/modelscope/modelscope |
| modelscope-hub 0.7.1 | lic |  |
| numpy 2.5.5 | lic | https://numpy.org |
| opentelemetry-api 1.45.2 | lic | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| packaging 26.4 | lic | https://github.com/pypa/packaging |
| protobuf 7.36.2 | lic |  |
| pyasn1 0.6.5 | lic | https://github.com/pyasn1/pyasn1 |
| pyasn1_modules 0.4.2 | lic | https://github.com/pyasn1/pyasn1-modules |
| pycparser 3.12 | lic | https://github.com/eliben/pycparser |
| pydantic 2.14.4 | lic | https://github.com/pydantic/pydantic |
| pydantic_core 2.50.5 | lic | https://github.com/pydantic |
| PyJWT 2.15.1 | lic | https://github.com/jpadilla/pyjwt |
| python-multipart 0.0.34 | lic | https://github.com/Kludex/python-multipart |
| pywin32 312 | lic | https://github.com/mhammond/pywin32 |
| PyYAML 6.0.4 | lic | http://lists.sourceforge.net/lists/listinfo/yaml-core |
| referencing 0.37.0 | lic | https://github.com/python-jsonschema/referencing |
| requests 2.34.2 | lic | https://github.com/psf/requests |
| rpds-py 2026.9.1 | lic | https://github.com/crate-py/rpds |
| sniffio 1.3.1 | lic | https://github.com/python-trio/sniffio |
| sse-starlette 3.7.1 | lic | https://github.com/sysid/sse-starlette |
| starlette 1.10.0 | lic | https://github.com/Kludex/starlette |
| tenacity 9.1.4 | lic |  |
| tqdm 4.70.1 | lic | https://tqdm.github.io |
| truststore 0.10.5 | lic | https://github.com/sethmlarson/truststore |
| typing-inspection 0.4.5 | lic | https://github.com/pydantic/typing-inspection |
| typing_extensions 4.16.0 | lic | https://github.com/python/typing_extensions |
| urllib3 2.8.0 | lic |  |
| uvicorn 0.54.0 | lic | https://uvicorn.dev/ |
| websockets 17.4 | lic | https://github.com/python-websockets/websockets |

Model weights and engine binaries are downloaded by scripts at install time
and are not part of this repository.
