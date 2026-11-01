"""The page published as an Artifact: it must load only what the Artifact's frame allows, and read the committed data."""
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "web" / "atlas.html").read_text(encoding="utf-8")


def test_the_page_is_written_for_the_skeleton_the_artifact_adds():
    assert PAGE.startswith("<title>")
    assert not re.search(r"<!doctype|<html|<head[\s>]|<body", PAGE, re.I)


def test_scripts_come_from_allowed_hosts_with_an_exact_version():
    sources = re.findall(r'<script src="([^"]+)"', PAGE)
    assert sources
    for source in sources:
        assert source.startswith(("https://cdn.jsdelivr.net/npm/", "https://unpkg.com/"))
        assert re.search(r"@\d+\.\d+\.\d+/", source)


def test_every_data_file_the_page_reads_is_committed():
    names = set(re.findall(r'json\("(\w+)"\)', PAGE))
    assert names == {"panel", "atlas", "distritos", "departamentos", "huella", "tokens"}
    for name in names:
        assert (ROOT / "datos" / "atlas" / f"{name}.json").is_file()
    assert "data/huella.txt" in PAGE and (ROOT / "datos" / "atlas" / "huella.bin").is_file()


def test_the_prepared_footprint_decodes_to_the_committed_bytes(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from scripts import preparar_web

    monkeypatch.setattr(preparar_web, "TARGET", tmp_path / "data")
    monkeypatch.setattr(preparar_web, "ROOT", tmp_path.parent)
    preparar_web.main()

    text = (tmp_path / "data" / "huella.txt").read_text(encoding="ascii")
    assert base64.b64decode(text) == (ROOT / "datos" / "atlas" / "huella.bin").read_bytes()
    assert (tmp_path / "data" / "panel.json").read_bytes() == (ROOT / "datos" / "atlas" / "panel.json").read_bytes()


def test_no_control_depends_on_a_download_the_frame_blocks():
    assert ".download =" not in PAGE and "<a download" not in PAGE


def test_the_author_is_named_under_the_title():
    assert re.search(r'</h1>\s*<p class="byline">Por Rodrigo Norabuena</p>', PAGE)
