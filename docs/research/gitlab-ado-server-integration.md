# GitLab → Azure DevOps Server Express integration research

Research date: **2026-11-16**. Sources: Microsoft and GitLab first-party documentation, fetched during this research. **No live API calls, credential tests, archive inspection, or script changes were performed.**

## 1. Decision and evidence boundary

**Recommendation: retain the tested artifact handoff, not a repository migration or a second build in ADO.** GitLab remains the application-source and CI system. A final GitLab CI notification starts the fixed ADO YAML pipeline through **Runs – Run Pipeline**, with candidate identifiers in `templateParameters`. VM1 validates the GitLab pipeline/job and imports the exact `site.zip` and manifest. Only an authorized **Deployer** can release the production deployment stage to the VM2 deployment agent. Starting an ADO run is **candidate notification**, not **Deployment Authorization**. The Runs API creates a run; environment approvals separately control when a resource-consuming stage may begin. [S04][S20–S22][S29–S31]

```text
GitLab repository → GitLab Runner: build/test/package
                         │ job-ID artifacts: out/site.zip + out/manifest.json
                         │ final notify: POST ADO /pipelines/{id}/runs
                         ▼
VM1 ADO Fetch: validate exact upstream pipeline/job; wait for CI success
               → download/verify exact files → ADO Build Artifacts
                         │
                  Deployer-only manual authorization
                         │
                         ▼
VM2 environment deployment job: consume that candidate; deploy
```

**Evidence labels used below:**

- **Reported implementation:** supplied task context and existing repository research, not a fresh implementation audit.
- **Documented fact:** supported by the cited official URL; documentation support does not prove installed configuration.
- **Recommendation / inference:** proposed engineering policy, not a native exactly-once or security guarantee.
- **Unknown / acceptance test:** must be established on the installed products.

Read for context:

- [`poc-runtime-api-credential-review.md`](poc-runtime-api-credential-review.md): records the direct `POST _apis/pipelines/{id}/runs?api-version=7.0`, `templateParameters`, the four GitLab project/job/artifact GETs, `read_api`/Reporter token, and ADO Container Build Artifacts.
- [`gitlab-ado-event-trigger.md`](gitlab-ado-event-trigger.md): describes a **target** webhook/receiver/Classic Release architecture and the final-job success race. Its target architecture must not be substituted for the reported newer direct-agent implementation.
- Root [`GLOSSARY.md`](../../GLOSSARY.md): a Release Candidate is not an authorized production deployment; Delivery to a production host is already Production Access. One authorized person may authorize and execute; two-person approval is not required.

**Reported implementation:** GitLab builds `site.zip` plus a manifest; a final notification calls Runs 7.0; ADO Fetch verifies the build job and downloads `out/site.zip` and `out/manifest.json`. The latest direct-agent package is believed to use YAML Environments, not Classic Release; package verification is outside this report. Nothing here requires replacing it with re-cloning, mirroring, or Classic Release.

**Unknown:** exact ADO Server **edition/build/update/patch**, GitLab **version/edition/tier**, runner/ADO-agent versions, task catalog, current checks and effective ACLs. Prior research dates and an API-version string are **not identification of the installed marketing version**.

## 2. Server/Express compatibility: establish this before implementation

**Documented fact:** Microsoft's Server installation documentation says Express supports the same features as Azure DevOps Server and is licensed for five active users. This supports evaluating Server features on Express; it does **not** make every Azure DevOps **Services** feature available on every Server release. This report is not a full license review. [S01]

Microsoft's REST mapping gives these baselines; each API version is compatible with the listed Server and newer Server versions. An API still needs its own endpoint/schema reference. [S02][S03]

| Server release in Microsoft's mapping | REST baseline | Published build baseline |
|---|---:|---|
| Server 2019 | 5.0 | `>= 17.143.28621.4` |
| Server 2020 | 6.0 | `>= 18.170.30525.1` |
| Server 2022 | 7.0 | `>= 19.205.33122.1` |
| Server 2022.1 | 7.1 | `>= 19.225.34309.2` |

Important endpoint-specific distinction:

- **Runs 7.0:** a Server-specific reference explicitly documents the collection-scoped endpoint, `templateParameters`, and Basic PAT authentication. This is the relevant support for the reported implementation—not just a cloud URL example. [S04]
- **Runs on the Server 6.0 reference:** the actual documented API is **`6.0-preview.1`**, not a promise that simply changing `7.0` to stable `6.0` preserves the contract. Preview APIs have separate lifecycle constraints. [S05][S03]
- **Build Queue:** use the reference matching the installed Server API baseline; stable Build Queue references exist for 5.0/6.0/7.0. This is a different request contract from Runs, not a reason to replace working Runs 7.0. [S07]
- **Artifacts:** keep `PublishBuildArtifacts@1` with `publishLocation: Container` for this Server handoff. Container here means the ADO artifact store, not Docker. The Pipeline Artifacts task documentation warns that Pipeline Artifacts are unsupported on-premises and directs Server users to Build Artifacts; its `publish`/`download` YAML shortcuts are Pipeline Artifact shortcuts. Confirm actual download-task major/minor availability rather than copying a Services task example. [S32][S33]

