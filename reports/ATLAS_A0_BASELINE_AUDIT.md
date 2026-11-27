# Atlas A0 基线审计

审计日期 2026-11-25。以 [PR #4](https://github.com/AIwork4me/Inclusive-JobBot/pull/4) 的远端 HEAD `888f910b99b90dd7a3ac0f8d8760c6a6bbdc4102` 为起点。该 SHA 的 [Windows/Linux CI](https://github.com/AIwork4me/Inclusive-JobBot/actions/runs/45460424398) 和 [证据检查](https://github.com/AIwork4me/Inclusive-JobBot/actions/runs/45460424334) 均通过。新工作在独立堆叠分支进行，追踪见 [Issue #5](https://github.com/AIwork4me/Inclusive-JobBot/issues/5)。

## 逐条复算

结果由 [进度生成器](../scripts/tools/atlas_progress.py) 从终态、源码采集和冻结档案中计算。历史材料通过 IJ-0.7 的 895 项 SHA256 检查。请从 [Dashboard](ATLAS_PROGRESS_DASHBOARD.md) 查看各分母和对应证据。

| 归档 | 复算结果 |
|---|---|
| 历史四臂 | 500 个独立任务，2,000 条模型试次，4,422 个源码捕获请求。按臂匹配请求与唯一 completion ID。历史 V2 评分沿用当时的合成回执宿主。 |
| TC-V2 | Vulkan 349/500，ROCm/HIP 347/500。两后端各有 25/100 条连续多工具案例通过。流式、三种子试次与固定夹具各有独立分母。 |
| MULTITOOL-V1 | 129/600。三种子面板 300 次试次，Pass@3 和 Pass^3 均为 22/100 个任务。 |
| AGENTIC-PLAN-V1 | Plan-first 0/800，Acting-first 0/800。双轨重复 0/960，来自 160 个独立任务。 |
| JOB-V1 Arm F | 无模型原配置 592/600，其中 342 条实际完成合成业务。修订后同集诊断 600/600，其中 350 条实际完成合成业务。 |
| TC-V2 LFM3 早期检查点 | 已执行 200 次，其中 15 次通过。冻结竞争性 roster 为 1,150 次，余下 950 次在此检查点为 NOT_RUN。 |
| Antigravity | AG-06 各 1/3。AG-11 在 Vulkan 与 ROCm/HIP 均为 BLOCKED，原因是缺少完整进程树出站观测。 |

## 新发现的 IJ-0.7 本机归档

B（LFM3）、D（Qwen3.5）、F（Ministral）、G（Gemma）各完成旧 TC-V2 roster 1,150 次，依次为 207、365、36、419 次 PASS。已对四个封存归档重跑 `benchmarks.competitive_slm.tc_v2_archive verify`，并提供各自的原始运行目录作为 `--source`。四臂均通过源记录及归档绑定验证。归档保留配置、roster 和运行身份。这些结果属于 IJ-0.7 原配置。 [归档](../evidence/IJ071/legacy_competitive/)

## 本轮硬件与 GPU 队列

现场通过 Windows CIM 观测 Windows 11 专业版 build 26200、AMD Ryzen AI MAX+ PRO 395、AMD Radeon 8060S、驱动 32.0.22018.5。内存模块报告 128 GiB，Windows 可见约 95.8 GiB，当次可用约 76.5 GiB。运行中的 Arm A 使用 Vulkan0，历史设备身份记录为 gfx1151。 [环境观测](../evidence/IJ071/windows-observation.json)

07:12（UTC+8）的既有 Arm A 检查点完成 252/600，23 PASS、229 FAIL、348 NOT_RUN，包含 1,978 次模型请求。225 条属于已有完整 GPU 会话证明的批次，其余来自当时在运行的会话。对照冻结 roster、配置哈希和 SQLite 哈希验证了终态文件。原进程继续写入原目录，未启动竞用 GPU 的新任务。 [检查点摘要](../evidence/IJ071/legacy-job-a-checkpoint.json)
