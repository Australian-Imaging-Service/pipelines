"""Build and publish immutable, complete pipeline release assets.

Only ``inventory`` imports Pydra. All other commands need Python and jsonschema,
with authenticated gh/docker CLIs for registry and release operations.
"""

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import jsonschema

CATALOGUE = "pipeline-release.json"
SCHEMA = (
    Path(__file__).resolve().parents[1] / "schemas" / "pipeline-release.schema.json"
)
SEGMENT = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
IMAGE_TAG = re.compile(
    r"ghcr\.io/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
    r"(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*"
    r":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"
)
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class CatalogueError(ValueError):
    """An invalid or incomplete release must not be published."""


def require(condition, message):
    if not condition:
        raise CatalogueError(message)


def text(value, label, maximum=512):
    require(
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and not re.search(r"[\x00-\x20\x7f]", value),
        f"Invalid {label}: expected a bounded string without whitespace/control characters",
    )
    return value


def spec_name(value):
    text(value, "spec")
    require(
        bool(re.fullmatch(SEGMENT + r"(?:/" + SEGMENT + r")*", value)),
        "Unsafe spec path",
    )
    require(
        not value.endswith((".yaml", ".yml")),
        "Spec must be a relative extensionless path",
    )
    return value


def command_name(value):
    text(value, "command name", 128)
    require(bool(re.fullmatch(SEGMENT, value)), "Unsafe command name")
    return value


def repository_name(value):
    text(value, "repository", 201)
    require(
        bool(
            re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}",
                value,
            )
        ),
        "Repository must be owner/repo",
    )
    return value


def tag_name(value):
    text(value, "release tag")
    require(
        not value.startswith(("-", "/"))
        and not value.endswith(("/", ".", ".lock"))
        and not re.search(r"[~^:?*\[\\]|\.\.|@\{|//", value),
        "Unsafe release tag",
    )
    return value


def commit_sha(value):
    require(
        isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value)),
        "Expected full commit SHA",
    )
    return value


def image_tag(value):
    text(value, "image tag")
    require(bool(IMAGE_TAG.fullmatch(value)), "Expected an explicit ghcr.io image tag")
    return value


def image_repository(value):
    return image_tag(value).rsplit(":", 1)[0]


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode()


def no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode_json(data):
    try:
        return json.loads(
            data,
            object_pairs_hook=no_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CatalogueError(f"Invalid JSON constant: {value}")
            ),
        )
    except (ValueError, UnicodeError) as exc:
        raise CatalogueError(f"Invalid JSON: {exc}") from exc


def read_json(path):
    require(
        Path(path).is_file() and not Path(path).is_symlink(),
        f"Missing or unsafe JSON file: {path}",
    )
    return decode_json(Path(path).read_bytes())


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(json_bytes(value))


