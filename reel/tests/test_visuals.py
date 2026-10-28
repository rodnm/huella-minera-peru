"""Resolving a scene's `visual`: a single image or a folder of numbered frames."""
import pytest
from PIL import Image

from reelkit.visuals import resolve_visual


def _png(path, color=(10, 20, 30)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 30), color).save(path)
    return path


def test_resolves_a_png_or_jpg_as_a_still_image(tmp_path):
    _png(tmp_path / "escenas" / "mapa.png")
    Image.new("RGB", (40, 30)).save(tmp_path / "foto.jpg")
    png = resolve_visual(tmp_path, "escenas/mapa.png")
    jpg = resolve_visual(tmp_path, "foto.jpg")
    assert png.kind == "image" and png.paths == [tmp_path / "escenas" / "mapa.png"]
    assert jpg.kind == "image"


def test_resolves_a_folder_as_frames_in_natural_numeric_order(tmp_path):
    for n in (10, 2, 1):
        _png(tmp_path / "anim" / f"{n}.png")
    v = resolve_visual(tmp_path, "anim")
    assert v.kind == "frames"
    assert [p.name for p in v.paths] == ["1.png", "2.png", "10.png"]


def test_folder_frames_ignore_non_png_files(tmp_path):
    _png(tmp_path / "anim" / "0001.png")
    (tmp_path / "anim" / "notas.txt").write_text("x")
    assert [p.name for p in resolve_visual(tmp_path, "anim").paths] == ["0001.png"]


def test_missing_path_raises_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="no existe"):
        resolve_visual(tmp_path, "escenas/falta.png")


def test_empty_folder_raises(tmp_path):
    (tmp_path / "vacia").mkdir()
    with pytest.raises(ValueError, match="PNG"):
        resolve_visual(tmp_path, "vacia")


def test_unsupported_extension_raises(tmp_path):
    (tmp_path / "video.gif").write_bytes(b"GIF89a")
    with pytest.raises(ValueError, match="formato"):
        resolve_visual(tmp_path, "video.gif")