**Acceptance test:** record the precise installed versions first, then exercise the chosen endpoint and each installed task. Successful reported use of 7.0 is useful operational evidence, but this research does not independently identify the installed Server build.

## 3. Practical direct GitLab CI → Runs API contract

### 3.1 Request, response, and identifiers

**Documented fact:** the Server 7.0 operation is: [S04]

```http
POST https://{instance}/{collection}/{project}/_apis/pipelines/{pipelineId}/runs?api-version=7.0
Authorization: Basic <base64(:ADO_PAT)>
Content-Type: application/json

{
  "templateParameters": {
    "gitlabProjectId": "123",
    "gitlabPipelineId": "12345",
    "gitlabJobId": "23456",
    "commitSha": "<full GitLab commit ID>",
    "releaseId": "r7-<first-eight-SHA-characters>",
    "zipSha256": "<64-character package SHA-256>"
  }
}
```

**These six parameter names match the accompanying `cicd/gitlab-ado/ado/azure-pipelines-import.yml`; they are application-defined keys, not names imposed by the Runs API.** Values are illustrative. Match the declared parameters and manifest schema; the allowed GitLab ref is management-owned policy, not a caller-selected target. Configure the instance, collection, ADO project, pipeline ID, GitLab instance/project, and production resource on the management side; do not let CI select them as arbitrary URLs or targets.

The collection base may include `/tfs/`; use the actual configured Server collection URL, not `dev.azure.com`. `pipelineId` identifies the configured pipeline; it is **not** an agent-pool queue ID, GitLab pipeline ID, or the newly created ADO run ID. [S02][S04]

The documented successful response is **HTTP 200 with a `Run`** containing `id`, `pipeline`, `url`, `state`, and `result`. Persist the returned run ID and correlation. `state` may be `inProgress`; `result=succeeded` is a separate outcome. For observation/reconciliation use: [S04][S06]

```http
GET {collectionBase}/{project}/_apis/pipelines/{pipelineId}/runs/{runId}?api-version=7.0
```

**Recommendation:** the notify job should confirm that it received a real expected-pipeline run response, record its ID, then exit successfully. It must **not wait for Fetch or deployment to finish**. A POST receipt is not artifact acceptance and certainly not deployment success. If HTTP times out after submission, do not assume no run was created: reconcile before replaying, and make candidate import idempotent. The documented request schema does not offer a GitLab-event idempotency-key contract. [S04][S06]

### 3.2 A narrowly scoped candidate contract

**Recommendation**, based on the API identity fields and input-injection risks in Microsoft's guidance: [S04][S12][S20–S22]

| Input or configuration | Policy |
|---|---|
| GitLab instance/project | Management-owned fixed values; optionally accept a project ID only to compare against the fixed value. |
| GitLab pipeline ID and packaging **job ID** | Positive IDs; verify their relationship using GitLab's API. The build job ID is not the notify job's `CI_JOB_ID`. |
| GitLab SHA/ref | Corroborating values; compare API job, API pipeline and manifest. Restrict allowed refs and pipeline sources by CD-owned policy. |
| ZIP/hash/manifest | Fixed internal artifact paths; check schema, size, hash and layout. Do not accept executable deployment scripts or a free-form download URL as privileged instructions. |
| ADO repository/ref/version, pools, environment/resource, scripts, destination paths, approval bypass | **Not candidate parameters.** Keep management-owned; test that the trigger credential cannot obtain an alternate ungated route. |
| Secrets | Never template parameters or manifest contents. Store in protected secret facilities and map only to the jobs that need them. |

`templateParameters` is an object for YAML template inputs. `variables` is a different dictionary of `{value,isSecret}` objects; Build Queue's `parameters` is different again. Typed YAML parameters can restrict values, but arbitrary string parameters still need validation and safe script argument handling. Avoid splicing untrusted `${{ parameters... }}` or macro-expanded values directly into executable PowerShell text. [S04][S07][S12]

### 3.3 Variable allowlists are not a proven Server security boundary

**Documented fact:** the UI provides **Settable at queue time** for Classic build variables and **Let users override this value when running this pipeline** for YAML UI variables. Microsoft's current input-security article documents the organization/project **Limit variables that can be set at queue time** setting, including REST rejection examples—but that subsection and **Edit queue build configuration** are inside the **Services (`azure-devops`) moniker**, not a blanket Server 2022 promise. [S12][S11]

**Recommendation:** use an explicit application-level allowlist and typed parameters regardless. Enable the platform restriction **if present and verified on this build**, and test unknown-variable and protected-variable overrides through REST. Do not say a Server checkbox, a hidden UI control, or the CI job's own JSON construction prevents a stolen PAT from submitting other valid payloads. Runs exposes `resources`, `stagesToSkip`, `variables`, and repository `refName`/`version`; `yamlOverride` is documented for preview use, not as arbitrary live YAML execution. Review each real override path rather than assuming all are equivalent. [S04][S12]

## 4. The pipeline-success race is the immediate correctness issue

**Documented fact:** GitLab's default `when: on_success` means no jobs in **earlier stages** failed; allowed failures count as success and skipped manual jobs can count as success. It does **not** assert that the current notify job or the whole pipeline has finished successfully. `GET /projects/:id/pipelines/:pipeline_id` separately exposes aggregate `status`, `source`, `ref`, `sha`, and `tag`. [S24][S20]

