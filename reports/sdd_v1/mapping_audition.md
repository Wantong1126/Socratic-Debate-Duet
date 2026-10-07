> Historical September report. Current sounds: docs/LISTENING_GUIDE.md. Cleanup was completed on 2026-10-07; see repository_cleanup_20261007.json. Old audition assets are preserved at reports/archive/listening/previous_menu/.

# M01–M06：单人音乐映射试听，2026-09-20

本轮交付可运行的原始真人记录回放、八个独立菜单项（六类音乐变化）、19 段短对照，以及现有参与者 A 声部上的邀请变换。人工可辨性、好听程度、疲劳、声音归属感和行为对应均未验收。没有开始双人系统，也没有删除历史文件、提交或推送。

## 启动和操作

在 `D:\sdd-sonification` 的 PowerShell 执行一条命令：

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition
```

默认 `replay`，读取 `reports/sdd_v1/live_sessions/obci_eeg1_20260919_194100` 的 **raw 样本重新计算**，播放原采样时钟的 60–84 秒片段，以 timbre 开始。启动器自动加载现有 SC harmonic receiver，输出保持原限幅和保守音量；不录音、不保存新的原始样本。现有 `.venv` 只有 Include，缺失 Scripts/python.exe；上述 Anaconda Python 的所需依赖已实际验证可用，未安装新软件。

| 操作 | 含义 |
| --- | --- |
| 1 / 2 / 3 | level / pitch / timbre；切换并从同一片段重播 |
| 4 / 5 | space_reverb / space_delay；同一个固定起音探针 |
| 6 / 7 / 8 | harmony / rhythm / note_weights |
| 空格 | 暂停／继续；暂停不给音频续 watchdog，不积压补发 |
| R | 重播；重新建立滤波、窗口、校准和平滑状态，并重算播放前的原始数据 |
| V | 在兼容候选上打开／关闭 invitation；活动邀请须先结束并等待释放 |
| I | 创建一个明确的 operator → A invitation event |
| E / D | 提前结束／拒绝；两者平滑释放，记录不同原因 |
| Q 或 Ctrl+C | 停止并释放 receiver 与自行启动的 server |
| + / - / T | manual 模式调控制值／恢复固定低→中→高→低轨迹 |

片段播完自动静音，等待 R、候选键或 Q。`--once` 播完自动退出。可选 `--candidate`、`--start`、`--duration`、`--session`；文件缺失或片段越界会报错，不换 fixture。

```powershell
python -m src.sdd.mapping_audition --mode manual --candidate pitch
python -m src.sdd.mapping_audition --candidate timbre --invitation
python -m src.sdd.mapping_audition --inspect
python -m src.sdd.mapping_audition --render-all
```

后续 live 的入口已接入同一 EnergyProcessor，但本轮未进行新的 live 对应验收：

```powershell
python -m src.sdd.mapping_audition --mode live --stream-name obci_eeg1 --confirm-live-hardware --candidate timbre
```

live 要求沿用已确认的 GUI LIVE / TimeSeriesRaw / uV / 八路顺序；启动后需 30 秒安定段、2 秒窗口及 20 秒有效个人基线。暂停后清空 inlet 积压并重新校准。失效、陈旧数据或断流不发送新声部健康帧。

## 实际来源和 M01 校验

`mapping_audition/raw_audit.json` 保存输入文件 SHA256 和实测结果：30,000 样本、8 路、120.041 秒、249.906 Hz；无非有限列、无整列 flatline、无超过 100 ms 的正向间隙。存在 1,563 次小时间回退，最小 -15.258 ms；最大正向步长 96.986 ms。Ch7/vertical_EOG 有 10.5867% 样本超过 98% rail 阈值，禁用其映射。其他通道通过这些数值检查，不等于排除了全部生理伪迹。

RawSampleReplay 复用 ReplaySource 读取 raw 行。原逐样本 LSL 时间、JSONL 写入时间分别保存；仅调度时间使用原相对 LSL 时间的因果 running maximum，保持样本顺序，不重采样、不重排、不补造样本。回退超过 100 ms 或停滞的记录拒绝播放。回放的样本年龄映射到本次 monotonic 时钟，不能用旧 LSL 绝对时间触发 watchdog，也不能每次把旧控制值假装成新样本。超过 100 ms 的间隙会清空滤波／窗口／校准状态。暂停移动播放时钟，重播重建全部处理状态。

F3 特征仍由现有 ControlSession → EEGControlFeatureEngine 计算。实际滤波为逐通道因果 HP 0.5 Hz(4阶) → LP 45 Hz(4阶) → 50 Hz notch(Q30)，再 HP 4 Hz(4阶) → LP 40 Hz(4阶)。raw 是 GUI 输出类型，不表示 Python 没有滤波。完整 delta 没有计算。

原始特征 `P = ∫[4,40] WelchPSD(F3) df`，单位 uV²；1 秒 Welch segment，50% overlap，2 秒分析窗。新试听使用 `clip((log10(P)-log10(P5))/(log10(P95)-log10(P5)),0,1)`，之后使用现有 0.5 秒 EMA。原 live_eeg 入口默认线性缩放不变。

本次明确选择先排除 0–30 秒安定段，随后以约 32.004–51.593 秒的 80 个有效窗口校准，约 51.822 秒开始产生有效控制。前 30 秒能量分布明显高于后段，不能诊断为某种心理状态或直接认定都是伪迹；排除它是本次回放试听的明确校准选择。P5/P95 为 35.0413/230.8824 uV²，冻结后不在线拉伸。有效段控制值中位数 0.373，5–95 百分位约 0.090–0.819；距离两端不足 0.02 的比例为 0.727%。最初沿用旧缩放时约 68% 控制值挤在下端，该方案未作为最终交付。原文件未改动。

## M02 参考与 M03/M04 映射表

参考由原 `sound/render_eeg_organism_v2_voicing_transition.scd` 重现，结果为 `mapping_audition/reference_reproduced.wav`，配置与测量见 `reference.json`。历史文件保留；不宣称波形逐位相同。

- A：G2 / D3 / A3 = 97.998859 / 146.832384 / 220 Hz；**音符权重** 0.48 / 0.32 / 0.20。
- B：C#3 / F#3 / C#4 / F#4 = 138.591315 / 184.997211 / 277.182631 / 369.994423 Hz；音符权重 0.34 / 0.28 / 0.22 / 0.16。
- 4.01 秒 A→B，9.01 秒 B→A；换音 crossfade 1.35 秒；16 秒 release。
- **泛音组权重** 1 / 0.72 / 0.30 / 0.10；组成员 [1,2,3] / [4,5,6] / [7,9,12] / [24,36,48]；沿用 softened beta profile。
- 新试听固定起点为 A、energy=0.68、同一泛音组基线；invitationDiagnosticDepth 默认 0，仅 `--diagnostic` 显式开启 0.85。

以下所有配对均为「手动试听可用，等待人听／真人静息回放可用／行为对应待验证」。本轮实时来源仅使用 F3 的上述能量；Ch7/Ch8 不参与，没有给它们伪造 EEG 标签。既往 F3 energy→level 的 live 联通证据仍成立，新菜单与对数缩放未获得新的 live 行为验收。

| 菜单 | 控制量低→高时实际改变 | 固定内容与限制 |
| --- | --- | --- |
| level | 声部附加增益 -12→0 dB | 固定音高、音色、节奏、效果；保留作响度对照 |
| pitch | 只改变上声线 A3→B3→C#4（220 / 246.942 / 277.183 Hz） | G2、D3 底座、权重、音色、效果固定；启用邀请时拒绝此配对 |
| timbre | 泛音权重 [0.90,0.24,0.07,0.015]→[0.42,0.65,0.55,0.23] | 音高、音符权重、节奏固定；core 使用组能量归一化 |
| space_reverb | dry/wet 0.06→0.38；tail 0.8→4 秒 | 固定和弦、音色；固定每小节一次同声部起音，方便判断尾音 |
| space_delay | 两次无反馈延迟，mix 0→0.32；第二次为第一回声的 0.55 | 延迟固定 1/3、2/3 秒；与 reverb 使用完全相同的固定起音探针；干声保留 |
| harmony | [G2,D3,A3]→[G2,E3,B3]→[G2,F#3,C#4] | 共同低音 G2、音区、音色、节奏、效果固定；邀请开启时拒绝 |
| rhythm | 90 BPM，4 拍小节，每小节 1／2／4 次起音 | 同一 oscillator field 的确定性门控；15 ms attack/100 ms release，保留 12% 底声；不用随机音量冒充节奏 |
| note_weights | 同和弦音符权重 [0.48,0.42,0.10]→[0.48,0.18,0.34] | 固定泛音权重；经原 voicing 通道每至少 1.5 秒 crossfade；与 timbre 分开，邀请开启时拒绝 |

范围、轨迹和配对见 `config/mapping_audition.json`。离散候选阈值为 1/3、2/3，回差 ±0.06；最短保持 1.5 秒，覆盖原 1.35 秒换音。rhythm 的密度变换推迟到下一小节边界，新增等待 0–2.667 秒，host 调度分辨率约 50 ms。原 4 Hz 配置取整为每 62 个样本一次描述量计算，输出仍由 SessionRuntime 最多 4 Hz 控制。额外映射 EMA 0.35 秒，SC 泛音 Lag 0.35 秒、效果 Lag 0.2 秒；分析窗与因果滤波另有响应延迟，不宣称零延迟。

空间候选的固定起音不受 EEG 控制，不是生理节奏映射；纯持续正弦的延迟副本无法展示可数回声，因此这两个候选使用相同探针。其他候选保持持续声部，rhythm 单独改变起音密度。

## M05 邀请及独立协议

继续使用 InvitationButton → InvitationEvent → InvitationEnvelopeController → `/sdd/invitation/v1/control` → 现有 A Synth 的 invitationAmount。无 event 时不执行邀请变化；拒绝、结束、暂停、断流的原因沿用原 controller。邀请 attack/hold/release/cooldown = 2/3/2/1 秒。当前专属试听为保留 G2/D3，只将上声线 A3 连续上移到 B3，再返回；core 对所有正在 crossfade 的 bank 使用相同包络。普通泛音／响度／空间／节奏仍按当前输入继续变化，结束后不会还原旧快照。是否听得出来源及是否像同一声部，等待人工判断。

现有九值 frame、12 值 voicing、6 值 invitation 合同不变。只有新启动器会安装独立的 `/sdd/music/v1/control`，由 `sound/music_audition_control.scd` 验证并更新既有 Synth；不创建节点，不更新 lastFrameAt/transportAlive。

```text
17 个 OSC 参数（依次）：
target=0(A), session_id:string, seq:int32, age_seconds,
auditionLevelDb,
musicGroup1, musicGroup2, musicGroup3, musicGroup4,
musicReverbMix, musicReverbTime, musicEchoMix,
musicRhythmPattern, musicTempo,
invitationHarmonyDepth, invitationDiagnosticDepth, musicPulse
```

拒绝错误宽度、错误 target、会话切换、重复／倒序 seq、age 不在 [0,0.5]、非有限或越界值。数值范围：level [-18,0] dB；四组 [0,1]；混响 mix [0,0.4]、time [0.5,5] 秒；echo [0,0.35]；pattern 只能 0/1/2/4；tempo [40,160] BPM（网格由 host 执行）；invitation depth [0,2] 半音、diagnostic [0,0.9]；pulse [0,1]。`age` 为发送时的控制年龄，不宣称测得 UDP 传输延时。程序停止音乐输出后扩展与邀请均不能续音频 watchdog。

## M06 音频、回归与剩余验收

短音频全部在 `reports/sdd_v1/mapping_audition/`：`manual_*.wav`、`replay_*.wav` 各 8 段，每段 24 秒加受控退出尾段；`compare_physiology_only.wav` / `compare_invitation_only.wav` / `compare_combined.wav` 使用同片段的 timbre 与第 7 秒显式邀请。每个同名 JSON 保存输入量、有效性、音乐参数、生效时间、事件和配置；`manifest.json` 保存输入 hash、WAV hash、peak/RMS、尾段和节点分配数。

首轮出现的 replay timbre 静音已修复：将新泛音控制改为独立 Lag，保留原群组控制的 VarLag；并在效果器入口防止非有限值传播。验收检查有效段 RMS，不能靠一次启动峰值判断正常出声。rhythm 做固定电平补偿，所有最终文件仍保留原 limiter/安全输出。最终 19 个文件均为 48 kHz 双声道、有限且有效段非静音，最高 peak 0.108082，最后 0.3 秒为静音；非 level 平均 RMS 的总跨度约 1.4 dB。近似 RMS 匹配不能替代人耳响度比较。

受影响的回归命令和逐项结果保存在 `mapping_audition/tests.log`（84 项通过）；覆盖 raw 时间/暂停/重播/缺文件/间隙、校准、单维度范围、回差与节拍、邀请参数所有权、旧协议和停止。没有扩展不相关行为验证。

`python -m scripts.verify_mapping_runtime`：静音的真实 SC runtime 验证通过，9 个错误 packet 拒绝；仅扩展与邀请持续输入时 2 秒 watchdog 正常触发；一个持续 Synth；停止后 Group/Synth 释放，server 退出 0。记录见 `protocol_runtime.json/.log`。

真实 Python raw replay→receiver 的脚本操作使用 `--invitation --actions config/mapping_runtime_check.json`，包括邀请、decline、暂停/继续、重播和正常完成。`session_20260920_154439/` 留有 60 个 frame、307 个 music packet、watchdog 与释放记录；最终 `session_20260920_155647/` 再次验证同一流程，另保存 `terminations.json` 的 declined / completed 原因。第一次脚本操作暴露同一循环内 invitation 采样时间早于 press 时间的问题，已统一时钟顺序；失败日志 `session_20260920_154313/` 保留为历史，不当作通过证据。上述 runtime 验证设置 `SDD_AUDITION_SILENT=1`，没有声学试听结论。

人工记录请填写 `mapping_audition/listening_notes.md`。先听手动轨迹，再同输入真人 replay；普通变化和邀请最后分别／一起比较。后续需有标签的重复 live 条件才能讨论对应是否稳定可学：P3/P4 alpha、F3/F4 theta、C3/C4 mu/beta 与肌肉输入本轮未新接通，不自动打开九值。听出了变化不证明自我归属或反思效果。

## 文件与任务说明

新增 `src/sdd/audition_features.py`、`music_mapping.py`、`mapping_audition.py`、`mapping_render.py`、两份 mapping 配置、SC 扩展与启动脚本、runtime 验证脚本及 `tests/test_mapping_audition.py`。复用并小幅扩展 `replay_source.py`、`eeg_control_demo.py`、`eeg_control_features.py` 和原 harmonic core；receiver 的旧“synthetic input”日志改为中性声部状态，实际来源由 Python 记录。旧入口默认行为保留。`SDD_V1_Plan/NEXT_CODEX_TASK.md` 当前已包含用户这份完整 M01–M06 任务说明，保留了执行期间出现的该文件更新；未重编号或覆盖 atomic plan。

overnight 清理只列于 `mapping_audition/cleanup_inventory.json` 和 `mapping_cleanup.md`，没有执行删除或移动。

最终启动验证补记：`session_20260920_160138/` 使用当前入口的 `--candidate space_delay --duration 3 --once`，从指定 raw 会话重算并送达 11 个 frame、56 个 music packet；receiver graceful release、专属 Group/Synth 消失、server 退出 0。输出静音，未代替人工试听。独立交付的 `mapping_audition_19_wavs_20260920.zip` 仅收录 manifest 中的 19 个 WAV；启动速查和映射表分别为 `mapping_audition/START_HERE.md` 与 `MAPPING_TABLE.md`。
