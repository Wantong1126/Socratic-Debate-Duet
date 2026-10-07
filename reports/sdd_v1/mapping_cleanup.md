# 本轮清理清单：仅调查，不移动或删除

实际逐文件路径、大小和 Git 状态见 `mapping_audition/cleanup_inventory.json`。

| 类别 | 本地文件／Git 跟踪 | 本次结论 |
| --- | --- | --- |
| `overnight files/codex_tasks/overnight/` | 10／10 | 旧任务说明，已有 Git 恢复来源；后续确认归档后再移出活动目录，本轮保留 |
| `reports/overnight/` | 1／1 | `20260904_014335/progress.md` 仍被 `SDD_V1_Plan/ATOMIC_REQUIREMENTS.md:34` 和 `requirements.json:178` 引用；先处理引用再考虑归档 |
| `recordings/` | 29／29 | 虽目录有 ignore 规则，已有这些文件仍受 Git 跟踪；部分是测试依赖，不能整目录删除 |
| `traces/` | 4／4 | `tests/test_g_lydian_voicing.py` 读取四份 `traces/organism_v2_g_lydian/*.json`；保留 |
| `reports/sdd_v1/live_sessions/` | 2／2 | 指定真人会话 metadata.json / records.jsonl 已在 Git 跟踪中；本次只读，未另存或强制提交，不是可重建渲染 |
| `reports/sdd_v1/t01_render/` | 1／1 | 用户选中的 G Lydian 参考，保留 |

`tests/test_persistent_voice_bank.py` 实际读取的是 `recordings/eeg_organism_v2_voicing/g_lydian_transition.wav`，不能以 t01_render 副本替代路径。`test_sonification_v2.py`、`test_beta_softening.py` 和其他声音测试还读取各自 recording 目录的 WAV；这 29 个文件须按测试引用逐项区分，不能统一视作缓存。

本轮新 `mapping_audition/*.wav` 和 score 是从配置、代码及私人真人源重建的产物；应保留试听用本地副本，未来提交时只挑选所需证据。`.gitignore` 中 `reports/sdd_v1/live.wav` 是单独忽略项，既不作为本次 replay 输入，也没有删除。没有对 `src/`、`sound/`、`config/`、录音或隐藏文件做清理。
