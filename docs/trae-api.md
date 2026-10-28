# Trae CN 签到接口与登录态说明

> 基于 Trae CN 客户端本地资源（`resources/app/out/main.js`）的静态分析，仅用于自动化自己账号的每日签到。

## 1. 接口

Host：`https://api.trae.cn`

| 用途 | 方法 | 路径 | Body |
|---|---|---|---|
| 查签到状态 | POST | `/trae/api/v2/ug/checkin_credits/status` | `{"req_source":2}` |
| 领取 | POST | `/trae/api/v2/ug/checkin_credits/claim` | `{"req_source":2}` |
| 余额/权益 | POST | `/trae/api/v2/pay/ide_user_ent_usage` | `{}` |

请求头：

```
Content-Type: application/json
Authorization: Cloud-IDE-JWT <token>
X-User-Region: CN
x-device-id: <本机设备号>
```

状态返回：`{"checked_in":bool,"code":0,"credits":100,"enable":true}`。
余额：`usage_summary.total_amount - consumed_amount`。

## 2. 登录态在哪

`%APPDATA%\Trae CN\User\globalStorage\storage.json` 的键：

```
iCubeAuthInfo://icube.cloudide
```

值为 base64 密文，解密后是 JSON：`{token, refreshToken, expiredAt, account, userRegion, ...}`。

> 注意：`~/.trae-cn/trae-jwt-token` **不是** API token，它是 TokenManager 写给 AI 子进程的临时 token，用它调接口会返回 `code:1001`。

## 3. "tc" 信封解密

密文前缀 `74 63 05 10 00 00`（"tc" + 版本）。算法：

```
key   = blob[6:38]                 # 32B
salt  = Ode[i] ^ Nde[i]            # 两组 64B 常量异或
c     = SHA512( SHA512(key) ‖ salt )
aesKey = c[0:16] ; iv = c[16:32]
plain  = AES-CBC-decrypt(blob[38:])
校验    : plain[0:64] == SHA512(plain[64:])
正文    : plain[64:]  → JSON
```

常量 `Ode` / `Nde` 见 `trae/checkin_api.js`。

## 4. 设备号

`x-device-id` 必须是本机注册过的真实值。可从
`%APPDATA%\Trae CN\logs\aha_log\aha_*.log` 里的 `device_id: 1729...` 提取；
`checkin_api.js` 会自动扫描最新日志，也可在 `config.json` 的 `trae.device_id` 手动指定。

## 5. 失效与自愈

- token 有效期约 7 天；过期后打开一次 Trae 会自动续期。
- 本项目的 `daily.py --mode auto` 会在 API 失败时走像素方案，此时 Trae 停留更久、顺带刷新 token，次日 API 恢复。
- 若客户端升级导致信封魔数变化，`checkin_api.js` 会明确报「未知信封版本」，需重新分析。
