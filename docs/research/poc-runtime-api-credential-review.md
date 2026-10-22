# POC 執行期 API、憑證與產品支援邊界審查

研究日期：**2026-10-22**（執行環境 `date -Iseconds`：`2026-10-22T15:33:52+08:00`）。

## 0. 證據邊界與簡報結論

本研究僅閱讀整合包的文件／source，並查閱 Microsoft Learn 與 GitLab 官方文件；**沒有重跑 pipeline、呼叫現場 API、驗證 token、檢查即時 ACL 或重新實測**。不研究 Azure DevOps Express 授權。以下省略所有現場主機位址、個人帳號、實際 namespace 與 token 值；URL 僅列官方文件，API 路徑使用 placeholder。

證據標示：

- **I（實作）**：source 可直接確認的呼叫、header、YAML 與邏輯；不是執行成功證明。
- **R（現場記載）**：整合包文件或委託方已確認的設定／歷史操作；本次未重新稽核。
- **D（產品文件）**：官方對 API、角色、版本或功能的說明；不是對此現場組合的測試報告。
- **U（待確認）**：正式導入前仍需取得的版本、ACL、設定或驗收證據。

**跨部門可用摘要：**

1. 對外執行期有兩組整合 secret：GitLab CI → ADO 的 **Build Read & execute PAT／Basic**；ADO Fetch → GitLab 的 **project access token、`read_api`、Reporter／`PRIVATE-TOKEN`**。Rollback Plan 使用 **`System.AccessToken`／Bearer**，不是第三個長效 PAT（C1–C8）。
2. 目標 VM 曾以一日 Full access PAT 註冊是 **R**；agent 後續使用 agent/listener credentials 與短效 job token，而非持續使用註冊 PAT。不能因此說 Full access 是最低需求，也不能把「All accessible organizations」誤認為 Full access（C10–C11）。
3. ADO 使用 **Server Build Artifacts，Container**，不是 Pipeline Artifacts。API `7.0` 的官方基線為 Server 2022；task 是否隨該 build 提供仍要另外確認，尤其 `DownloadBuildArtifacts@1` 文件版本範圍（C9、C12）。
4. GitLab Self-Managed Free 可使用這些基本 API／project token／protected branch；**required MR approval、Code Owner approval enforcement 是 Premium／Ultimate 功能**。Masked/protected 變數仍可能被可執行惡意 CI 的人竊取，不能宣稱已自動強制 CI 審查（C5、C14–C16）。
5. **Scope 不等於 resource ACL，更不是管理權限。** 排隊、讀歷史、使用環境、修改 checks、註冊 agent 與操作 Windows 各有不同授權面（C2、C8、C10、C13）。

### 已閱讀的整合包依據

以下路徑均相對於整合包根目錄：

| 代號 | 來源 | 本次用途 |
| --- | --- | --- |
| S1 | `docs/03-API-AND-INTEGRATION-CONTRACT.md` §§3.1–3.4、3.6 | scope／角色、建置與執行期區隔、註冊歷史、Container 記載 |
| S2 | `source/gitlab-project/.gitlab-ci.yml`：`workflow`、`trigger-ado` | POST、Basic header、API version、template parameters、branch 條件 |
| S3 | `source/ado-repo/scripts/Get-GitLabRelease.ps1` | 四個 GET、`PRIVATE-TOKEN`、來源與產物一致性檢查 |
| S4 | `source/ado-repo/scripts/Plan-Rollback.ps1`：`Api`、`Stage-Succeeded`、`$builds` | Build List／Timeline、Bearer、200 筆歷史視窗、測試模式例外 |
| S5 | `source/ado-repo/azure-pipelines.yml`：Fetch／Deploy | variable group、Publish／Download Build Artifacts、Container |
| S6 | `source/ado-repo/rollback/azure-pipelines-rollback.yml`：Plan | `SYSTEM_ACCESSTOKEN: $(System.AccessToken)`；未引用 GitLab secret group |

## 1. GitLab CI → ADO pipeline

### C1. POST Run Pipeline、參數契約與 Basic 認證相符

