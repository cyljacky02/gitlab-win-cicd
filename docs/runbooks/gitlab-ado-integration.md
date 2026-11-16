# GitLab ↔ Azure DevOps Server Express：VM1／VM2 串接指南

> **目前採用路線：**GitLab 放原始碼／發 webhook，ADO VM1 取碼與建置；請從 [ADO source-build 指南](gitlab-ado-source-build.md) 繼續。原 [webhook agentless probe](gitlab-ado-webhook-smoke.md) 已由使用者回報手動 Test 自動 Run 成功。**本頁保留較早的 GitLab CI artifact 交接備選，不是目前必做步驟，也不要求 GitLab Runner。**

## 先說下一步

你的最新現況（依本次說明，不是簡報的舊進度）：

- GitLab Server＋既有 GitLab Runners：**Linux**（依本次補充）。
- VM1：ADO Server Express＋Windows Build Agent 已安裝，基本 CI/CD 已測。
- VM2：Deploy Agent 已安裝，基本部署已測。
- **現在先接「GitLab 候選版本 → ADO 驗證存版」，不要先重做 Agent／部署引擎。**

本次提供的[套件](../../cicd/gitlab-ado/README.md)可供修改、測試；沒有連進你的 VM，也沒有替你建立 token、ACL 或核准設定。

```text
應用程式 push 到 GitLab main
  → Linux GitLab Runner：sh＋Python 建置後封裝 site.zip + manifest.json
  → notify_ado 用受限 PAT 排入固定 ADO IMPORT-ONLY pipeline，保存 run ID 後立即結束
  → VM1 Build Agent 以管理側 read_api token 反查 GitLab
      等整條 pipeline 最終 success → 驗 project/ref/SHA/必要 jobs/固定 job ID/ZIP/hash
  → ADO Server Build Artifact：release（候選版本，還不是部署放行）
  ── 本次第一階段到這裡；VM2 不應收到工作或候選檔案 ──
  → 下一階段：授權部署人員選確切 importer build／candidate，ADO 放行
  → VM2 才下載該版本、重新驗 hash，呼叫既有部署腳本／已驗證的 WinCD
```

這裡的「↔」是兩個方向的 HTTPS/API，不是 Git 雙向同步：Runner → ADO 排程；VM1 → GitLab 讀取產物。**不需要先做 Git mirror、ADO GitLab extension 或新增 webhook receiver。**

這是舊研究 `gitlab-ado-event-trigger.md` 已列出的「CI 直呼」簡化備案，不是把其中「CI 不持 ADO PAT」的受保護 webhook receiver 方案宣稱成已實作。**本次 CI 會持一組受限 queue PAT**；若單位規範連這種權限都不能交給 CI，就停止這條路，改採管理側 receiver／collector，不能用 masked 變數迴避規範。

## 0. 開始前只確認這些資料

| 項目 | 取得方式／填法 |
|---|---|
| ADO 精確 edition、版本／build／patch | ADO About／Administration Console；不要由 Agent 版號猜 |
| GitLab／Runner 版本與 executor | GitLab Help、Runner 管理頁、`gitlab-runner --version` |
| Collection URL | 瀏覽器的 collection 層，例如 `https://ado.example.internal/tfs/DefaultCollection`；**不含 project** |
| ADO project | 例如 `CDPlatform`；不是 repo 名稱 |
| VM1 agent pool、agent name、服務帳號 | Project settings → Agent pools；確認 importer 使用既有 VM1，不是 VM2 |
| VM2 的註冊類型 | 一般 pool agent？Environment 的 VM resource？Classic Deployment Group？三者不可混用 |
| GitLab project ID／path／來源分支 | 專案頁的 Project ID、`group/application`、目前先用 `main` |
| 既有建置指令／實際 publish 輸出目錄 | 例如現行 CI 產生的 `publish/`；本包示範頁不是雷影／精誠建置指令 |

