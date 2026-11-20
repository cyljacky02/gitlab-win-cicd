# GitLab → ADO → VM：只交付原始碼 ZIP

## 本輪只做這條線

```text
GitLab Rayin / poc/cicd push
  → 有認證的 ADO Runs REST（不是原本公開的 smoke webhook）
  → VM1：取這次 push 的確切 SHA → ZIP → ADO Build Artifact
  → VM2：下載同一 ADO run 的包 → 驗 SHA-256 → D:\TestCICD\Rayin-<run ID>-<SHA>.zip
```

**ZIP 本身，不解壓、不 restore／build／compile、不執行應用腳本、不操作 IIS／服務。** GitLab 不需要 Runner 或 `.gitlab-ci.yml`。先手動驗通，再接 webhook；原本的 agentless smoke 不加上 credentials 或 VM2 工作。

## 已確認設定與證據界線

| 項目 | 本次設定 |
|---|---|
| GitLab repo | `http://10.93.19.25/grp-smt-maint/Cathaysec.Com.Smt.Rayin.git` |
| GitLab source ref | `refs/heads/poc/cicd` |
| ADO project／repo | 沿用 `Deployment`／原本的受控測試 repo |
| ADO YAML branch | 沿用 **`poc/webook-smoke`（現場拼字沒有 h）**，不是 GitLab branch |
| ADO 交付 pipeline／definitionId | `GitLab-Rayin-Zip-Delivery`／`5`（使用者已確認） |
| ADO project URL | `http://10.92.4.86/DefaultCollection/Deployment`（使用者提供的 webhook URL 前綴） |
| VM1 pool／Agent.Name | `Default`／`SECSVR004-086T` |
| VM2 Environment／VM resource | `test-deploy-agent`／`SECSVR4-80`；不是一般 pool 或 Classic Deployment Group |
| VM2 目的目錄 | 本次使用 `D:\TestCICD`；Agent 服務帳號須有寫入權，D: 須存在 |
| GitLab Webhook UI | 使用者已確認有 Custom headers 與 Custom webhook template |
| 取碼 credential／variable group | 使用者已回報完成；不用重建 |
| 本次傳輸 | 使用者指定 PRIVATE NETWORK 的 HTTP；手動 Run 勾 `allowInsecureHttpLab`，HTTP 仍非加密傳輸 |

先前通過的是 Tools.Rs 的網頁 Test → ADO 零動作探針。**最新現場證據：使用者截圖確認現存 ADO 分支是 `poc/webook-smoke`（沒有 h），而 template／診斷原本查的是 `poc/webhook-smoke`。這個拼字不一致解釋了 `exactRefCount=0` 與 unresolved-ref 400，並非重新授權就能修正。** 已更正 Custom webhook template 的 `self.refName`、診斷預設與操作說明；保留現有分支，不改 main、不重建分支、不再擴權。手動交付已回報成功；**修正後的真 push 自動交付也已由使用者回報成功**（GitLab push → ADO → VM2 收到 ZIP）。該次自動 run 的 run ID／SHA／ZIP hash 對帳資料尚未取得。本機沒有代設公司 ADO／GitLab 或宣稱已代驗成功。

**已改用帶核准的交付（使用者回報已跑通）**：GitLab webhook 現在指向核准版 pipeline **7**，見[核准版操作指南](gitlab-ado-approval-delivery.md)。本文的 pipeline 5 為前一階段基線。核准設在 Environment `test-deploy-agent`，設定後本 pipeline 5 也會被擋；核准版驗收後 webhook 改指新 ID 並停用 pipeline 5。

若 VM2 是正式環境，送 ZIP／下載到 Agent workspace 都是 **Production Access**。必須先由授權部署人員放行指定版本與目標，才能開始 `Deliver` stage；在 Environment 資源端設妥 checks／權限並實測，YAML 寫 `environment:` 本身不是核准機制。一般隔離測試環境不額外強迫雙人審批。

## 第一步：同一 ADO 分支放入四個檔案

到 **ADO → Deployment → Repos → 原本 repo → branch `poc/webook-smoke`**。新增以下 YAML／腳本；若已有 `Get-GitLabSource.ps1`，更新為本版：

| ADO repo 路徑 | 本 repo 的完整檔案 |
|---|---|
| `/azure-pipelines-gitlab-file-delivery.yml` | [完整 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery.yml) |
| `/scripts/Get-GitLabSource.ps1` | [精確 SHA 唯讀取碼](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1) |
| `/scripts/New-GitLabSourcePackage.ps1` | [tracked checkout files 封裝](../../cicd/gitlab-ado/ado/scripts/New-GitLabSourcePackage.ps1) |
| `/scripts/Copy-GitLabSourcePackage.ps1` | [驗證並複製 ZIP](../../cicd/gitlab-ado/ado/scripts/Copy-GitLabSourcePackage.ps1) |

Commit 到**已有的 ADO `poc/webook-smoke`**，不是 GitLab 的 `poc/cicd`。不改／覆蓋舊 smoke YAML，不建立新 repo 或 branch。

目前 YAML 已指定：

```yaml
environment:
  name: test-deploy-agent
  resourceName: SECSVR4-80
  resourceType: virtualMachine
```

VM1 另保留 `Default`＋`Agent.Name -equals SECSVR004-086T`。不要把 Environment 名稱填到 pool，也不要拿掉 VM1 host restriction。[2]

## 第二步：建立交付 pipeline，但先不要 Run

1. **Pipelines → New pipeline → Azure Repos Git → 同一 repo → Existing Azure Pipelines YAML file**。
2. Branch 選 `poc/webook-smoke`，path 選 `/azure-pipelines-gitlab-file-delivery.yml`。
3. **Save**，命名 `GitLab-Rayin-Zip-Delivery`。不要選原本 `GitLab-Webhook-Smoke` 來修改。
4. 若 UI 先自動啟動空 SHA 的 run，取消即可；它應在 fetch 前拒絕空 SHA，不應派送 VM2 工作。
5. 只授權這支受控 pipeline 使用 VM1 pool 與 Environment `test-deploy-agent`，不開放所有 pipelines。確認 resource `SECSVR4-80` online。

