import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml

from scripts.release_catalogue import commit_sha, repository_name, spec_name

API = "https://sandbox.zenodo.org/api"
LICENSE_MAP_URL = (
    "https://raw.githubusercontent.com/zenodo/zenodo/"
    "df5a28e95cd71712f98b9a73ce0c7387cbf75bdf/"
    "zenodo/modules/fixtures/data/licenses_map.json"
)
LICENSE_MAP_SHA256 = "6cb98d316c629b92827890d417b3de6674fa5ae1d77c0795a000ea5d7e1411d1"


class ZenodoError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ZenodoError(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ZenodoError("Zenodo redirected a request; refusing to send credentials")


@lru_cache(maxsize=1)
def license_aliases():
    """Load Zenodo's pinned legacy-to-SPDX map without sending credentials."""
    try:
        with build_opener(NoRedirect()).open(LICENSE_MAP_URL, timeout=30) as response:
            data = response.read()
    except (HTTPError, URLError) as exc:
        raise ZenodoError("Could not retrieve Zenodo licence mapping") from exc
    require(
        hashlib.sha256(data).hexdigest() == LICENSE_MAP_SHA256,
        "Zenodo licence mapping checksum mismatch",
    )
    try:
        mapping = json.loads(data)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ZenodoError("Invalid Zenodo licence mapping") from exc
    require(
        isinstance(mapping, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()),
        "Invalid Zenodo licence mapping",
    )
    return {key.lower(): value.lower() for key, value in mapping.items()}


def licenses_match(actual, expected):
    if not isinstance(actual, str) or not isinstance(expected, str):
        return False
    actual, expected = actual.lower(), expected.lower()
    if actual == expected:
        return True
    aliases = license_aliases()
    return aliases.get(actual, actual) == aliases.get(expected, expected)


class Client:
    def __init__(self, token):
        require(bool(token), "ZENODO_SANDBOX_TOKEN is required")
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, url, data=None, content_type="application/json"):
        parsed = urlsplit(url)
        require(
            parsed.scheme == "https"
            and parsed.netloc == "sandbox.zenodo.org"
            and parsed.path.startswith("/api/"),
            "Refusing request outside Zenodo Sandbox API",
        )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
            "User-Agent": "ais-pipelines-zenodo/1.0",
        }
        try:
            with self.opener.open(
                Request(url, data=data, headers=headers, method=method), timeout=60
            ) as response:
                body = response.read()
        except HTTPError as exc:
            raise ZenodoError(f"Zenodo {method} failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise ZenodoError(f"Zenodo {method} failed: {exc.reason}") from exc
        return json.loads(body) if body else None

    def json(self, method, url, body=None):
        data = json.dumps(body).encode() if body is not None else None
        return self.request(method, url, data)

    def deposits(self):
        result = []
        page = 1
        while True:
            items = self.json(
                "GET",
                f"{API}/deposit/depositions?size=100&all_versions=1&page={page}",
            )
            require(isinstance(items, list), "Invalid Zenodo deposition listing")
            result.extend(items)
            if len(items) < 100:
                return result
            page += 1


class SpecLoader(yaml.SafeLoader):
    pass


SpecLoader.add_constructor(
    "!join", lambda loader, node: "".join(map(str, loader.construct_sequence(node)))
)


def load_spec_metadata(spec, spec_dir):
    spec_name(spec)
    path = (Path(spec_dir) / f"{spec}.yaml").resolve()
    require(
        path.is_relative_to(Path(spec_dir).resolve()) and path.is_file(),
        f"{spec}: pipeline spec not found within spec directory",
    )
    content = path.read_bytes()
    try:
        data = yaml.load(content, Loader=SpecLoader)
    except yaml.YAMLError as exc:
        raise ZenodoError(f"{spec}: invalid YAML: {exc}") from exc
    require(isinstance(data, dict), f"{spec}: spec must be a mapping")
    for key in ("title", "version", "license"):
        require(
            isinstance(data.get(key), str) and data[key].strip(),
            f"{spec}: missing {key}",
        )
    require(
        bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", data["license"])),
        f"{spec}: invalid license identifier",
    )
    docs = data.get("docs")
    require(
        isinstance(docs, dict)
        and isinstance(docs.get("description"), str)
        and docs["description"].strip(),
        f"{spec}: missing docs.description",
    )
    authors = data.get("authors")
    require(isinstance(authors, list) and authors, f"{spec}: missing authors")
    creators = []
    for author in authors:
        require(
            isinstance(author, dict)
            and isinstance(author.get("name"), str)
            and author["name"].strip(),
            f"{spec}: author requires a name",
        )
        creator = {"name": author["name"]}
        if author.get("affliation"):
            creator["affiliation"] = author["affliation"]
        creators.append(creator)
    return content, data, creators


def validate_selected_specs(selected_specs, spec_dir):
    specs = Path(selected_specs).read_text().splitlines()
    require(bool(specs), "No pipeline specs were selected")
    errors = []
    for spec in specs:
        try:
            load_spec_metadata(spec, spec_dir)
        except ZenodoError as exc:
            errors.append(str(exc))
    require(not errors, "Invalid release metadata:\n" + "\n".join(errors))
    print(f"Validated Zenodo metadata for {len(specs)} selected pipelines")


def build_metadata(entry, repository, commit, spec_dir):
    repository_name(repository)
    commit_sha(commit)
    spec = spec_name(entry["spec"])
    require(entry["id"] == spec.replace("/", "."), "Pipeline ID mismatch")
    require(
        re.fullmatch(r"ghcr\.io/\S+@sha256:[0-9a-f]{64}", entry["image"]),
        "Pipeline image must be digest-pinned",
    )
    content, data, creators = load_spec_metadata(spec, spec_dir)
    require(data["version"] == entry["version"], f"{spec}: version mismatch")
    marker = f"ais-pipeline:{repository.lower()}:{entry['id']}"
    source_url = f"https://github.com/{repository}/blob/{commit}/specs/australian-imaging-service/{spec}.yaml"
    manifest = {
        "pipeline_id": entry["id"],
        "version": entry["version"],
        "source_commit": commit,
        "spec_url": source_url,
        "image": entry["image"],
        "spec_sha256": hashlib.sha256(content).hexdigest(),
    }
    description = (
        f"<p>{html.escape(data['docs']['description'].strip())}</p>"
        f'<p>Source: <a href="{html.escape(source_url, quote=True)}">'
        f"pipeline specification</a>. Image: <code>{html.escape(entry['image'])}</code>.</p>"
    )
    metadata = {
        "title": data["title"],
        "upload_type": "software",
        "description": description,
        "creators": creators,
        "version": entry["version"],
        "access_right": "open",
        "license": data["license"],
        "keywords": [marker],
        "prereserve_doi": True,
        "related_identifiers": [
            {"identifier": source_url, "relation": "isDocumentedBy"}
        ],
    }
    files = {
        "pipeline-spec.yaml": content,
        "release-metadata.json": (
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        ).encode(),
    }
    return marker, metadata, files


def find_deposit(client, marker, version):
    records = [
        d
        for d in client.deposits()
        if marker in d.get("metadata", {}).get("keywords", [])
    ]
    concepts = {str(d["conceptrecid"]) for d in records}
    require(len(concepts) <= 1, f"Multiple Zenodo records match {marker}")
    matches = [d for d in records if d.get("metadata", {}).get("version") == version]
    require(
        len(matches) <= 1, f"Multiple Zenodo deposits match {marker} version {version}"
    )
    return records, matches[0] if matches else None


def latest_record(records, marker):
    try:
        ordered = sorted(
            records,
            key=lambda d: datetime.fromisoformat(d["created"].replace("Z", "+00:00")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ZenodoError(f"Cannot determine latest version for {marker}") from exc
    require(
        ordered
        and (len(ordered) == 1 or ordered[-1]["created"] != ordered[-2]["created"]),
        f"Ambiguous latest version for {marker}",
    )
    return ordered[-1]


def prepare(client, entry, repository, commit, spec_dir):
    marker, metadata, files = build_metadata(entry, repository, commit, spec_dir)
    records, deposit = find_deposit(client, marker, entry["version"])
    if deposit and deposit["submitted"]:
        verify_files(client, deposit, files)
        return deposit
    new_version = False
    if deposit is None:
        drafts = [d for d in records if not d["submitted"]]
        require(not drafts, f"Another draft exists for {marker}; resolve it first")
        if records:
            new_version = True
            latest = latest_record(records, marker)
            response = client.json(
                "POST",
                f"{API}/deposit/depositions/{latest['id']}/actions/newversion",
            )
            deposit = client.json("GET", response["links"]["latest_draft"])
            deposit = client.json(
                "PUT",
                f"{API}/deposit/depositions/{deposit['id']}",
                {"metadata": metadata},
            )
        else:
            deposit = client.json(
                "POST", f"{API}/deposit/depositions", {"metadata": metadata}
            )
    else:
        comparable = ("title", "version", "upload_type", "description")
        creators = deposit["metadata"].get("creators", [])
        actual_license = deposit["metadata"].get("license")
        expected_license = metadata["license"]
        require(
            all(deposit["metadata"].get(key) == metadata[key] for key in comparable)
            and licenses_match(actual_license, expected_license)
            and marker in deposit["metadata"].get("keywords", [])
            and len(creators) == len(metadata["creators"])
            and all(
                all(actual.get(key) == value for key, value in expected.items())
                for actual, expected in zip(creators, metadata["creators"])
            ),
            f"Existing draft metadata differs for {marker} version {entry['version']}",
        )
    existing = client.json("GET", f"{API}/deposit/depositions/{deposit['id']}/files")
    prior_files = None
    for item in existing:
        name = item.get("filename") or item.get("key")
        require(name in files, f"Unexpected file in Zenodo draft: {name}")
        if item.get("checksum") not in (
            hashlib.md5(files[name]).hexdigest(),
            "md5:" + hashlib.md5(files[name]).hexdigest(),
        ):
            if not new_version and prior_files is None:
                published = [record for record in records if record["submitted"]]
                if published:
                    prior = latest_record(published, marker)
                    prior_files = client.json(
                        "GET", f"{API}/deposit/depositions/{prior['id']}/files"
                    )
                else:
                    prior_files = []
            inherited = any(
                (prior.get("filename") or prior.get("key")) == name
                and prior.get("checksum", "").removeprefix("md5:")
                == item.get("checksum", "").removeprefix("md5:")
                for prior in (prior_files or [])
            )
            require(new_version or inherited, f"Existing draft file differs: {name}")
            client.request(
                "DELETE",
                f"{API}/deposit/depositions/{deposit['id']}/files/{item['id']}",
            )
    existing = client.json("GET", f"{API}/deposit/depositions/{deposit['id']}/files")
    names = {item.get("filename") or item.get("key") for item in existing}
    for name, content in files.items():
        if name not in names:
            client.request(
                "PUT",
                deposit["links"]["bucket"] + "/" + quote(name),
                content,
                "application/octet-stream",
            )
    verify_files(client, deposit, files)
    return deposit


def verify_files(client, deposit, files):
    actual = client.json("GET", f"{API}/deposit/depositions/{deposit['id']}/files")
    require(len(actual) == len(files), "Zenodo deposit files differ from expected")
    for item in actual:
        name = item.get("filename") or item.get("key")
        require(name in files, "Unexpected file in Zenodo deposit")
        digest = hashlib.md5(files[name]).hexdigest()
        require(
            item.get("checksum") in (digest, "md5:" + digest),
            f"Zenodo file checksum mismatch: {name}",
        )


def process(args):
    if args.action == "validate-specs":
        validate_selected_specs(args.selected_specs, args.spec_dir)
        return
    client = Client(os.environ.get("ZENODO_SANDBOX_TOKEN"))
    if args.action == "validate":
        inventory = json.loads(Path(args.inventory).read_text())
        for item in inventory["pipelines"]:
            entry = dict(item)
            entry["image"] = item["image_tag"].rsplit(":", 1)[0] + "@sha256:" + "0" * 64
            build_metadata(entry, args.repository, args.commit, args.spec_dir)
        print(f"Validated Zenodo metadata for {len(inventory['pipelines'])} pipelines")
        return
    if args.action == "prepare-entry":
        require(bool(args.entry), "Entry file is required")
        entry = json.loads(Path(args.entry).read_text())
        deposit = prepare(client, entry, args.repository, args.commit, args.spec_dir)
        print(f"{entry['id']} {entry['version']}: Zenodo Sandbox draft {deposit['id']}")
        return
    require(
        bool(args.catalogue and args.previous),
        "Catalogue and previous directory are required",
    )
    catalogue = json.loads(Path(args.catalogue).read_text())
    previous_path = Path(args.previous) / "pipeline-release.json"
    previous = json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    old = {item["id"]: item["version"] for item in previous.get("pipelines", [])}
    for entry in catalogue["pipelines"]:
        if old.get(entry["id"]) == entry["version"]:
            continue
        deposit = prepare(client, entry, args.repository, args.commit, args.spec_dir)
        if args.action == "publish" and not deposit["submitted"]:
            deposit = client.json(
                "POST", f"{API}/deposit/depositions/{deposit['id']}/actions/publish"
            )
        if args.action == "publish":
            require(
                deposit.get("submitted") is True,
                f"Zenodo has not confirmed publication for {entry['id']}; rerun the release",
            )
            doi = deposit.get("doi") or deposit.get("metadata", {}).get(
                "prereserve_doi", {}
            ).get("doi")
            require(
                isinstance(doi, str) and doi.startswith("10.5072/"),
                f"Sandbox did not return a test DOI for {entry['id']}",
            )
            print(
                f"{entry['id']} {entry['version']}: {doi} (Sandbox test DOI), "
                f"https://sandbox.zenodo.org/records/{deposit['id']}"
            )
        else:
            print(
                f"{entry['id']} {entry['version']}: Zenodo Sandbox draft {deposit['id']}"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["validate-specs", "validate", "prepare-entry", "prepare", "publish"],
    )
    parser.add_argument("--selected-specs")
    parser.add_argument("--entry")
    parser.add_argument("--inventory")
    parser.add_argument("--catalogue")
    parser.add_argument("--previous")
    parser.add_argument("--repository")
    parser.add_argument("--commit")
    parser.add_argument("--spec-dir", required=True)
    args = parser.parse_args()
    if args.action == "validate-specs":
        if not args.selected_specs:
            parser.error("validate-specs requires --selected-specs")
    elif not (args.repository and args.commit):
        parser.error(f"{args.action} requires --repository and --commit")
    try:
        process(args)
    except ZenodoError as exc:
        print(f"Zenodo Sandbox: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
