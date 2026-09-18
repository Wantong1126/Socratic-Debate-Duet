# T02–T09 实现与复现

仅处理单人合成控制输入、内部记录/回放及现有声音。未接入真人 EEG、未实现 T10+，未安装音频系统。所有 A/B 音库是一个 Synth 内部换音缓冲，不是两个参与者。

| 任务 | 交付、固定输入与配置 | 验证入口 |
|---|---|---|
| T02 | `src/sdd/session_types.py`：session_id、匿名 A/B、seq、同一单调时钟域的 sampled_at/received_at、live/replay/fixture、valid/reason；事件 source/target。九值线上包不变。非法值明确无效，JSON 中非有限值记 null 并留原因。 | `tests.test_sdd_session.SessionTests.test_t02_invalid_is_not_sanitized_into_valid_silence` |
| T03 | `session_recorder.py`：配置及 SC 配置文本快照、Git HEAD/工作区状态/源码 SHA256、源信息、seed、单调时间起点↔wall 时间、原始块/帧/事件。输出目录必须新建，逐行 flush；live 原始数据/帧必须显式 allow_live_recording。 | `test_t03_record_provenance_raw_events_and_consent`：seed=123，250Hz 模拟原始单通道、按钮事件、无效帧、禁止 live 保存 |
| T04 | `fixture_source.py`：控制 fixture 与模拟原始 EEG 分开；control 单字段阶梯、可配置断流；raw 为 10Hz 正弦＋seeded noise，单位 V，明确模拟。 | `test_t04_reproducible_single_field_and_dropouts`；`config/sdd_v1.toml`；固定 seed=20260904 |
| T05 | `replay_source.py`：显式 raw/control 模式，不用控制帧冒充原始 EEG；保留原记录输入/事件/seed；pause/resume 平移时基；落后时控制帧只交付最新帧，raw 样本不丢弃。 | `test_t05_replay_mode_pause_and_same_input_for_two_mappings`：同一输入分别 energy/beta 映射；虚拟暂停 49.9s，无补发洪峰 |
| T06 | `session_runtime.py`：匿名单人绑定、默认4Hz、单个最新帧槽；迟到后从当前时间设下个期限；重复 seq、重复采样时间、未来/过期/无效帧不续命。记录输入在映射前。 | `test_t06_latest_only_no_catchup_and_no_health_from_invalid`；补充 invalid flood、pending frame 失效测试 |
| T07 | 复用原持续 Group+Synth、六音容量、1.35s 内部交叉淡化，未改 core 音色；固定频率 98/146.832384/220Hz，权重 .48/.32/.20。 | `scripts/verify_sdd_v2_live.scd`；`tests.test_persistent_voice_bank`；五分钟结果见 verification.md |
| T08 | Python 主动停止发 `/eeg/organism/v2/stop`，无效/失联不再发送帧；日志写 quality/signal_loss/stop 原因；进程崩溃依赖 receiver watchdog。receiver 新增数值有限且[0,1]检查，非法消息不更新健康时间。保留 limiter、渐变、watchdog。 | `scripts/verify_sdd_runtime.py`：真实 Python 断流及故意 abrupt child exit；SC 节点与音频见 verification.md |
| T09 | `single_dimension_baseline` 仅开放已有 energy（可显式选已有 band），固定其余八值及 voicing；默认 energy=.2/.5/.8，各4s，原 -40…-18dB 范围与 .25s energyLag 不变。 | `scripts/prepare_sdd_baseline.py`、`sound/render_sdd_baseline.scd`、`scripts/verify_sdd_evidence.py`；听觉差异 **等待试听** |

## 从工程根复现

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
.venv/Scripts/python.exe -m src.sdd.demo --output reports/sdd_v1/my_fixture
.venv/Scripts/python.exe -m src.sdd.demo --output reports/sdd_v1/my_dropout --dropout 4 8
.venv/Scripts/python.exe -m src.sdd.demo --replay reports/sdd_v1/my_fixture --output reports/sdd_v1/my_replay
.venv/Scripts/python.exe -m scripts.prepare_sdd_baseline
& D:/OpenBCI/supercollider/sclang.exe -D sound/render_sdd_baseline.scd
.venv/Scripts/python.exe -m scripts.verify_sdd_runtime --run-name runtime_live_session_new
.venv/Scripts/python.exe -m scripts.analyze_sdd_runtime runtime_live_session_new
```

默认 dry-run，无 EEG、无 OSC。`--send` 才向已经显示 READY 的 v2 receiver 发送；此时 Ctrl+C 和正常结束都主动 stop。重启前重新 evaluate receiver。已有音乐 demo 保持原来的 Ctrl+C→watchdog 行为，不改变原公共接口。

保存的本次例子是 `fixture_run`、`dropout_run`、`replay_run`（各有 metadata.json 与 records.jsonl），不得把它们的墙钟时间解释为 EEG 采样时间。fixture 4Hz 是控制更新率，模拟 raw 250Hz 是独立测试采样率。`scripts.verify_sdd_evidence` 比较本次保存的输入和 WAV；不能据此认定有人听过。

SC 实测脚本仅在 57120/57130 未占用时运行，使用独立 scsynth server，最后仅关闭自身创建的 server。五分钟 soak 用：

```powershell
$env:SDD_VERIFY_FRAMES='1200'
& D:/OpenBCI/supercollider/sclang.exe -D scripts/verify_sdd_v2_live.scd
.venv/Scripts/python.exe -m scripts.verify_sdd_runtime
```

采样时间必须先换算到本会话单调时钟域；真实 LSL 校时属于 T18，当前未实现。线上九值包没有身份/时间/seq，receiver 只能检查报文值与到达间隔；新入口的 Python 封套负责输入新鲜度。绕过该入口直接重复发送合法九值包，receiver 无法识别源样本重复；未伪称改变了这个公共协议限制。

运行 `verify_sdd_runtime` 必须给一个从未存在过的 `--run-name`；脚本拒绝覆盖已有证据目录/日志。它创建隔离 57120/57130 SC server、以 `--send` 运行 12 秒 fixture（4–8 秒断流）、启动一个有意 `os._exit(17)` 的短 Python 子进程、再运行原 `synthetic_music_demo` 的 16 秒 combined 场景。`runtime_live_session_clean` 是本次通过记录：32 fixture 帧、signal_loss/stop 两个事件、三个 watchdog（fixture 断流、异常子进程、demo 结束）、三代稳定 Group+Synth、最终 root tree 无该 Synth，combined 为65 frames/2 voicings/0 skipped。日志无 `ERROR:` 或 `FAILURE IN SERVER`。本机 SC 每次定义时仍打印默认用户 synthdef `.meta` 路径不存在的三条环境通知；实际 `/d_recv`、Synth、录音和释放均成功，未改动用户目录来消除该提示。

## 试听记录（未填写结果）

听 `baseline_energy.wav`：0–4s 低、4–8s 中、8–12s 高，12s 停止开始；保持设备音量不变。记录三档是否可区分、是否仍像同一持续声部、有无突兀变化、停止是否舒适。听 `t01_render/g_lydian_transition.wav` 的 4s/9s 换音，记录是否平滑。当前均 **PENDING HUMAN LISTENING**；不因测试通过而标记人听验收通过。

范围止于 T09。下一个最小动作是完成这两段人工试听并保存观察；更长时长、其他设备测试仍需独立记录，不能由本次有限时长 soak 外推。