## 第三步：取碼 credential 與 HTTP 決策

若 Rayin 的 VM1 匿名連通尚未驗收，先更新並執行[既有 connectivity YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)，依[取碼指南](gitlab-ado-source-build.md)確認 Git 與匿名 HTTP response；不必再重測舊 Tools.Rs probe，也不必另建 source-only pipeline。

ADO **Pipelines → Library → `gitlab-source-readonly`**：

```text
GITLAB_GIT_USERNAME = <Rayin project deploy token Username>
GITLAB_GIT_TOKEN    = <短效 Token，設為 secret 鎖頭>
```

只需 Rayin 專案的 **`read_repository`**，不是 `read_api`、個人密碼或 ADO PAT。若沿用 variable group，先確認不會覆蓋別的仍在使用的 token。只授權受控取碼／交付 pipeline，不授權 smoke。只有 Package job 引用此 group；VM2 不持 GitLab credential。

### 傳輸不可默默放寬

- **優先 HTTPS**：取得已核准的 GitLab HTTPS clone URL，將新 YAML 的三處 `SOURCE_REPOSITORY_URL` 一起改成相同值；正常驗 TLS／CA。
- **目前提供的 GitLab HTTP URL 預設會拒絕送 credential。** 本次使用者已指定只用 PRIVATE NETWORK 的 HTTP，並回報完成唯讀憑證／variable group；此 POC 手動 Run 勾 `allowInsecureHttpLab`，沿用短效專案唯讀 token，測後撤銷。PRIVATE NETWORK 不會把 HTTP 變成加密通道。
- ADO Library 管理頁及下節的 webhook／PAT 傳輸也要使用 HTTPS／受核准管理通道；Git 取碼例外不會一併核准 ADO PAT 的 HTTP 傳輸。
- 不關閉 TLS、不加 PAT 到公開 incoming-webhook endpoint，也不開 IIS Basic 來硬闖。

## 第四步：手動 Run 完整交付（會寫入 VM2）

確定 VM2 是本次允許寫入的測試目標後：

1. GitLab → Rayin → Code → Commits → branch `poc/cicd` → 複製完整 **40 碼 SHA**。
2. ADO → **新的 `GitLab-Rayin-Zip-Delivery` → Run pipeline**。
3. ADO branch 選 `poc/webook-smoke`；`gitlabCommitSha` 填上述 GitLab SHA。
4. 本次依使用者指定的內網 HTTP POC，勾 `allowInsecureHttpLab`；此 checkbox 只控制 GitLab 取碼，不會加密流量。
5. 確認 Package 在 VM1、Deliver 在 Environment 的 `SECSVR4-80`，不是在 VM1 直接寫 D:。

成功後：

- ADO run 的 artifact **`source-package`**：ZIP、`source-package.json`、`source-provenance.json`。
- VM2 **只有 ZIP**：`D:\TestCICD\Rayin-<ADO run ID>-<完整 GitLab SHA>.zip`。
- Copy task log 有 `Delivered ZIP:` 與相同 SHA-256；ZIP 內無 `.git`，沒有被解壓，也沒有啟停服務。

不要填 `latest`、branch 名、短 SHA 或 ADO tool commit。每次事件固定自己的 SHA；若後來有新的 push 排隊，也不能換成較新 tip。VM2 使用 `DownloadBuildArtifacts@1 buildType: current`，不下載其他 run 的 latest。[1]

## 第五步：手動交付成功後，才設定 GitLab 自動觸發

使用 Custom headers＋Custom webhook template，直接呼叫**有認證的 Runs REST**；不使用原本 `gitlab-ado-smoke-rs` 公開 endpoint。[3][4]

### 5.1 ADO 觸發 credential

由有權人員準備專用低權限身分與短效 PAT：

- scope：**Build (Read & execute)**，作用域限本 collection。現場為排查 unresolved-ref 曾補上 **Code (Read)**，但同一 400 未解決；不能據此宣稱 Code scope 就是 Runs API 的根因。下節的直接 Git Refs GET 查詢需要 Code 讀取 scope，PAT 身分也必須有對應 repo Read；scope 不會賦予帳號本來沒有的權限，不再加 Write／Manage／Full access。
- 有效權限只允許 queue 此交付 pipeline；不授予 edit pipeline、repo write、管理權或其他 deployment definition 權限。PAT scope 本身不是 pipeline-specific ACL。
- 保護現有 ADO repo 的可執行分支／歷史定義與 pipeline 編輯權限，盤點可 queue 身分能否透過 `resources.repositories.self` 選到不受信任 YAML。payload 的正常 ref pin 不是防止持有人改 request 的安全邊界。
- 對 Environment／pool／Library 只授權這支 pipeline；保留既有測試環境權限，正式資源必須有放行邊界。

**PAT 不放 YAML／GitHub／GitLab Secret token 欄位，也不要貼給助理。** 在受控 Windows PowerShell 本機將 PAT 轉為 Authorization value 並複製到剪貼簿（不要輸出到 log）：

```powershell
$secret = Read-Host 'Short-lived ADO trigger PAT' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    $pat = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $value = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(':' + $pat))
    Set-Clipboard -Value $value
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    $pat = $null; $value = $null; $secret = $null
}
```

貼上 Custom header 後清除剪貼簿：`Set-Clipboard -Value ''`。Base64 仍是 secret，不是加密；避免共用剪貼簿／歷史記錄。

### 5.2 Rayin → Settings → Webhooks → Add new webhook

| 欄位 | 設定 |
|---|---|
| URL | `http://10.92.4.86/DefaultCollection/Deployment/_apis/pipelines/5/runs?api-version=7.1` |
| Custom headers → Name | `Authorization` |
| Custom headers → Value | 直接貼上一步剪貼簿的完整字串（已含 `Basic`＋一個空格，不加尖括號／引號） |
| Custom headers → 第二筆 Name／Value | `Content-Type`／`application/json`（現場使用者已補齊） |
| Trigger | 只勾 **Push events** |
| Push branch filter | **Wildcard pattern**，填 `poc/cicd`；不是 regex，不加 `refs/heads/` |
| Secret token | 留空；它不是 ADO PAT 欄位，也不是 ADO HMAC |
| SSL verification | 保持啟用 |
| Custom webhook template | 下方完整 JSON |

