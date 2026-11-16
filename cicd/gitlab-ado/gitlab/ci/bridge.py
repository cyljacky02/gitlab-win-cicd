#!/usr/bin/env python3
"""Linux GitLab jobs: package bytes or queue the Windows ADO importer.

Standard library only; Python >= 3.9. No PowerShell, jq, curl, or zip executable.
The management-side ADO verifier remains PowerShell on Windows VM1.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile


class BridgeError(Exception):
    pass


def positive_id(value, name):
    value = str(value)
    if not re.fullmatch(r"[1-9][0-9]{0,17}", value):
        raise BridgeError(f"Invalid {name}; expected a positive decimal ID.")
    return value


def full_sha(value):
    if not re.fullmatch(r"[a-fA-F0-9]{40}", value):
        raise BridgeError("Expected a full 40-character Git commit SHA.")
    return value.lower()


def required(env, name):
    value = env.get(name, "")
    if not value:
        raise BridgeError(f"Missing {name}.")
    return value


def ci_identity(env):
    ids = {name: positive_id(required(env, name), name) for name in (
        "CI_PROJECT_ID", "CI_PIPELINE_ID", "CI_PIPELINE_IID", "CI_JOB_ID"
    )}
    sha = full_sha(required(env, "CI_COMMIT_SHA"))
    branch = required(env, "CI_COMMIT_BRANCH")
    if env.get("CI_COMMIT_TAG"):
        raise BridgeError("Only a branch build can produce/notify a candidate.")
    return ids, sha, branch, required(env, "CI_PROJECT_PATH")


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bridge-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def package_candidate(input_directory, output_directory="out", env=None):
    env = os.environ if env is None else env
    ids, sha, branch, project_path = ci_identity(env)
    source = Path(input_directory)
    if source.is_symlink() or not source.is_dir():
        raise BridgeError("InputDirectory must be a regular directory, not a symlink.")
    source = source.resolve()
    output = Path(output_directory).resolve()
    if output == source or source in output.parents:
        raise BridgeError("OutputDirectory must be outside InputDirectory.")
    files, directories = [], []
    for root, dirnames, filenames in os.walk(source, followlinks=False):
        dirnames.sort()
        filenames.sort()
        for name in dirnames + filenames:
            path = Path(root) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise BridgeError("Symlinks and non-regular package inputs are not permitted.")
            if path.parent == source and name.casefold() == "release.json":
                raise BridgeError("Root release.json is reserved for the bridge.")
            (directories if stat.S_ISDIR(mode) else files).append(path)
    if not files:
        raise BridgeError("Package input is empty.")
    output.mkdir(parents=True, exist_ok=True)
    archive_path, manifest_path = output / "site.zip", output / "manifest.json"
    for path in (archive_path, manifest_path):
        if path.is_symlink():
            raise BridgeError("Package output must not be a symlink.")
        path.unlink(missing_ok=True)
    release_id = f"r{ids['CI_PIPELINE_IID']}-{sha[:8]}"
    marker = {
        "releaseId": release_id, "commitSha": sha,
        "projectId": int(ids["CI_PROJECT_ID"]),
        "pipelineId": int(ids["CI_PIPELINE_ID"]), "jobId": int(ids["CI_JOB_ID"]),
    }
    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in directories + files:
                archive.write(path, path.relative_to(source).as_posix())
            archive.writestr("release.json", json.dumps(marker, ensure_ascii=False))
        manifest = {
            "schema": 1, "releaseId": release_id,
            "projectId": marker["projectId"], "projectPath": project_path,
            "pipelineId": marker["pipelineId"], "jobId": marker["jobId"],
            "commitSha": sha, "ref": branch, "zipName": "site.zip",
            "zipSha256": file_sha256(archive_path), "zipBytes": archive_path.stat().st_size,
        }
        write_json(manifest_path, manifest)
    except Exception:
        archive_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
        raise
    print(f"Packaged candidate {manifest['projectId']}/{manifest['pipelineId']}/{manifest['jobId']}.")
    return manifest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_run(url, payload, token):
    # One POST, no retry and no redirects (including same-origin redirects).
    auth = base64.b64encode((":" + token).encode("utf-8")).decode("ascii")
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
        "Authorization": "Basic " + auth,
        "Content-Type": "application/json; charset=utf-8",
    })
    try:
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(request, timeout=60) as response:
            if not 200 <= response.status < 300:
                raise BridgeError("Unexpected HTTP status.")
            data = response.read(4194305)
            if len(data) > 4194304:
                raise BridgeError("Response exceeds size limit.")
            return json.loads(data.decode("utf-8"))
    except Exception:
        # Do not echo exception/response/request objects: they can contain secrets.
        raise BridgeError("ADO queue request failed or its outcome is unknown. Check ADO Runs before retrying; no automatic POST retry is performed.") from None


def send_candidate(manifest_path="out/manifest.json", receipt_path="out/bridge-receipt.json", env=None):
    env = os.environ if env is None else env
    ids, sha, branch, project_path = ci_identity(env)
    pipeline_id = positive_id(required(env, "ADO_PIPELINE_ID"), "ADO_PIPELINE_ID")
    cd_commit = full_sha(required(env, "ADO_CD_COMMIT"))
    project = required(env, "ADO_PROJECT")
    token = required(env, "ADO_QUEUE_PAT")
    base = required(env, "ADO_COLLECTION_URL")
    try:
        uri = urllib.parse.urlsplit(base)
        if (uri.scheme not in ("https", "http") or not uri.hostname or uri.username is not None
                or uri.password is not None or uri.query or uri.fragment or re.search(r"[\x00-\x20]", base)):
            raise ValueError()
        uri.port  # Validate malformed ports too.
    except ValueError:
        raise BridgeError("Invalid ADO collection URL; credentials/query/fragment are not permitted.") from None
    if uri.scheme != "https":
        if env.get("ADO_ALLOW_INSECURE_HTTP") != "true":
            raise BridgeError("HTTPS is required; HTTP is an explicit isolated-lab exception only.")
        print("WARNING: LAB ONLY: HTTP exposes credentials and payloads.", file=sys.stderr)
    with Path(manifest_path).open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise BridgeError("Manifest exceeds size limit.")
    try:
        manifest = json.loads(data.decode("utf-8-sig"))
        if not isinstance(manifest, dict):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise BridgeError("Invalid manifest JSON.") from None
    expected_release = f"r{ids['CI_PIPELINE_IID']}-{sha[:8]}"
    if (type(manifest.get("schema")) is not int or manifest["schema"] != 1
            or str(manifest.get("projectId")) != ids["CI_PROJECT_ID"]
            or manifest.get("projectPath") != project_path
            or str(manifest.get("pipelineId")) != ids["CI_PIPELINE_ID"]
            or manifest.get("commitSha") != sha or manifest.get("ref") != branch
            or manifest.get("releaseId") != expected_release or manifest.get("zipName") != "site.zip"
            or not re.fullmatch(r"[a-fA-F0-9]{64}", str(manifest.get("zipSha256")))):
        raise BridgeError("Manifest does not belong to this GitLab pipeline.")
    job_id = positive_id(manifest.get("jobId"), "manifest jobId")
    # CI_JOB_ID here is the notify job, NOT the packaging job; use manifest.jobId.
    payload = {
        "resources": {"repositories": {"self": {"refName": "refs/heads/main", "version": cd_commit}}},
        "templateParameters": {
            "gitlabProjectId": ids["CI_PROJECT_ID"], "gitlabPipelineId": ids["CI_PIPELINE_ID"],
            "gitlabJobId": job_id, "commitSha": sha, "releaseId": expected_release,
            "zipSha256": manifest["zipSha256"],
        },
    }
    url = f"{base.rstrip('/')}/{urllib.parse.quote(project, safe='')}/_apis/pipelines/{pipeline_id}/runs?api-version=7.0"
    run = post_run(url, payload, token)
    if not isinstance(run, dict):
        raise BridgeError("Invalid ADO run response; reconcile before retrying.")
    run_id = positive_id(run.get("id"), "ADO run ID")
    if not isinstance(run.get("pipeline"), dict) or str(run["pipeline"].get("id")) != pipeline_id:
        raise BridgeError("ADO response pipeline mismatch; reconcile before retrying.")
    receipt = {
        "gitlab_project_id": ids["CI_PROJECT_ID"], "gitlab_pipeline_id": ids["CI_PIPELINE_ID"],
        "gitlab_job_id": job_id, "gitlab_commit_sha": sha, "ado_run_id": run_id,
        "ado_pipeline_id": pipeline_id, "ado_cd_commit": cd_commit,
        "queued_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(receipt_path, receipt)
    print(f"ADO importer run {run_id} queued. This is NOT import success or deployment authorization.")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = commands.add_parser("package")
    package.add_argument("input_directory")
    package.add_argument("--output", default="out")
    notify = commands.add_parser("notify")
    notify.add_argument("--manifest", default="out/manifest.json")
    notify.add_argument("--receipt", default="out/bridge-receipt.json")
    args = parser.parse_args()
    try:
        if args.command == "package":
            package_candidate(args.input_directory, args.output)
        else:
            send_candidate(args.manifest, args.receipt)
        return 0
    except BridgeError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        print("Bridge failed; check input paths, permissions and configuration. No credentials or response body logged.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