**REST 基線：本包使用 Runs API 7.0（Server 2022 起的相容基線），不是 Services 的 `az pipelines` CLI。** 若實機是 Server 2020，先停止套用此 YAML/API；不要只改成 `6.0` 就假設 templates／tasks 均相容。既有研究中的 `20.256.*` 只是歷史紀錄，不能替你的新 VM 定版。[1][2]

## 1. 先驗網路、TLS 與分工

| 發起端 | 目的地 | 用途 |
|---|---|---|
| GitLab Runner 所在機 | GitLab HTTPS | 取應用來源、回傳 artifacts |
| GitLab Runner 所在機 | ADO collection HTTPS | 僅排程 import-only pipeline |
| VM1 Build Agent | GitLab HTTPS | 唯讀查詢／下載固定 job 的 artifacts |
| VM1 Build Agent | ADO collection HTTPS | 取工作、上傳 Build Artifact |
| VM2 Deploy Agent | ADO collection HTTPS | **放行後**取工作／下載確切版本 |

- 不需要 Runner → VM2 的 SMB／WinRM／RDP，也不要給 Runner 任何正式主機密碼、共用目錄或 Production agent 權限。
- Windows VM1／VM2 可跑 `Test-NetConnection <實際主機名> -Port <實際HTTPS埠>`；Linux Runner 可跑 `getent hosts <實際主機名>`、`curl --head --max-time 15 https://<實際主機名>:<實際HTTPS埠>/`（不帶 token；401/403 也可能代表網路已到達）。在 Docker executor 要從 **job container** 內測，不是只測 Runner host。DNS、路由、proxy、TLS 是不同檢查；登入導向頁的 200 不等於 API 認證成功。
- 憑證的 SAN 必須含實際 URL 主機名；把經管理者確認的內部 CA chain 匯入服務帳號能使用的信任存放區，然後以實際 Agent／Runner 服務帳號測。不要 `-SkipCertificateCheck`／`curl -k`。
- 預設只准 HTTPS。若隔離實驗室現有 ADO 只有 HTTP，本包有明確 opt-in（後述），但 PAT 會明文傳輸：**不可用正式／可重用憑證，不算正式導入驗收通過。**
- 本包不跟隨 API／artifact redirect；GitLab 使用外部 object storage 回 302 時會拒絕。應由管理者提供同源交付或另外設計嚴格 allowlist 與跨域移除 token；不要直接開啟任意 redirect。

## 2. 沿用現有 Linux GitLab Runner，不要改成 Windows

**前版誤把 GitLab Runner 範本寫成 Windows，這裡已修正。** GitLab Server 與 Runners 都是 Linux；VM1／VM2 的 ADO Agents 是 Windows，這是兩組不同的執行端。

| 程式 | 真正執行位置 | 使用語言 |
|---|---|---|
| 封裝、通知 ADO | Linux GitLab Runner 的 job | `.sh` 入口＋Python 3.9+ 標準函式庫 |
| GitLab API 複核、存版 | VM1 Windows ADO Build Agent | `ado/scripts/Import-GitLabCandidate.ps1` |
| 放行後的版本複驗／換版 | VM2 Windows ADO Deploy Agent | PowerShell／既有 WinCD 介面 |

**不是 ADO 規定只能跑 PowerShell，而是這些 ADO jobs 目前派到 Windows Agent。** Linux 端只經 HTTPS＋JSON／ZIP 與 ADO 交接，不需要安裝 PowerShell、遠端登入 VM1，或新增 Windows GitLab Runner。

1. 在既有 Runner 管理頁確認 **executor 與 tags**；Linux 是 OS，不代表一定是 Docker executor。[3][4]
2. 將範本 `tags: [gitlab-bridge-linux]` 改為既有 Runner 的實際 tags（必須全部匹配）；不要為了套範本先改 tag／重註冊 Runner。
3. 確認該 job 執行環境提供 Python 3.9+、POSIX `sh`，以及 ADO HTTPS 的 CA 信任：

   | 既有 executor | 準備方式 |
   |---|---|
   | **shell** | 在現有 Linux host 的 Runner 帳號環境提供 `python3`；`image:` 會被忽略，不要在 job 裡使用 sudo 裝套件。 |
   | **Docker／Kubernetes** | 用包含 Python 3.9+ 的已核准 Linux job image；本包 smoke test 用 `python:3.12-alpine` 示範，正式依規範選內網 mirror／釘 image digest。 |

   在實際 job 執行 `python3 --version`。封裝與 HTTP／JSON 都用 Python 標準函式庫，不依賴 `jq`、`zip`、`curl` 或 PowerShell。既有應用程式 build image／建置工具照舊，不要為了範例換掉正式編譯環境；可在原 image 加入 Python，或另用封裝 job 讀取先前的 build artifacts。
