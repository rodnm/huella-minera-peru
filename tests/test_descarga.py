import hashlib
import json

from brillo.descarga import download, fetch_arcgis_layer, record, sha256


class FakeResponse:
    def __init__(self, payload: bytes = b"", data: dict | None = None):
        self.payload, self.data = payload, data

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.payload

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, **kwargs):
        self.calls.append((url, params))
        return self.routes(url, params)

    post = get


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"night lights")
    assert sha256(f) == hashlib.sha256(b"night lights").hexdigest()


def test_download_writes_file_and_skips_it_when_present(tmp_path):
    session = FakeSession(lambda url, params: FakeResponse(b"xlsx bytes"))
    dest = tmp_path / "inei" / "anexo.xlsx"
    download("https://example.org/anexo.xlsx", dest, session=session)
    download("https://example.org/anexo.xlsx", dest, session=session)
    assert dest.read_bytes() == b"xlsx bytes"
    assert len(session.calls) == 1


def test_record_writes_url_date_and_hash_to_manifest(tmp_path):
    f = tmp_path / "originales" / "inei" / "anexo.xlsx"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"data")
    manifest = tmp_path / "originales" / "MANIFEST.json"
    record(manifest, name="pobreza_inei_2018", url="https://example.org/anexo.xlsx", path=f,
           page="https://example.org/page", license="Open", downloaded_at="2026-10-28")
    entry = json.loads(manifest.read_text(encoding="utf-8"))["pobreza_inei_2018"]
    assert entry == {"url": "https://example.org/anexo.xlsx", "page": "https://example.org/page", "license": "Open",
                     "file": "inei/anexo.xlsx", "bytes": 4, "sha256": hashlib.sha256(b"data").hexdigest(),
                     "downloaded_at": "2026-10-28"}


def test_fetch_arcgis_layer_queries_all_object_ids_in_batches(tmp_path):
    def routes(url, params):
        if params.get("returnIdsOnly") == "true":
            return FakeResponse(data={"objectIds": [3, 1, 2, 5, 4]})
        ids = [int(i) for i in params["objectIds"].split(",")]
        return FakeResponse(data={"type": "FeatureCollection",
                                  "features": [{"type": "Feature", "properties": {"OBJECTID": i}, "geometry": None}
                                               for i in ids]})

    session = FakeSession(routes)
    out = tmp_path / "distritos.geojson"
    fetch_arcgis_layer("https://example.org/MapServer/2", out, session=session, batch=2)
    features = json.loads(out.read_text(encoding="utf-8"))["features"]
    assert sorted(f["properties"]["OBJECTID"] for f in features) == [1, 2, 3, 4, 5]
    assert len(session.calls) == 1 + 3