**Inference for this direct handoff:**

```text
build job succeeds and uploads artifacts
notify job starts, so its own pipeline can still be running
notify POST creates ADO run
ADO Fetch may start before notify exits
only after notify and all other required jobs finish can GitLab show success
```

Consequences:

1. A successful build job plus an existing ZIP proves neither the complete test policy nor whole-pipeline success. The four GETs recorded in the existing runtime review establish project/job/file checks; **they are not evidence of an aggregate pipeline-success gate**. This report has not audited the latest scripts. [S20–S22][S24]
2. Requiring `pipeline.status=success` immediately, without retry, can falsely reject a valid handoff. A fixed sleep is not a correctness condition.
3. If notify waits for ADO completion while Fetch waits for GitLab success, they wait on each other. This is a consequence of the above lifecycle, not a missing REST parameter.

### Recommended bounded handshake

This is **custom orchestration**, not a native distributed transaction:

1. Notify runs only for the agreed protected source branch/pipeline source and after all required packaging/test dependencies. It submits the fixed Runs request, saves the ADO run ID and exits; it does not await deployment. Use explicit dependencies if a `needs` DAG is involved—being visually placed in a last stage is not by itself the policy. [S24]
2. VM1 checks the exact project/job/pipeline identifiers. It then reads **that pipeline ID**, not `latest`, until `status=success` or a bounded deadline. Pending/running/other nonterminal states remain ineligible; failure, cancellation, skipped/manual-blocked/unexpected states do not grant eligibility. Retry transient API/network failures with bounded backoff; 401/403 and identity mismatch fail closed. GitLab's API supplies the states; retry policy and deadline are application choices. [S20][S21]
3. Require the named mandatory test/package jobs to have truly succeeded if policy demands this. Aggregate success alone can include allowed failures/skips. If enumerating jobs, follow pagination and intentionally handle retries (`include_retried=false` excludes retried jobs by default). [S21][S24]
4. Only after successful validation publish the imported candidate as eligible for deployment. An earlier temporary download on VM1 is not authorization; never publish or expose an ineligible candidate as deployable, and never pre-copy it to VM2.
5. Record the validated success snapshot, exact job/pipeline/SHA/hash, ADO run ID and policy version. Job retry/replacement must not silently change the bytes associated with an already authorized candidate. [S20–S22]

**Required race tests:** slow notify completion; notify failure after accepted POST; cancellation immediately after POST; parallel/late failing jobs; mandatory allowed-failure job; blocking manual job; timeout; duplicate POST; lost response; packaging-job retry. None may cause automatic production deployment or fallback to a newer artifact.

**Optional future alternative:** a pipeline-success webhook/receiver can move notification after CI completion, as the earlier event-trigger report proposes. It is not required to repair this POC: the direct Runs API path plus a bounded management-side success check is the smaller change. Do not silently introduce a receiver/Classic redesign into the tested path.

## 5. ADO Fetch → GitLab: exact artifact identity and permissions

### 5.1 API sequence

The following are documented APIs; the validation policy in the right column is **recommended**, with the existing four-call checks already reported in the runtime review. All GitLab paths below are under the fixed instance's `/api/v4`. [S19–S22]

| Call | Required interpretation |
|---|---|
| `GET /projects/{P}` | Compare fixed numeric project/namespace; discover `default_branch` only if policy intentionally follows it. The mutable project default is not an immutable release policy. |
| `GET /projects/{P}/jobs/{J}` | Require expected packaging job name/stage, success, allowed ref, `tag=false`, matching `pipeline.id` and `commit.id`; validate actual response fields for the installed version. |
| **Add/confirm** `GET /projects/{P}/pipelines/{L}` | Bounded full-pipeline success check from §4; compare project, SHA/ref/source/tag. |
| `GET /projects/{P}/jobs/{J}/artifacts/out/site.zip` | Download the actual single ZIP file from that job's artifact archive. |
| `GET /projects/{P}/jobs/{J}/artifacts/out/manifest.json` | Download the paired manifest from the **same** job; verify identities and recomputed payload hash. |

**Documented fact:** `GET /projects/{P}/jobs/{J}/artifacts` returns the **whole job artifacts archive**. The single-file route `.../artifacts/*artifact_path` extracts and streams one file. Do not confuse GitLab's outer archive with the inner deployable `site.zip`. [S22]

**Recommendation:** make the imported candidate key `(GitLab instance, project ID, pipeline ID, packaging job ID)` and store the full GitLab commit plus ZIP SHA-256. Treat the manifest and content as untrusted CI output: a matching hash detects content mismatch, not malicious code or independent provenance. Validate archive paths/layout/size before privileged deployment. Publish payload, manifest and verification record to the **current exact ADO build/run**, and have VM2 consume that artifact—not another run's latest result. [S22][S32]

### 5.2 Why job-ID URLs, not branch lookup

**Documented fact:** these are different operations: [S22]

```http
# Exact job's artifacts
GET /projects/{P}/jobs/{J}/artifacts/out/site.zip

# Latest successful pipeline for a moving ref
GET /projects/{P}/jobs/artifacts/{ref}/raw/out/site.zip?job=build
```

