# Qwen3-14B 零工具澄清配对实验

同一条公开任务、同一个模型、给定目标、相同采样设置。五种合同分别使用 Native 与 Constrained，每格预注册一个请求。工具名从实际响应的 actions 读取，世界判定按归档请求和响应重放。

| 合同 | 解码模式 | 传输 | 提议工具 | Oracle | 校验结果 |
|---|---|---|---|---|---|
| original | native | PASS | ask | FAIL | invalid V2 schema |
| original | constrained | PASS | clarify_dates | FAIL | unavailable tool or invalid argument keys |
| clarification | native | PASS | clarify | FAIL | invalid V2 schema |
| clarification | constrained | PASS | 空数组 | FAIL | undefined terminal reference |
| tools | native | PASS | ask | FAIL | invalid V2 schema |
| tools | constrained | PASS | 空数组 | FAIL | undefined terminal reference |
| zero | native | PASS | ask | FAIL | invalid V2 schema |
| zero | constrained | PASS | 空数组 | FAIL | undefined terminal reference |
| combined | native | PASS | 空数组 | FAIL | undefined terminal reference |
| combined | constrained | PASS | 空数组 | FAIL | undefined terminal reference |

## 观测范围

- native 有 5/5 个完整可解析提议，其中 4/5 个使用未提供的工具。Oracle 通过 0/5，失败 5/5，未运行 0/5。
- constrained 有 5/5 个完整可解析提议，其中 1/5 个使用未提供的工具。Oracle 通过 0/5，失败 5/5，未运行 0/5。

每格只有一个观测，同一个任务重复用于十个合同设置。这组数据能够定位该输入的合同和引用错误，无法估计跨任务成功率或重复运行可靠性。

## 逐项证据

下列文件按 JSONL 解压后的行号定位，每行包含原始请求、响应、采样记录及判定。对应目录内的 manifest.json 保存文件哈希，identity.json 保存模型和引擎身份。

- original / native 第 1 行，任务 `69d36d0fcd4ac71db48d59bff9f9816030b274f7a8d4380cf2c771bb5041e9e7`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- original / constrained 第 2 行，任务 `810ae0eeddc9289557f499ca8775e3795c4d3e82aaa78fdfb41a13053ddf526b`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- clarification / native 第 3 行，任务 `a2760ed5d04be58579765b6c4eb900a4a65424bd3cab55201243695d578b945d`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- clarification / constrained 第 4 行，任务 `6bdcb6aa9fb60b4901a15499bc5093a10eff17ecd339438159b026179199da1f`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- tools / native 第 5 行，任务 `364003af8570e399d65973c52118e8aa4134f96d8e66e16a850e342c6d03a85d`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- tools / constrained 第 6 行，任务 `b8ab0e5598a683840b018601210017d5522bc9b7584d49dad299c382496c5c8a`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- zero / native 第 7 行，任务 `a2b3d6182d93381e19a45081afd6994aad6aeca54bfb0289eb3186563ac077b1`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- zero / constrained 第 8 行，任务 `295097b74cd0fd0730cc20497cf72b3a24e06de6d2f2829376df6ebccd941437`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- combined / native 第 9 行，任务 `9c5ff7518fe6a63357f41e51888a910d5ae005d36ed2d366a5459f0ac085acea`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
- combined / constrained 第 10 行，任务 `17907a86a5f74d6e12ea57eb2588e8d9180e7f9eb1ca1e2878267fca5be3a5f6`。[物理记录](../evaluation/aeve/results/sessions/ij073-1ae4ecc5df2b45d6a924b2fa01cbe672/captures.jsonl.gz)