- **主張／I、R：** S2 由 manifest 組出 `templateParameters`，POST `{collection}/{project}/_apis/pipelines/{pipelineId}/runs?api-version=7.0`。Header 為 `Authorization: Basic base64(":" + PAT)`。S1 記載專用非管理觸發身分，PAT 為 Build Read & execute。
- **D／官方 URL 與短引用：**
  - [Runs – Run Pipeline，7.0](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.0)：`POST .../_apis/pipelines/{pipelineId}/runs?api-version=7.0`；request body 列 `templateParameters`；Security：**“Personal access token.”**、**“Type: basic”**。
  - [Use personal access tokens，Server 2022](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022)：**“The username can be empty.”**、**“Base64-encode the string `:{PAT}`”**。
  - [REST API overview／Server URI](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.0)：Server instance 格式為 **“`{server:port}/tfs/{collection}`”**。
- **文件範圍：** API reference 使用 Services URL 範例；Server collection base URL 另由官方 overview 支持，並須符合 C12 版本矩陣。Basic 是 HTTP header 形式，不代表要開啟 IIS Basic Authentication；同一 PAT 文件明示 Server 應保持 IIS Basic Authentication 關閉。
- **U：** 未檢查現場反向代理、TLS、IIS 設定或 token 目前是否有效；不能把靜態 POST 視為本次重新成功觸發。

### C2. `vso.build_execute` 支持排隊，但 Readers／QueueBuilds 是另一層

