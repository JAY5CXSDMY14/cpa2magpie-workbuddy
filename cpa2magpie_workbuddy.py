#!/usr/bin/env python3
"""把 CLIProxyAPI (CPA) 的 WorkBuddy 认证文件转进 magpie 的 plugin-auth.json。

用法:
  python3 cpa2magpie_workbuddy.py workbuddy-123.json [workbuddy-456.json ...] [选项]

选项:
  --target PATH      magpie 的 plugin-auth.json（默认 ~/.config/magpie/plugin-auth.json；
                     Docker 版是卷里的 /config/magpie/plugin-auth.json）
  --site cn|ai       强制指定国内版 (workbuddy) 或国际版 (workbuddy-ai)，默认自动判断
  --dry-run          只打印要写入的内容（token 打码），不改文件

注意:
  1. 先退出 magpie（App / magpie serve / Docker 容器），再运行，跑完再启动。
  2. WorkBuddy 的 refresh token 会轮换：先把这些文件从 CPA 的 auth 目录移走，
     再运行本脚本，之后不要再放回 CPA，否则两边会互相把对方挤掉线。
  3. magpie 里要装好 @magpie-community/opencode-workbuddy-auth 插件。
"""
import argparse, json, os, shutil, sys, time, random, string
from datetime import datetime

ALIASES = {
    "access":  ["access_token", "accessToken", "access"],
    "refresh": ["refresh_token", "refreshToken", "refresh"],
    "uid":     ["uid", "user_id", "userId", "account_uid"],
    "domain":  ["domain"],
    "enterpriseId": ["enterprise_id", "enterpriseId", "enterprise"],
    "tokenType": ["token_type", "tokenType"],
    "expires": ["expires_at", "expiresAt", "expired", "expire", "expiry", "expires"],
    "refreshExpiresAt": ["refresh_expires_at", "refreshExpiresAt", "refresh_expired"],
    "expiresIn": ["expires_in", "expiresIn"],
    "name":    ["nickname", "email", "phone_number", "phoneNumber", "phone", "label", "name"],
}


def walk(obj, out):
    """把嵌套 JSON 摊平成 key -> 第一个非空标量值。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                walk(v, out)
            elif v not in (None, "") and k not in out:
                out[k] = v
    elif isinstance(obj, list):
        for v in obj:
            walk(v, out)


def pick(flat, field):
    for k in ALIASES[field]:
        if k in flat:
            return flat[k]
    return None


def to_ms(v):
    """时间戳(秒/毫秒) 或 RFC3339 字符串 -> 毫秒。"""
    if v in (None, ""):
        return 0
    if isinstance(v, (int, float)):
        return int(v * 1000) if v < 1e12 else int(v)
    s = str(v).strip()
    if s.isdigit():
        return to_ms(int(s))
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return 0


def detect_site(raw_text, forced):
    if forced:
        return "workbuddy-ai" if forced == "ai" else "workbuddy"
    t = raw_text.lower()
    if "workbuddy.ai" in t or "codebuddy.ai" in t or '"global"' in t:
        return "workbuddy-ai"
    return "workbuddy"


def convert(path, forced_site):
    raw = open(path, encoding="utf-8").read()
    flat = {}
    walk(json.loads(raw), flat)
    access, refresh, uid = pick(flat, "access"), pick(flat, "refresh"), pick(flat, "uid")
    missing = [n for n, v in (("access_token", access), ("refresh_token", refresh), ("uid", uid)) if not v]
    if missing:
        raise SystemExit(f"{path}: 找不到 {', '.join(missing)}。把文件的字段名（不要 token 值）发给我，我来适配。")
    expires = to_ms(pick(flat, "expires"))
    if not expires and pick(flat, "expiresIn"):
        expires = int(time.time() * 1000) + int(pick(flat, "expiresIn")) * 1000
    entry = {
        "type": "oauth",
        "access": str(access),
        "refresh": str(refresh),
        "expires": expires,  # 过期了也没关系，插件会用 refresh token 续
        "accountId": str(pick(flat, "name") or uid),
        "uid": str(uid),
        "domain": str(pick(flat, "domain") or ""),
    }
    for f in ("enterpriseId", "tokenType"):
        if pick(flat, f):
            entry[f] = str(pick(flat, f))
    rexp = to_ms(pick(flat, "refreshExpiresAt"))
    if rexp:
        entry["refreshExpiresAt"] = rexp
    return detect_site(raw, forced_site), entry


def slot_key(all_auth, provider, uid):
    # 同一个 uid 已经在里面：覆盖它
    for k, v in all_auth.items():
        if (k == provider or k.startswith(provider + "#")) and isinstance(v, dict) and v.get("uid") == uid:
            return k
    if provider not in all_auth:
        return provider
    while True:
        k = provider + "#" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        if k not in all_auth:
            return k


def mask(e):
    m = dict(e)
    for f in ("access", "refresh"):
        m[f] = m[f][:6] + "…" + m[f][-4:] if len(m[f]) > 12 else "…"
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--target", default=os.path.expanduser("~/.config/magpie/plugin-auth.json"))
    ap.add_argument("--site", choices=["cn", "ai"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    a.target = os.path.abspath(os.path.expanduser(a.target))

    all_auth = {}
    if os.path.exists(a.target):
        txt = open(a.target, encoding="utf-8").read()
        if txt.strip("\x00 \n"):
            all_auth = json.loads(txt)
        elif txt:
            raise SystemExit(f"{a.target} 是全零的坏文件，先用 magpie 恢复（.bak）再来。")

    for f in a.files:
        provider, entry = convert(f, a.site)
        key = slot_key(all_auth, provider, entry["uid"])
        all_auth[key] = entry
        print(f"{f} -> {key}: {json.dumps(mask(entry), ensure_ascii=False)}")

    if a.dry_run:
        print("（dry-run，没有写文件）")
        return
    os.makedirs(os.path.dirname(a.target), exist_ok=True)
    if os.path.exists(a.target):
        bak = a.target + ".before-cpa-" + time.strftime("%Y%m%d%H%M%S")
        shutil.copy2(a.target, bak)
        print("已备份原文件 ->", bak)
    tmp = a.target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(all_auth, fh, ensure_ascii=False, indent=2)
        fh.flush(); os.fsync(fh.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, a.target)
    print("已写入", a.target, "。现在启动 magpie，在 Usage / Providers 里应该能看到这些 WorkBuddy 账号。")


if __name__ == "__main__":
    main()