`ADO_COLLECTION_URL` 沿用原 ADO collection base（不含 `/Deployment`）；pipeline ID 是新 pipeline URL 的 `definitionId`，不是某筆 run 的 `buildId`。HTTPS 優先；若僅 HTTP，未取得**獨立且明確**核准的隔離 PAT 傳輸例外前，不建立含 credential 的 webhook。

完整 template（亦可用[此 JSON 檔](../../cicd/gitlab-ado/ado/gitlab-file-delivery-push.template.json)）：

```json
{
  "resources": {
    "repositories": {
      "self": { "refName": "refs/heads/poc/webook-smoke" }
    }
  },
  "templateParameters": {
    "gitlabCommitSha": "{{checkout_sha}}",
    "allowInsecureHttpLab": true
  }
}
```

這是 **GitLab webhook template**，不是 `.gitlab-ci.yml`。`checkout_sha` 綁定這次 push，不是用 GitLab SHA 覆寫 ADO repo 的 `self.version`。本檔及連結 JSON **已依使用者指定的 PRIVATE NETWORK HTTP POC 明確設為 `allowInsecureHttpLab: true`**，不是通用安全預設；來源改 HTTPS 時應改回 false。script／手動 YAML 的預設仍為 false。這個參數只允許 HTTP Git 取碼，不會加密流量或保護 GitLab → ADO 的 PAT 傳輸。template 不含 PAT，Authorization 仍只在 GitLab Custom headers 設定。

建議正常請求再於 `self` 加上 `version: <已審核的ADO工具完整commit SHA>` 釘住工具版本，後續更新工具時同步；這仍不取代 queue ACL／repo 信任邊界。Server 若回 API version unsupported，保留非敏感錯誤核對安裝版；不因 cloud 文件而猜最新版本可用。[3]

### 此次 400 已定位：ADO ref 拼字不一致

唯讀報告顯示 definition 5／repo `Deployment` 的 API 都回 200，但對原請求的 ref 精確查詢為 0；成功 run 的歷史 branch 紀錄不能當成現存 ref 的證據。使用者隨後提供 ADO Branches 截圖，實際分支清楚是：

```text
現存 ADO 分支：poc/webook-smoke
原本誤填：    poc/webhook-smoke
```

**本次只更新 GitLab Rayin 那筆 webhook 的 Custom webhook template**，使用上面的完整 JSON（或連結的最新 template 檔），使 `self.refName` 為 `refs/heads/poc/webook-smoke`。Name 少了 h 是現場既存名稱，保留它；不用改 ADO pipeline YAML／三支 scripts、不建立／重新命名分支、不再加 scope。GitLab app branch／push filter 仍是 `poc/cicd`，Authorization 與 Content-Type 保持已通過的設定。

儲存後依下一節做 `poc/cicd` 的受控真 push 驗收；這次會真的 queue pipeline 5 並交付 ZIP。GitHub 的 commit／push 只更新參考套件，不能代替使用者在公司 GitLab 儲存 webhook。

### 唯讀核對工具（供後續相同類型問題使用，不是本次必要下一步）

