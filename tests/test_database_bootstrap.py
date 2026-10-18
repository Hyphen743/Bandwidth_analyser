"""Fresh-install database bootstrap tests."""

from accounts import ensure_account_schema
from db.repository import DatabaseRepository
from ui.common import _initialize_database


def test_dashboard_bootstrap_creates_settings_table(tmp_path):
    db_path = tmp_path / "fresh-install.db"
    assert not db_path.exists()

    _initialize_database(str(db_path))

    repo = DatabaseRepository(db_path)
    assert repo.get_setting("theme_mode") == "light"
    assert repo.get_setting("data_source") == "simulated"
    repo.set_setting("user_custom_value", "keep-me")
    repo.insert_user("Fresh Install Check", "guest")
    ensure_account_schema(repo)

    with repo.get_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"settings", "users", "devices", "bandwidth_usage", "accounts"} <= tables

    # A second process startup must leave existing configuration and rows intact.
    _initialize_database.clear()
    _initialize_database(str(db_path))
    assert repo.get_setting("user_custom_value") == "keep-me"
    assert len(repo.get_users().query("name == 'Fresh Install Check'")) == 1
