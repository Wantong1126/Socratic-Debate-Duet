# Python → receiver 最终联调记录

命令：

```powershell
.venv/Scripts/python.exe -m scripts.verify_sdd_runtime --run-name runtime_live_session_clean
.venv/Scripts/python.exe -m scripts.analyze_sdd_runtime runtime_live_session_clean
```

第一条命令退出 0。它使用脚本自行创建且自行关闭的 57120/57130 SuperCollider server，不触及已有 server。输入是 `config/sdd_v1.toml` 的 fixture，明确不是 EEG。

结果：32 个 fixture frame；断流区间 `[4, 8)` 秒保留 `signal_loss`，正常结束留 `stop`；随后的发送子进程故意以 `os._exit(17)` 异常结束，receiver watchdog 同样淡出；原 `src.sonification.synthetic_music_demo` combined 16 秒 run 发送 65 frame、3 次 decision、2 次 voicing、0 skipped。三个 receiver 生命周期都在树中为一个专属 Group 加一个 Synth，最终 root tree 不含它们。

`runtime_live_session_clean.json` 是机器检查结果，`runtime_live_session_clean.log` 是 SC 全量日志，`runtime.wav` 是实测录音。日志无 `ERROR:`/`FAILURE IN SERVER`。它有 3 条 SuperCollider 默认用户 synthdef `.meta` 路径不存在的环境通知；没有创建/修改用户目录以压制该提示，因为定义仍以 `/d_recv` 被实际接收且合成、watchdog、停止均成功。

听觉结论仍为 **PENDING HUMAN LISTENING**。这次自动检查只覆盖传输、节点、停止和有限/未削波录音。

文件 SHA-256：

- `runtime.wav`：`C64CEE54E4D09BBB56569A6BBB1D18E9C62437B47BEC1B180121F2D4DC455DE1`
- `runtime_live_session_clean.log`：`8792EE8EE765EA653F851E644B603175BC3F01E7B777FC2885DAD5ADA9510261`
- `runtime_live_session_clean.json`：`86AAB89E4ACCE42B90E7EC89122B544ABFA755B6631CF760C4FACB9327097553`
- `final_tests.log`：`802425C0CC50C65CAB8F1BF264734B4B3882F54E25A05A7FD1F7F3AA56E058DF`，101/101 通过。
