"""Download primary sources and record each file's origin in datos/originales/MANIFEST.json."""
import hashlib
import json
import time
from datetime import date
from pathlib import Path

import requests
import truststore

# Verify TLS against the operating system's certificate store: some government servers (GEOCATMIN) omit their
# intermediate certificate, which the OS store can complete and certifi cannot. Verification stays on.
truststore.inject_into_ssl()

# An honest User-Agent: some government portals block unknown clients, and we do not pretend to be a browser
USER_AGENT = "paradoja-del-brillo/0.1 (student data project; +https://github.com/rodnm/paradoja-del-brillo)"


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, dest: Path, session=None, retries: int = 3) -> Path:
    """Stream ``url`` to ``dest``; a file that already exists is kept, so re-runs are cheap."""
    if dest.exists():
        return dest
    session = session or new_session()
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, stream=True, timeout=120)
            response.raise_for_status()
            with open(partial, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            partial.replace(dest)
            return dest
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(2 ** attempt)
    return dest


def record(manifest: Path, name: str, url: str, path: Path, page: str, license: str,
           downloaded_at: str | None = None) -> dict:
    """Add or replace one source in the manifest, with its size and SHA-256."""
    entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    entries[name] = {
        "url": url,
        "page": page,
        "license": license,
        "file": path.relative_to(manifest.parent).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "downloaded_at": downloaded_at or date.today().isoformat(),
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(dict(sorted(entries.items())), indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return entries[name]


def fetch_arcgis_layer(layer_url: str, dest: Path, session=None, batch: int = 200) -> Path:
    """Save every feature of an ArcGIS MapServer layer as GeoJSON.

    These servers cap each answer and some reject offset paging, so we ask for all object IDs first and then query
    them in batches.
    """
    if dest.exists():
        return dest
    session = session or new_session()
    ids = session.get(f"{layer_url}/query", params={"where": "1=1", "returnIdsOnly": "true", "f": "json"},
                      timeout=120).json()["objectIds"]
    ids = sorted(ids)
    features = []
    for start in range(0, len(ids), batch):
        chunk = ",".join(str(i) for i in ids[start:start + batch])
        response = session.post(f"{layer_url}/query", data=None,
                                params={"objectIds": chunk, "outFields": "*", "outSR": "4326", "f": "geojson"},
                                timeout=300)
        response.raise_for_status()
        features.extend(response.json()["features"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
                    encoding="utf-8")
    return dest