Ref lookup requires a completed successful pipeline; “latest” is determined by **pipeline creation time**, not individual job finish time. HEAD/SHA references are not supported by this ref-name endpoint. Parent/child pipelines with the same job name are searched parent-first. These semantics make ref lookup unsuitable for binding an authorization to the supplied job or SHA. Job-ID downloads avoid that moving selection, but do not themselves assert aggregate pipeline success. [S22]

**Documented fact:** `expire_in` starts when artifacts are uploaded; omitted expiry uses the instance default. Latest-artifact retention/Keep settings can override expiry and cleanup is asynchronous. Current GitLab documentation has evolving latest-pipeline retention behavior; verify the installed version and settings instead of promising a precise deletion time. Artifacts can also be deleted. [S23][S24][S22]

**Recommendation:** retain the reported 30-day GitLab configuration only if it exceeds maximum handoff delay. Once accepted, set explicit ADO retention appropriate for delayed authorization, audit and rollback. A job ID is an identity, not permanent storage. Missing/expired/deleted files must fail closed—never switch to branch `latest` or rebuild a supposedly identical candidate.

### 5.3 Keep the existing read credential separate

**Documented facts:**

- Access tokens can be sent using the recommended `PRIVATE-TOKEN` header. `read_api` is API-read scope; `read_repository` is Git-over-HTTP/repository-files access, not a replacement for general Jobs/Pipelines/Artifacts API reads. `api` adds broad read/write API capability. [S25][S26]
- Project token bot permissions depend on **both role and scope**. Project tokens are available with any license on Self-Managed, while GitLab.com requires Premium/Ultimate. Internal-project visibility is an important exception to simplistic “this token can read absolutely nothing else” claims. [S27]
- Private pipeline/artifact visibility and `artifacts:access`/older `artifacts:public` settings affect who can download. Reporter plus `read_api` is a defensible baseline for this reported project, **not an unconditional promise for every artifact ACL**. [S28][S24]

**Recommendation:** retain the reported project token with `read_api` and Reporter, verify the new pipeline GET and all existing GETs on the installed GitLab, and grant no write scope merely to poll for success. Store it only in the VM1 Fetch job's protected secret context, not in the GitLab manifest or VM2's application payload. Test cross-project denial, write denial, expiry and rotation. The paid-tier note beside artifact API `job_token` options is about that token/multi-project use case, not a claim that all job-artifact GETs require a paid tier. [S22][S25–S28]

Do **not** forward the notify job's `CI_JOB_TOKEN` as ADO's asynchronous fetch credential. It is valid only while that GitLab job is running and is revoked when it finishes—exactly when the success handshake needs the notifier to exit. The token also has a restricted endpoint set, not the same privileges as the existing read token. [S38]

## 6. Build Queue API and external Git: supported alternatives, not this POC's new path

### 6.1 Queue by fixed build definition ID

**Documented fact:** Build Queue accepts a build `definition` reference, `parameters` as a **string**, `sourceBranch`, `sourceVersion`, and other fields. Its `queue` field is deprecated and is not the selector for all job queues. Use the fixed **definition ID**, not a display name, build ID or pool queue ID. `Definitions – List` supports name/path filtering and returns definition IDs; resolve and verify the intended definition administratively, rather than choosing the first matching name on every event. [S07][S08]

```http
POST {collectionBase}/{project}/_apis/build/builds?api-version=7.0
Authorization: Basic <base64(:ADO_PAT)>
Content-Type: application/json

{
  "definition": { "id": 42 },
  "parameters": "{\"GitLabPipelineId\":\"12345\",\"GitLabBuildJobId\":\"23456\"}"
}
```

This illustrates the legacy variable/parameter-string contract; it is **not** the current Runs `templateParameters` request. Use a JSON serializer, not shell-built JSON interpolation. A successful queue response is a Build, not proof its tasks completed. Use the corresponding Server 5.0/6.0 reference if needed; the current reported YAML handoff should retain Runs 7.0 until there is an identified reason to change. [S07]

### 6.2 Queueing does not pin an arbitrary external checkout

**Documented facts:** Build Queue describes `sourceBranch`/`sourceVersion` as the build's source branch/version. ADO defines `Build.SourceBranch` and `Build.SourceVersion` relative to the **triggering repository**. Runs separately exposes repository resource `refName` and `version`. [S07][S18][S04]

**Implications / recommendations:**

- In the reported artifact-import YAML pipeline, the ADO orchestration repository/version and the GitLab **application** SHA are different identities. Pass the GitLab SHA as candidate metadata and verify it through GitLab/manifest; do not put a GitLab-only SHA into the ADO YAML repository's `sourceVersion`/`self.version` and expect it to download the artifact.
- In a hypothetical script-clone pipeline, queueing a SHA is not magic plumbing into `git clone`. A script must explicitly fetch and detach-checkout the requested commit and verify its result. This is **not recommended as a change to this POC**.
- In a Classic definition with native **Other Git** sources, `sourceVersion` relates to that configured source provider. The REST schema alone does not prove arbitrary-SHA fetch behavior for a particular private GitLab/shallow-fetch/Server combination; test it if that alternative is ever chosen.
- Never use `Build.SourceVersion` as the GitLab status callback SHA unless GitLab really is that triggering source. Keep an explicit validated `GitLabCommitSha` in the candidate record. [S18]