4. Docker job 的 CA 信任須在 **container** 裡具備；只在 Runner host 裝內部 CA 不一定足夠。Python 使用正常 TLS 憑證驗證；必要時以 `SSL_CERT_FILE` 指向管理者核實的 CA bundle，不要關閉驗證。
5. 沿用受控 project／protected branch／protected variables 的安全設定，確認 MR／其他專案不能取得 queue PAT。Runner tags 只是派工條件，不是權限隔離；shell executor 直接使用 Runner 帳號權限，更不能當成不可信多租戶沙箱。

VM1 importer pool 仍只能執行 CD 信任程式；Linux Runner 不持 VM2 存取權。`gitlab/ci/*.ps1`、`config.windows.example.toml` 只保留作 Windows 替代版／回歸參考，**你們的預設 GitLab pipeline 不再使用它們**。

## 3. 兩組 runtime secret，分別放兩邊

### A. ADO → GitLab：唯讀

在 GitLab 建專用 project access token：起點為 **Reporter＋`read_api`**，設定到期／輪替；實際 artifact access／CI visibility 可能要求不同角色，須以四類 GET 實測。不要先給 Maintainer／`api` 解決所有 403；`read_repository` 或 deploy token 也不是此 API 流程的替代。[5]

在 ADO **Pipelines → Library → Variable groups** 建 `gitlab-readonly`，新增 secret：

```text
GITLAB_READ_TOKEN = <GitLab 唯讀 token>
```

只授權 **importer pipeline** 使用，勿選全 pipelines 開放。不要放進 GitLab CI variables、JSON policy、YAML 或 VM2。

### B. GitLab → ADO：僅排程 importer

由專用非管理 ADO 帳號建立 PAT：**Build (Read & execute)**，設定期限。Scope 不是單支 pipeline 限制；還要在有效 ACL 上限制：[6]

- project 必要讀取／指定 importer 的 View definition、View builds、Queue builds。
- 不加入 Contributors／Build Administrators／Project Administrators 等廣權群組；檢查繼承。
- 不得 Edit pipeline、改 ACL、使用 VM2／Production pool、執行其他 deploy pipeline、Release 建立／部署／核准、讀 Production secrets。
- **負向測試**：同 PAT 排其他 pipeline 必須失敗；嘗試變更 self repo ref/version、pool／variable 覆寫與資源使用，不得跑到未審碼或 VM2。若實際 Server 權限無法封住，不能拿這條直呼路線進 Production。

GitLab 專案 **Settings → CI/CD → Variables** 設定：

| 名稱 | 範例／來源 | 性質 |
|---|---|---|
| `ADO_COLLECTION_URL` | `https://ado.example.internal/tfs/DefaultCollection` | 非 secret；Protected |
| `ADO_PROJECT` | `CDPlatform`；腳本會 URL encode | 非 secret；Protected |
| `ADO_PIPELINE_ID` | 第 4 步建立的 **import-only** pipeline ID | 非 secret；Protected |
| `ADO_CD_COMMIT` | 第 4 步 CD repo 的已審核完整 40 碼 commit SHA | 非 secret；Protected |
| `ADO_QUEUE_PAT` | 上述專用帳號 PAT | **Masked＋Protected**，支援時 Hidden；不要啟用 variable expansion |

