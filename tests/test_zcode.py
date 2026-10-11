import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "cpa2magpie_zcode.py")
BIG = os.path.join(HERE, "fixtures", "cpa-zcode-bigmodel.json")
NOBASE = os.path.join(HERE, "fixtures", "cpa-zcode-nobase.json")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], check=True, capture_output=True, text=True)


def test_new_overwrite_and_site():
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "plugin-auth.json")
        json.dump({"workbuddy": {"type": "oauth", "uid": "u1"}}, open(target, "w"))
        run(BIG, NOBASE, "--target", target)
        run(BIG, "--target", target)  # 同一个 key 再跑：覆盖，不重复
        data = json.load(open(target))
        z = {k: v for k, v in data.items() if k == "zcode" or k.startswith("zcode#")}
        assert len(z) == 2 and "workbuddy" in data
        by_key = {v["key"]: v for v in z.values()}
        assert by_key["fakeid1.fakesecret1"] == {"type": "api", "key": "fakeid1.fakesecret1", "metadata": {"site": "bigmodel"}}
        assert by_key["fakeid2.fakesecret2"]["metadata"]["site"] == "zai"
        assert oct(os.stat(target).st_mode & 0o777) == "0o600"


def test_forced_site_and_dry_run():
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "plugin-auth.json")
        out = run(NOBASE, "--target", target, "--site", "bigmodel", "--dry-run").stdout
        assert not os.path.exists(target) and "fakesecret2" not in out and "bigmodel" in out


if __name__ == "__main__":
    test_new_overwrite_and_site(); test_forced_site_and_dry_run(); print("ok")