def run(*args):
    try:
        return subprocess.run(
            list(args), check=True, capture_output=True, text=True
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise CatalogueError(
            f"{args[0]} {args[1]} failed (exit {exc.returncode}): {exc.stderr or exc.stdout}"
        ) from exc


def plan_file(path):
    plan = read_json(path)
    require(
        isinstance(plan, dict) and set(plan) == {"build", "unchanged"},
        "Plan needs exactly build and unchanged",
    )
    for group in plan.values():
        require(
            isinstance(group, list) and len(group) <= 10000,
            "Plan selections must be bounded arrays",
        )
        for spec in group:
            spec_name(spec)
        require(len(group) == len(set(group)), "Duplicate plan spec")
    require(
        not set(plan["build"]) & set(plan["unchanged"]),
        "Build and unchanged selections overlap",
    )
    return {key: sorted(value) for key, value in plan.items()}


def validate_inventory(value):
    require(
        isinstance(value, dict) and set(value) == {"schema_version", "pipelines"},
        "Invalid inventory shape",
    )
    require(value["schema_version"] == "1.0", "Unsupported inventory schema version")
    pipelines = value["pipelines"]
    require(
        isinstance(pipelines, list) and len(pipelines) <= 10000,
        "Invalid inventory pipelines",
    )
    ids, specs, images = set(), set(), set()
    for item in pipelines:
        require(
            isinstance(item, dict)
            and set(item) == {"spec", "id", "version", "image_tag", "commands"},
            "Invalid inventory pipeline shape",
        )
        spec_name(item["spec"])
        require(
            item["id"] == item["spec"].replace("/", "."),
            "Pipeline ID must be dotted spec path",
        )
        text(item["version"], "version")
        image_tag(item["image_tag"])
        names = item["commands"]
        require(
            isinstance(names, list) and 0 < len(names) <= 1000, "Invalid command list"
        )
        for name in names:
            command_name(name)
        require(len(names) == len(set(names)), "Duplicate command names")
        for key, seen in (("id", ids), ("spec", specs), ("image_tag", images)):
            require(item[key] not in seen, f"Duplicate inventory {key}: {item[key]}")
            seen.add(item[key])
    return value


def load_app(path, root_dir):
    from frametree.core.serialize import ClassResolver
    from pydra2app.xnat import XnatApp

    with ClassResolver.FALLBACK_TO_STR:
        return XnatApp.load(path, root_dir=root_dir, registry="ghcr.io")


def inventory(args):
    plan = plan_file(args.plan)
    root, directory = Path(args.spec_root).resolve(), Path(args.spec_dir).resolve()
    require(directory.is_relative_to(root), "Spec directory must be within spec root")
    items = []
    for spec in sorted(plan["build"] + plan["unchanged"]):
        path = directory / (spec + ".yaml")
        require(path.resolve().is_relative_to(directory), f"Spec escapes root: {spec}")
        require(path.is_file(), f"Missing spec: {spec}")
        app = load_app(path, root_dir=root)
        commands = app.commands
        names: list[str]
        if isinstance(commands, dict):
            names = [str(name) for name in commands]
        else:
            names = [
                str(command) if isinstance(command, str) else str(command.name)
                for command in commands
            ]
        items.append(
            {
                "spec": spec,
                "id": spec.replace("/", "."),
                "version": str(app.version),
                "image_tag": app.reference,
                "commands": sorted(names),
            }
        )
    write_json(
        args.output, validate_inventory({"schema_version": "1.0", "pipelines": items})
    )


def selected(inventory_path, spec):
    spec_name(spec)
    items = validate_inventory(read_json(inventory_path))["pipelines"]
    found = [item for item in items if item["spec"] == spec]
    require(len(found) == 1, f"Spec not in inventory: {spec}")
    return found[0]


def image_env(args):
    item = selected(args.inventory, args.spec)
    artifact_id = hashlib.sha256(item["id"].encode()).hexdigest()[:24]
    command_names = json.dumps(sorted(item["commands"]), separators=(",", ":"))
    with Path(args.output).open("a") as stream:
        stream.write(
            f"IMAGE_TAG={item['image_tag']}\nPIPELINE_ID={artifact_id}\n"
            f"COMMAND_NAMES_JSON={command_names}\n"
        )


def inspect_image(tag):
    # Buildx exposes the remote manifest descriptor (including an index digest).
    descriptor = decode_json(
        run(
            "docker",
            "buildx",
            "imagetools",
            "inspect",
            tag,
            "--format",
            "{{json .Manifest}}",
        )
    )
    require(
        isinstance(descriptor, dict), "Registry returned an invalid manifest descriptor"
    )
    digest = descriptor.get("digest")
    require(
        isinstance(digest, str) and bool(DIGEST.fullmatch(digest)),
        "Registry returned an invalid sha256 digest",
    )
    return image_repository(tag) + "@" + digest


def verify_local_image(tag, pinned):
    digests = decode_json(
        run("docker", "image", "inspect", tag, "--format", "{{json .RepoDigests}}")
    )
    require(
        isinstance(digests, list)
        and all(isinstance(digest, str) for digest in digests),
        "Docker returned invalid local image RepoDigests",
    )
    require(
        pinned in digests,
        "Registry digest does not match the locally pushed image; "
        "the tag may have been retargeted or the image was not pushed",
    )


def asset_name(pipeline_id, name):
    return (
        "command-"
        + hashlib.sha256((pipeline_id + "\0" + name).encode()).hexdigest()
        + ".json"
    )


def command_document(path, item, name, pinned, allow_tag=False):
    value = read_json(path)
    require(isinstance(value, dict), f"Command must be a JSON object: {path}")
    allowed = {pinned, item["image_tag"]} if allow_tag else {pinned}
    require(
        isinstance(value.get("image"), str) and value["image"] in allowed,
        f"Command image mismatch: {path}",
    )
    runtime_name = value.get("name")
    text(runtime_name, "runtime command name", 1024)
    require(
        runtime_name == name or runtime_name.endswith("." + name),
        f"Command runtime name does not match {name}",
    )
    return value


def materialize(item, commands_dir, output_dir, pinned=None):
    pinned = pinned or inspect_image(item["image_tag"])
    entry = {key: value for key, value in item.items() if key != "commands"}
    entry.update(image=pinned, commands=[])
    names = {f"{name}.json" for name in item["commands"]}
    require(
        {path.name for path in Path(commands_dir).iterdir()} == names,
        f"Missing or unexpected command files for {item['spec']}",
    )
    for name in sorted(item["commands"]):
        value = command_document(
            Path(commands_dir) / f"{name}.json", item, name, pinned, allow_tag=True
        )
        value["image"] = pinned
        data = json_bytes(value)
        asset = asset_name(item["id"], name)
        (output_dir / asset).write_bytes(data)
        entry["commands"].append(
            {"name": name, "path": asset, "sha256": hashlib.sha256(data).hexdigest()}
        )
    return entry


def install_directory(staged, destination):
    destination = Path(destination)
    if destination.exists():
        require(
            destination.is_dir() and not destination.is_symlink(),
            "Unsafe output directory",
        )
        existing = {path.name for path in destination.iterdir()}
        expected = {path.name for path in staged.iterdir()}
        if existing:
            require(
                existing == expected,
                f"Output directory is not empty or an identical retry: {destination}",
            )
            for name in expected:
                require(
                    (destination / name).is_file()
                    and not (destination / name).is_symlink()
                    and (destination / name).read_bytes()
                    == (staged / name).read_bytes(),
                    f"Output differs from existing file: {name}",
                )
            return
        destination.rmdir()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged.replace(destination)


def workspace(destination):
    # Explicit local parent: never use the OS temporary directory.
    parent = Path(destination).absolute().parent
    parent.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=".release-catalogue-", dir=parent)