`ADO_CD_COMMIT` 會釘住 ADO `self` 的 trusted `main` 版本。**這只是正常請求的 pin，不會把 PAT 變成不能改 request 的 capability token**；可執行 CI 的人仍可能偷走 PAT，故 importer 專案／repo／資源隔離與有效 ACL 不可省略。所有可執行的 CD 分支及歷史版本都不得提供繞過治理的入口。勿啟用 `CI_DEBUG_TRACE`。Masked／Protected 不能保證對惡意 CI 保密。[6][7]

僅隔離 HTTP 實驗室：GitLab 額外設 `ADO_ALLOW_INSECURE_HTTP=true`；GitLab HTTP API 另須 CD policy 的 `allowInsecureHttp=true`。兩者獨立、預設皆拒絕 HTTP；不允許跳過 TLS 憑證驗證。

## 4. 在 ADO 建立「只匯入」pipeline（先不動 VM2）

1. 在 **CD 管理的 Azure Repos repo** 放入本套件，保持路徑 `cicd/gitlab-ado/...`。這不是 GitLab 應用 repo 的鏡像，程式只由 CD 管理者維護。YAML 不從 GitLab clone／執行任何 script。
2. 複製並編輯**無 secret** 的固定 policy：

   ```powershell
   Copy-Item .\cicd\gitlab-ado\ado\import-policy.example.json .\cicd\gitlab-ado\ado\import-policy.json
   ```

   設實際 `gitlabBaseUrl`、`projectId`（字串）、`projectPath`、`allowedRef`。起步只接 `main`；若既有名稱是 `master`，同步修改 GitLab workflow 和 policy，不要兩邊各猜一個。

   本包範例 job 名稱是 `package`／`notify_ado`；若沿用舊 ZIP 的 `build`／`trigger-ado`，將 `packageJobName/packageJobStage` 及 `requiredJobs` 同步改成其真實值。**正式專案有 unit_test、security_scan 等必要檢查時，必須逐項加入 requiredJobs，而且 job 不可 allow_failure。** 名稱／stage 必須唯一；parallel matrix、child pipelines 需另設政策，不能略過檢查。
3. 編輯 [`azure-pipelines-import.yml`](../../cicd/gitlab-ado/ado/azure-pipelines-import.yml) 的 `pool.name` 為 VM1 現有 Build Agent pool。不要填 VM2 pool、Environment 或 Deployment Group。讓這個 pool 只可被受信 CD definitions 使用。
4. commit／push 至 CD repo 的受控 `main`。取得這個 commit 的完整 SHA，供 `ADO_CD_COMMIT` 使用。更新 policy/script 後必須審查新 commit，並同步更新 pin；不要改用 `latest`。
5. ADO **Pipelines → New pipeline → Azure Repos Git → 選 CD repo → Existing Azure Pipelines YAML file**，路徑 `/cicd/gitlab-ado/ado/azure-pipelines-import.yml`，儲存。命名例如 `GitLab-Candidate-Import-main`。
6. 記下 URL 裡的 definition/pipeline ID，填 GitLab `ADO_PIPELINE_ID`；授權此 pipeline 使用 `gitlab-readonly`。必要時先取消沒有參數的初次執行；空參數會被腳本拒絕。
7. 檢查 pipeline 只有 `Import` job＋`PublishBuildArtifacts@1`，沒有 `deployment`、VM2 pool 或自動 Release trigger。使用的是 **Server 支援的 Build Artifacts / Container**，不是 `PublishPipelineArtifact`／YAML `publish` 捷徑。[8]

第一次測試時，若專案其他既有 Release 已廣泛監看所有 builds，先收窄它們的 artifact source，確保新 importer 不會被誤選為自動部署來源。

## 5. 在 GitLab 隔離專案做真 push

先用**專用測試 GitLab project**，將第 4 步的 policy 指向它。之後換正式應用 project 要以新的受控 policy／importer 重新測，不能偷偷改通知參數冒充不同應用。

