"""Offline checks for Linux CI code; no GitLab/ADO services contacted."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import TestCase, main, mock
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("linux_bridge", PACKAGE / "gitlab/ci/bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class LinuxJobTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="linux-bridge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.output = self.root / "input", self.root / "out"
        self.source.mkdir()
        (self.source / "index.html").write_text("<h1>test</h1>", encoding="utf-8")
        (self.source / ".hidden").write_bytes(b"\x00\xff\x01")
        self.env = {
            "CI_PROJECT_ID": "123", "CI_PROJECT_PATH": "group/application",
            "CI_PIPELINE_ID": "456", "CI_PIPELINE_IID": "7", "CI_JOB_ID": "789",
            "CI_COMMIT_SHA": "0123456789abcdef0123456789abcdef01234567", "CI_COMMIT_BRANCH": "main",
            "ADO_COLLECTION_URL": "https://ado.invalid/collection", "ADO_PROJECT": "Import Project",
            "ADO_PIPELINE_ID": "10", "ADO_CD_COMMIT": "b" * 40,
            "ADO_QUEUE_PAT": "offline-queue-token",
        }

    def package(self):
        return bridge.package_candidate(self.source, self.output, self.env)

    def notify(self):
        # GitLab changes CI_JOB_ID between package and notify jobs.
        return bridge.send_candidate(self.output / "manifest.json", self.output / "bridge-receipt.json", {**self.env, "CI_JOB_ID": "790"})

    def test_archive_manifest_marker_and_bytes_match_windows_contract(self):
        manifest = self.package()
        self.assertEqual(set(manifest), {"schema", "releaseId", "projectId", "projectPath", "pipelineId", "jobId", "commitSha", "ref", "zipName", "zipSha256", "zipBytes"})
        self.assertEqual(manifest["releaseId"], "r7-01234567")
        self.assertEqual(manifest["zipBytes"], (self.output / "site.zip").stat().st_size)
        self.assertEqual(manifest["zipSha256"], bridge.file_sha256(self.output / "site.zip"))
        with zipfile.ZipFile(self.output / "site.zip") as archive:
            self.assertEqual(set(archive.namelist()), {"index.html", ".hidden", "release.json"})
            self.assertEqual(archive.read(".hidden"), b"\x00\xff\x01")
            marker = json.loads(archive.read("release.json"))
            self.assertEqual(marker, {"releaseId": manifest["releaseId"], "commitSha": manifest["commitSha"], "projectId": 123, "pipelineId": 456, "jobId": 789})
        self.assertFalse((self.source / "release.json").exists())

    def test_empty_reserved_and_nested_output_rejected(self):
        with self.subTest("reserved"):
            (self.source / "release.json").write_text("business file")
            with self.assertRaisesRegex(bridge.BridgeError, "reserved"):
                self.package()
            (self.source / "release.json").unlink()
        with self.subTest("nested output"):
            with self.assertRaisesRegex(bridge.BridgeError, "outside"):
                bridge.package_candidate(self.source, self.source / "out", self.env)
        with self.subTest("empty"):
            for path in self.source.iterdir():
                path.unlink()
            with self.assertRaisesRegex(bridge.BridgeError, "empty"):
                self.package()

    def test_symlink_input_rejected(self):
        try:
            (self.source / "linked").symlink_to(self.source / "index.html")
        except OSError:
            self.skipTest("Host does not permit creating symlinks; test runs on Linux CI.")
        with self.assertRaisesRegex(bridge.BridgeError, "Symlinks"):
            self.package()

    def test_invalid_ids_sha_and_tag_rejected(self):
        for field, value in (("CI_PIPELINE_IID", "0"), ("CI_PROJECT_ID", "../123"), ("CI_COMMIT_SHA", "deadbeef"), ("CI_COMMIT_TAG", "v1")):
            with self.subTest(field=field), self.assertRaises(bridge.BridgeError):
                bridge.package_candidate(self.source, self.output, {**self.env, field: value})

    def test_queue_payload_pin_uses_package_job_not_notify_job(self):
        manifest = self.package()
        with mock.patch.object(bridge, "post_run", return_value={"id": 42, "pipeline": {"id": 10}}) as post:
            receipt = self.notify()
        url, payload, token = post.call_args.args
        self.assertEqual(url, "https://ado.invalid/collection/Import%20Project/_apis/pipelines/10/runs?api-version=7.0")
        self.assertEqual(payload["resources"]["repositories"]["self"], {"refName": "refs/heads/main", "version": self.env["ADO_CD_COMMIT"]})
        self.assertEqual(payload["templateParameters"], {"gitlabProjectId": "123", "gitlabPipelineId": "456", "gitlabJobId": "789", "commitSha": manifest["commitSha"], "releaseId": manifest["releaseId"], "zipSha256": manifest["zipSha256"]})
        self.assertEqual(token, self.env["ADO_QUEUE_PAT"])
        self.assertEqual(receipt["ado_run_id"], "42")
        self.assertEqual(receipt["gitlab_job_id"], "789")
        self.assertNotIn(token, json.dumps(receipt) + json.dumps(payload))

    def test_manifest_tampering_rejected_before_post(self):
        original = self.package()
        for key in ("schema", "projectId", "projectPath", "pipelineId", "jobId", "commitSha", "ref", "releaseId", "zipName", "zipSha256"):
            with self.subTest(key=key), mock.patch.object(bridge, "post_run") as post:
                manifest = {**original, key: "wrong"}
                (self.output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(bridge.BridgeError):
                    self.notify()
                post.assert_not_called()
        self.assertFalse((self.output / "bridge-receipt.json").exists())

    def test_http_credentials_query_fragment_urls_rejected(self):
        self.package()
        for url in ("http://ado.invalid/collection", "https://user:secret@ado.invalid/c", "https://ado.invalid/c?x=1", "https://ado.invalid/c#fragment"):
            with self.subTest(url=url), mock.patch.object(bridge, "post_run") as post:
                with self.assertRaises(bridge.BridgeError):
                    bridge.send_candidate(self.output / "manifest.json", self.output / "receipt.json", {**self.env, "ADO_COLLECTION_URL": url})
                post.assert_not_called()

    def test_bad_ado_response_does_not_write_receipt(self):
        self.package()
        for run in ({"id": 0}, {"id": 42, "pipeline": {"id": 99}}, None):
            with self.subTest(run=run), mock.patch.object(bridge, "post_run", return_value=run):
                with self.assertRaises(bridge.BridgeError):
                    self.notify()
        self.assertFalse((self.output / "bridge-receipt.json").exists())

    def test_real_loopback_post_and_failures_have_no_redirect_or_retry(self):
        self.package()
        for status in (200, 401, 500, 302):
            with self.subTest(status=status):
                calls = []
                class Handler(BaseHTTPRequestHandler):
                    def do_POST(server):
                        calls.append((server.path, server.headers["Authorization"], json.loads(server.rfile.read(int(server.headers["Content-Length"])))))
                        body = b'{"id":42,"pipeline":{"id":10}}'
                        server.send_response(status)
                        server.send_header("Content-Length", str(len(body)))
                        server.send_header("Location", "/do-not-follow")
                        server.end_headers()
                        server.wfile.write(body)
                    def log_message(*args):
                        pass
                server = HTTPServer(("127.0.0.1", 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                receipt = self.output / "bridge-receipt.json"
                receipt.unlink(missing_ok=True)
                env = {**self.env, "ADO_COLLECTION_URL": f"http://127.0.0.1:{server.server_port}/collection", "ADO_ALLOW_INSECURE_HTTP": "true", "CI_JOB_ID": "790"}
                try:
                    with mock.patch.dict(os.environ, {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}):
                        if status == 200:
                            bridge.send_candidate(self.output / "manifest.json", receipt, env)
                            self.assertTrue(receipt.exists())
                        else:
                            with self.assertRaisesRegex(bridge.BridgeError, "no automatic POST retry") as caught:
                                bridge.send_candidate(self.output / "manifest.json", receipt, env)
                            self.assertNotIn(self.env["ADO_QUEUE_PAT"], str(caught.exception))
                            self.assertFalse(receipt.exists())
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0][0], "/collection/Import%20Project/_apis/pipelines/10/runs?api-version=7.0")
                    self.assertEqual(calls[0][1], "Basic " + base64.b64encode(b":offline-queue-token").decode())
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()

    def test_python_package_passes_windows_ado_zip_and_marker_checks(self):
        if not shutil.which("powershell"):
            self.skipTest("PowerShell 5.1 is available on VM1, not required on Linux Runner.")
        self.package()
        def quote(path):
            return "'" + str(path).replace("'", "''") + "'"
        command = (
            "$ErrorActionPreference='Stop'; . " + quote(PACKAGE / "shared/Bridge.Common.ps1") + "; "
            "$manifest=Get-Content -LiteralPath " + quote(self.output / "manifest.json") + " -Raw -Encoding UTF8 | ConvertFrom-Json; "
            "Test-BridgeZip -Path " + quote(self.output / "site.zip") + " -MaxExpandedBytes 268435456; "
            "Assert-BridgeZipMarker -Path " + quote(self.output / "site.zip") + " -Manifest $manifest"
        )
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_yaml_does_not_invoke_powershell(self):
        text = (PACKAGE / "gitlab/gitlab-ci.example.yml").read_text(encoding="utf-8")
        self.assertIn("new-release-candidate.sh", text)
        self.assertIn("send-ado-candidate.sh", text)
        self.assertNotIn(".ps1", text)
        self.assertNotIn("gitlab-bridge-windows", text)
        self.assertNotIn("needs:", "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")))


if __name__ == "__main__":
    main()