先前為排查上述 400 加上 `Code → Read` 仍未解決；已知拼字錯誤後，不再擴權、改成 main 或刪除 `resources`。如日後仍需核對，下載[唯讀查詢工具](../../cicd/gitlab-ado/tools/Test-AdoPipelineReference.ps1)到你本機 Windows 的工作目錄（不是放進 GitLab repo，也不是新增 pipeline task），用 **Windows PowerShell** 執行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Test-AdoPipelineReference.ps1
```

提示時輸入 **與 webhook 相同的原始 ADO PAT**，不是 `Basic ...` 編碼後的整串，也不是 GitLab deploy token。PAT 以隱藏輸入接收，不寫入檔案或輸出；此工具同樣依本次 HTTP POC 使用已提供的內網 URL。預設 project URL、pipeline `5`、`refs/heads/poc/webook-smoke` 都已填好。

工具只執行 GET，**不建立 run、不執行 pipeline、不改 ADO／GitLab 設定、不派送 VM2**，也不跟隨 redirect／使用 Windows 自動登入。查詢：

1. Build definition 5：實際 repo ID／名稱／類型、default branch、YAML path。
2. 該 repo 的精確 ref（用前綴查詢後再核對 exact name）：HTTP status、可見的 exact count／tip commit。
3. 同 definition 最近一筆成功 run：repo ID、ADO source branch／tool commit，以便比較 pipeline 是否換了綁定。

只回報篩選後的 JSON 欄位；server error body、其他 definition variables、身份詳細資料、Authorization／cookies 都不輸出。可貼這份工具輸出的 JSON，不要貼 PAT 或 GitLab Request headers。`lastSuccessfulAdoToolCommit` 是 **ADO 流程 repo** 的 commit，不是 GitLab app 的 SHA，不能拿來填 `gitlabCommitSha`。

判讀不超出證據：

- `definitionHttpStatus` 非 200：先處理此 PAT／URL 下的 definition 讀取結果，工具不再繼續查其他 endpoint。
- `refsHttpStatus` 401／403／404：讀取被拒或資源不可見，`exactRefCount` 保持 null，不當成分支已被刪除。
- `refsHttpStatus=200`、`exactRefCount=0`：這次查詢沒有精確匹配的可見 ref，不拿相似名稱（例如 `...-old`）當成成功。
- `exactRefCount=1`：此 PAT 已能讀到該 ref；若 Runs 仍 400，接著比對 GitLab 實際送出的 `resources.repositories.self` 與這份 report，而不是再加權限。
- 現在的 `adoRepoId` 與 `lastSuccessfulRepoId` 不同：有 definition 綁定／成功 run 來源差異的直接證據，先核對再決定修正，不自動切換 repo 或版本。

本機以假的 ADO HTTP fixture 執行真實 PowerShell 工具，驗證 **9/9 通過**：正常 metadata、相似 ref、ref 拒絕、非預期 JSON、repo 差異、redirect 不跟隨、definition 401 不洩漏資料，另重現「原誤填 ref 查不到現存分支」，並鎖定 template／診斷預設使用截圖確認的拼字。這不代表已在公司環境重跑自動交付。[16][17][18]

### 5.3 真 push 驗收

在 GitLab **既有 `poc/cicd`** 做允許的測試提交／push，確認：

1. Recent events 的 response 為成功且有新的 ADO run ID，不只是舊 smoke 收到 HTTP 200。
2. ADO 新 run 的 SHA、ZIP manifest 與 GitLab 該次 push SHA 完全相同。
3. `SECSVR4-80` 的 `D:\TestCICD` 出現相同 run ID／SHA／SHA-256 的 ZIP，舊包仍在。
4. 其他 branch 的 push 不觸發**這個 webhook**。UI Test 只能當 sample payload；不能取代真 push 的 branch filter／SHA 驗收。
5. 空／`null`／全零 SHA 應在 fetch 前拒絕，沒有 Deliver；可手動提交無效參數驗證，**不要為驗收而刪除真的 `poc/cicd`**。

GitLab 可能重送，ADO Runs API 不提供本套件的持久去重；可能產生不同 ADO run ID 的重複 ZIP，不宣稱 exactly-once。GitLab Rails／Sidekiq 都要能連 ADO，目的地需符合 GitLab outbound allowlist。驗收後停用不再需要的短時 smoke，撤銷測試 token。

## 契約與失敗行為

- ZIP 只含該 SHA **checkout 後的 tracked regular files**，保留相對路徑／dotfiles，不包含 `.git`、untracked files 或交付 metadata；Git checkout 的 `.gitattributes` 換行設定仍適用，不宣稱逐 blob 的 raw archive。
- 明確拒絕 LFS pointer、symlink、submodule；不把 pointer／空目錄冒充完整內容，不執行其 hooks／filters／app code。
- ZIP hash 是傳輸一致性證據，不是簽章或部署授權。
- VM2 核對固定 repo／ref／SHA／ADO run／filename／size／SHA-256，metadata 留在 ADO artifact，目的地只送 ZIP。
- 不解壓，所以不會將來源 ZIP entry 寫入目的目錄。目的地必須是正常本機絕對路徑，不允許 drive root、UNC、`..` 或既有 junction／symlink。
- 先複製暫存檔、驗 hash，再在同目錄 rename 成最終 ZIP；不同內容的同名檔拒絕、不覆蓋。相同包重試可直接驗證成功。從不 mirror／purge／刪除既有包或目的目錄。
- ADO artifact／stage retry 與 retention 依現場設定；本 POC 不提供 rollback、耐久去重或自動清理機制。

## VM1 checkout 的 `gitVersion` null 修正

使用者回報 **PackageSource／`SECSVR004-086T`** 在 ADO 自己的 checkout 失敗：

```text
Syncing repository: Deployment (Git)
Prepending Path environment variable with directory containing git.exe
git version
error launching git:
Value cannot be null. (Parameter 'gitVersion')
```

這是在取 Git 版本時失敗，**還沒進入 GitLab fetch／credential 步驟**。Agent source 的 prepend 訊息出自內附 Git 分支；Git launcher 無法啟動導致沒有可解析版本。仍不能僅靠這段 log 斷言是 bundle 損毀或特定 Windows／防毒問題。[6][7]

修正版僅調整 VM1：

- PackageSource 設 `System.PreferGitFromPath: 'true'`。
- 在 `checkout: self` **前**以 inline PowerShell 實測 Git for Windows 2.31+，依序檢查 Program Files 安裝、服務帳號 PATH、Agent bundle；不能啟動／沒有版本的候選者會跳過。
- 印出選用的 executable 與版本，以 `task.prependpath` 交給後續 checkout／取碼；不是只改 PowerShell 當下的 PATH。
- 若都不可用，在 checkout 前停止並明確要求 VM 管理者安裝／修復核准的 Git，不自動下載，不改 Agent service／token／VM2。

**現場只需更新一個檔案**：ADO 原 repo／`poc/webook-smoke` 的 `/azure-pipelines-gitlab-file-delivery.yml`，完整取代為[最新版](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery.yml)。不用改三支 scripts、不重建 pipeline。儲存後用 **Run pipeline 開新的 run**，不要只 Retry 舊 run 的 stage；GitLab SHA 沿用欲驗收的完整值，HTTP POC 勾 `allowInsecureHttpLab`。

先看新 task `Select and validate Git before VM1 checkout` 是否印出 `Selected checkout Git:` 與 `git version ...`，再看後面的 checkout 是否成功。**使用者已回報 preflight 與 ADO checkout 通過**，目前不用再改 Git 選用。後續取碼／ZIP 雖顯示綠燈，但因發現 entrypoint 空跑，不能把它們視為實際檔案驗收；需依下節的新 wrapper 重跑。本機沒有代測公司 GitLab credential。

## VM1 上傳 artifact 缺少 `node16` runtime 的修正

最新使用者回報：Git preflight、checkout、GitLab 取碼與 ZIP task 全部通過，但 `Store ZIP and integrity/provenance for this ADO run` 在 task 啟動時回報：

```text
Required Node runner is missing:
C:\azagent\A1\externals\node16\bin\node.exe
```

這是現場 `PublishBuildArtifacts@1` task 與 Agent runtime 不匹配，還沒進入上傳程式，不是 ZIP 驗證失敗或 GitLab token 問題。**不重新取 token、不自動下載 Node，也不更改 Agent 安裝。**

新版僅把這個 Publish task 改成已在現場可執行的 `PowerShell@2`，發出 Agent 原生 `artifact.upload` logging command；Agent source 支援整個目錄遞迴上傳，並在上傳後將 `Container` artifact 關聯到當前 build。原 Publish task 本身也使用相同指令。[9][10]

- 只允許 package 目錄裡的 ZIP、manifest、provenance 三個普通檔案；缺檔、額外檔案或目錄／連結會在發出上傳指令前拒絕。
- 保留 artifact 名稱／container folder `source-package`、同一 ADO run、原 ZIP bytes；無額外 PAT、UNC share 或 Pipeline Artifacts。
- 由 Agent 的現有 job connection 完成上傳；非同步上傳／關聯錯誤仍由 Agent 回報 step 失敗。不要設定 `continueOnError` 或在上傳後清理 package。
- VM2 的 `DownloadBuildArtifacts@1 buildType: current` 不變；VM2 自己的 runtime 可用性尚未驗收，不因這次 VM1 錯誤就預先改掉 consumer。

**現場仍只需更新同一份** `/azure-pipelines-gitlab-file-delivery.yml`（ADO 原 repo／`poc/webook-smoke`），再 **Run pipeline 開新 run**，完整 SHA 與 `allowInsecureHttpLab` 沿用。三支 scripts、variable group、pipeline definition 都不用重建。

上傳成功的驗收是新 run 的 `source-package` artifact 確實含 ZIP＋兩份 JSON，且 Package stage 成功；PowerShell 印出 upload 指令本身不代表 Server 已收妥。接著才觀察 Deliver／VM2。此修正本機僅測指令／檔案檢查契約，尚未連公司 Server 驗證傳輸。

## ZIP task 綠燈但上傳目錄不存在：腳本入口修正

使用者套用原生上傳版本後，`Store ZIP...` 在 `Source package directory is missing; nothing published` 停止。**本機已重現同一種成功空跑模式**：

```text
. New-GitLabSourcePackage.ps1 <arguments>
# 沒報錯、沒有建立 package；只載入 function
& New-GitLabSourcePackage.ps1 <arguments>
# 實際進入 main，驗證來源並封裝
```

Microsoft 的 PowerShell@2 Windows／TypeScript runner 都會將 `targetType: filePath` 的目標腳本 dot-source（`.`）。我們的三支腳本用 `$MyInvocation.InvocationName -ne '.'` 保留「直接執行才進 main、helper import 不自動執行」的邊界，因此在舊 task 寫法下 main 被跳過。[11][12]

**不能只加 `runScriptInSeparateScope: true`**：它改的是 task 生成之暫存 wrapper 的執行方式，內層 `filePath` 仍會 dot-source。可靠修正是將 Get／New／Copy 三個 task 都改成 `targetType: inline`，明確用 `&` 呼叫既有腳本，保留 helper／離線測試需要的 import guard。[11][12]

- 新 wrapper 的來源、證據、package 路徑皆以同一組 Agent environment 變數計算。
- ZIP wrapper 在腳本返回後立即確認 manifest 已存在，並印出 `Source package directory:`；上傳步驟也印出自己讀取的完整目錄，不再用綠燈推論有檔案。
- VM2 Copy wrapper 亦明確 `&` 執行，否則相同問題會使 Deliver 假成功。目的目錄仍是受控 YAML 固定的 `D:\TestCICD`，不接受 webhook 指定。
- 這不是 token scope 或 Server 上傳 API 的問題，不改 credential、不改已通過的 checkout workaround，也不 fallback 搜尋其他 run 的 ZIP。

**現場只需再次完整更新交付 YAML**（同一 ADO repo／`poc/webook-smoke` 的 `/azure-pipelines-gitlab-file-delivery.yml`）。三支 scripts 不用改。另有同步修正診斷用 source-only YAML 的相同 Get 呼叫；沒使用該 pipeline 就不用額外操作。

儲存後 **Run pipeline 新 run**，保留完整 GitLab SHA，HTTP POC 勾 `allowInsecureHttpLab`。本次要確認真正的輸出：

1. Get task 有 `Checked out exact GitLab commit ...`，不是只顯示 task 起訖。
2. ZIP task 有 `Packaged ...`、ZIP SHA-256、`Source package directory: ...`。
3. 上傳讀取相同目錄，run 的 `source-package` artifact 含 ZIP＋兩份 JSON。
4. Deliver task 有 `Delivered ZIP:`，VM2 目的目錄確實有相同 ZIP／hash。

本機回歸直接執行 YAML inline wrappers，以 real Git fixture 實際產生 ZIP、複製到暫存目的地並核對內容／SHA／hash；Get wrapper 以無效 SHA 驗證確實進入 main 且在 network／credential 之前拒絕。這修正了先前測試只以 `& script.ps1` 執行、沒有覆蓋 task 呼叫方式的缺口；不宣稱已連公司 GitLab 或完成現場交付。

## Read task 約 5 分鐘 timeout：先取得實際 fetch 證據

使用者回報新版 Read task 執行約 **5 分鐘 3 秒** 後 `Git timed out; no source checkout accepted`，之後診斷版的 `temporary-pack-bytes` 持續為 0。fetch 的設定上限是 300 秒，其他 Git 子命令是 120 秒；這指向 fetch 等待，但 **pack 為 0 只代表未觀察到本機 pack 檔資料，不足以斷言 token、TCP、proxy 或 Server 狀態**。

現有 fetch 會讀取固定 branch 的歷史，以驗證指定 SHA 的 ancestry；不是只下載一個 ZIP 或一個 commit。若 repo 歷史很大可能影響時間，但**未取得進度前不直接增加 timeout，也不偷改 shallow／latest，避免變更精確版本驗證契約**。

本輪只為 `Get-GitLabSource.ps1` 補診斷：

- 每個 Git 子命令的 start／completed、已用時間及自己的 timeout。
- fetch 等待期間每 15 秒回報暫存 pack 檔總 bytes；增加代表本機 pack 活動，**一直為 0 不等於證明 TCP／HTTP 從未連上**。
- fetch 改 `--progress`，但不原樣輸出 stderr；結束或超時時，只報 Counting／Receiving／Resolving 的白名單數字摘要。
- 已返回的明確錯誤僅報 authentication／connection／name-resolution／tls／low-speed 類別，不輸出 URL、headers、token、remote 文字、stdout 或完整 argv。
- 該診斷輪次仍維持 300 秒，逾時終止 Git process tree，不發布 source／evidence／ZIP，不切換版本或目標；最新 900 秒調整依據見下節 Receiving 92% 的新證據。

**本次現場只更新 script，不用再改 YAML**：ADO 原 repo → `poc/webook-smoke` → `/scripts/Get-GitLabSource.ps1`，完整取代為[最新版](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1)。保留已修正 inline `&` 的交付 YAML，按 Run pipeline 開新 run、沿用完整 SHA、勾 `allowInsecureHttpLab`。

回報以下 `[GitSource]` 行即可，不需 token 或全份 debug log：

```text
[GitSource] start fetch; timeout=300s
[GitSource] fetch elapsed=15s; temporary-pack-bytes=...
...
[GitSource] Receiving objects ...
Git timed out during fetch after 300s; no source checkout accepted.
```

若出現持續增加的 pack bytes／Receiving，下一步才評估傳輸量／速度與 timeout／封裝策略。若沒有這類證據，先核對 VM1 → GitLab 的連線／proxy／Server 回應；不能把 GitLab → ADO webhook 已通當作反向取碼也通。已有[無憑證 connectivity pipeline](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)可獨立核對 HTTP response，但其 .NET HTTP 路徑與 Git/proxy 不一定相同，亦不代表 authenticated fetch 成功。

**上一輪已改跑短時匿名連通，而非重等 fetch 的 300 秒**：更新 ADO 原 repo／`poc/webook-smoke` 的 `/azure-pipelines-gitlab-connectivity.yml`，完整使用[新版 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)。沿用 `GitLab-Connectivity-VM1`；若尚未建立，就 New pipeline → 同一 repo／同一 ADO branch／Existing YAML 選此檔。這不是 ZIP 交付 pipeline，沒有 credential group、checkout、Git executable 或 VM2 工作，只在 `SECSVR004-086T` 做 request timeout 15 秒的匿名 HTTP probe（job 上限 2 分鐘）。

回報 Agent.Name 與 `Anonymous GitLab HTTP status:`，或 `No HTTP response ... WebExceptionStatus=...`；proxy 只顯示有／無，不回報值。收到 200／401／403 只證明收到 HTTP 回應；沒有回應才先查此 Agent 的 route／proxy／服務。若 probe 成功而 Git 仍無進度，再比對 Git 與 .NET 的 proxy／認證／Server Git backend 等證據。不能用互動式登入者瀏覽器可開頁面，代替 Agent 服務帳號的連線驗收。本機已用 loopback HTTP fixture 執行同一段 inline probe，確認 401 接收、302 不跟隨、404 拒絕、無 Authorization／Cookie header、proxy 值不輸出；沒有連公司 endpoint。

這是診斷增補，**不是已解決現場 fetch timeout**。本機用受控 executable 重現實際 runner 的 timeout／終止路徑（縮短至 1 秒），另以 16 秒等待驗 heartbeat，並檢查憑證及 remote 文字不出現在日誌；沒有連公司 GitLab。

## 匿名 HTTP 401／三個 proxy 變數 False 後：同 Git 的 30 秒 ref probe

使用者已回報同一 VM1 的匿名 HTTP 約 5 秒收到 401，以及 `HTTP_PROXY`／`HTTPS_PROXY`／`NO_PROXY` 均為 False。這只能證明該 .NET HTTP request 收到回應與這三個環境變數未設定；不證明 Git 認證成功，也不排除 `ALL_PROXY` 等來源。

下一步 **只更新 ADO 原 repo／`poc/webook-smoke` 的 `/scripts/Get-GitLabSource.ps1`**，使用[最新版完整腳本](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1)，交付 YAML 不用改。以 `GitLab-Rayin-Zip-Delivery` 開新 run、原本完整 GitLab SHA、HTTP checkbox 勾選。

新版先用與 fetch 相同 Git、相同 runtime-only credential／隔離 config，在 **30 秒**上限內執行 `ls-remote --exit-code --refs origin <固定 source ref>`；不下載歷史、不列出或記錄其他 refs、不執行應用程式。只接受固定 ref 的單一有效 commit advertisement。成功後仍依原契約 fetch／驗 ancestry／checkout 輸入的 SHA，**不拿 probe 看到的 tip 偷換所選版本**。[13]

| 新的結果 | 能縮小的範圍 |
|---|---|
| `Git timed out during ls-remote after 30s` | Git 讀取 ref 就卡住，還沒下載歷史；先查 Git transport／Server 回應，不以 repo 歷史很大作結論。 |
| `category=authentication` | Git 返回可辨識的認證／存取錯誤，核對 Rayin token Username、期限、`read_repository` 與帳號存取政策；不先加大權限。 |
| `category=ref-not-found` | Git 以 `--exit-code` 回傳 2，確認固定 `refs/heads/poc/cicd` 存在及權限。 |
| `Git ref probe passed`，之後 fetch 才 timeout | ref 讀取已通，問題縮小至後續協商／pack 準備與下載等；仍不能只據此認定為速度或包太大。 |

回報 `[GitSource] ALL_PROXY present:`（只要 True／False）、`start ls-remote`、`completed ls-remote`／`Git ref probe passed` 或最後的 timeout／category 行，不要貼 credential／原始 stderr。

安全契約現在明確允許 **ref probe 與 fetch 兩個固定來源的唯讀子程序**各取得一次短時 URL-scoped header；其他子命令不帶 credential，沒有持久化設定、額外 PAT 或公開 webhook 授權。Probe 失敗不進 fetch、不發布 source／evidence／ZIP，清理本次暫存目錄。這是分離故障階段的診斷，不是已解決現場 timeout。

本機另以真實 Git client 對 loopback smart-HTTP fixture 執行相同 helper，驗證固定路徑帶短時 header 能讀 ref、錯誤 credential 安全分類為 authentication、缺 ref 分類為 ref-not-found，且不建立 `.git`／credential config。此 fixture 使用假 credential，不是公司 GitLab 的驗收。

## Ref probe 已通、fetch 仍無 pack：取得 fetch 的 HTTP 階段證據

使用者已回報 `Git ref probe passed; fixed source ref is readable`，接著 fetch 在 300 秒 timeout，暫存 pack bytes 仍為 0。這排除了「同一 Git 根本無法讀取固定 ref」的情況；**不應因此重建 token，也不能只憑 pack 為 0 就認定 repo 太大／完全沒連線**。

這時要區分 fetch 的 HTTP request 是否得到回應，而不是再做一次匿名 HTTP。另須注意：依 Git protocol 版本，`ls-remote` 本身也可能使用 POST，故不能把目前結果簡化成「GET 通、POST 不通」。[14]

**現場只更新 `/scripts/Get-GitLabSource.ps1`**（ADO 原 repo／`poc/webook-smoke`，同一[完整腳本](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1)），YAML／credential 不變。跑 **`GitLab-Rayin-Zip-Delivery` 的新 run**，原完整 SHA，HTTP checkbox 勾選。

新版只對 fetch 子程序啟用 `GIT_TRACE_CURL=1`、`GIT_TRACE_CURL_NO_DATA=1` 與 `GIT_TRACE_REDACT=1`；trace 只導向該子程序的私有 stderr 記憶體，不落檔、不原樣輸出。返回／timeout 後，只從白名單解析 method（GET／POST）與三位數 HTTP status，原始 headers、URL、cookies、credential 和 body 都不進 pipeline log。[15]

回報 task 尾端新增的行，例如：

```text
[GitSource] HTTP request 1: method=GET; response-status=200
[GitSource] HTTP request 2: method=POST; response-status=not-observed
```

或第二行為 `response-status=200`／其他 status。

| 觀察 | 下一個有證據的查核方向 |
|---|---|
| POST `not-observed` | client trace 未觀察到這個 request 的回應 status；依同一 run 的時間查 GitLab／中間設備是否收到並完成請求。這不是證明 backend 一定沒收到。 |
| POST `200` 但無 pack／Receiving | 已觀察到 HTTP response status，不代表 Git payload 已完整開始／完成；對照 Server pack 準備、串流與 client trace 同時段。 |
| 401／403／其他 status | 依 fetch request 的實際 status 查 Server／權限／中間設備，不把匿名 probe 的 401 混為同一個證據。 |
| 沒有 method/status events | 記錄不足，不據此宣稱沒有送 request；需進一步在 Agent／Server 端對照。 |

status 是 client 觀察到的最後一個 response code，可能含中間或 provisional response，不是完整 HTTP transaction／Git 成功驗收。**該 HTTP 診斷輪次未延長 300 秒、不改 HTTP 協定版本、不降為 shallow、不換成 latest，也不要求使用者貼 raw trace**。收到下面的 Receiving 92% 新證據後，才調整下載時間上限。

若再次卡在 POST 等待或 200 後無資料，就用此次 ADO run ID、起訖時間、已成功讀 ref／fetch method/status 與 GitLab 管理者對照相同時段的 access／backend 紀錄；不再無根據地輪換 token 或重等同一份 run。

本機用實際 Git＋loopback smart-HTTP fixture（假 credential）分別重現 POST 不回 header，以及 POST 回 200 後不送 body，確認摘要能區分且不輸出 auth／cookie／URL；另以受控 executable 檢查同樣資訊邊界。這不是公司 GitLab 的根因重現或現場修復。

## 已觀察到 Receiving 92%：將完整 fetch 總上限調為 15 分鐘

使用者提供：

```text
Counting objects: 100% (6194/6194)
Receiving objects: 92% (5731/6194)
```

這是實際 Git 接收進度，足以否定「完全沒有下載」的假設；`temporary-pack-bytes=0` 不是這次傳輸的可靠完成度指標。**92% 是 Git 物件數比例，不是 bytes 比例，也不證明最後 8% 只需要很短時間或一直持續前進**。

基於已收到資料但遭原 300 秒總 deadline 中止，本輪將固定 full-history fetch 上限改為 **900 秒（15 分鐘）**。這是有依據的時間預算調整，不是宣稱已確認全部效能根因。以下不變：

- 30 秒的 `ls-remote` probe、其他 Git 子命令各 120 秒。
- 原有 `http.lowSpeedLimit=1`／`http.lowSpeedTime=30`（HTTP 低速判斷，不等於 Git 物件進度 watchdog）。
- 完整固定 branch fetch、SHA existence／ancestry／detached HEAD 驗證，不 shallow、不改成最新 tip。
- 超時／失敗仍終止，沒有半成品 source／evidence／ZIP 發布或 VM2 派工。

**現場仍只更新一支 script**：ADO 原 repo／`poc/webook-smoke` 的 `/scripts/Get-GitLabSource.ps1`，使用[最新版完整腳本](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1)。交付 YAML 不用改；現有 Package job 的外層上限為 20 分鐘。source-only 診斷 YAML 另同步調為 20 分鐘，以容納 15 分鐘 fetch，未使用該診斷 pipeline 就不必更新它。

然後跑 **`GitLab-Rayin-Zip-Delivery` 新 run**，ADO branch `poc/webook-smoke`、原完整 GitLab SHA、`allowInsecureHttpLab` 勾選。先確認日誌是 `start fetch; timeout=900s`。真正取碼完成的證據是 `completed fetch`、後續 SHA／HEAD 驗證與 `Checked out exact GitLab commit ...`；僅 Receiving 100% 仍不是整條交付完成。

若在 900 秒後仍失敗，或一直停在同一個 Receiving 數值，不再反覆提高上限。需提供該次 run 的最後 Counting／Receiving／Resolving、HTTP 摘要與時間，查是否大物件、吞吐量／串流或本機資源停滯；若是外層 job timeout，亦需區分於 fetch timeout。單憑目前百分比不指定某個效能根因。

## 本機檢查與現場故障排查

本機 Windows PowerShell 5.1：Git process 診斷檢查 **26/26 通過**（受控 executable 驗 timeout／heartbeat／安全分類／數字進度及 stderr 不洩漏，未測公司 GitLab）；task entrypoint 檢查 **8/8 通過**（實際 YAML wrappers、real Git ZIP／manifest／Copy／hash、Get 入口前置驗證、helper import 不執行 main）；原生 artifact upload 檢查 **12/12 通過**（直接執行 YAML inline code：固定 artifact／root、只發一次目錄指令、path escaping、缺檔／額外檔案／假 ZIP 目錄不發上傳指令、不修改 package；未測 Server 傳輸）。Git bootstrap 檢查 **7/7 通過**（正常 Git、無法啟動的 executable、exit 0 但沒有版本、完全無可用 Git、PATH 輸出及 checkout 前順序）；這不是 ADO Agent 的現場重現。既有取碼回歸 **21/21 通過**（另核對 probe 30 秒、fetch 900 秒、先 probe 再 fetch、probe 失敗不下載、錯誤 ref 拒絕，歷史 SHA 不換成 probe tip）。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitSourceDiagnostics.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-PowerShellTaskEntrypoints.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-BuildArtifactUpload.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitCheckoutBootstrap.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitLabSource.ps1
```