1. 把整個 `cicd/gitlab-ado/` 套件複製到該專案的 **`ci/bridge/`**；確認存在：

   ```text
   ci/bridge/gitlab/ci/new-release-candidate.sh
   ci/bridge/gitlab/ci/send-ado-candidate.sh
   ci/bridge/gitlab/ci/bridge.py
   ci/bridge/gitlab/demo-site/index.html
   ```

2. 在**空的測試專案**，把 `ci/bridge/gitlab/gitlab-ci.example.yml` 複製成根目錄 `.gitlab-ci.yml`；在該專案根目錄 `.gitignore` 加入 `/out/`，避免本機產物誤入版控（不影響 CI 上傳 artifacts）。不要覆蓋正式專案既有 pipeline；正式串接時合併 jobs/stages。
3. 完成第 3 步 CI variables、protected main、Runner tag 設定，真 push 一個 commit 到 `main`。
4. 觀察 GitLab：
   - `package` 成功，產生 `out/site.zip`、`out/manifest.json`。
   - `notify_ado` 成功，log 顯示 `ADO importer run <id> queued`。
   - `out/bridge-receipt.json` 保存 GitLab IDs／SHA、ADO run ID／CD commit，**不含 token**。
   - 整條 pipeline 最後為 success。
5. 觀察 ADO importer：可以短暫出現等待 GitLab success；之後應成功並出現 **release** artifact，僅含：

   ```text
   site.zip
   manifest.json
   verification.json
   ```

6. 下載到**管理側**，比對 verification 的 project／pipeline／job／ref／SHA／hash／ADO build ID；檢查 VM2 **沒有新部署工作、沒有本候選檔案送入**。

### 為什麼通知不等 ADO？

通知 job 自己尚未結束時，整條 GitLab pipeline 通常仍是 running。若 GitLab 等 ADO 完成，而 ADO 等 GitLab success，就死鎖。本實作是：**POST → 保存 run ID → job 結束**；ADO 對該特定 pipeline 做有期限的狀態查詢（預設 10 分鐘），success 才匯入。不是用固定 sleep 假裝成功，也不是週期掃全專案。[9]

新 job **不使用 `needs: [package]`**，避免跳過其他測試；若要改成 needs，必須把所有必要工作與政策一起重新設計。整條 pipeline success 仍可能包含 skipped／allowed-failure jobs，所以 importer 另驗必要 jobs 為實際 success 且 `allow_failure=false`。

### 接雷影／精誠時改哪裡？

- 保留現有 **Linux** 建置／測試命令；在全部必要驗證成功後，以 `sh ci/bridge/gitlab/ci/new-release-candidate.sh <真正publish目錄>` 封裝。該 job 的 image／host 須有 Python 3.9+，不是改跑 Windows。
- 此工具會在副本加入根目錄 `release.json`，不修改原 build output；若來源已有同名檔案會拒絕封裝。**若應用已有同名檔案或有自己的 package layout，先協調格式，不能覆蓋業務檔案。**
- `gitlabJobId` 必須是**產生 artifacts 的 package job ID**，不是 notify job ID。
- 若保留原 CI 的 Linux/Docker 封裝實作，manifest／root release.json 必須符合下一節；本包的 Linux scripts 已提供同一契約。不要在 VM1 重新執行應用程式建置碼。
- 本包只示範一個應用／一個分支。第二個應用或 Production 建立獨立的 policy＋importer＋權限映射；不要讓 GitLab 輸入任意環境、pool 或部署指令。

## 6. 固定契約：和最新 Direct-agent ZIP 哪些相同、哪些不同？

### GitLab artifact manifest（camelCase，沿用最新 ZIP）

```json
{
  "schema": 1,
  "releaseId": "r7-aaaaaaaa",
  "projectId": 123,
  "projectPath": "group/application",
  "pipelineId": 456,
  "jobId": 789,
  "commitSha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ref": "main",
  "zipName": "site.zip",
  "zipSha256": "<實際64碼SHA-256>",
  "zipBytes": 12345
}
```

