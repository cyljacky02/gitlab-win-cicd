# GitLab CE artifact handoff to on-premises CD

> Historical polling proposal. The v0.6 presentation instead adopts the event-driven recommendation in [GitLab → ADO event-trigger research](gitlab-ado-event-trigger.md). The recommendation below is retained for comparison, not the current deck architecture.

## Slide-ready recommendation

**Authorized management-side Collector polls GitLab → queues an importer only for a new Release Candidate → ADO Server Build Artifacts → Classic Release → dedicated target Deployment Group.** `master` → automatic SIT; `pre-production` → automatic UAT; `production` → manual authorized Production. GitLab CI holds **no CD/Production credentials**. Polling, validation, deduplication, ZIP handling and deployment scripts are **custom glue**, not a native GitLab release-artifact source.[1–8,19]

**Deck implementation choice:** schedule one protected Collector build that is **not** a release artifact source. It queues one of three fixed importer definitions through the Server Build Queue REST API only when a new eligible candidate exists. This combines documented scheduling/queue/publication primitives and avoids no-change polling runs becoming deployment releases; it is a design recommendation, not a native connector or runtime-tested integration.[2–4,8,19]

**Evidence boundary:** documentation-verified feasibility, **not a runtime-tested POC**. Baseline: ADO Server 2022 (REST 7.0), current GitLab Self-Managed Free/CE, Rundeck Community core APIs. Inventory installed versions before implementation; Server 2020 uses REST 6.0, Server 2019 uses 5.0. Do not infer old-version support from current GitLab documentation.[1,9]

## One concrete minimal ADO implementation

Use **one protected scheduled Collector and three protected, CD-owned importer build definitions**, fixed to `master/SIT`, `pre-production/UAT`, and `production/Production`, and three matching one-environment Classic release definitions. **Native ADO build-branch filters see the importer's repository branch (for example `main`), not the original GitLab ref.** Route by the fixed definition pair and revalidated GitLab metadata, never by those filters. Keep scripts/configuration in a CD-owned repository, not developer-controlled GitLab YAML. This is a recommended design using supported Server build/release primitives.[2–8]

1. **Native Server scheduler for Collector:** Classic Build → Triggers → Scheduled; uncheck **Only schedule builds if the source or pipeline has changed**. Select the self-hosted management pool. No webhook receiver/external queue bridge is necessary. YAML schedules also apply to Server: `always: true`, `trigger: none`, trusted configuration branch. Cron is UTC; `batch` requires Server 2022.1+, and does not prevent overlap with `always: true`, so use a durable script lock.[8]
2. **Custom Collector/importer:** the Collector polls and queues a fixed importer only for a new candidate, using the Build Queue API and an identity limited to executing those import definitions. The importer revalidates metadata and downloads the pinned payload; publish its payload and provenance manifest with `PublishBuildArtifacts@1`, `PathtoPublish: $(Build.ArtifactStagingDirectory)`, `ArtifactName: drop`, `publishLocation: Container`. This is **Build Artifacts**, not Services-only `PublishPipelineArtifact`.[2,10,19]
3. **Native release binding:** source type **Azure Pipelines**, exact corresponding importer definition; bind a specific importer build version, never download GitLab “latest” during deployment. SIT/UAT: enable the corresponding importer build artifact's **continuous-deployment trigger** (documented for **Azure DevOps Server**, not Services-only), stage **After release**, PR triggers disabled. Production: artifact CD trigger **off**, authorized user creates a release selecting an imported build; stage **Manual only** plus named **pre-deployment approvers**. Restrict release creation/deployment/edit/permission administration. Same authorized person may initiate and approve; separate-person approval is optional, not this project's requirement.[3–5,7]
4. Each stage uses its own dedicated **Deployment Group job**, with agent on the target executing CD-owned local deployment steps. Production bytes remain on management storage until deployment authorization; do not pre-copy them to Production. Deployment Groups are Classic-only.[6,11]

**No-change handling (custom):** the Collector ends successfully without queuing an importer. Its own build is not a Release artifact source, so a no-change scan creates no release. Only successful new importer builds feed SIT/UAT releases. Do not treat native scheduling/CD as exactly-once; persist and reconcile the candidate-to-import mapping.[2–4,8,19]

## GitLab selection, identity and retention

Official Free APIs, with `PRIVATE-TOKEN` header; prefix endpoints with `/api/v4`:[1,12,13]

```text
GET /projects/P/pipelines?ref=master&source=push&status=success&order_by=id&sort=desc
GET /projects/P/pipelines/L
GET /projects/P/pipelines/L/jobs?scope[]=success&include_retried=false
GET /projects/P/jobs/J
GET /projects/P/jobs/J/artifacts
```

Repeat for exactly `pre-production` and `production`; paginate. **Do not use `scope=branches` for history**: it returns only the latest pipeline per ref. Recheck fixed project, pipeline success, exact ref, `source=push`, `tag=false`, SHA, job's pipeline ID, allowlisted job name and successful status. Push includes tags: `source=push` alone is insufficient. Reject MR, child, tag, web/API/scheduled pipelines unless explicitly added to policy.[12,13]

`/jobs/artifacts/:ref/download?job=NAME` is mutable latest-successful selection (creation time), accepts branch/tag, not SHA/HEAD, and searches parent before child. Pin **project/pipeline/job IDs** and SHA; a retried job has its own selection implications. Job ID pins identity, **not permanent storage**.[1,13]

Use project token **Reporter + `read_api`** where artifact-access policy permits; Self-Managed project tokens are available with any license. Alternative: dedicated ordinary user's PAT with only project Reporter membership and `read_api`. `read_repository` is insufficient; deploy tokens cannot access these general REST APIs. Do not depend on Premium multi-project `job_token` artifact access.[1,14–17]