### 6.3 Native GitLab repository limitations

**Documented facts:**

- Microsoft documents an **Other Git service connection** with external repository URL and username/password/token. Its Classic-source route is distinct from native YAML repository support; Microsoft's Other Git fallback example explicitly permits only Classic build and no CI/PR trigger when server-side access is disabled. [S14][S15]
- The YAML repository schema lists `git`, `github`, `githubenterprise`, and `bitbucket`; **`type: git` means Azure Repos Git, not any Git URL**. GitLab/`othergit` is not a documented YAML resource type. Server multi-repo checkout is documented as limited to Azure Repos Git in the same organization/collection. [S16][S17]
- Microsoft's external Git guidance says inaccessible/private-network Other Git does not support the automatic CI-trigger path and supports manual/scheduled starts; a self-hosted agent's clone connectivity is different from the service's ability to reach the repository. Do not turn that cloud-oriented network wording into a requirement to publish an internal GitLab instance to the internet. The explicit REST bridge avoids depending on automatic repository detection. [S14][S15]
- The repository-support table lists providers individually; the fact Services supports a provider does not establish Server support. A generic service connection is not evidence of a first-party GitLab YAML or GitLab CI artifact provider. [S13–S17]

**Recommendation:** use a protected ADO orchestration repository plus GitLab job-ID artifact download. An Other Git connection, re-clone or mirrored application repository is unnecessary for the current handoff.

## 7. ADO → GitLab commit status: optional, explicit, and potentially cyclic

**Documented fact:** GitLab's official Commits API provides this external-status operation: [S40]

```http
POST https://gitlab.example/api/v4/projects/{P}/statuses/{validatedGitLabSha}
PRIVATE-TOKEN: <separate status-writer token>
Content-Type: application/json

{
  "state": "success",
  "name": "ado/candidate-import",
  "ref": "<validated source ref>",
  "pipeline_id": 12345,
  "target_url": "https://ado.example/<collection>/<project>/_build/results?buildId=6789",
  "description": "Exact GitLab artifact imported and verified"
}
```

`state` is required and supports `pending`, `running`, `success`, `failed`, `canceled`, `skipped`. `name`/`context` distinguishes the check; `pipeline_id` selects among pipelines sharing a SHA; `ref` identifies the branch/tag; `target_url` links back to ADO. Successful creation returns **201**. Concurrent SHA/ref updates can return **409**, which the API says to retry; explicitly selecting an over-limit pipeline can return **422**. Confirm field availability against the installed GitLab version. [S40]

**Documented fact:** external statuses are jobs in an **external stage**. GitLab appends them to a suitable existing pipeline, or creates an `external`-source pipeline if none is suitable. Omitting a pipeline ID can attach a status to an unexpected duplicate pipeline. Job update/retry behavior depends on name, user and SHA; this is not simply arbitrary replacement of the pipeline's aggregate status field. [S40][S41]

**Security:** keep the Fetch `read_api` token read-only. Posting status needs a separate write-capable credential, such as a project token with `api` scope and an appropriately authorized bot role; validate the actual minimum role on the installed endpoint. `write_repository` is not general API-write scope. `CI_JOB_TOKEN`'s documented Commits API access does **not** include `POST /projects/:id/statuses/:sha`, and it is short-lived in any case. Do not claim the existing two-secret runtime design already includes status-write capability. [S25–S27][S38]

**Inference / recommendation:** adding `pending`/`running` external ADO status jobs to the very GitLab pipeline that Fetch is waiting to become successful can introduce another circular dependency. GitLab documents that these statuses participate as pipeline jobs; test aggregate-state effects on the installed version. For the minimal POC, **omit callbacks**, or post only a clearly scoped final import result **after** upstream-success eligibility has been captured, without making that downstream result a prerequisite for its own upstream gate. Separate import and deployment contexts. A status saying “imported” must never imply “authorized” or “deployed.” Do not wait on the future ADO deployment—including human approval—in the notifying GitLab job. [S20][S40][S41]

If a future alternative manually clones GitLab in ADO, use the **verified checked-out GitLab commit** for this call. Neither that clone nor an Other Git connection automatically establishes native GitLab status integration. Microsoft's Git-source status documentation explicitly distinguishes provider support; custom status publication is still integration work. [S15][S18][S40]

## 8. Windows GitLab Runner: enough to build and notify, not production access

**Deployment clarification from the user:** the actual GitLab Server and GitLab Runners are **Linux-based**. The accompanying default `gitlab/gitlab-ci.example.yml` now uses `.sh` entry points plus Python 3.9+; no Windows GitLab Runner or PowerShell installation on Linux is needed. The `.ps1` importer/consumer still executes on the Windows ADO agents. This section is retained as background for an alternative Windows CI runner, **not the deployment instructions for this environment**; follow the [current runbook](../runbooks/gitlab-ado-integration.md).

**Documented facts:** Windows Runner requires Git and a runner executable; GitLab documents registering it, installing/starting a Windows service, restricting write permissions on its directory/executable, and viewing logs in Windows Event Log. A custom service account needs a password and **Log on as a service**. [S34]

For a version supporting the current authentication-token workflow, the setup shape is:

