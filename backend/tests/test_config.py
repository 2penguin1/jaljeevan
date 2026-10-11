from app.core.config import Settings


def test_the_database_url_is_built_from_the_parts_aws_provides(monkeypatch):
    for key, value in {"DB_HOST": "db.abc.ap-south-1.rds.amazonaws.com", "DB_PORT": "5432", "DB_NAME": "jal",
                       "DB_USER": "jal_admin", "DB_PASSWORD": "p@ss/word"}.items():
        monkeypatch.setenv(key, value)
    url = Settings(_env_file=None).database_url
    assert url == "postgresql+psycopg://jal_admin:p%40ss%2Fword@db.abc.ap-south-1.rds.amazonaws.com:5432/jal"


def test_without_the_parts_the_url_setting_is_used(monkeypatch):
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@localhost:5433/x")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://a:b@localhost:5433/x"
