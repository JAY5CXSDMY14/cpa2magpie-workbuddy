import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "cpa2magpie_workbuddy.py")
SAMPLE = os.path.join(HERE, "fixtures", "cpa-workbuddy-sample.json")


def run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], check=True, capture_output=True, text=True)


def test_new_and_overwrite():
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "plugin-auth.json")
        json.dump({"workbuddy": {"type": "oauth", "access": "x", "refresh": "y", "expires": 0, "accountId": "old", "uid": "u999"}}, open(target, "w"))
        run(SAMPLE, "--target", target)
        run(SAMPLE, "--target", target)  # 同一 uid 再跑：覆盖，不重复
        data = json.load(open(target))
        mine = [v for k, v in data.items() if v.get("uid") == "u123"]
        assert len(mine) == 1 and len(data) == 2
        e = mine[0]
        assert e["type"] == "oauth" and e["refresh"] == "rt_fake_refresh_token"
        assert e["enterpriseId"] == "ent9" and e["accountId"] == "138xxxx0000"
        assert e["expires"] == 1791666000000
        assert oct(os.stat(target).st_mode & 0o777) == "0o600"


def test_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "plugin-auth.json")
        out = run(SAMPLE, "--target", target, "--dry-run").stdout
        assert not os.path.exists(target) and "fake_refresh" not in out


if __name__ == "__main__":
    test_new_and_overwrite(); test_dry_run_writes_nothing(); print("ok")