```powershell
# Administrator setup session; obtain the token securely, never commit it.
.\gitlab-runner.exe register --url "https://gitlab.example" `
  --token "$env:RUNNER_AUTH_TOKEN" --executor "shell" `
  --description "windows-ci-handoff"
# Configure the reviewed service identity, then install/start the service.
.\gitlab-runner.exe install
.\gitlab-runner.exe start
```

The last two lines are GitLab's default built-in-System service example, **not a recommendation to run arbitrary application builds as SYSTEM on VM1**. Select a dedicated least-privilege Windows service account where feasible, using GitLab's documented custom-account install option without leaving passwords in committed files or logs. Pin a tested runner version rather than assuming the latest binary is compatible with the installed GitLab. [S34][S36]

**Documented fact:** current runner creation uses a runner authentication token (`glrt-`), saved with configuration in `config.toml`; legacy registration tokens and some CLI configuration flags are deprecated. Use the installed GitLab's supported workflow, and set server-side project scope, tags and protection in the proper UI/API rather than assuming legacy flags work with a new authentication token. [S35][S37]

**Recommended runner settings:**

- Dedicated project runner; tag such as `windows-ci-handoff`; matching CI job `tags`; disable untagged jobs. A runner must have **all** tags requested by a job. Tags route work; they are not a security authorization mechanism. [S37]
- Set the runner **Protected**, use protected delivery refs, and explicitly review any MR access to protected runners/variables. Store the ADO PAT as masked/protected CI secret, but do not treat masking as protection against malicious CI code. [S37][S39]
- Use `executor = "shell"` and explicitly choose an installed PowerShell shell (`powershell` or supported `pwsh`) in `config.toml`. Install build dependencies under the service account's execution context. Shell jobs run locally with the runner user's permissions and have limited isolation. [S36]
- Protect runner binary/configuration/workspaces and credential material; no production filesystem/share/service credentials. Do not install this GitLab CI runner on VM2. If hosted on VM1 beside the ADO Server/agent, do not claim process/work-directory separation is strong isolation: a privileged shell job can compromise that host. Prefer an isolated CI runner for production use; a trusted-code two-VM POC must document the co-hosting risk. [S34][S36][S37]

### Private source checkout inside GitLab CI

**Documented fact:** GitLab's job token can clone a private project during a running job using username `gitlab-ci-token` and the job token as the HTTPS password. It inherits the triggering user's access level, with a restricted resource set. Cross-project access normally requires the source project/group in the **target project's job-token allowlist** and the triggering user's required target permissions; an allowlist is not a grant of user membership. [S38]

**Recommendation:** use Runner's normal authenticated source checkout for the application's own GitLab job; do not add a long-lived clone PAT merely to build a private project. If a build genuinely needs another private repository, verify its membership/allowlist and never log the credential-bearing clone URL. This source-checkout permission does not replace ADO's persistent `read_api` artifact-reader credential. [S37][S38]

## 9. Push mirroring: availability correction, not the recommendation

**Documented facts:** GitLab push mirroring is listed for **Free, Premium and Ultimate**, including Self-Managed. It is incorrect to say all push mirroring requires Premium. **Pull** mirroring and regex **Mirror specific branches** have Premium/Ultimate conditions. The docs describe generic Git destinations, HTTP(S)/SSH URLs, credentials/host-key verification, update delay, divergence/overwrite behavior, and a maximum of ten enabled push mirrors per project. They do not establish a dedicated native Azure DevOps Server Express connector or this installation's connectivity. [S42][S43]

**Implications / recommendation:** a push mirror to Azure Repos would need GitLab-server-to-ADO network reachability and a write-authorized destination credential; a runner reaching the Runs API does not prove that path. Mirroring copies Git refs/commits, **not GitLab CI job artifacts or success/authorization evidence**. It adds synchronization, credential and divergence handling and does not solve the final-job race. Retain it only as a separately justified future option, not as a prerequisite or pivot for the working ZIP/manifest handoff. [S42][S43]

## 10. Permissions and deployer-only manual authorization

### 10.1 Separate trigger, read, administration and production identities

**Documented facts:** Server supports Windows authentication/.NET client libraries or PATs; the cloud OAuth/Entra app-auth advice is not a general Server replacement. PATs use HTTP `Basic base64(:PAT)`; **IIS Basic Authentication must remain disabled** for Server PAT authentication. A PAT cannot grant more permission than its owner. [S09][S10]

Build execute scope (`vso.build_execute`, Build Read & execute) includes queueing **and** build-result/artifact/definition capabilities; it is not a single-definition capability token. `Queue builds`, `View builds`, and `View build definition` are separate ACL permissions, with definition-level configuration and inheritance. [S07][S11]

**Recommended effective access matrix**—test both allows and denies, not merely PAT scope:

| Principal | Allow | Must not acquire |
|---|---|---|
| GitLab CI trigger identity/PAT | Necessary view/queue on the fixed handoff pipeline only | Pipeline/repository edit, permission management, check edit/bypass/approval, other pipeline queue, VM2 OS/share/service access |
| VM1 Fetch credential | Fixed GitLab project API reads/artifact downloads | Git/API writes or a requirement for production credentials |
| ADO orchestration/resource administrators | Controlled YAML/scripts, variable groups, agent/resource configuration | Unreviewed changes that create an ungated VM2 route |
| Deployer group | View exact candidate and manually authorize the approved application/environment/candidate | Implicitly authorizing a different candidate or target |
| VM2 deployment-agent OS identity | Only required local application/file/service operations after authorized dispatch | General CI-build service or unrestricted shared administrator credential |

