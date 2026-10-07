# 音乐映射表

所有 `manual` 文件使用同一低→中→高→低轨迹；所有 `replay` 文件使用同一真人静息记录 60–84 秒的 **F3 4–40 Hz 能量**。单位为 uV²，按约 32–52 秒有效个人基线做对数百分位缩放与平滑。没有说话/聆听等条件标签，不赋予心理解释。

| 候选 | 控制量低→高改变什么 | 主要固定内容 | 手动对照 | 真人回放 |
| --- | --- | --- | --- | --- |
| level | 附加增益 -12→0 dB | 音高、音色、节奏、效果 | [WAV](manual_level.wav) | [WAV](replay_level.wav) |
| pitch | 上声线 A3→B3→C#4 | G2/D3 底座、音色、节奏、效果 | [WAV](manual_pitch.wav) | [WAV](replay_pitch.wav) |
| timbre | 泛音组由低组占优转向更多高组 | 音高、音符权重、节奏、效果 | [WAV](manual_timbre.wav) | [WAV](replay_timbre.wav) |
| space_reverb | 混响 mix 0.06→0.38；tail 0.8→4 秒 | 和弦、音色、每小节一次固定起音 | [WAV](manual_space_reverb.wav) | [WAV](replay_space_reverb.wav) |
| space_delay | 两次无反馈回声，mix 0→0.32 | 和弦、音色、同一固定起音；延迟 1/3、2/3 秒 | [WAV](manual_space_delay.wav) | [WAV](replay_space_delay.wav) |
| harmony | G–D–A → G–E–B → G–F#–C# | 共同低音 G2、音区、音色、节奏、效果 | [WAV](manual_harmony.wav) | [WAV](replay_harmony.wav) |
| rhythm | 每小节 1→2→4 次起音 | 90 BPM、和弦、音色、效果 | [WAV](manual_rhythm.wav) | [WAV](replay_rhythm.wav) |
| note_weights | 同和弦内 D3 权重减少、A3 权重增加 | 音高集合、泛音组、节奏、效果 | [WAV](manual_note_weights.wav) | [WAV](replay_note_weights.wav) |

泛音组权重与和弦内音符权重是两种不同控制。离散音高/和声有回差和至少 1.5 秒保持；换音交叉淡化 1.35 秒。节奏密度在下一小节生效，最多增加 2.67 秒等待，不能称零延迟。真实片段不一定遍历手动轨迹的全部状态。

九值 frame 在新试听中保持固定，只有独立音乐控制和既有 voicing 通道随候选变化。没有完整九值实时计算，也没有使用 Ch7/Ch8 驱动声音；Ch7 的饱和质量标记保留。

## 邀请来源对照

| 文件 | 生理映射 | 邀请 |
| --- | --- | --- |
| [仅生理变化](compare_physiology_only.wav) | 真人 F3 energy → timbre | 无 event、无邀请变换 |
| [仅邀请](compare_invitation_only.wav) | timbre 控制固定 0.5 | 第 7 秒显式事件，上声线暂时 A3→B3→A3 |
| [两者一起](compare_combined.wav) | 同一真人 F3 energy → timbre 持续运行 | 同时执行相同邀请，不恢复旧音色快照 |

邀请只改现有声部的上声线，不播放另一段提示音。开启邀请时禁用生理 pitch/harmony/note_weights，避免共同占用上声部。诊断音量深度默认关闭。

状态：八个候选均为 **手动试听可用／真人回放可用／等待人工试听／行为对应待验证**。只有既往 F3 energy→level 链路有 live 联通证据；本次新的缩放和菜单不能据此直接标为 live 已验收。所有可辨性、同声部感、舒适度及心理结论仍待人工/live 验证。
