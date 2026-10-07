# 单人音乐映射：启动与试听

在 `D:\sdd-sonification` 的 PowerShell 执行：

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition
```

程序自动启动现有 harmonic receiver。默认读取 `obci_eeg1_20260919_194100` 真人静息会话的原始八路数据，重新滤波、计算和校准，播放原记录 **60–84 秒**的 F3 energy → timbre。无需佩戴电极，不保存新的原始数据或录音。当前 `.venv/Scripts/python.exe` 缺失，上述 Python 已验证依赖可用。

| 按键 | 操作 |
| --- | --- |
| 1 / 2 / 3 | 响度 / 上声线音高 / 泛音音色 |
| 4 / 5 | 混响 / 延迟 |
| 6 / 7 / 8 | 和声 / 节奏 / 和弦内音符权重 |
| R | 同一片段重播并重置处理状态 |
| 空格 | 暂停 / 继续 |
| V | 启用 / 禁用邀请；与 pitch、harmony、note_weights 冲突时拒绝 |
| I | 明确触发一次 operator → A 邀请 |
| E / D | 结束 / 拒绝邀请，平滑释放 |
| Q / Ctrl+C | 停止并释放声音 |

切换候选会重播同一片段。片段结束静音，等待下一次操作。默认没有 GUI 按钮，使用键盘；I 不代表系统检测到论证缺陷或反思成功。

手动模式使用同一低→中→高→低控制轨迹；`+` / `-` 可改为手动量，T 恢复轨迹：

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition --mode manual --candidate pitch
```

一次播完自动关闭的真人回放：

```powershell
& "C:\Users\cc_10\anaconda3\python.exe" -m src.sdd.mapping_audition --candidate timbre --invitation --once
```

本轮不用 live 即可试听全部交付。后续真人现场验证的入口为 `--mode live --stream-name obci_eeg1 --confirm-live-hardware`，它会要求当前 GUI 流并重新建立有效基线；新菜单的 live 行为对应仍待验证。

## 不启动 Python/SC，直接听 WAV

`../mapping_audition_19_wavs_20260920.zip` **只含 19 个 WAV**，无真人原始样本、配置、日志或额外参考曲：

- `01_manual/`：8 个同轨迹的手动对照。
- `02_human_replay/`：8 个同一真人片段的回放对照。
- `03_invitation_comparison/`：仅生理、仅邀请、两者一起，共 3 个。

各段主内容 24 秒，加约 3.4 秒受控停止尾段。先挑一行的 manual / replay 成对听，不必一次听完。空间候选用了相同固定起音，帮助分辨混响尾音和延迟重复。邀请对照在约 7 秒开始、9 秒到顶、12 秒开始返回、14 秒结束。

映射范围与固定内容见 [映射表](MAPPING_TABLE.md)。试听后填写 [人工记录](listening_notes.md)：听出了哪种变化、何时开始/结束、能否区分来源、是否仍像同一声部、是否好听或疲劳。所有人工结果目前均为等待试听。

技术验证：84 项受影响回归通过；真实 receiver 拒绝 9 个错误消息，扩展/邀请不能续音频 watchdog，持续节点数为一个声部 Synth，停止后释放。最终 3 秒 raw replay 启动检查收到 11 帧和 56 个 music packet，正常退出；该检查静音，不当作人工试听通过。