def record(args):
    item = selected(args.inventory, args.spec)
    pinned = inspect_image(item["image_tag"])
    verify_local_image(item["image_tag"], pinned)
    with workspace(args.output_dir) as temporary:
        staged = Path(temporary)
        entry = materialize(item, args.commands_dir, staged, pinned=pinned)
        write_json(staged / "entry.json", entry)
        install_directory(staged, args.output_dir)


def asset_url(repository, tag, name):
    return f"https://github.com/{repository}/releases/download/{quote(tag, safe='')}/{quote(name, safe='')}"


def validate_catalogue(value, directory, repository=None, tag=None, commit=None):
    try:
        jsonschema.Draft202012Validator(read_json(SCHEMA)).validate(value)
    except jsonschema.ValidationError as exc:
        raise CatalogueError(f"Invalid catalogue schema: {exc.message}") from exc
    source = value["source"]
    repository_name(source["repository"])
    tag_name(value["release"]["tag"])
    if repository is not None:
        require(source["repository"] == repository, "Catalogue repository mismatch")
    if tag is not None:
        require(value["release"]["tag"] == tag, "Catalogue release tag mismatch")
    if commit is not None:
        require(source["commit"] == commit, "Catalogue source commit mismatch")
    inventory_value = {
        "schema_version": "1.0",
        "pipelines": [
            {
                **{key: item[key] for key in ("id", "spec", "version", "image_tag")},
                "commands": [command["name"] for command in item["commands"]],
            }
            for item in value["pipelines"]
        ],
    }
    validate_inventory(inventory_value)
    paths, runtime_names = set(), set()
    for item in value["pipelines"]:
        require(
            item["image"].startswith(image_repository(item["image_tag"]) + "@")
            and bool(DIGEST.fullmatch(item["image"].split("@")[-1])),
            "Pinned image repository/digest mismatch",
        )
        for command in item["commands"]:
            name, asset = command["name"], command["path"]
            require(
                asset == asset_name(item["id"], name) and asset not in paths,
                "Invalid or duplicate command asset path",
            )
            paths.add(asset)
            require(
                command["url"]
                == asset_url(source["repository"], value["release"]["tag"], asset),
                "Command URL provenance mismatch",
            )
            if directory is not None:
                path = Path(directory) / asset
                document = command_document(path, item, name, item["image"])
                require(
                    hashlib.sha256(path.read_bytes()).hexdigest() == command["sha256"],
                    f"Command checksum mismatch: {asset}",
                )
                require(
                    document["name"] not in runtime_names,
                    "Duplicate runtime command name",
                )
                runtime_names.add(document["name"])
    return paths