Avoid inherited broad group grants for the trigger identity; validate project/folder/definition ACLs and explicit denies. A safe request generated by CI is not sufficient if the same credential can directly invoke another pipeline or alternate source/resource configuration. [S11][S04]

### 10.2 YAML environments are a supported direction, but checks must be verified

**Documented fact:** the **Server 2022** Environments page explicitly describes manual approval checks for production, security for users **and pipelines**, and resource owners controlling stage consumption. Server VM-resource documentation describes registering an agent and targeting a named `virtualMachine` resource. Therefore a categorical “Server/Express has no YAML Environments or environment approvals” claim is not justified. [S29][S31][S01]

Microsoft's approvals page explains that checks live **outside YAML** and are evaluated before a stage consumes resources; designated approvers can allow or reject a run, self-approval can be configured, and resource administrators can bypass checks. The page's current overall banner says Services while several relevant sections explicitly include Server monikers; use the explicit Server environment guidance plus installed-build tests, **not the assumption that every listed advanced check is available on every Server build**. [S30][S29]

**Recommendations:**

1. Keep the current YAML environment approach if package inspection and installed-build tests confirm it. Restrict the production environment/resource to the reviewed pipeline, and put approval at the production-consuming **stage**, not only an inline “please confirm” script. [S29–S31]
2. Approvers are only the authorized Deployer group; permit one authorized Deployer to approve their own requested deployment if that matches the glossary. Do not accidentally require an unrelated second approver. [S30]
3. Audit who can **change, disable or bypass** the check as well as who can approve. The current Environments page says Creator/Administrator/User roles can manage approvals/checks; do not assume a broadly assigned User role is harmless or that only Administrators can edit checks. Verify effective behavior on the installed build. [S29][S30]
4. VM1 may automatically fetch/verify/store candidates, but must not write any candidate bytes to production VM2 before authorization—not even to an agent staging directory or share. Only the gated production stage may dispatch the VM2 job and download its artifact. This is the repository's governance requirement; verify actual job/artifact-download timing, not just the presence of `environment:` in YAML.
5. Approval is for the displayed application + target + **exact candidate/job/hash/ADO run**. Changing candidate or target requires new authorization. Denial, no response, check timeout, failed Fetch and an accepted CI POST must never authorize deployment.

**Unknown:** no current check configuration, approver membership, bypass ACL, pipeline allowlist, pool route or VM2 write-timing evidence was inspected. A configured approval gate can allow the stage to continue automatically **after human authorization**; that is different from automatic production authorization. If the installed gate cannot enforce the boundary, do not enable production deployment until an independently verified deployer-controlled gate exists.

## Official source index

All references below are first-party documentation. Server-specific REST references are preferred where available. GitLab documentation is rolling; reselect version-matched documentation during implementation. Citation ranges such as `[S20–S22]` refer to the corresponding entries below.