`releaseId` 是 `r<CI_PIPELINE_IID>-<SHA前8碼>`；`pipelineId` 是全域 API ID，**不是 IID**。ZIP 直接包含站台檔案，根目錄 `release.json` 記錄 releaseId／commitSha／projectId／pipelineId／jobId。**重試 package job 會換 job ID，但 releaseId 可能不變**；部署放行必須綁定 project/pipeline/job＋SHA-256＋確切 importer build，不能只看 releaseId，不能沿用舊核准。

通知呼叫：

```http
POST {collection}/{URL-encoded-project}/_apis/pipelines/{importerId}/runs?api-version=7.0
Authorization: Basic <base64(:PAT)，禁止記錄>
```

body 的 `templateParameters` 仍是六個字串：`gitlabProjectId`、`gitlabPipelineId`、`gitlabJobId`、`commitSha`、`releaseId`、`zipSha256`。正常請求額外在 `resources.repositories.self` 固定 CD `main`＋已審 commit。**200/201 只代表排入，不代表匯入或部署成功。**[2]

管理側用固定 project API 複核 project、指定 pipeline、所有 current/non-retried jobs、指定 job，再從以下**固定 job ID**單檔 API 下載：[5]

```text
GET /api/v4/projects/P/jobs/J/artifacts/out/manifest.json
GET /api/v4/projects/P/jobs/J/artifacts/out/site.zip
```

不用 `latest`、不用 branch latest-successful URL。產物過期／無權限時拒絕，絕不改抓最新；GitLab artifacts 設 30 天也不是永久保存，ADO build retention 也要覆蓋等待放行、稽核與退版期間。[5]

### 本包的 verification.json 不是舊部署 envelope

本包寫 snake_case 稽核欄位：`candidate_id`（P-L-J）、`release_id`、`project_id`、`pipeline_id`、`job_id`、`ref`、`sha`、`sha256`、`size_bytes`、`ado_build_id`、`ado_cd_commit`、`policy_sha256` 等。**舊 ZIP Deploy 模組不能因檔名相同就直接接上。**

接 VM2 可使用本包的 [`Test-ImportedCandidate.ps1`](../../cicd/gitlab-ado/ado/scripts/Test-ImportedCandidate.ps1) 驗這個新 envelope，再進入你既有、已驗證的部署／WinCD 介面。它驗資料、hash 與被指定的 build/candidate，**不是簽章、不是核准、也不會替你安全解壓或執行換版**。

## 7. 第一階段通過後，才接回 VM2

### 7.1 先辨識你現在的 Deploy Agent 模型

| VM2 在哪裡看得到 | 正確編排方式 |
|---|---|
| Project settings → Agent pools | 一般 pool agent；YAML 用固定 deployment pool，Environment 僅作受保護的放行資源 |
| Pipelines → Environments → 某環境 → VM resource | YAML deployment job 指定該 Environment 的 `resourceType: VirtualMachine`／target resource；不要把環境名當 pool 名 |
| Pipelines → Deployment groups | Classic Release 的 Deployment Group job，不是 YAML build pool |

最新 ZIP 用一般 deployment pool＋Environment checks；較早版用 Environment VM resource。你只說「Deploy Agent 已安裝」，還不足以決定該用哪份部署 YAML。**不要為了套範本先刪除／重註冊已驗證的 Agent。**[10]

### 7.2 Production 邊界（不可由通知直接跳過）

- GitLab 能產生候選版本，但不能放行 Production。授權部署人員選定**應用＋環境＋確切候選版本**，更換任一項要重新放行。依 `GLOSSARY.md`，不強迫雙人審批；若單位要求兩人再另設。
- VM2 工作、artifact download／暫存也是正式存取。**核准前不可先送檔到 VM2**，不能只把「執行換版」放在核准後。
- Environment checks／Classic pre-deployment approvals 是**資源端設定**，YAML 寫 `environment:` 不會自動建立安全邊界。確認實際 Server 版本提供的 UI／有效 ACL，測 reject、timeout、取消與未授權排程。[10][11]
- 選擇既有、已驗證的一種模型。若目前已有 Classic Release，可建立一份**手動測試 release**，artifact source 固定 importer definition、版本固定成功 build，關閉 continuous deployment trigger，stage 設 Manual only＋授權部署人員 pre-deployment approval；agent job／Deployment Group job 依實際註冊，不混搭。
- 若目前用 YAML，另建**手動 consumer pipeline**或沿用既有受控部署 definition，輸入經授權的確切 importer build ID。Build Artifacts download 使用 `specific build`；不要 `latest`。禁止 GitLab queue 身分執行這支 consumer；先設妥 Environment／pool／repo／variables 權限，再測下載發生時機。