def release_list(repository):
    result = decode_json(
        run(
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{repository}/releases?per_page=100",
        )
    )
    require(
        isinstance(result, list) and all(isinstance(page, list) for page in result),
        "Malformed releases response",
    )
    releases = [release for page in result for release in page]
    for release in releases:
        require(
            isinstance(release, dict)
            and isinstance(release.get("tag_name"), str)
            and type(release.get("draft")) is bool
            and type(release.get("prerelease")) is bool
            and isinstance(release.get("assets"), list),
            "Malformed release record",
        )
        for asset in release["assets"]:
            require(
                isinstance(asset, dict) and isinstance(asset.get("name"), str),
                "Malformed release asset",
            )
        tag_name(release["tag_name"])
        if not release["draft"]:
            require(
                isinstance(release.get("published_at"), str)
                and release["published_at"],
                "Missing release publication date",
            )
            try:
                published_at = datetime.fromisoformat(release["published_at"])
                require(
                    published_at.tzinfo is not None,
                    "Release publication date must have a timezone",
                )
            except ValueError as exc:
                raise CatalogueError("Malformed release publication date") from exc
    return releases


def download(repository, tag, name, directory):
    run(
        "gh",
        "release",
        "download",
        tag,
        "--repo",
        repository,
        "--pattern",
        name,
        "--dir",
        str(directory),
    )
    require(
        (Path(directory) / name).is_file(), f"Release did not provide asset: {name}"
    )


def previous(args):
    repository, tag = repository_name(args.repository), tag_name(args.tag)
    candidates = [
        release
        for release in release_list(repository)
        if not release["draft"]
        and not release["prerelease"]
        and release["tag_name"] != tag
        and any(asset["name"] == CATALOGUE for asset in release["assets"])
    ]
    with workspace(args.output_dir) as temporary:
        staged = Path(temporary)
        if candidates:
            release = max(
                candidates, key=lambda item: (item["published_at"], item["tag_name"])
            )
            previous_tag = tag_name(release["tag_name"])
            download(repository, previous_tag, CATALOGUE, staged)
            catalogue = read_json(staged / CATALOGUE)
            paths = validate_catalogue(catalogue, None, repository, previous_tag)
            available = [asset["name"] for asset in release["assets"]]
            require(len(available) == len(set(available)), "Duplicate release assets")
            require(
                paths <= set(available), "Previous release is missing command assets"
            )
            for name in sorted(paths):
                download(repository, previous_tag, name, staged)
            validate_catalogue(catalogue, staged, repository, previous_tag)
        install_directory(staged, args.output_dir)


