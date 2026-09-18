# T01 v2 baseline — 2026-09-18

起点提交：`54afe69bb252064b90f697a610acd11052839ea7`，初始工作区干净。实际递归查找未发现 AGENTS.md；未回滚、清理或提交未知改动。

本次结论：v2 起点经最小修复可运行。恢复 protocol.py 被截断的 21 行导入/常量；保留已有声音、地址和范围。当前 voicing 已使用 MIDI 36–71，旧四份参考轨迹仍含超范围高音，按现有算法与 seed=20260904 重生成；未改变选音算法。

入口区别：旧 `scripts/start_eeg_organism.ps1` → `src.eeg_control_demo` → `src/organism_osc.py` → `sound/eeg_organism_engine.scd`，使用 `config/sonification.toml`、`/eeg/organism/frame` 18 值（六通道 E/C/M）。新入口：启动现有 SC server 后 evaluate `sound/eeg_organism_v2_receiver.scd`，加载 `config/eeg_organism_v2.scd` 与 `sound/eeg_harmonic_field_v2_core.scd`；Python 从工程根运行：

```powershell
.venv/Scripts/python.exe -m src.sonification.synthetic_music_demo --scenario calm-stable --duration 0.25 --rate 4 --seed 20260904 --dry-run
.venv/Scripts/python.exe -m src.sonification.synthetic_music_demo --scenario combined --duration 40 --rate 4 --seed 20260904
```

九值 `/eeg/organism/v2/frame` 顺序：energy, centroid, mobility, spectral_entropy, novelty, delta, theta, alpha, beta。独立 `/eeg/organism/v2/voicing`：f1…f6 后 w1…w6；空槽权重为零。Python、receiver 与 core 当前配置均为 40–500 Hz；G Lydian 候选实际 C#2–B4（69.296–493.883 Hz）在范围内；不把 clamp 当音域映射。停止为 `/eeg/organism/v2/stop`；旧停止脚本不能代替它。

本次验证：
- 修复前全套：46 项，6 个导入错误。修复后首次全套 90 项，仅旧轨迹对比失败。
- 轨迹更新后相关测试：`python -m unittest tests.test_synthetic_music tests.test_persistent_voice_bank tests.test_sonification_v2 tests.test_g_lydian_voicing -q`，33/33 通过，见 t01_tests.log。PowerShell 将 unittest stderr 包装为 NativeCommandError，但 unittest 自身结果为 OK。
- 最短 dry-run：0.25 秒、4 Hz、2 帧、1 次决策/voicing，无跳帧。新增固定种子、频率不被 clamp、落后不补发测试。
- `scripts/render_eeg_organism_v2_voicing_transition.ps1 -OutputDirectory reports/sdd_v1/t01_render`：SC 3.14.1 实际 NRT 渲染 19.0013 秒，48kHz/24-bit/stereo，peak 0.0576684，无削波/非有限值。此文件检验固定换音，不代表全部音乐场景试听。
- `D:/OpenBCI/supercollider/sclang.exe -D scripts/verify_sdd_v2_live.scd`：独立 57130 测试 server，实际加载上述 receiver，240 次帧更新，六次节点树均为 Group 1000 + Synth 1001，约一分钟无增长；断流触发 2 秒 watchdog；stop 后专属 Group/Synth 消失，server 仍在，最后仅关闭测试自行创建的 server。见 live.log、live.wav（48kHz stereo float，peak 0.03226179，最后一秒精确静音）。系统识别 Realtek 音频设备，SC 成功启动/录制；没有声学监听结论。

听觉范围：换音平滑、音色连续性、舒适度及实际扬声器/耳机听感均 **等待试听 / PENDING HUMAN LISTENING**。自动测量不替代听觉验收。一分钟节点证据不宣称数小时稳定。

历史单独说明：旧 Task 06 因外部 HEAD 变化及 worker 配额终止而未验收；旧 90 passed 属于 Task 05，未当成本次通过。现用户已授权继续，不再把当时停机说明当永久禁令。

T02–T09 已在 `reports/sdd_v1/tasks.md` 留下实现、固定输入、配置和复现命令；下一步不再是代码自动验收，而是完成其中列出的两段人工试听记录。

补充联调（T06–T08）：`scripts/verify_sdd_runtime.py --run-name runtime_live_session_clean` 用隔离 SC server 实际运行 Python `--send` fixture（4–8s 断流）、故意 `os._exit(17)` 的发送子进程，以及原 combined music demo。最终记录为 32 fixture 帧、signal_loss/stop 事件、三次 watchdog；combined 为65 frames、2 voicings、0 skipped，三代 receiver 节点最终释放。日志无 `ERROR:` 或 `FAILURE IN SERVER`。SC 对缺失默认用户 synthdef `.meta` 路径打印三条环境通知；没有改动用户目录，实际合成、录音和停止均已完成。