三支交付 script parser、YAML／JSON parsing 先前通過。另以暫存 real-Git fixture 實際執行新 ZIP／Copy 腳本，確認 tracked dotfile／Unicode filename 可封裝、untracked 不入包、`export-ignore` 不漏包、只放 ZIP、hash 相同及相同包重試不覆蓋；手動拒絕檢查涵蓋篡改 ZIP、不同內容同名檔保留、`..` 目的路徑、錯誤 run、全零 SHA、LFS pointer 與失敗後不發布／清理暫存。這是本機操作檢查，不是現場 E2E 證據。

| 現象 | 檢查 |
|---|---|
| VM1 checkout 的 `gitVersion` null | 依上節更新同一份 YAML；先看 preflight 選用的 Git／版本，沒有可用 Git 時修復 VM1 工具安裝，不改 GitLab token。 |
| HTTP refused | 預期安全預設；本次內網 HTTP POC 勾 `allowInsecureHttpLab`，不關 TLS。 |
| Fetch 401／403 | Rayin 的 token Username／期限／`read_repository`；勿誤用 Tools.Rs project token。 |
| Environment/resource not found | `test-deploy-agent`、`SECSVR4-80`、case-sensitive `virtualMachine`、Agent online／pipeline resource authorization。 |
| Fetch 有 Receiving 92% 後撞 300 秒 | 更新 Get script 至 900 秒版本，確認 `timeout=900s`，不改 YAML／token；若仍卡固定進度，不再盲目加時間，依該 run 的進度／HTTP／資源證據定位。 |
| ZIP task 綠燈但 source package directory missing | 更新交付 YAML 的三個 inline `&` wrappers；確認 Get／ZIP 的實際 SHA、包名與完整目錄輸出，不只看 task 綠燈。 |
| VM1 Publish 缺少 `externals\node16\bin\node.exe` | 更新同一份 YAML，使用 PowerShell 發出原生 Build Artifact upload 指令；不重新建 token 或自動安裝 Node。 |
| DownloadBuildArtifacts@1 不存在／缺 runtime | 查 VM2 的 Server task／Agent runtime；VM1 上傳修正不代表 VM2 已驗收，提供該下載 task 的非敏感錯誤再定位。[1] |
| D: absent／Access denied | 查 VM2 本機 D: 與 Agent 服務帳號 ACL，不給 GitLab VM 密碼或改成 VM1 share copy。 |
| LFS／submodule／symlink refused | 本 POC 未支援；先定義需求，不略過檢查當完整交付。 |
| ZIP hash／run／SHA mismatch | 停止，查是否下載錯 run 或 artifact 被替換；不 fallback 到 latest。 |
| Webhook unresolved-ref 400；補 Code Read 無效 | 本次已由截圖確認 ADO 分支為 `poc/webook-smoke`，template 曾誤填 `poc/webhook-smoke`；只修正 GitLab Custom webhook template 的 self ref，不重建分支、不改 main、不再擴權。 |
| GitLab webhook 401／403 | 分辨 ADO／IIS／proxy；查 PAT、有效 queue ACL、傳輸政策，不開 IIS Basic。[5] |
| HTTP 200 但檔案未到 | 200 只代表新 run 被建立；查 Package／Deliver／Environment checks 與新 run ID。 |

