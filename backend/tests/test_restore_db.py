from scripts.restore_db import parse_s3, restore


class FakeS3:
    def __init__(self):
        self.calls = []

    def download_file(self, bucket, key, path):
        self.calls.append((bucket, key, path))


class Done:
    returncode = 0
    stderr = ""


def test_s3_addresses_are_split_into_bucket_and_key():
    assert parse_s3("s3://jal-data/dumps/jal.dump") == ("jal-data", "dumps/jal.dump")


def test_restore_downloads_then_runs_pg_restore_without_the_password_on_the_command_line(monkeypatch):
    for k, v in {"DB_HOST": "db.internal", "DB_PORT": "5432", "DB_NAME": "jal", "DB_USER": "admin",
                 "DB_PASSWORD": "s3cret"}.items():
        monkeypatch.setenv(k, v)
    s3, seen = FakeS3(), {}

    def run(cmd, env, capture_output, text):
        seen.update(cmd=cmd, env=env)
        return Done()

    assert restore("s3://jal-data/dumps/jal.dump", s3=s3, run=run) == 0
    assert s3.calls[0][:2] == ("jal-data", "dumps/jal.dump")
    cmd = seen["cmd"]
    assert cmd[0] == "pg_restore" and "--no-owner" in cmd and "--no-acl" in cmd and cmd[-1] == s3.calls[0][2]
    assert ["-h", "db.internal"] == cmd[cmd.index("-h"):cmd.index("-h") + 2] and "s3cret" not in " ".join(cmd)
    assert seen["env"]["PGPASSWORD"] == "s3cret"
