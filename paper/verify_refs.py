"""Resolve scholarly identifiers; retain compact primary-source metadata, not paper text."""

import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

references = {}
for name, doi in {
    "dixon1997": "10.1111/1467-9876.00065",
    "bailey2014": "10.3905/jpm.2014.40.5.094",
    "efron1979": "10.1214/aos/1176344552",
}.items():
    url = "https://api.crossref.org/works/" + doi
    with urllib.request.urlopen(url, timeout=45) as response:
        raw = response.read()
    message = json.loads(raw)["message"]
    assert message["DOI"].lower() == doi.lower()
    references[name] = {
        "doi": message["DOI"],
        "title": message["title"],
        "authors": message["author"],
        "published": message["published"],
        "container": message.get("container-title"),
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "page": message.get("page"),
        "verification_url": url,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
    }
url = "https://export.arxiv.org/api/query?id_list=1710.02824"
with urllib.request.urlopen(url, timeout=45) as response:
    raw = response.read()
entry = ET.fromstring(raw).find("{http://www.w3.org/2005/Atom}entry")
ns = {"a": "http://www.w3.org/2005/Atom"}
assert "1710.02824" in entry.findtext("a:id", namespaces=ns)
references["kaunitz2017"] = {
    "arxiv_id": "1710.02824",
    "title": entry.findtext("a:title", namespaces=ns),
    "authors": [a.findtext("a:name", namespaces=ns) for a in entry.findall("a:author", ns)],
    "published": entry.findtext("a:published", namespaces=ns),
    "verification_url": url,
    "response_sha256": hashlib.sha256(raw).hexdigest(),
}
url = "https://the-odds-api.com/liveapi/guides/v4/"
with urllib.request.urlopen(url, timeout=45) as response:
    raw = response.read()
assert b"x-requests-remaining" in raw
references["oddsdocs"] = {
    "title": "Odds API Documentation V4",
    "verification_url": url,
    "identifier_type": "official documentation URL; no scholarly DOI",
    "response_sha256": hashlib.sha256(raw).hexdigest(),
}
Path(__file__).with_name("reference_verification.json").write_text(
    json.dumps({"verified_at": datetime.now(UTC).isoformat(), "references": references}, indent=2)
    + "\n"
)
print("Verified", len(references), "references")