[1]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/download-build-artifacts-v1?view=azure-pipelines-server
[2]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/environments-virtual-machines?view=azure-devops-server
[3]: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-server-rest-7.1
[4]: https://docs.gitlab.com/user/project/integrations/webhooks/
[5]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-server
[6]: https://github.com/microsoft/azure-pipelines-agent/blob/master/src/Agent.Plugins/GitCliManager.cs
[7]: https://github.com/git-for-windows/MINGW-packages/blob/main/mingw-w64-git/git-wrapper.c
[8]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/windows-agent?view=azure-devops-server#what-version-of-git-does-my-agent-run
[9]: https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops#upload-upload-an-artifact
[10]: https://github.com/microsoft/azure-pipelines-agent/blob/v2.214.1/src/Agent.Worker/Build/ArtifactCommandExtension.cs
[11]: https://github.com/microsoft/azure-pipelines-tasks/blob/master/Tasks/PowerShellV2/powershell.ps1
[12]: https://github.com/microsoft/azure-pipelines-tasks/blob/master/Tasks/PowerShellV2/powershell.ts
[13]: https://git-scm.com/docs/git-ls-remote
[14]: https://git-scm.com/docs/http-protocol
[15]: https://git-scm.com/docs/git#Documentation/git.txt-GIT_TRACE_CURL
[16]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/definitions/get?view=azure-devops-server-rest-7.1
[17]: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/refs/list?view=azure-devops-server-rest-7.1
[18]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-server-rest-7.1

原 Publish task 的 [Container 分支](https://github.com/microsoft/azure-pipelines-tasks/blob/master/Tasks/PublishBuildArtifactsV1/publishbuildartifacts.ts) 發出 `artifact.upload`；[FileContainerServer source](https://github.com/microsoft/azure-pipelines-agent/blob/v2.214.1/src/Agent.Worker/Build/FileContainerServer.cs) 處理目錄內容與相對路徑。

Microsoft 文件列明 [`System.PreferGitFromPath`][8] 可覆寫 Windows Agent 的內附 Git 選用；這不會修復 Git 安裝本身。

觸發方式的第一方來源與版本限制見[研究筆記](../research/gitlab-ado-file-delivery-trigger.md)。