### 7.3 consumer 在換版前執行的驗證

把 CD 信任的套件（至少 `ado/scripts/`＋相對位置的 `shared/`）部署在受控位置，**不是執行 ZIP 裡的部署腳本**。假設人工選定 importer build `321`，下載後管理側已核對 candidate 為 `123-456-789`：

```powershell
# 路徑、IDs、ref、releaseId 必須替換成「這次已放行」的確切值，不能硬沿用範例。
& C:\CD\cicd\gitlab-ado\ado\scripts\Test-ImportedCandidate.ps1 `
  -ArtifactDirectory 'C:\approved-download\release' `
  -ExpectedImportBuildId '321' `
  -ExpectedProjectId '123' `
  -ExpectedRef 'main' `
  -ExpectedCandidateId '123-456-789' `
  -ExpectedReleaseId 'r7-aaaaaaaa'
if (-not $?) { throw 'Candidate verification failed; stop before deployment.' }

# 驗證通過後，才呼叫你已驗證的換版腳本／WinCD。
# 不在此猜測尚未提供的 WinCD package/config 參數，也不自動啟動 IIS 或導流。
```

Classic Release 可用固定 artifact alias（例如 `Candidate`）的 `Release.Artifacts.Candidate.BuildId` 取得已選 build ID；實際下載根目錄依 alias／artifact 名確認。其餘放行欄位從管理側核對的該 build 證據固定下來，限制 release edit／queue-time override 權限，不能讓應用程式隨意改。檢查的是「本次放行對象」，不是僅對下載檔自算 hash 就算核准。[12]

本包未提供可直接啟動 VM2 的 deploy YAML：在 Agent 類型與 WinCD 介面未知時，那會假裝已完成整合。**第一階段不需要它；你原來測通的部署流程先保留。**

## 8. 驗收與錯誤排除

### 必測清單（現場尚未執行）

| 測試 | 預期 |
|---|---|
| 真 push、必要 jobs 成功 | GitLab receipt → ADO run → release artifact，可逐一對帳；VM2 無工作 |
| 通知時 pipeline 仍 running | ADO 等待；GitLab 通知 job 不等待 ADO，最後 success 才發布 |
| 必要 test 失敗／取消、notify 排入後 pipeline 被取消 | 不發布；不能因 build 已成功就通過 |
| pipeline success 但必要 job skipped／allow_failure | 不發布 |
| 換 project/ref/SHA/job、tag/MR/API pipeline、舊 retried job | 不發布 |
| manifest／release.json／ZIP hash 不一致、危險 ZIP path／link／大小超限 | 不發布 |
| artifact 404／過期／403／302、TLS 錯誤、token 到期 | fail closed，不改抓 latest，不跳 TLS |
| 同 PAT 排 deploy／其他 pipeline、改未審來源／資源 | 不得成功；若能越權就是 no-go |
| 重送同通知、HTTP queue 回應遺失 | 人工對帳；可能重複 importer，但**不得自動部署** |
| 日後接 VM2：未核准／拒絕／逾時 | 無候選檔案寫入 VM2；不是僅「沒有換版」 |
| 日後接 VM2：換 candidate／build／環境 | 舊核准不能套用，重新放行且重新驗 hash |

### 常見現象

