# WorkBuddy 签到说明

脚本在 `workbuddy/`，核心是 `buddy_station.py`（纯标准库，无第三方依赖）。

## 常用命令

```bash
python workbuddy/buddy_station.py checkin      # 签到
python workbuddy/buddy_station.py --json       # 余额/连续天数/本月记录
python workbuddy/buddy_station.py checkin --full   # 完整播报
```

## 登录态

```
%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info
```

accessToken 为 AES-256-GCM 信封，脚本会自动识别并解密；解密在**本机**完成，token 不外传。

## Windows / Git Bash

Git Bash 里 `LOCALAPPDATA` 常为空，先补环境变量：

```bash
export LOCALAPPDATA="C:\\Users\\<你>\\AppData\\Local"
export APPDATA="C:\\Users\\<你>\\AppData\\Roaming"
```

## 余额口径

客户端面板的「积分余额」与签到接口的 `total_credits` 不是同一口径。
准确余额请走 `/billing/meter/get-user-resource-summary`（脚本已处理，失败时才降级）。

## 定时

`buddy_station.py` 不依赖 WorkBuddy 客户端保持打开，可直接用计划任务在每天固定时间调用 `checkin`。
如果要和 Trae 一起跑，可把两条命令写进同一个 `.cmd` 或 Python 编排脚本。