Set expiry longer than maximum polling outage, copy promptly into retained CD storage, retain importer builds/releases through approval and rollback. GitLab defaults preserve latest successful artifacts, but settings/newer pipelines/deletion defeat permanence. `POST /projects/P/jobs/J/artifacts/keep` preserves expiry; it is a write operation, **not permitted by `read_api`**. Use separately authorized preservation or configured retention, not a broader collector token.[1,18]

## Reliability and trust boundaries — custom requirements

Persist unique `(project,pipeline,job)` → importer build/candidate mapping; reconcile publication after crashes before retrying. Lock imports, never republish an acknowledged job, and gate target execution against duplicate candidate/environment records. Native scheduling/CD is **not an exactly-once protocol**. Serialize deployments; compare pipeline IDs per branch so an older pipeline finishing later cannot overwrite a newer deployed candidate. Record skipped versions; explicit authorized rollback overrides ordering. These are design requirements, not vendor-provided GitLab integration guarantees.[1–8,12,13]

Hash bytes after import and verify at deployment; hashes detect substitution, not trustworthiness of developer-produced content. GitLab's outer artifact ZIP may contain an inner application ZIP: either fetch the approved inner path with `/jobs/J/artifacts/*artifact_path`, or extract the outer archive once. Validate paths, traversal, links, size limits and package layout; never execute repository-supplied scripts on the credentialed collector.[1]

Keep GitLab read token on management only; separate SIT/UAT execution identities from Production target rights. Importer identities must lack Production deployment/edit/approval rights. The scheduled Collector requires no external inbound receiver; its narrowly restricted identity queues only fixed importer builds, while importer identities have no Release/Production authority. Queue API: `POST https://ado/Collection/Project/_apis/build/builds?api-version=7.0`, body `{"definition":{"id":42},"parameters":"{\"GitLabPipelineId\":\"123\"}"}`; importer revalidates inputs. Server supports Windows authentication/PAT, not Services Entra/OAuth assumptions. Any PAT uses Build execute scope plus narrowly restricted definition permissions, no Release/Production authority.[7,9,19,20]

## Rundeck OSS fallback and alternatives

Core job YAML supports schedules, scripts and `multipleExecutions: false`; use a CD-owned scheduled collector applying the same checks, storing immutable candidates on management storage. Custom dispatch automatically calls fixed SIT/UAT jobs; Production is **unscheduled**, run only by authorized deployers choosing an exact candidate. Do not claim OSS supplies an ADO-equivalent approval workflow.[21–23]

API: `POST /api/18/job/UUID/run`, header `X-Rundeck-Auth-Token`, JSON `{"options":{"candidate":"P-L-J"}}`. Token authorization roles + ACL must allow only selected project/job `read/run` and required node execution; deny Production run, job edits, arbitrary commands and `runAs` to automation. Fixed job IDs/node filters and validated candidate options prevent environment escalation; token alone is not inherently job-scoped.[22,23]

**Alternatives:** pipeline webhook → protected receiver adds inbound service, secret verification (`X-Gitlab-Token`), replay handling and API revalidation; it is notification, **not** native ADO GitLab artifact triggering. GitLab job → CD API exposes execution authority to developer-controlled scripts; reject for Production. Outbound management polling is the smallest defensible trust boundary. Microsoft documents no built-in GitLab CI artifact source here; Services-only Pipeline Artifact tasks/authentication and third-party connectors must not be assumed supported on Server.[3,10,20,24]

## Official primary sources

[1]: https://docs.gitlab.com/api/job_artifacts/
[2]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines-server
[3]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/artifacts?view=azure-devops-server
[4]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-server
[5]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-server
[6]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-server
[7]: https://learn.microsoft.com/en-us/azure/devops/pipelines/policies/permissions?view=azure-devops-server
[8]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/scheduled-triggers?view=azure-devops-server
[9]: https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rest-api-versioning?view=azure-devops-server
[10]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines
[11]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-group-phases?view=azure-devops-server
[12]: https://docs.gitlab.com/api/pipelines/
[13]: https://docs.gitlab.com/api/jobs/
[14]: https://docs.gitlab.com/user/project/settings/project_access_tokens/
[15]: https://docs.gitlab.com/security/tokens/access_token_scopes/
[16]: https://docs.gitlab.com/user/permissions/
[17]: https://docs.gitlab.com/user/project/deploy_tokens/
[18]: https://docs.gitlab.com/ci/jobs/job_artifacts/
[19]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-rest-7.0
[20]: https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/authentication-guidance?view=azure-devops-server
[21]: https://docs.rundeck.com/docs/manual/document-format-reference/job-yaml-v12.html
[22]: https://docs.rundeck.com/docs/api/#running-a-job
[23]: https://docs.rundeck.com/docs/administration/security/authorization.html
[24]: https://docs.gitlab.com/user/project/integrations/webhooks/

[1] [GitLab Job Artifacts API][1] · [2] [PublishBuildArtifacts@1][2] · [3] [Classic artifact sources][3] · [4] [Classic release triggers][4] · [5] [Release approvals][5] · [6] [Deployment Groups][6] · [7] [Pipeline permissions][7] · [8] [Server scheduling][8] · [9] [REST version compatibility][9] · [10] [Pipeline Artifact limitation][10] · [11] [Deployment Group jobs][11] · [12] [Pipelines API][12] · [13] [Jobs API][13] · [14] [Project tokens][14] · [15] [Token scopes][15] · [16] [GitLab permissions][16] · [17] [Deploy-token limitation][17] · [18] [Artifact expiry][18] · [19] [Queue Build API][19] · [20] [Server authentication][20] · [21] [Rundeck core job format][21] · [22] [Job execution/token API][22] · [23] [Rundeck ACLs][23] · [24] [GitLab webhooks][24]