def validate_entry(entry, item, directory):
    require(isinstance(entry, dict), "Built entry must be an object")
    for key in ("spec", "id", "version", "image_tag"):
        require(entry.get(key) == item[key], f"Entry {key} mismatch for {item['spec']}")
    require(
        isinstance(entry.get("commands"), list)
        and all(
            isinstance(command, dict) and set(command) == {"name", "path", "sha256"}
            for command in entry["commands"]
        ),
        f"Invalid built entry commands for {item['spec']}",
    )
    require(
        all(isinstance(command["name"], str) for command in entry["commands"])
        and sorted(command["name"] for command in entry["commands"])
        == sorted(item["commands"]),
        f"Entry command selection mismatch for {item['spec']}",
    )
    candidate = copy.deepcopy(entry)
    for command in candidate["commands"]:
        require("url" not in command, "Built entry must not contain release URLs")
        command["url"] = asset_url(
            "validation/validation", "validation", command.get("path", "")
        )
    validate_catalogue(
        {
            "schema_version": "1.0",
            "release": {"tag": "validation"},
            "source": {"repository": "validation/validation", "commit": "0" * 40},
            "pipelines": [candidate],
        },
        directory,
    )
    return entry


def bootstrap(item, destination):
    pinned = inspect_image(item["image_tag"])
    run("docker", "pull", pinned)
    container = run("docker", "create", "--entrypoint", "/bin/true", pinned)
    require(
        bool(re.fullmatch(r"[0-9a-f]{12,64}", container)),
        "Docker returned an invalid container ID",
    )
    try:
        with workspace(destination / "commands") as temporary:
            commands = Path(temporary)
            for name in sorted(item["commands"]):
                run(
                    "docker",
                    "cp",
                    f"{container}:/xnat_commands/{name}.json",
                    str(commands / f"{name}.json"),
                )
            return materialize(item, commands, destination, pinned=pinned)
    finally:
        run("docker", "rm", container)


def assemble(args):
    repository, tag, commit = (
        repository_name(args.repository),
        tag_name(args.tag),
        commit_sha(args.commit),
    )
    plan = plan_file(args.plan)
    items = validate_inventory(read_json(args.inventory))["pipelines"]
    by_spec = {item["spec"]: item for item in items}
    require(
        set(by_spec) == set(plan["build"] + plan["unchanged"]),
        "Inventory and plan selection differ",
    )
    prior_path = Path(args.previous_dir) / CATALOGUE
    prior = read_json(prior_path) if prior_path.exists() else None
    previous_entries = {}
    if prior is not None:
        validate_catalogue(prior, args.previous_dir, repository)
        require(
            prior["release"]["tag"] != tag,
            "Previous catalogue cannot be current release",
        )
        previous_entries = {item["id"]: item for item in prior["pipelines"]}
    else:
        require(
            Path(args.previous_dir).is_dir(),
            "Missing previous directory: run previous first",
        )
        require(
            not any(Path(args.previous_dir).iterdir()),
            "Previous directory lacks its catalogue",
        )
    built = {}
    for path in sorted(Path(args.entries_dir).rglob("entry.json")):
        entry = read_json(path)
        require(
            isinstance(entry, dict) and entry.get("spec") in plan["build"],
            "Unexpected built entry",
        )
        spec = entry["spec"]
        require(spec not in built, f"Duplicate built entry: {spec}")
        validate_entry(entry, by_spec[spec], path.parent)
        built[spec] = (entry, path.parent)
    require(
        set(built) == set(plan["build"]),
        "Missing built entries; refusing partial release",
    )
    with workspace(args.output_dir) as temporary:
        staged = Path(temporary)
        pipelines = []
        for spec in sorted(by_spec):
            item = by_spec[spec]
            if spec in built:
                entry, source = built[spec]
                entry = copy.deepcopy(entry)
            else:
                prior_entry = previous_entries.get(item["id"])
                if (
                    prior_entry is not None
                    and prior_entry["version"] == item["version"]
                ):
                    require(
                        prior_entry["image_tag"] == item["image_tag"],
                        f"Previous image tag mismatch: {spec}",
                    )
                matches = False
                if prior_entry is not None:
                    matches = all(
                        prior_entry[key] == item[key]
                        for key in ("id", "spec", "version", "image_tag")
                    ) and sorted(
                        command["name"] for command in prior_entry["commands"]
                    ) == sorted(
                        item["commands"]
                    )
                if matches and prior_entry is not None:
                    require(
                        inspect_image(item["image_tag"]) == prior_entry["image"],
                        f"Image tag was retargeted: {spec}",
                    )
                    entry, source = copy.deepcopy(prior_entry), Path(args.previous_dir)
                else:
                    entry, source = bootstrap(item, staged), staged
            for command in entry["commands"]:
                if source != staged:
                    shutil.copyfile(source / command["path"], staged / command["path"])
                command["url"] = asset_url(repository, tag, command["path"])
            pipelines.append(entry)
        value = {
            "schema_version": "1.0",
            "release": {"tag": tag},
            "source": {"repository": repository, "commit": commit},
            "pipelines": sorted(pipelines, key=lambda item: item["id"]),
        }
        if prior is not None:
            value["previous_release"] = {
                "tag": prior["release"]["tag"],
                "commit": prior["source"]["commit"],
            }
        validate_catalogue(value, staged, repository, tag, commit)
        write_json(staged / CATALOGUE, value)
        install_directory(staged, args.output_dir)