- **主張／R：** S1 記載 Build (Read & execute)、`vso.build_execute`，觸發身分使用 project Readers 加指定 pipeline 的 QueueBuilds；這是現場授權組合，不是「持有 PAT 就有所有 pipeline 排隊權」。
- **D／官方 URL 與短引用：**
  - [Microsoft scope 定義](https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/oauth?view=azure-devops)：`vso.build_execute` 對應 **“Build (read and execute)”**，包含 **“the ability to queue a build”**，並繼承 `vso.build`。
  - [Permissions reference，Server 2022](https://learn.microsoft.com/en-us/azure/devops/organizations/security/permissions?view=azure-devops-2022)：**“Queue builds `Build, QueueBuilds`”**；**“View builds `Build, ViewBuilds`”**；**“View build definition `Build, ViewBuildDefinition`”**。
  - [PAT prerequisites](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022)：**“A PAT can't grant more permissions than its owner has.”**
- **文件範圍：** scope 定義頁在 OAuth 章節，這裡僅引用 scope 名稱／能力，不宣稱 Server 可使用該頁的外部 OAuth app flow。7.0 Run Pipeline 頁直接列 Basic PAT，未逐一列 scope；「現場採 Build Read & execute」由 S1 支持，scope 能力由官方表交叉支持，**不是 endpoint 最低 scope 的負向測試證明**。Readers 是一種授權配置，不是官方對此 endpoint 唯一強制群組。
- **U：** 應留存觸發身分的有效 project／pipeline ACL、繼承、群組與拒絕設定，以及無權 pipeline 的負向驗收；確認沒有 Edit pipeline、Manage permissions、環境管理等不必要權限。`vso.build_execute` 本身也不是僅能 POST 某一支 pipeline 的單用途 scope。

## 2. ADO Fetch → GitLab：四個 GET 與讀取憑證

### C3. G1：讀 project，釘選來源與 default branch

- **主張／I：** S3 以 `PRIVATE-TOKEN` GET `/api/v4/projects/:id`，比較 `path_with_namespace`，取得 `default_branch`；沒有 clone repository。
- **D／官方 URL 與短引用：** [Projects API – Retrieve a project](https://docs.gitlab.com/api/projects/#retrieve-a-project)：**“`GET /projects/:id`”**；response attributes 列 **“`path_with_namespace`”**、**“`default_branch`”**。
- **文件範圍：** endpoint 與欄位是產品 API；private project 的可見性、token scope／角色仍要滿足 C5–C6。公開 project 的匿名讀取能力不能反推 private project 不需權限。
- **U：** 未核對現場釘選值、可見性與實際 response；default branch 可被有管理能力的人變更，這項比較不等於不可變的 CI 審核政策。

### C4. G2：讀指定 job，而不是只信任外部傳入的 SHA

- **主張／I：** S3 GET `/api/v4/projects/:id/jobs/:job_id`，檢查 job `name=build`、`status=success`、`ref=default_branch`、非 tag、`pipeline.id` 與 `commit.id`。
- **D／官方 URL 與短引用：** [Jobs API – Retrieve a job by job ID](https://docs.gitlab.com/api/jobs/#retrieve-a-job-by-job-id)：**“Retrieve a job with a specified job ID.”**、**“`GET /projects/:id/jobs/:job_id`”**；官方 response 示例包含 `commit`、`pipeline`、`ref`、`tag`、`name`、`status`。
- **文件範圍：** Jobs API 標示 Free／Premium／Ultimate、Self-Managed。官方支持讀取 job；上述「必須是本 POC build/default branch」是 S3 自訂驗證，不是 GitLab endpoint 自動替外部 CD 強制的規則。
- **U：** 未核對目前 CI job 命名、權限與 response；需保護可修改 CI／default branch 的管理面。來源檢查不能辨識已獲授權執行的惡意 build。

### C5. G3／G4：依 job ID 讀取兩個單檔 artifact；Reporter 有條件成立

- **主張／I、R：** S3 GET `/api/v4/projects/:id/jobs/:job_id/artifacts/out/site.zip` 及同一路徑的 `out/manifest.json`；S1 記載 `read_api` + Reporter。S2 僅設 `artifacts.paths: [out/]` 與 `expire_in: 30 days`，未設更高角色的 `artifacts:access`。
- **D／官方 URL 與短引用：**
  - [Job Artifacts API – single file by job ID](https://docs.gitlab.com/api/job_artifacts/#download-a-single-artifact-file-by-job-id)：**“`GET /projects/:id/jobs/:job_id/artifacts/*artifact_path`”**、**“extracted from the archive and streamed to the client”**；頁面 Tier 包含 Free。
  - [Pipeline visibility](https://docs.gitlab.com/ci/pipelines/settings/#change-which-users-can-view-your-pipelines)：限制可見性時，private project 的 pipelines／相關功能為 **“project members (Reporter or higher) only”**。
  - [YAML `artifacts:access`](https://docs.gitlab.com/ci/yaml/#artifactsaccess)：**“determine who can access the job artifacts from the GitLab UI or API”**；`developer`、`maintainer`、`none` 可進一步限制。
- **文件範圍：** 支持使用 Reporter 作此私有專案讀取基線，**不支持「所有 GitLab 設定下 Reporter 必定可下載」**。舊 `artifacts:public: false` 也可排除 Reporter；project CI/CD 可見性與 artifact 存在／保留狀態仍有影響。此 POC 用的是 project access token，不是 `job_token`；API 頁中 multi-project job token 的付費註記不能套到所有 artifact GET。
- **U：** 需以現場 GitLab 精確版本、可見性與 artifact ACL 驗收四個 GET；若正式 CI 改成 `developer`／`maintainer`，應重設交付設計，而不是不經審查就提高 token 角色。30 天是 YAML 設定，不能保證檔案恰好於第 30 天刪除或永久存在。

### C6. Project access token 的 `read_api` + Reporter 與 `PRIVATE-TOKEN` 有官方依據

- **主張／I、R：** S3 header 為 `PRIVATE-TOKEN`；token 的 project 類型、scope、角色由 S1／委託方確認，程式本身沒有 introspection 證明它是哪種 token。此四個 GET 不需要新增寫入 scope `api`；不 clone，不能用 `read_repository` 取代一般 Jobs／Artifacts API 的讀取授權。
- **D／官方 URL 與短引用：**
  - [REST API authentication](https://docs.gitlab.com/api/rest/authentication/#personal-project-and-group-access-tokens)：**“Pass the token using the `PRIVATE-TOKEN` header (recommended)”**。
  - [Access token scopes](https://docs.gitlab.com/security/tokens/access_token_scopes/)：`read_api` 為 **“Grants read access to the API for the token’s scope.”**；`read_repository` 使用 **“Git-over-HTTP or the repository files API”**。
  - [Project access tokens – bot users](https://docs.gitlab.com/user/project/settings/project_access_tokens/#bot-users-for-projects)：bot 權限 **“correspond with the role and scope of the associated access token”**。
  - [Project access tokens API](https://docs.gitlab.com/api/project_access_tokens/#create-a-project-access-token)：`access_level` 的 **“`20` (Reporter)”**，預設則為 `40`，建立時不可省略最小角色設定。
- **文件範圍：** scope 與 bot role 都要滿足，Reporter 不是 scope 的別名；`read_api` 也是專案 API 的廣泛讀取，不是僅能讀這四條路由的 artifact-only scope。官方 scope 描述與角色／artifact 文件支持這個設計，但本研究未重做最低權限測試。
- **U：** 應留存不含 secret 的 token metadata（類型、角色、scope、expiry）、輪替與撤銷紀錄；另驗收無法 push、無法寫 API、無法讀其他 private project。S1 提及 group access token 作替代，但 **group token 與單 project token 的授權邊界不同**，不能直接當作相同最小權限。

### C7. Self-Managed Free 可用 project token，但「絕對僅此 project」有例外

- **主張／D、R：** S1 的單 project token 選擇在 Self-Managed Free 有官方支持；不可誤用 GitLab.com 的付費條件，也不可把 project token 宣傳成無條件隔離所有其他專案。
- **D／官方 URL 與短引用：**
  - [REST authentication – supported offerings](https://docs.gitlab.com/api/rest/authentication/)：project token 支持 **“GitLab Self-Managed: Free, Premium, and Ultimate.”**；GitLab.com 為 Premium／Ultimate。
  - [Project access tokens](https://docs.gitlab.com/user/project/settings/project_access_tokens/)：Self-Managed **“available with any license”**；同頁警示 **“that token can access all projects that have visibility level set to Internal”**（internal user 建立的 token）。
  - [Activate EE](https://docs.gitlab.com/administration/license/)：**“without a license, only Free features are enabled”**。
  - [Official editions 說明](https://docs.gitlab.com/solutions/cloud/aws/gitlab_single_box_on_aws/)：**“Instances running on Community Edition (CE) require a migration to Enterprise Edition (EE)”** 才能訂閱 Premium／Ultimate。
- **文件範圍：** CE／EE 是發行 edition，Free／Premium／Ultimate 是功能層級，不能混稱；EE 無付費授權也可僅有 Free。基本 project token 的 Free Self-Managed 支持可作 CE 方案依據，但不代表付費治理功能也在 CE。官方 project token 頁同時描述 project scope 與 Internal visibility 例外，簡報應一併保留。
- **U：** 未重新確認現場 edition／version、token creator 是否 internal、其他專案是否 Internal；應用實際版本文件與可見性清單界定外洩半徑，而非宣稱零跨專案讀取風險。

## 3. Rollback Plan：ADO 內部 API 與 job token

### C8. Build List／Timeline 是執行期 GET，憑證為短效 job token

- **主張／I：** S4 呼叫：
  - `GET {collection}/{project}/_apis/build/builds?definitions={deployDef},{rollbackDef}&statusFilter=completed&$top=200&api-version=7.0`
  - `GET {collection}/{project}/_apis/build/builds/{id}/timeline?api-version=7.0`
  - S6 明確映射 `SYSTEM_ACCESSTOKEN: $(System.AccessToken)`；S4 用 `Authorization: Bearer ...`。只有 `PLAN_LOCAL_TEST=1` 且沒有 token 時，程式才允許 Windows default credentials；那是測試例外，不是正常 pipeline 另有 PAT。
- **D／官方 URL 與短引用：**
  - [Builds – List，7.0](https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-rest-7.0)：列 `definitions`、`statusFilter`、`$top`、`continuationToken`；讀取 scope 為 **“`vso.build`”**。
  - [Timeline – Get，7.0](https://learn.microsoft.com/en-us/rest/api/azure/devops/build/timeline/get?view=azure-devops-rest-7.0)：路徑為 `.../builds/{buildId}/timeline/{timelineId}`；`timelineId` **非 required**，scope 為 **“`vso.build`”**。
  - [Predefined variables](https://learn.microsoft.com/en-us/azure/devops/pipelines/build/variables?view=azure-devops-2022#systemaccesstoken)：**“In YAML, you must explicitly map `System.AccessToken`”**。
  - [PowerShell REST 示例](https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/powershell?view=azure-devops-2022#example-powershell-script-access-rest-api)：**`Authorization = "Bearer $env:SYSTEM_ACCESSTOKEN"`**。
  - [Job access tokens](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/access-tokens?view=azure-devops-2022)：**“dynamically generated ... for each job at run time”**；權限取決於 **“(a) job authorization scope and (b) ... project or collection build service account”**。
- **文件範圍：** 兩個讀 API 的 reference scope 可說明讀取能力，**不表示需要為 Rollback 發行 `vso.build` 長效 PAT**。job token 是 Azure Pipelines 自行發放，scope／ACL 由 job authorization 與 Build Service 身分決定。不能把該內部 OAuth job token 與「Server 不支援外部 OAuth app flow」混為一談。
- **U：** 未核對現場 job 是 project 還是 collection scope，亦未核對 Build Service 對兩支 definition 的 View builds／View build definition。應在不加 PAT 的前提下驗收讀取權限與 401／403 處理。

### C8a. 「可回滾歷史」目前只是 200 筆視窗，不是完整 inventory 或線上真相

- **主張／I：** S4 未追 continuation token；在所讀取紀錄中，檢查 Deploy／Rollback stage 的 timeline `result=succeeded`，再依 finish time 排序，推論目前 live 與可回滾候選。這是 POC 的篩選模型，不是 Microsoft 保證的完整部署真相。
- **D／官方 URL 與短引用：**
  - [Build List](https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-rest-7.0)：`$top` 是 **“The maximum number of builds to return.”**；`continuationToken` 用來 **“return the next set of builds”**；`statusFilter` 與 `resultFilter` 是不同欄位。
  - [Timeline](https://learn.microsoft.com/en-us/rest/api/azure/devops/build/timeline/get?view=azure-devops-rest-7.0)：record `identifier` 為 **“consistent across attempts”**，另有 `attempt`、`type`、`result`。
- **文件範圍：** `completed` 不等於成功部署；source 額外檢查 stage 是正確的區隔，但沒有分頁、retention／刪除、重跑 stage 與同步問題的完整保證。此處官方支持的是資料模型，不是 POC 的「live」演算法。
- **U：** 需設計超過 200 筆、歷史被刪除、stage retry／多 attempt、手動主機變更與並行部署的驗收；不得對簡報宣稱能列出所有歷史版本或已重新驗證真正線上版本。

## 4. Artifact 儲存、agent 註冊與執行期身分

### C9. 實作是 Build Artifacts／Container，不是 Pipeline Artifacts

- **主張／I、R：** S5 Fetch 執行 `PublishBuildArtifacts@1`，`publishLocation: Container`，之後用 `DownloadBuildArtifacts@1`、`buildType: current`。S1 記載 `release` 為 Container，包含 ZIP、manifest、verification。`Container` 是 ADO artifact 儲存類型，這裡不是 Docker container，也不是 GitLab registry。
- **D／官方 URL 與短引用：**
  - [PublishBuildArtifacts@1](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines)：**“Azure Pipelines (Container)”** 與 **“FilePath (A file share)”**；task 可發布到 Azure Pipelines／TFS／file share。
  - [DownloadBuildArtifacts@1](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/download-build-artifacts-v1?view=azure-pipelines)：**“download files that were saved as artifacts of a completed build”**；列 `buildType: current`。
  - [PublishPipelineArtifact@1](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines-2022)：**“This task is supported on Azure DevOps Services only.”**；Server 應 **“use Build Artifact Task instead”**。
- **文件範圍：** 支持 Server 選擇 Build Artifacts 的方向；文件對 Services 的 Pipeline Artifacts 效能建議不能直接套在地端 Server。task major version 是否存在仍見 C12。
- **U：** 本次未查實際 artifact metadata、存留政策、下載 ACL、task minor version 或 agent 版本；不能聲稱已實際重新上傳／下載或證明永久不可變。

### C10. 一日 Full PAT 是註冊歷史，不是 agent runtime credential

- **主張／R：** S1／委託方記載目標 environment VM 曾使用網頁註冊腳本及一日 Full access PAT；管理 pool agent 則記載使用 Windows 整合認證。這些是歷史記載，不是本次重新登入查證。
- **D／官方 URL 與短引用：**
  - [VM environment registration](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-virtual-machines?view=azure-devops-2022)：**“You need the PAT only to install the agent.”**；目前文件描述產生腳本的 token **“expires three hours after the script is generated”**。
  - [Agent PAT registration](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/personal-access-token-agent-registration?view=azure-devops-2022)：**“only at the time of registering the agent, and not for subsequent communication”**。
  - [Agents – Communication](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-2022#communication)：註冊後使用 **“listener OAuth token”**；取工作時取得 **“job-specific OAuth token”**，完成後 **“discards the job-specific `OAuth` token”**；並以註冊時交換的 public/private key 保護 job payload。
- **文件範圍：** 一日是現場 PAT 的歷史有效期；三小時是目前官方產生腳本的描述，不能改寫現場歷史。註冊 PAT、agent listener credentials、job token、Windows service account 是四種不同的身分／生命週期；撤銷註冊 PAT 不等於移除已註冊 agent 或解除主機執行能力。
- **U：** 需取得註冊 PAT 已撤銷／到期證據，以及 agent credentials 保護、主機 service identity、重註冊與移除流程；本次沒有檢查 agent credential 檔案或 token 值。

### C11. 不得把 Full access 或兩個猜測 scope 包裝成 VM 註冊的官方最低需求

- **主張／D、R：** S1 建議未來實測 Environment Read & manage／Agent Pools Read & manage；它不是已驗證的最低 scope 結論。Full scope 也不會讓無權身分自動取得 environment 或 deployment pool 管理能力。
- **D／官方 URL 與短引用：**
  - [PAT agent registration](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/personal-access-token-agent-registration?view=azure-devops-2022)：一般 agent 使用 **“Agent Pools (read, manage)”**；deployment group agent 為 **“Deployment group (read, manage)”**。同頁對 deployment group／VM resource 註冊錯誤另提 **“All accessible organizations”**。
  - [Environment VM prerequisites](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-virtual-machines?view=azure-devops-2022#prerequisites)：列 deployment pool **“Administrator role”**、project 的 **“Project Administrator or Build Administrator”** 權限及 Windows VM 的 **“PowerShell administrator permissions”**。
  - [Agents authentication](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-2022#authentication)：Windows Server agent 另有 **“Negotiate”**／**“Integrated”**；需 server 支持對應驗證方法。
- **文件範圍：** 文件區分一般 pool agent、classic deployment group agent 與 YAML environment VM。不能直接用其中一種的 scope 表當作所有版本 environment VM 的已證明最小組合；**All accessible organizations 是 PAT 的可用組織範圍，不是 Full access 的功能 scope 全選**。官方列的是操作前提，也不能據此斷言每個管理群組都是唯一最低 ACL。
- **U：** 要在指定 Server build／agent version 下，分別驗收最低 PAT scope、environment／deployment pool ACL、註冊者與本機管理權；`--auth negotiate` 在該 environment 註冊組合是否成立亦未重測。正式簡報宜寫「可評估 Windows 整合註冊；最低權限待驗收」。

## 5. 產品支援、版本與治理邊界

### C12. `api-version=7.0` 有 Server/build 基線，不能由 API version 反推現場產品 build

- **主張／I：** S2／S4 明確釘選 REST `7.0`。僅看到這個字串，不能宣稱已查明現場為哪個 Server update、patch 或精確 build；更不能說所有 Server 都支援。
- **D／官方 URL 與短引用：**
  - [REST API／Server build mapping](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.0)：**“compatible with the Server version listed, as well as Server versions that are newer”**。

    | 官方 Server mapping | REST API | 官方 build 基線 |
    | --- | --- | --- |
    | Azure DevOps Server 2019 | 5.0 | `>= 17.143.28621.4` |
    | Azure DevOps Server 2020 | 6.0 | `>= 18.170.30525.1` |
    | Azure DevOps Server 2022 | 7.0 | `>= 19.205.33122.1` |
    | Azure DevOps Server 2022.1 | 7.1 | `>= 19.225.34309.2` |

  - [REST API versioning](https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rest-api-versioning?view=azure-devops-2022)：**“API version must be specified with every request.”**；已發布 API 的 preview **“can be deactivated after 12 weeks”**。
  - [DownloadBuildArtifacts@1](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/download-build-artifacts-v1?view=azure-pipelines)：本次取得的官方頁面 syntax／requirements 版本範圍為 **`azure-pipelines-2022.1`、`2022.2`、`server`、Services**，未列初版 `2022`；requirements 為 **“Agent version ... 2.191.1 or greater”**。
- **文件範圍：** 矩陣是版本對應，不保證所有 task、preview endpoint、checks 路由與 response 行為都相同。Server 2020 不在 REST 7.0 支持範圍；較新 Server 可支持較舊 REST，不必因頁面預設 7.1／7.2 就升級 source 的 API version。**REST 7.0 基線也不能單獨證明 `DownloadBuildArtifacts@1` 在初版 2022 隨附可用**；需檢查實際 task catalog。S1 的建置期 `7.0-preview.*` 也不能由本報告的三條穩定 runtime API 自動背書。
- **U：** 導入驗收應留存 Server edition／精確 build／patch、agent version、兩個 task 的實際 major/minor，以及對應版本 API smoke test；本研究未取得這些即時資料。GitLab 官方站為滾動文件，也應另釘選現場 GitLab 版本，不把新功能或新 UI 名稱當作舊 CE 必然具有。

### C13. Scope、resource ACL、管理權與 OS 權限必須分欄列示

- **主張／綜合判讀：** 此 POC 的 runtime credential inventory 不能省略 resource ACL；「token 有 scope」既不代表使用環境已授權，也不代表可管理檢核規則或主機。
- **D／官方 URL 與短引用：**
  - [PAT prerequisites](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022)：**“A PAT can't grant more permissions than its owner has.”**
  - [Pipeline resource security](https://learn.microsoft.com/en-us/azure/devops/pipelines/security/resources?view=azure-devops-2022)：**“only specific users and pipelines ... can access protected resources”**；protected resources 列 environments、agent pools、repositories、secret variable groups。
  - [Environments – security](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments?view=azure-devops-2022#security)：**“user permissions and pipeline permissions”**；環境 approval/check 管理能力並不限於 Administrator，文件也列 Creator／User，Reader 不可。
  - [Project access token prerequisites](https://docs.gitlab.com/user/project/settings/project_access_tokens/)：建立 token 要有 **“Maintainer or Owner role”**；不等於 runtime bot 也要同樣高角色。
- **文件範圍／實作對照：**

  | 動作／生命週期 | 憑證與能力面 | 還需分開驗收的 ACL／管理面 |
  | --- | --- | --- |
  | GitLab 觸發 ADO（I、R） | Build Read & execute PAT／Basic | PAT owner 對指定 pipeline 的 QueueBuilds、讀取必要資訊；不能因此管理環境 |
  | ADO Fetch GitLab（I、R） | project token `read_api`／PRIVATE-TOKEN | bot Reporter、project／CI 可見性、artifact ACL |
  | Rollback Plan（I） | job token／Bearer | project／collection Build Service 的 build history 讀取權 |
  | ADO artifact task（I） | agent／job 認證流程 | pipeline 身分、artifact ACL、task 可用版本；source 沒有另傳長效 PAT |
  | environment／pool／variable group 使用（I、R） | runtime pipeline 的身分／資源授權 | user permission 與允許使用資源的 pipeline allowlist；checks 在資源管理面 |
  | 建置、改 ACL、設 checks、建 token（R） | S1 記載 bootstrap 管理憑證 | 管理者／resource owner 能力，不是 runtime 最小需求 |
  | VM 註冊與執行（R、D） | 註冊認證 → agent credentials／job token | 註冊 ACL、本機管理權、Windows service account／檔案與服務權限各自分開 |

- **U：** S5／S6 引用 environment 或註解說有 approval，**不是本次查證該 check／allowlist 目前存在**；需取得資源端設定。特別稽核誰能改 checks、variable group、CI、repo、agent pool 與 service account，不能只列「誰能按 Run」。本報告不判定 Express 功能／授權支持。

### C14. Masked／protected 不是對惡意 CI 的 secret 防外洩保證

- **主張／I、R：** S2 註解／S1 記載觸發 PAT 為 masked+protected；S2 workflow 僅允許 default branch 且排除 `merge_request_event`。source 可證明 branch 條件，不能證明變數旗標、branch ACL 或 CI 審核已由平台自動強制。
- **D／官方 URL 與短引用：**
  - [CI/CD variable security](https://docs.gitlab.com/ci/variables/#cicd-variable-security)：**“malicious code can compromise both masked and protected variables”**。
  - [Mask a variable](https://docs.gitlab.com/ci/variables/#mask-a-cicd-variable)：**“not a guaranteed way to prevent malicious users from accessing variable values”**。
  - [Protect a variable](https://docs.gitlab.com/ci/variables/#protect-a-cicd-variable)：僅向執行於 **“protected branches or protected tags”** 的 pipeline 提供；目前 MR／merged-results pipeline 另有可選存取條件。
- **文件範圍：** Masking 主要減少 job log 誤洩；protected 限縮可取得 secret 的 ref／pipeline 條件，不阻止已能在允許範圍內執行的 CI 程式把 secret 送出。default-branch-only 不等於「所有預設分支變更先經獨立審查」。限制 CI 的人、runner、網路與 secret 最小權限仍是必要設計；這是風險控制建議，不是本次已施行事項。
- **U：** 需取得實際 masked／protected flag、預設分支保護、CI include／script 變更管理、runner 管理者與外連限制證據；否則不得宣稱 token 無法被 pipeline 作者取得。

### C15. CE／Free 可 protected branch；這不等於 required MR approval

- **主張／D：** GitLab 基本 project protected branch 支持 Free，可用角色控制誰能 push／merge；CE 簡報可談限制 direct push 與維運審查流程，但不能把付費「required approvals」包裝成 Free 已有的自動 gate。
- **D／官方 URL 與短引用：**
  - [Protected branches](https://docs.gitlab.com/user/project/repository/branches/protected/)：**“Tier: Free, Premium, Ultimate”**；控制 **“which users can merge and push code changes”**。
  - [Require merge requests](https://docs.gitlab.com/user/project/repository/branches/protected/#require-merge-requests)：`Allowed to push and merge` 設 **“No one”**；project 設定須 Maintainer／Owner。特定 users／groups allowlist 與 group-level 規則另有 Premium／Ultimate 條件。
  - [MR approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)：Free 的 approvals **“are optional and don’t prevent merging without approval”**；Required approvals 標示 **“Tier: Premium, Ultimate”**。
- **文件範圍：** Free 可強制走 MR 的路徑限制，和「必須取得指定人／指定數量核准才可 merge」是不同能力。可人工要求維運角色檢查 CI 再合併，但這是流程／角色分工；不能宣稱 CE 原生 required approval 已強制雙人或 CI 特定檔案審查。需同時防範有權改保護規則者。
- **U：** 尚未查證現場 protected branch 的有效規則、wildcard 重疊或維運 merge 權；S2 的 workflow 不是其證據。若需要強制 approvals，另案評估付費 tier 或獨立 gate，不能視為 POC 已實作。

### C16. CODEOWNERS enforcement 屬付費，單放檔案不產生已強制的核准保證

- **主張／D：** 本研究不把 CODEOWNERS 文字檔、protected branch 或人工約定，說成 CE 已自動強制 CI 檔案擁有者核准。
- **D／官方 URL 與短引用：**
  - [Code Owners](https://docs.gitlab.com/user/project/codeowners/)：**“Tier: Premium, Ultimate”**；要強制，target branch 必須 protected 且 **“Code Owner approval ... must be enabled”**。
  - [Require Code Owner approval](https://docs.gitlab.com/user/project/repository/branches/protected/#require-code-owner-approval)：**“Tier: Premium, Ultimate”**。
  - [Code Owners – push bypass](https://docs.gitlab.com/user/project/codeowners/#allowed-to-push-and-merge-to-a-protected-branch)：直接 push 跳過 MR 時，**“Code Owner approvals built into merge requests are also skipped”**。
- **文件範圍：** 即使購買支援 tier，也要有檔案規則、分支設定、必要 approval 與不當 direct-push 權限的控制；購買授權或存在 CODEOWNERS 檔案本身不是 enforcement 證據。
- **U：** 沒有本次現場設定或負向驗收，不宣稱 required MR approval／CODEOWNERS 已啟用；CE 情境只能描述為人工審查約定或待建 gate。

## 6. 簡報用語與未解問題交接

| 建議用語 | 避免用語 | 依據 |
| --- | --- | --- |
| 「source 顯示這些 API／headers；官方文件支持對應能力，現場 ACL 待盤點」 | 「本次全部重測成功／官方保證此環境全部可用」 | C1–C13 |
| 「兩組外部整合 secret；Rollback 與 artifact 工作另用 agent／job 認證」 | 「三個 runtime 長效 PAT」或「整套只有兩個憑證」 | C6、C8、C10 |
| 「VM 曾使用一日 Full PAT 註冊，runtime 不依賴該 PAT；最低註冊權限待驗收」 | 「正式 runtime 必須 Full access PAT」 | C10–C11 |
| 「Build Artifacts／Server Container」 | 「已採用 Pipeline Artifacts」 | C9 |
| 「REST 7.0 基線 Server 2022，task／patch 仍要核對」 | 「所有 ADO Server 都支持／7.0 表示只能裝 2022 初版」 | C12 |
| 「protected branch 與人工 CI 審查；required approval／CODEOWNERS 另有 tier 與設定條件」 | 「CE 已自動強制所有 CI 變更雙人審核」 | C14–C16 |

正式驗收應交接：Server／GitLab／agent／task 精確版本；token 非敏感 metadata 與撤銷紀錄；PAT owner、bot、Build Service、pipeline allowlist、check 管理者的有效 ACL；四個 GitLab GET 與兩個 ADO GET 的正／負向測試；超過 200 筆與 retry 的 rollback 歷史測試；惡意 CI 與 direct-push 的治理測試。**這些是待執行工作，不是本研究完成的現場測試。**
