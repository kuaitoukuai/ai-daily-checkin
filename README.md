# ai-daily-checkin

> WorkBuddy & Trae 每日自动签到：**API 优先、UI 兜底、微信推送 + 桌面通知、Windows 计划任务**。
> 一个仓库装两套签到，逻辑同构：读本机登录态 → 调接口 → 幂等判断 → 失败回落 UI → 通知。

## 它能做什么

| 平台 | 方式 | 是否需打开应用 | 说明 |
|---|---|---|---|
| WorkBuddy | 读本机登录态 + 接口直查 | 否 | 调用官方 daily-checkin 接口，幂等 |
| Trae CN | 方案 A：解密登录态调接口 | 否 | 需本机已登录 Trae CN |
| Trae CN | 方案 B：截图像素识别 + 点击 | 是 | API 失败时兜底，可自动开关 Trae |

两个平台都支持：**签到前/后积分对比**、**微信推送（PushPlus）**、**Windows 桌面 Toast**。

## 目录结构

```
ai-daily-checkin/
├─ trae/
│  ├─ checkin_api.js     # 方案 A：登录态解密 + checkin_credits 接口
│  ├─ checkin_ui.py      # 方案 B：找窗口 → 定位按钮 → 像素判定 → 点击
│  ├─ daily.py           # 编排：开 Trae → API 优先 → UI 兜底 → 退出 → 通知
│  ├─ notify.py          # PushPlus 推送 + Toast 调用
│  └─ toast.ps1          # WinRT 桌面通知
├─ workbuddy/
│  ├─ buddy_station.py   # WorkBuddy 积分助手（签到/查询/播报）
│  ├─ push_notify.py     # 多通道推送
│  └─ toast.ps1
├─ docs/
│  ├─ trae-api.md        # Trae 接口与信封解密说明
│  └─ workbuddy.md       # WorkBuddy 用法
├─ config.example.json
├─ LICENSE
└─ README.md
```

## 快速开始

### 1. 配置

```bash
cp config.example.json config.json
```

按需填写（均可留空，代码会尝试自动探测）：

```json
{
  "trae": { "device_id": "" },
  "pushplus_token": ""
}
```

- `trae.device_id`：留空则从 Trae 日志自动提取。
- `pushplus_token`：留空则只发桌面通知，不推送微信；也可用环境变量 `PUSHPLUS_TOKEN`。

### 2. Trae 签到

```bash
# 只查状态（不领取）
node trae/checkin_api.js --dry-run

# 直接调接口签到（不需要打开 Trae）
node trae/checkin_api.js

# 完整流程：打开 Trae → API 优先 → UI 兜底 → 退出 → 通知
python trae/daily.py --mode auto
```

`trae/daily.py` 参数：

| 参数 | 说明 |
|---|---|
| `--mode auto` | 默认。需要时启动 Trae，API 优先，失败走像素方案 |
| `--mode api` | 只走 API，不启动 Trae |
| `--mode ui` | 只走像素方案（会启动/退出 Trae） |
| `--no-launch` | 不自动启动 Trae |
| `--no-quit` | 跑完不退出 Trae |
| `--dry-run` | 只检测，不领取/不点击 |

### 3. WorkBuddy 签到

```bash
# 签到（默认精简输出）
python workbuddy/buddy_station.py checkin

# 查余额/连续天数
python workbuddy/buddy_station.py --json
```

> Windows 的 Git Bash 里 `LOCALAPPDATA` 可能为空，先执行：
> `export LOCALAPPDATA="$LOCALAPPDATA_HOME"` 指向 `C:\Users\<你>\AppData\Local`。

### 4. 定时任务（Windows，每天 08:30）

```powershell
$py = (Get-Command pythonw).Source
$script = "C:\path\to\ai-daily-checkin\trae\daily.py"
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$script`" --mode auto" -WorkingDirectory "C:\path\to\ai-daily-checkin"
$trigger = New-ScheduledTaskTrigger -Daily -At 08:30
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName "AiDailyCheckin" -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

用 `pythonw.exe` 可以避免黑框；`Interactive` 登录态保证桌面通知和 UI 点击可用。

## 设计要点

1. **API 优先**：接口签到不依赖界面，锁屏也能跑，速度快。
2. **UI 兜底**：接口因 token 过期等原因失败时，自动走像素方案；此时 Trae 停留更久会顺带刷新 token，次日 API 自愈。
3. **幂等**：先读 `checked_in`，已签到绝不做写操作。
4. **零依赖搬运**：Trae 侧只需 Node（API）与 Python + Pillow/numpy/pywin32（UI）；WorkBuddy 侧纯标准库。

## 安全与合规

- 本仓库**不含任何 token、账号、设备号**；`config.json`、`logs/`、`shots/` 已在 `.gitignore` 中。
- 登录态解密仅在本机进行，凭据不离开本机（仅发送到对应平台的官方接口）。
- 本项目仅用于自动化**你自己账号**的每日签到，请遵守各平台服务条款；因使用产生的风险由使用者自行承担。

## 致谢

- `workbuddy/` 下的脚本来自 **totorosir-workbuddy-score v3.3.1**（作者 totorosir，MIT-0 许可）。
- Trae 接口与信封解密思路来自对客户端本地资源（`resources/app/out/main.js`）的静态分析。

## License

MIT