def release_lookup(repository, tag):
    release_id = None
    try:
        output = subprocess.run(
            ["gh", "api", f"repos/{repository}/releases/tags/{quote(tag, safe='')}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        if not re.search(r"\(HTTP 404\)", exc.stderr or ""):
            raise CatalogueError(
                f"Release lookup failed: {exc.stderr or exc.stdout}"
            ) from exc
        # The tag endpoint excludes drafts; authenticated listing includes them.
        matches = [
            release
            for release in release_list(repository)
            if release["tag_name"] == tag
        ]
        require(len(matches) <= 1, "Ambiguous releases with the same tag")
        if not matches:
            return None
        release_id = matches[0].get("id")
        require(type(release_id) is int and release_id > 0, "Invalid release ID")
        output = run("gh", "api", f"repos/{repository}/releases/{release_id}")
    value = decode_json(output)
    require(
        isinstance(value, dict)
        and value.get("tag_name") == tag
        and type(value.get("draft")) is bool
        and type(value.get("prerelease")) is bool
        and isinstance(value.get("assets"), list),
        "Malformed release lookup response",
    )
    if release_id is not None:
        require(value.get("id") == release_id, "Release ID changed during lookup")
    return value


def verify_tag_commit(repository, tag, commit):
    reference = decode_json(
        run("gh", "api", f"repos/{repository}/git/ref/tags/{quote(tag, safe='')}")
    )
    for _ in range(10):
        require(
            isinstance(reference, dict) and isinstance(reference.get("object"), dict),
            "Malformed Git tag reference",
        )
        obj = reference["object"]
        sha = commit_sha(obj.get("sha"))
        if obj.get("type") == "commit":
            require(
                sha == commit,
                "Release tag does not point to the catalogue source commit",
            )
            return
        require(obj.get("type") == "tag", "Release tag must resolve to a commit")
        reference = decode_json(run("gh", "api", f"repos/{repository}/git/tags/{sha}"))
    raise CatalogueError("Release tag annotation chain is too deep")


def verify_release_assets(
    repository, tag, release, expected, assets_dir, scratch_parent
):
    names = []
    for asset in release["assets"]:
        require(
            isinstance(asset, dict) and isinstance(asset.get("name"), str),
            "Malformed release asset",
        )
        names.append(asset["name"])
    require(len(names) == len(set(names)), "Duplicate release assets")
    managed = {
        name for name in names if name == CATALOGUE or name.startswith("command-")
    }
    require(managed == expected, "Release catalogue assets are missing or unexpected")
    with workspace(scratch_parent / "verification") as temporary:
        staged = Path(temporary)
        for name in sorted(expected):
            download(repository, tag, name, staged)
            require(
                (staged / name).read_bytes() == (assets_dir / name).read_bytes(),
                f"Published asset differs: {name}",
            )


def publish(args):
    repository, tag, commit = (
        repository_name(args.repository),
        tag_name(args.tag),
        commit_sha(args.commit),
    )
    directory = Path(args.assets_dir)
    catalogue = read_json(directory / CATALOGUE)
    expected = validate_catalogue(catalogue, directory, repository, tag, commit) | {
        CATALOGUE
    }
    require(
        {path.name for path in directory.iterdir()} == expected,
        "Unexpected files in release assets directory",
    )
    verify_tag_commit(repository, tag, commit)
    release = release_lookup(repository, tag)
    if release is not None:
        require(not release["prerelease"], "Prereleases are not supported")
        if not release["draft"]:
            verify_release_assets(
                repository, tag, release, expected, directory, directory.parent
            )
            return
        require(
            release.get("target_commitish") == commit,
            "Draft target commit mismatch; refusing to take over draft",
        )
        names = [
            asset.get("name") for asset in release["assets"] if isinstance(asset, dict)
        ]
        managed = {
            name
            for name in names
            if isinstance(name, str)
            and (name == CATALOGUE or name.startswith("command-"))
        }
        require(managed <= expected, "Draft contains unexpected catalogue assets")
        if CATALOGUE in names:
            with workspace(directory.parent / "draft-check") as temporary:
                download(repository, tag, CATALOGUE, temporary)
                existing = read_json(Path(temporary) / CATALOGUE)
                validate_catalogue(existing, None, repository, tag, commit)
                require(
                    existing == catalogue,
                    "Existing draft catalogue differs; refusing to overwrite",
                )
    else:
        run(
            "gh",
            "release",
            "create",
            tag,
            "--repo",
            repository,
            "--draft",
            "--verify-tag",
            "--target",
            commit,
            "--title",
            tag,
        )
    # Upload commands first; the catalogue acts as the draft's complete manifest.
    for name in sorted(expected - {CATALOGUE}) + [CATALOGUE]:
        run(
            "gh",
            "release",
            "upload",
            tag,
            str(directory / name),
            "--repo",
            repository,
            "--clobber",
        )
    release = release_lookup(repository, tag)
    if release is None:
        raise CatalogueError("Release disappeared during draft publication")
    require(
        release["draft"] and not release["prerelease"],
        "Release is no longer a stable draft",
    )
    require(
        release.get("target_commitish") == commit, "Draft target changed during upload"
    )
    verify_release_assets(
        repository, tag, release, expected, directory, directory.parent
    )
    run("gh", "release", "edit", tag, "--repo", repository, "--draft=false", "--latest")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    options = {
        "inventory": ["plan", "spec-root", "spec-dir", "output"],
        "image-env": ["inventory", "spec", "output"],
        "record": ["inventory", "spec", "commands-dir", "output-dir"],
        "previous": ["repository", "tag", "output-dir"],
        "assemble": [
            "inventory",
            "plan",
            "entries-dir",
            "previous-dir",
            "repository",
            "tag",
            "commit",
            "output-dir",
        ],
        "publish": ["repository", "tag", "commit", "assets-dir"],
    }
    handlers = {
        "inventory": inventory,
        "image-env": image_env,
        "record": record,
        "previous": previous,
        "assemble": assemble,
        "publish": publish,
    }
    for name, flags in options.items():
        command = commands.add_parser(name)
        for flag in flags:
            command.add_argument("--" + flag, required=True)
        command.set_defaults(handler=handlers[name])
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        args.handler(args)
    except (CatalogueError, OSError) as exc:
        print(f"release-catalogue: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
