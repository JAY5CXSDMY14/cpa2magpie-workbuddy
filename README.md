# cpa2magpie-workbuddy

> 现在也支持 **ZCode**：`cpa2magpie_zcode.py`，见下方「ZCode」一节。

把 [CLIProxyAPI (CPA)](https://github.com/router-for-me/CLIProxyAPI) 里 WorkBuddy 插件生成的认证文件（`workbuddy-<uid>.json`），转进 [magpie](https://github.com/yetone/magpie) 的 `plugin-auth.json`，不用在 magpie 里逐个重新登录。

## 为什么需要它

- `magpie accounts import` 只支持 `codex | claude | antigravity | factory`，没有 WorkBuddy。
- magpie 的 WorkBuddy 现在由社区插件 `@magpie-community/opencode-workbuddy-auth` 提供（provider id：国内版 `workbuddy`，国际版 `workbuddy-ai`），只支持两种登录：浏览器登录，或者读 WorkBuddy 桌面端的 `.info` 文件。
- 插件的登录信息存在 `plugin-auth.json`，格式和 OpenCode 的 `auth.json` 一样：第一个账号存在 `workbuddy` 下，后面的账号存在 `workbuddy#<slot>` 下。本脚本直接写这种格式。

## ⚠️ refresh token 会轮换

WorkBuddy 每次刷新都会换一个新的 refresh token。CPA 和 magpie 如果共用同一份凭证，谁先刷新，另一边就会掉线。所以文件要**移出** CPA，不能复制。

## 使用步骤

1. 在 magpie 里装好插件：`magpie plugin add @magpie-community/opencode-workbuddy-auth`（已经装了就跳过）
2. **退出 magpie**：App、`magpie serve`，或者 `docker stop magpie`
3. 把 `workbuddy-*.json` 从 CPA 的 auth 目录**移走**（例如 `mv ~/cli-proxy-api/auths/workbuddy-*.json ~/cpa-wb/`）。CPA 会自动卸下这些账号
4. 先预览一遍，token 会打码：
   ```bash
   python3 cpa2magpie_workbuddy.py ~/cpa-wb/workbuddy-*.json --dry-run
   ```
5. 正式写入：
   ```bash
   # 本机 magpie（默认 ~/.config/magpie/plugin-auth.json）
   python3 cpa2magpie_workbuddy.py ~/cpa-wb/workbuddy-*.json
   # Docker 版 magpie：指向卷里的文件
   python3 cpa2magpie_workbuddy.py ~/cpa-wb/workbuddy-*.json --target /path/to/volume/magpie/plugin-auth.json
   ```
   国际版如果识别错了，加 `--site ai`；国内版加 `--site cn`。
6. 启动 magpie，到 Usage 或 Routing 里确认这些账号已经出现，再随便发一条请求测试一下。

## 行为说明

- 写入前会把原文件备份成 `plugin-auth.json.before-cpa-<时间戳>`。写入是原子的，权限 0600
- 同一个 uid 再跑一次会覆盖原来那条，不会重复添加
- 字段名兼容 `access_token/accessToken`、`refresh_token`、`uid/user_id`、`expired/expires_at`（RFC3339 或时间戳都行）、`enterprise_id` 等，嵌套的字段也能找到
- access token 过期了也没关系，插件会用 refresh token 自动续上
- 团队（企业）账号会带上 `enterpriseId`，否则 WorkBuddy 会按个人账号返回模型

## 给执行 agent 的说明

- 提示「找不到 xxx」时，只把字段**名**汇报给用户，不要输出 token 值。然后在 `ALIASES` 里补上别名
- 不要把任何真实的 `*.json` 认证文件提交进仓库（`.gitignore` 已经排除）
- 不要在 magpie 运行时改 `plugin-auth.json`
- 测试：`python3 tests/test_convert.py`

## 已知限制

- 只用合成数据测过，CPA 插件真实文件的字段名还没确认
- 插件不支持 magpie 内置 WorkBuddy 的每日签到、积分统计（见插件 README）


---

# ZCode：CPA → magpie

把 CPA 的 ZCode 插件（[lengjingxu/CLIProxyAPI-ZCode](https://github.com/lengjingxu/CLIProxyAPI-ZCode)）的认证文件（auth 目录里以 `zcode` 开头的 JSON，内容是 `{"type":"zcode","api_key":"<id>.<secret>",...}`）转进 magpie。

- magpie 侧用社区插件 `@magpie-community/opencode-zcode-auth`，provider id `zcode`
- 写成插件「GLM Coding Plan API key」登录的同款条目：`{"type":"api","key":"<id>.<secret>","metadata":{"site":"zai|bigmodel"}}`；第一个账号在 `zcode`，后面的在 `zcode#<slot>`
- **API key 不会轮换**，所以和 WorkBuddy 不同：CPA 里的文件可以留着，两边同时用同一个 key（共用额度）。不想共用就移走

## 使用步骤

1. `magpie plugin add @magpie-community/opencode-zcode-auth`（装过就跳过）
2. 退出 magpie
3. 预览：
   ```bash
   python3 cpa2magpie_zcode.py ~/cli-proxy-api/auths/zcode*.json --dry-run
   ```
   看输出里的 `site=` 对不对。文件里没有 `base_url` 时，CPA 实际用的是 `config.yaml` 里 `plugins.configs.zcode.base_url`（默认 `api.z.ai`）；那里写的是 `open.bigmodel.cn` 的话，加 `--site bigmodel`
4. 正式写入（Docker 同样用 `--target`）：
   ```bash
   python3 cpa2magpie_zcode.py ~/cli-proxy-api/auths/zcode*.json
   ```
5. 启动 magpie，在 Usage 里能看到 GLM Coding Plan 的额度就说明成功

## 行为说明

- 同一个 key 重跑会覆盖，不重复添加；写前备份、原子写入、0600，和 WorkBuddy 脚本一样
- 字段名兼容 `api_key/apiKey/api-key/apikey/key/token`、`base_url/baseUrl/base-url`（与 CPA 插件一致）
- 测试：`python3 tests/test_zcode.py`

## 已知限制

- 只转 API key。CPA 内置的 `zai` OAuth 登录（`-zai-login`）存的是另一种格式，没有覆盖；遇到时让执行 agent 汇报字段名
- 用 key 登录时，插件的 Start Plan（免费额度）和赠送套餐的识别依赖 ZCode 会话 token，key 登录多半拿不到，基本只走 Coding Plan
