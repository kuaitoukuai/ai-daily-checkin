# WorkBuddy 积分助手（vendored）

本目录脚本来自 **totorosir-workbuddy-score v3.3.1**（作者 totorosir，MIT-0 许可），
为便于合并进本仓库做了原样保留，未修改业务逻辑。

| 文件 | 说明 |
|---|---|
| `buddy_station.py` | 主程序：读本机登录态 → 查积分/签到/播报 |
| `push_notify.py` | 多通道推送（PushPlus / Server酱等） |
| `toast.ps1` | 系统通知 |
| `SKILL.md` | 原技能说明（完整命令与参数） |

## 最常用

```bash
# 签到
python buddy_station.py checkin

# 只看余额/连续天数（JSON）
python buddy_station.py --json
```

## Windows / Git Bash 注意

Git Bash 里 `LOCALAPPDATA` 可能为空，先补：

```bash
export LOCALAPPDATA="C:\\Users\\<你>\\AppData\\Local"
export APPDATA="C:\\Users\\<你>\\AppData\\Roaming"
```

登录态位置：`%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info`

## 许可

MIT-0（MIT No Attribution）。原始说明见 `SKILL.md` 与仓库根 `LICENSE` 的第三方声明。
