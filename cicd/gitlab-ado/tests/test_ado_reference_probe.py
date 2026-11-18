"""Offline tests for the operator's read-only ADO reference probe (Windows PS 5.1)."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "Test-AdoPipelineReference.ps1"
POWERSHELL = shutil.which("powershell.exe")
REPO_ID = "11111111-1111-1111-1111-111111111111"
OLD_REPO_ID = "22222222-2222-2222-2222-222222222222"
# Exact spelling observed in the user's ADO Branches screenshot (no "h").
REF = "refs/heads/poc/webook-smoke"
PREVIOUS_WRONG_REF = "refs/heads/poc/webhook-smoke"


@unittest.skipUnless(POWERSHELL, "Requires Windows PowerShell 5.1")
class AdoReferenceProbeTests(unittest.TestCase):
    def run_probe(self, mode, source_ref=None):
        self.assertTrue(PROBE.exists(), "Read-only ADO reference probe is missing")
        requests = []
        expected_auth = "Basic " + base64.b64encode(b":offline-token").decode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(("GET", self.path, self.headers.get("Authorization")))
                path = urlsplit(self.path).path
                query = parse_qs(urlsplit(self.path).query)
                status = 200
                if path.endswith("/build/definitions/5"):
                    if mode == "redirect":
                        self.send_response(302)
                        self.send_header("Location", "/must-not-follow")
                        self.end_headers()
                        return
                    if mode == "definition-denied":
                        status = 401
                        body = {"message": "PRIVATE-MARKER offline-token"}
                    else:
                        body = {
                            "id": 5, "name": "GitLab-Rayin-Zip-Delivery",
                            "repository": {"id": REPO_ID, "name": "ControlRepo", "type": "TfsGit", "defaultBranch": "refs/heads/main"},
                            "process": {"yamlFilename": "/azure-pipelines-gitlab-file-delivery.yml"},
                            "variables": {"SECRET": {"value": "PRIVATE-MARKER offline-token"}},
                        }
                elif path.endswith(f"/git/repositories/{REPO_ID}/refs"):
                    if mode == "ref-denied":
                        status = 403
                    # Model the API's prefix filter against the ACTUAL branch,
                    # rather than making the fixture agree with any requested name.
                    refs = [{"name": REF + "-old", "objectId": "c" * 40}]
                    if mode not in ("missing-ref", "ref-denied"):
                        refs.append({"name": REF, "objectId": "a" * 40})
                    prefix = "refs/" + query.get("filter", [""])[0]
                    body = {"value": [r for r in refs if r["name"].startswith(prefix)]}
                    if mode == "invalid-ref-json":
                        body = {"message": "PRIVATE-MARKER offline-token"}
                elif path.endswith("/build/builds"):
                    if query.get("definitions") != ["5"] or query.get("$top") != ["1"]:
                        status = 400
                    body = {"value": [{"id": 321, "sourceBranch": REF, "sourceVersion": "b" * 40,
                                       "repository": {"id": OLD_REPO_ID if mode == "changed-repo" else REPO_ID}}]}
                else:
                    status = 404
                    body = {"message": "PRIVATE-MARKER offline-token"}
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                requests.append(("POST", self.path, None))
                self.send_error(405)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory(prefix="ado ref probe tests-") as tmp:
                wrapper = Path(tmp) / "invoke.ps1"
                wrapper.write_text(
                    "param([string]$Script,[string]$Url,[string]$RequestedRef)\n"
                    "$ErrorActionPreference='Stop'\n"
                    "$secret=ConvertTo-SecureString 'offline-token' -AsPlainText -Force\n"
                    "$parameters=@{ProjectUrl=$Url;Pat=$secret}\n"
                    "if($RequestedRef){$parameters.SourceRef=$RequestedRef}\n"
                    "& $Script @parameters\n", encoding="utf-8-sig")
                command = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper),
                           "-Script", str(PROBE), "-Url", f"http://127.0.0.1:{server.server_port}/collection/Deployment"]
                if source_ref is not None:
                    command.extend(["-RequestedRef", source_ref])
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("offline-token", result.stdout + result.stderr)
            self.assertNotIn("PRIVATE-MARKER", result.stdout + result.stderr)
            self.assertTrue(requests)
            self.assertTrue(all(method == "GET" and auth == expected_auth for method, _, auth in requests))
            self.assertTrue(all(path.startswith("/collection/Deployment/_apis/") for _, path, _ in requests))
            return json.loads(result.stdout), requests
        finally:
            server.shutdown()
            server.server_close()

    def test_current_definition_exact_ref_and_success_run_are_reported_without_queueing(self):
        report, requests = self.run_probe("good")
        self.assertEqual(len(requests), 3)
        self.assertEqual(report["adoRepoId"], REPO_ID)
        self.assertEqual(report["yamlPath"], "/azure-pipelines-gitlab-file-delivery.yml")
        self.assertEqual(report["exactRefCount"], 1)
        self.assertEqual(report["refTipCommit"], "a" * 40)
        self.assertEqual(report["lastSuccessfulAdoToolCommit"], "b" * 40)
        self.assertEqual(report["lastSuccessfulRunId"], 321)

    def test_template_targets_observed_ado_spelling_without_changing_gitlab_version(self):
        template = json.loads((ROOT / "ado" / "gitlab-file-delivery-push.template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["resources"]["repositories"]["self"]["refName"], REF)
        self.assertEqual(template["templateParameters"]["gitlabCommitSha"], "{{checkout_sha}}")
        self.assertIs(template["templateParameters"]["allowInsecureHttpLab"], True)

    def test_previous_wrong_spelling_does_not_resolve_the_existing_branch(self):
        report, _ = self.run_probe("good", source_ref=PREVIOUS_WRONG_REF)
        self.assertEqual(report["requestedAdoRef"], PREVIOUS_WRONG_REF)
        self.assertEqual(report["refsHttpStatus"], 200)
        self.assertEqual(report["exactRefCount"], 0)
        self.assertEqual(report["lastSuccessfulAdoRef"], REF)

    def test_similar_ref_name_is_not_treated_as_the_requested_ref(self):
        report, _ = self.run_probe("missing-ref")
        self.assertEqual(report["refsHttpStatus"], 200)
        self.assertEqual(report["exactRefCount"], 0)
        self.assertIsNone(report["refTipCommit"])

    def test_denied_refs_are_not_reported_as_an_absent_branch(self):
        report, _ = self.run_probe("ref-denied")
        self.assertEqual(report["refsHttpStatus"], 403)
        self.assertIsNone(report["exactRefCount"])
        self.assertEqual(report["lastSuccessfulRunId"], 321)

    def test_unexpected_json_is_not_mistaken_for_an_absent_ref(self):
        report, _ = self.run_probe("invalid-ref-json")
        self.assertEqual(report["refsHttpStatus"], 200)
        self.assertEqual(report["refsFormat"], "unexpected-json")
        self.assertIsNone(report["exactRefCount"])

    def test_definition_repository_change_is_visible(self):
        report, _ = self.run_probe("changed-repo")
        self.assertEqual(report["adoRepoId"], REPO_ID)
        self.assertEqual(report["lastSuccessfulRepoId"], OLD_REPO_ID)

    def test_login_redirect_is_not_followed_with_pat(self):
        report, requests = self.run_probe("redirect")
        self.assertEqual(report["definitionHttpStatus"], 302)
        self.assertEqual(len(requests), 1)

    def test_definition_auth_failure_is_reported_without_raw_error_or_more_requests(self):
        report, requests = self.run_probe("definition-denied")
        self.assertEqual(report["definitionHttpStatus"], 401)
        self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