- **[S01]** Microsoft, Server installation / Express feature and license statement: https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-2022
- **[S02]** Microsoft, REST overview, Server collection URI and API/build mapping: https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.0
- **[S03]** Microsoft, REST versioning and supported Server versions: https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rest-api-versioning?view=azure-devops-2022
- **[S04]** Microsoft, **Server Runs – Run Pipeline 7.0**: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-server-rest-7.0
- **[S05]** Microsoft, **Server Runs 6.0 reference**, specifying `6.0-preview.1`: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-server-rest-6.0
- **[S06]** Microsoft, Server Runs – Get 7.0: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/get?view=azure-devops-server-rest-7.0
- **[S07]** Microsoft, Server Builds – Queue: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-server-rest-7.0 ; version-specific alternatives: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-server-rest-6.0 and https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-server-rest-5.0
- **[S08]** Microsoft, Server Build Definitions – List 7.0: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/definitions/list?view=azure-devops-server-rest-7.0
- **[S09]** Microsoft, PAT authentication, ownership permissions and Server IIS caveat: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022
- **[S10]** Microsoft, Server versus Services authentication: https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/authentication-guidance?view=azure-devops-2022
- **[S11]** Microsoft, permissions reference / build-definition ACLs: https://learn.microsoft.com/en-us/azure/devops/organizations/security/permissions?view=azure-devops-2022
- **[S12]** Microsoft, secure pipeline inputs / queue variables and parameters: https://learn.microsoft.com/en-us/azure/devops/pipelines/security/inputs?view=azure-devops-2022
- **[S13]** Microsoft, repository-provider support table: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/?view=azure-devops-2022
- **[S14]** Microsoft, Other Git service connections: https://learn.microsoft.com/en-us/azure/devops/pipelines/library/service-endpoints?view=azure-devops-2022#other-git-service-connection ; explicit Classic Other Git fallback: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/github-enterprise?view=azure-devops#not-reachable-from-azure-pipelines
- **[S15]** Microsoft, Git source options, external triggers and build-status provider behavior: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/pipeline-options-for-git?view=azure-devops-2022
- **[S16]** Microsoft, repository YAML schema and meaning of `type: git`: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/resources-repositories-repository?view=azure-pipelines-2022
- **[S17]** Microsoft, Server multi-repo checkout limitation: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/multi-repo-checkout?view=azure-devops-2022
- **[S18]** Microsoft, predefined source variables: https://learn.microsoft.com/en-us/azure/devops/pipelines/build/variables?view=azure-devops-2022#build-variables
- **[S19]** GitLab, Projects API: https://docs.gitlab.com/api/projects/#retrieve-a-project
- **[S20]** GitLab, Pipelines API: https://docs.gitlab.com/api/pipelines/#retrieve-a-single-pipeline
- **[S21]** GitLab, Jobs API / job detail, pagination and retries: https://docs.gitlab.com/api/jobs/
- **[S22]** GitLab, Job Artifacts API / job-ID versus ref lookup: https://docs.gitlab.com/api/job_artifacts/
- **[S23]** GitLab, job artifacts and retention: https://docs.gitlab.com/ci/jobs/job_artifacts/
- **[S24]** GitLab, YAML semantics (`when`, `needs`, artifacts expiry/access): https://docs.gitlab.com/ci/yaml/
- **[S25]** GitLab, REST authentication: https://docs.gitlab.com/api/rest/authentication/
- **[S26]** GitLab, token scopes: https://docs.gitlab.com/security/tokens/access_token_scopes/
- **[S27]** GitLab, project access tokens / offerings, bot role and Internal visibility caveat: https://docs.gitlab.com/user/project/settings/project_access_tokens/
- **[S28]** GitLab, pipeline visibility: https://docs.gitlab.com/ci/pipelines/settings/#change-which-users-can-view-your-pipelines
- **[S29]** Microsoft, **Server Environments**, manual approvals and user/pipeline security: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments?view=azure-devops-2022
- **[S30]** Microsoft, approvals/checks and bypass semantics; inspect feature monikers: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals?view=azure-devops-2022
- **[S31]** Microsoft, **Server environment VM resources**: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-virtual-machines?view=azure-devops-2022
- **[S32]** Microsoft, Publish Build Artifacts task / Container: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines-2022
- **[S33]** Microsoft, Pipeline Artifacts task / on-premises warning and YAML shortcuts: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines-2022
- **[S34]** GitLab, Windows Runner installation/service/security: https://docs.gitlab.com/runner/install/windows/
- **[S35]** GitLab, runner registration/authentication-token workflow: https://docs.gitlab.com/runner/register/
- **[S36]** GitLab, Shell executor and security: https://docs.gitlab.com/runner/executors/shell/
- **[S37]** GitLab, runner protection, tags and authentication-token security: https://docs.gitlab.com/ci/runners/configure_runners/
- **[S38]** GitLab, job-token lifetime, endpoint permissions, private cloning and allowlist: https://docs.gitlab.com/ci/jobs/ci_job_token/
- **[S39]** GitLab, CI secret-variable security: https://docs.gitlab.com/ci/variables/#cicd-variable-security
- **[S40]** GitLab, Commits API / set commit pipeline status: https://docs.gitlab.com/api/commits/#set-commit-pipeline-status
- **[S41]** GitLab, external commit-status pipeline selection/update behavior: https://docs.gitlab.com/ci/ci_cd_for_external_repos/external_commit_statuses/
- **[S42]** GitLab, repository mirroring and tier-specific features: https://docs.gitlab.com/user/project/repository/mirror/
- **[S43]** GitLab, push mirroring availability, updates and limits: https://docs.gitlab.com/user/project/repository/mirror/push/

## 11. Implementation implications

1. **Preserve the current architecture:** GitLab build → final CI notification → fixed **Runs 7.0 / `templateParameters`** → VM1 artifact Fetch → gated YAML deployment to VM2. No application-source re-clone, push mirror, or Classic migration is required. [S04][S22][S29–S32]
2. **First correctness change:** confirm/add an exact-pipeline GET and bounded success wait in Fetch; make notify exit after receiving/persisting the ADO run ID. Keep mandatory-job success checks distinct from aggregate success. Test the failure-after-POST race before calling the handoff reliable. [S20][S21][S24]
3. **Keep exact bytes:** packaging job ID, manifest, GitLab SHA and ZIP hash must correlate to the imported ADO run and the authorized deployment. Missing/expired artifacts fail closed. Never substitute branch `latest`. [S21–S24]
4. **Keep two external integration secrets unless callbacks are deliberately added:** narrowly ACL-bound ADO Build Read & execute PAT for notification; GitLab project `read_api` token for Fetch. Optional status callbacks need separately approved write capability, and must not create a success-gate cycle. [S07][S09][S11][S26][S38][S40][S41]
5. **Prove the authorization boundary:** record Deployer membership, check editors/bypass users, environment/pipeline allowlist, VM2 agent routes and negative REST tests. No production dispatch or file copy before authorization. A queued run, GitLab success or an external status is not authorization. [S29–S31]
6. **Version/acceptance evidence before rollout:** obtain installed Server/GitLab/agent/task versions; verify Runs 7.0, Build Artifacts, environment approval behavior, queue-input restrictions, private artifact reads and credential rotation on that exact build. Do not infer product version from the API string or a research date. [S02–S05][S12][S22][S29][S32][S33]
