#!/usr/bin/env python3
"""把 CLIProxyAPI (CPA) 的 ZCode 认证文件转进 magpie 的 plugin-auth.json。

CPA 侧：lengjingxu/CLIProxyAPI-ZCode 插件，auth 目录里文件名以 zcode 开头，内容形如
  {"type":"zcode","api_key":"<apiKeyId>.<secretKey>","base_url":"...","label":"..."}
magpie 侧：@magpie-community/opencode-zcode-auth 插件（provider id: zcode），
  粘贴 key 的登录存为 {"type":"api","key":"<id>.<secret>","metadata":{"site":"zai|bigmodel"}}

用法:
  python3 cpa2magpie_zcode.py zcode-a.json [zcode-b.json ...] [选项]

选项:
  --target PATH          magpie 的 plugin-auth.json（默认 ~/.config/magpie/plugin-auth.json；
                         Docker 版是卷里的 /config/magpie/plugin-auth.json）
  --site zai|bigmodel    强制指定站点。文件里没有 base_url 时，CPA 用的是 config.yaml 里
                         plugins.configs.zcode.base_url（默认 api.z.ai）——那里填的是
                         open.bigmodel.cn 的话，要加 --site bigmodel
  --dry-run              只打印要写入的内容（key 打码），不改文件

注意:
  1. 先退出 magpie（App / magpie serve / Docker 容器），再运行，跑完再启动。
  2. ZCode 的 API key 不会轮换，CPA 和 magpie 可以同时用同一个 key（共用同一份额度）。
  3. magpie 里要装好 @magpie-community/opencode-zcode-auth 插件。
"""
import argparse, json, os, random, shutil, string, sys, time

PROVIDER = "zcode"
ALIASES = {
    # 和 CPA 插件 credentialFromAuthFile 的顺序一致
    "key":  ["api_key", "apiKey", "api-key", "apikey", "key", "token"],
    "base": ["base_url", "baseUrl", "base-url"],
    "site": ["site"],
}


def pick(doc, field):
    for k in ALIASES[field]:
        v = doc.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # 兜底：嵌套一层（例如 {"metadata": {...}} / {"storage": {...}}）
    for v in doc.values():
        if isinstance(v, dict):
            r = pick(v, field)
            if r:
                return r
    return None


def site_of(doc, forced):
    if forced:
        return forced, "参数指定"
    s = (pick(doc, "site") or "").lower()
    if s in ("zai", "bigmodel"):
        return s, "文件里的 site"
    base = (pick(doc, "base") or "").lower()
    if "bigmodel" in base:
        return "bigmodel", "base_url"
    if "z.ai" in base:
        return "zai", "base_url"
    return "zai", "默认（文件没有 base_url）"


def convert(path, forced_site):
    doc = json.load(open(path, encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit(f"{path}: 不是 JSON 对象")
    t = str(doc.get("type", "")).lower()
    if t and t != PROVIDER:
        print(f"{path}: 提示：type 是 {t!r}，不是 zcode，仍按 key 转换", file=sys.stderr)
    key = pick(doc, "key")
    if not key:
        raise SystemExit(f"{path}: 找不到 api_key。把文件的字段名（不要 key 值）发给我，我来适配。")
    if "." not in key:
        print(f"{path}: 提示：key 不是 <id>.<secret> 格式，magpie 可能不认", file=sys.stderr)
    site, why = site_of(doc, forced_site)
    entry = {"type": "api", "key": key, "metadata": {"site": site}}
    return entry, why


def slot_key(all_auth, key):
    # 同一个 key 已经在里面：覆盖它
    for k, v in all_auth.items():
        if (k == PROVIDER or k.startswith(PROVIDER + "#")) and isinstance(v, dict) and \
                (v.get("key") == key or v.get("access") == key):
            return k
    if PROVIDER not in all_auth:
        return PROVIDER
    while True:
        k = PROVIDER + "#" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        if k not in all_auth:
            return k


def mask(e):
    m = json.loads(json.dumps(e))
    k = m["key"]
    m["key"] = k[:4] + "…" + k[-4:] if len(k) > 12 else "…"
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--target", default=os.path.expanduser("~/.config/magpie/plugin-auth.json"))
    ap.add_argument("--site", choices=["zai", "bigmodel"])
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
        entry, why = convert(f, a.site)
        slot = slot_key(all_auth, entry["key"])
        all_auth[slot] = entry
        print(f"{f} -> {slot}（site={entry['metadata']['site']}，依据：{why}）: {json.dumps(mask(entry), ensure_ascii=False)}")

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
    print("已写入", a.target, "。现在启动 magpie，在 Usage / Providers 里应该能看到这些 ZCode 账号。")


if __name__ == "__main__":
    main()