- **GitLab job pending**：先看 tag、Runner online、Protected runner／protected branch 是否相容；不是 ADO 問題。
- **Linux job 出現 `powershell`／`pwsh` 找不到**：代表仍在跑先前的 Windows GitLab 範本；改成此指南的 `.sh` job，**不用在 Linux 補裝 PowerShell**。`python3` 找不到則在既有 shell host 或已核准的 job image 提供 Python 3.9+；勿以 job 臨時改系統權限。
- **ADO 401／403**：檢查 URL 是否到 collection、PAT 到期／scope／有效 ACL／代理驗證。PAT 使用 Basic header，不代表要啟用 IIS Basic；Microsoft 明示 Server 的 IIS Basic 會影響 PAT，勿用它當捷徑。[6]
- **ADO 404／400**：確認 project URL encode、pipeline ID、YAML 路徑、六參數名稱、REST／Server 版本、`ADO_CD_COMMIT` 是否存在於 CD `main`。
- **Queue request failed/outcome unknown**：POST 可能已成功。先在 ADO 找同 GitLab pipeline/job/SHA 的 run；無法讀紀錄時請管理者對帳，勿盲目重試通知或整條 GitLab pipeline。
- **匯入等待 10 分鐘逾時**：看 notify 是否還在等 ADO、是否有 blocking manual job、後續 stage 卡住。修正 pipeline；不要刪除 success 檢查。
- **Missing/ambiguous required job**：policy 跟現行 CI job/stage 不一致，或 matrix／child pipeline 尚未建模；不要改成「找任一成功 job」。
- **GitLab 403**：以唯讀 token 實測 project／pipeline／jobs／artifact API，查 visibility 與 artifacts access；不要直接擴成管理員。
- **OutputDirectory already exists**：確認 YAML 的 clean workspace、每 build 獨立 staging；腳本刻意不刪除任意現存輸出，避免混版。
- **VM2 收到新工作／檔案**：立即停止測試，查 importer 是否誤指 deploy definition／pool，或其他 Release 設了自動 artifact trigger。

### 上線前還缺的可靠性

此套件刻意不宣稱 exactly-once：沒有耐久 inbox／候選唯一鎖／queue 回應遺失對帳、自動補送、亂序部署 high-water mark、部署互斥、retention 保護與長期告警。擴到自動 SIT/UAT 或 Production 前要補上，或回到受保護 receiver 的完整設計。hash 是完整性證據，不代表程式安全，也不授予正式存取權。

## 9. 本次驗證範圍與參考

- 已閱讀期中簡報來源／講稿與四個 ZIP 的相關交接／部署實作；最新 FINAL 內層仍有 nested source ZIP，並非根目錄直接就是 pipeline。
- 舊 ZIP 的 E2E 成功是**包內歷史證據**，不是本次在你新 VM 重跑；最新包原本不 gate 全 pipeline success，此處明確加強。
- Linux CI 預設範本已改為 `.sh`＋Python 標準函式庫；本輪在 Windows 主機跑 Python 測試 **10 通過、1 因 symlink 建立權限略過**，並驗 Python ZIP 與 ADO PowerShell 檢查互通。`sh -n` 通過；尚未在實際 Linux Runner／container 真 push，沒有 Linux 現場 E2E 成功宣稱。
- 自動化 Windows 離線測試：PowerShell 5.1 **99/99 通過**（本輪重新執行；通知用本機 loopback，importer API 用假資料，無現場 API 呼叫）。指令見[套件 README](../../cicd/gitlab-ado/README.md)；現場網路／ACL／Agent／核准／WinCD 整合仍須按此表驗收。
- 補充官方查核：[本次研究](../research/gitlab-ado-server-integration.md)、[既有執行期權限研究](../research/poc-runtime-api-credential-review.md)。

[1]: https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rest-api-versioning?view=azure-devops-2022
[2]: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.0
[3]: https://docs.gitlab.com/runner/register/
[4]: https://docs.gitlab.com/runner/executors/
[5]: https://docs.gitlab.com/api/job_artifacts/
[6]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022
[7]: https://docs.gitlab.com/ci/variables/#cicd-variable-security
[8]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines
[9]: https://docs.gitlab.com/ci/yaml/
[10]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-2022
[11]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022
[12]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/variables?view=azure-devops-2022
