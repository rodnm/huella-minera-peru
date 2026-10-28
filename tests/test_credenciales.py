import pytest

from brillo.credenciales import load_token


def test_environment_variable_wins_over_dotenv(tmp_path):
    (tmp_path / ".env").write_text("BLACKMARBLE_TOKEN=from-file\n", encoding="utf-8")
    assert load_token({"BLACKMARBLE_TOKEN": "from-env"}, tmp_path / ".env") == "from-env"


def test_dotenv_is_read_when_the_variable_is_missing(tmp_path):
    (tmp_path / ".env").write_text("# NASA Earthdata\nBLACKMARBLE_TOKEN = 'from-file'\n", encoding="utf-8")
    assert load_token({}, tmp_path / ".env") == "from-file"


def test_missing_token_explains_how_to_set_it(tmp_path):
    with pytest.raises(SystemExit, match="urs.earthdata.nasa.gov"):
        load_token({}, tmp_path / ".env")
