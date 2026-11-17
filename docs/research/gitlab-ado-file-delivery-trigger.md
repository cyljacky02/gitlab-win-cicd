# GitLab → ADO Server: authenticated file-delivery trigger

## Verdict

**Conditionally viable without a GitLab Runner or new receiver:** compose GitLab's documented project-webhook custom headers/payload with ADO's authenticated Runs REST API. This is a composition of official interfaces, not a dedicated GitLab connector. Installed versions, permissions and connectivity remain unverified.

Use a **separate controlled delivery pipeline**. Keep incoming connection `gitlab-ado-smoke-rs` and its unauthenticated pipeline zero-op: project routing may switch to Rayin, but no secrets, source fetching or delivery. Native incoming-webhook HMAC-SHA1 verification is different from GitLab's `X-Gitlab-Token`; adding a PAT to that public endpoint does not secure it. [1], [2]

**Subsequent user confirmation:** the Rayin webhook UI exposes both Custom headers and Custom webhook template. The [delivery pipeline and setup guide](../runbooks/gitlab-ado-file-delivery.md) are now supplied. This confirms feature visibility, not HTTPS/PAT policy, queue ACLs or successful end-to-end triggering.

## GitLab availability and payload behavior

Project webhooks support **Free, Premium and Ultimate**, including Self-Managed; configuration requires Maintainer/Owner. Group webhooks are unnecessary. [1]

| Capability | Official history |
| --- | --- |
| Custom payload template | 16.10, `custom_webhook_template` flag, documented enabled by default; GA 17.0, flag removed |
| Custom headers | 16.11, `custom_webhook_headers` flag, enabled by default; GA 17.0, flag removed |
| Interpolated-value JSON serialization | 18.4, initially disabled; enabled by default/GA 18.6; flag removed 18.10 |

Thus **17.0+ is the straightforward feature baseline**, not a recommendation to run an unsupported old release. Confirm both controls/flags on the actual server. `Authorization` is allowed: GitLab's API documentation explicitly shows that custom-header name; generated delivery headers cannot be overridden. [1], [3]

Use **quoted** `"{{checkout_sha}}"`: a normal SHA-1 push becomes a JSON string containing exactly its 40 hexadecimal characters. The SHA needs no JSON escaping even with older interpolation. Avoid arbitrary commit-message interpolation on older versions. Quoting also avoids GitLab 18.8–18.10's documented unquoted-placeholder saving bug. [1], [4], [5]

## Minimal UI/request example

In `grp-smt-maint/Cathaysec.Com.Smt.Rayin` → **Settings → Webhooks → Add new webhook**:

- **URL:** the POST URL below; use the actual collection base URL (`/tfs` may be absent).
- **Trigger:** Push events only; **Wildcard pattern:** literal `poc/cicd`.
- **Custom headers:** name `Authorization`, value `Basic <BASE64(:ADO_PAT)>` (encode the leading colon too; no newline).
- Leave **Secret token** empty; it is not the ADO credential. Keep SSL verification enabled.
- **Custom webhook template / Custom payload:** the JSON below.

```http
POST https://<ado-host>/tfs/<collection>/Deployment/_apis/pipelines/<delivery-pipeline-id>/runs?api-version=7.1
Authorization: Basic <BASE64(:ADO_PAT)>
Content-Type: application/json
```

```json
{
  "resources": {
    "repositories": {
      "self": { "refName": "refs/heads/poc/webhook-smoke" }
    }
  },
  "templateParameters": {
    "gitlabCommitSha": "{{checkout_sha}}"
  }
}
```

GitLab supplies JSON Content-Type. Wildcard mode with this literal is an exact branch-name match, **not regex** and not a full Git ref. If deliberately selecting regex mode, use `^poc/cicd$`; do not put regex anchors into wildcard mode. [1], [6], [16]

ADO documents this Server endpoint, `templateParameters`, repository `refName`, and a successful `200` Run response. API **7.1** is documented for Server 2022.1 and newer; use it conservatively for reported 25H2 after checking the actual build, rather than assuming Services/latest API parity. The Azure Repos control branch selects YAML; the GitLab SHA is a separate parameter, **not** `self.version`. [7], [8]

## Safety gates and facts to check

- **Authentication:** dedicated low-privilege ADO identity; short-lived, collection-scoped PAT with **Build (Read & execute)** (`vso.build_execute`). Scope is not pipeline-specific: restrict effective **Queue builds** permissions to the delivery pipeline; do not grant pipeline-edit/repository-write/admin rights. Keep **IIS Basic Authentication disabled** for PAT authentication. Protect the control branch and authorize only this pipeline to the required resources. [7], [9], [10]
- **Exact SHA / deletion:** declare `gitlabCommitSha` as a string parameter. Pass it as data, not interpolated script code; confirm this repository uses SHA-1 IDs, validate `\A[0-9a-fA-F]{40}\z` and reject forty zeros **before fetching/writing**. On branch deletion, `checkout_sha` is null; this quoted template yields an empty string with legacy interpolation or `"null"` with serialization. Branch filtering does not exclude deletion. Reject/no-op either value; never fall back to branch HEAD. GitLab source confirms these behaviors. [4], [11]
- **Delivery prerequisites:** fixed GitLab project, ADO-held read credential, exact-SHA fetch, no application build or execution of fetched scripts. GitLab's archive API can directly return ZIP with `archive.zip?sha=<validated-SHA>`. Fail closed if unavailable. Target Environment `test-deploy-agent`, `resourceType: virtualMachine`, `resourceName: SECSVR4-80`; verify its agent is online and service identity can write **only the intended** `D:\TestCICD` destination. [12], [13]
- **Transport:** use trusted **HTTPS** end-to-end. Base64 is not encryption. Plain HTTP is only an **explicitly accepted, isolated disposable-lab exception**, with a lab-only expiring PAT, restricted network and revocation afterward—not a secure production recommendation or a verified capability of this installation. Confirm actual PAT acceptance; do not weaken authentication to force it. Microsoft's agent-registration guidance requires HTTPS for PAT use. [9], [14]
- **Connectivity/test:** allowlist the ADO host/port in GitLab outbound-request policy; both Sidekiq and Rails nodes need access. Verify a real `poc/cicd` push binds its exact SHA, another branch does not trigger, deletion cannot deliver, and the response contains a run ID. Treat UI Test as sample data, not proof of branch filtering. Retries/resends can duplicate runs; Runs REST does not document GitLab-key deduplication. Pushes changing more than three refs can suppress hooks by default. [1], [7], [11], [15]

## Smallest fallback

If either custom control is unavailable, upgrading GitLab is the smallest receiver-free remedy. If version/authentication policy blocks that, automatic delivery needs a small authenticated adapter that validates GitLab event/ref/SHA and calls Runs REST with an ADO-held credential. If no receiver is permitted, manually queue the controlled pipeline with an explicit SHA; it is safe but not automatic. Never promote the unauthenticated smoke path.

## Primary sources

1. [GitLab webhook configuration and feature history][1]
2. [ADO native incoming-webhook authentication][2]
3. [GitLab project-webhook API and Authorization example][3]
4. [GitLab interpolation/serialization implementation][4]
5. [GitLab template troubleshooting][5]
6. [GitLab branch-filter implementation][6]
7. [ADO Server Runs REST contract][7]
8. [ADO Server/API compatibility mapping][8]
9. [ADO PAT authentication][9]
10. [ADO pipeline permissions][10]
11. [GitLab push SHA and sample-payload implementation][11]
12. [GitLab exact-SHA ZIP archive API][12]
13. [ADO Environment VM resources][13]
14. [ADO PAT agent-registration HTTPS requirement][14]
15. [GitLab outbound-request controls][15]
16. [GitLab exact/wildcard ref matching][16]

[1]: https://docs.gitlab.com/user/project/integrations/webhooks/
[2]: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/resources-webhooks-webhook?view=azure-pipelines-server
[3]: https://docs.gitlab.com/api/project_webhooks/
[4]: https://gitlab.com/gitlab-org/gitlab/-/merge_requests/197992.diff
[5]: https://docs.gitlab.com/user/project/integrations/webhooks_troubleshooting/#custom-webhook-template-with-unquoted-placeholders-cannot-be-saved
[6]: https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/models/hooks/active_hook_filter.rb
[7]: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-server-rest-7.1
[8]: https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.2#api-and-tfs-version-mapping
[9]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-server
[10]: https://learn.microsoft.com/en-us/azure/devops/pipelines/policies/permissions?view=azure-devops-server
[11]: https://gitlab.com/gitlab-org/gitlab/-/raw/master/lib/gitlab/data_builder/push.rb
[12]: https://docs.gitlab.com/api/repositories/#retrieve-file-archive-from-a-repository
[13]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-virtual-machines?view=azure-devops-server
[14]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/personal-access-token-agent-registration?view=azure-devops-server
[15]: https://docs.gitlab.com/security/webhooks/
[16]: https://gitlab.com/gitlab-org/gitlab/-/raw/master/app/models/ref_matcher.rb
