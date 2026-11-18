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
| ADO YAML branch | 沿用 `poc/webhook-smoke`，不是 GitLab branch |
| VM1 pool／Agent.Name | `Default`／`SECSVR004-086T` |
| VM2 Environment／VM resource | `test-deploy-agent`／`SECSVR4-80`；不是一般 pool 或 Classic Deployment Group |
| VM2 目的目錄 | 本次使用 `D:\TestCICD`；Agent 服務帳號須有寫入權，D: 須存在 |
| GitLab Webhook UI | 使用者已確認有 Custom headers 與 Custom webhook template |
| 取碼 credential／variable group | 使用者已回報完成；不用重建 |
| 本次傳輸 | 使用者指定 PRIVATE NETWORK 的 HTTP；手動 Run 勾 `allowInsecureHttpLab`，HTTP 仍非加密傳輸 |

先前通過的是 Tools.Rs 的網頁 Test → ADO 零動作探針。**最新現場回報：修正 task 入口後，Rayin Read task 實際執行，但在約 5 分鐘 3 秒回報 `Git timed out`，與 fetch 的 300 秒上限相符。** VM1 Git preflight／ADO checkout 已通過；先前取碼／ZIP 的綠燈因 entrypoint 空跑不能算檔案驗收。目前新增階段／安全進度診斷，但尚不能確定是路由／proxy／Server 等待或傳輸量／速度。Rayin 的真實取碼／ZIP、真 push、artifact 上傳／下載及 VM2 放檔仍待驗收。本機未連公司內網，沒有代設 credentials 或操作 VM。

若 VM2 是正式環境，送 ZIP／下載到 Agent workspace 都是 **Production Access**。必須先由授權部署人員放行指定版本與目標，才能開始 `Deliver` stage；在 Environment 資源端設妥 checks／權限並實測，YAML 寫 `environment:` 本身不是核准機制。一般隔離測試環境不額外強迫雙人審批。

## 第一步：同一 ADO 分支放入四個檔案

到 **ADO → Deployment → Repos → 原本 repo → branch `poc/webhook-smoke`**。新增以下 YAML／腳本；若已有 `Get-GitLabSource.ps1`，更新為本版：

| ADO repo 路徑 | 本 repo 的完整檔案 |
|---|---|
| `/azure-pipelines-gitlab-file-delivery.yml` | [完整 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery.yml) |
| `/scripts/Get-GitLabSource.ps1` | [精確 SHA 唯讀取碼](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1) |
| `/scripts/New-GitLabSourcePackage.ps1` | [tracked checkout files 封裝](../../cicd/gitlab-ado/ado/scripts/New-GitLabSourcePackage.ps1) |
| `/scripts/Copy-GitLabSourcePackage.ps1` | [驗證並複製 ZIP](../../cicd/gitlab-ado/ado/scripts/Copy-GitLabSourcePackage.ps1) |

Commit 到**已有的 ADO `poc/webhook-smoke`**，不是 GitLab 的 `poc/cicd`。不改／覆蓋舊 smoke YAML，不建立新 repo 或 branch。

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
2. Branch 選 `poc/webhook-smoke`，path 選 `/azure-pipelines-gitlab-file-delivery.yml`。
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
3. ADO branch 選 `poc/webhook-smoke`；`gitlabCommitSha` 填上述 GitLab SHA。
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

- scope：**Build (Read & execute)**，作用域限本 collection。
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
| URL | `{ADO_COLLECTION_URL}/Deployment/_apis/pipelines/{交付pipeline的definition ID}/runs?api-version=7.1` |
| Custom headers → Name | `Authorization` |
| Custom headers → Value | 上一步剪貼簿的 `Basic <base64>` |
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
      "self": { "refName": "refs/heads/poc/webhook-smoke" }
    }
  },
  "templateParameters": {
    "gitlabCommitSha": "{{checkout_sha}}",
    "allowInsecureHttpLab": false
  }
}
```

這是 **GitLab webhook template**，不是 `.gitlab-ci.yml`。`checkout_sha` 綁定這次 push，不是用 GitLab SHA 覆寫 ADO repo 的 `self.version`。HTTP Git source 若已明確獲准，可將此 template 的 `allowInsecureHttpLab` 改為 `true`；未核准則維持 false 並先改 GitLab HTTPS。它不控制或保護 GitLab → ADO 那一段 PAT 傳輸。

建議正常請求再於 `self` 加上 `version: <已審核的ADO工具完整commit SHA>` 釘住工具版本，後續更新工具時同步；這仍不取代 queue ACL／repo 信任邊界。Server 若回 API version unsupported，保留非敏感錯誤核對安裝版；不因 cloud 文件而猜最新版本可用。[3]

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

**現場只需更新一個檔案**：ADO 原 repo／`poc/webhook-smoke` 的 `/azure-pipelines-gitlab-file-delivery.yml`，完整取代為[最新版](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery.yml)。不用改三支 scripts、不重建 pipeline。儲存後用 **Run pipeline 開新的 run**，不要只 Retry 舊 run 的 stage；GitLab SHA 沿用欲驗收的完整值，HTTP POC 勾 `allowInsecureHttpLab`。

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

**現場仍只需更新同一份** `/azure-pipelines-gitlab-file-delivery.yml`（ADO 原 repo／`poc/webhook-smoke`），再 **Run pipeline 開新 run**，完整 SHA 與 `allowInsecureHttpLab` 沿用。三支 scripts、variable group、pipeline definition 都不用重建。

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

**現場只需再次完整更新交付 YAML**（同一 ADO repo／`poc/webhook-smoke` 的 `/azure-pipelines-gitlab-file-delivery.yml`）。三支 scripts 不用改。另有同步修正診斷用 source-only YAML 的相同 Get 呼叫；沒使用該 pipeline 就不用額外操作。

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
- timeout 仍是 300 秒，逾時終止 Git process tree，不發布 source／evidence／ZIP，不切換版本或目標。

**本次現場只更新 script，不用再改 YAML**：ADO 原 repo → `poc/webhook-smoke` → `/scripts/Get-GitLabSource.ps1`，完整取代為[最新版](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1)。保留已修正 inline `&` 的交付 YAML，按 Run pipeline 開新 run、沿用完整 SHA、勾 `allowInsecureHttpLab`。

回報以下 `[GitSource]` 行即可，不需 token 或全份 debug log：

```text
[GitSource] start fetch; timeout=300s
[GitSource] fetch elapsed=15s; temporary-pack-bytes=...
...
[GitSource] Receiving objects ...
Git timed out during fetch after 300s; no source checkout accepted.
```

若出現持續增加的 pack bytes／Receiving，下一步才評估傳輸量／速度與 timeout／封裝策略。若沒有這類證據，先核對 VM1 → GitLab 的連線／proxy／Server 回應；不能把 GitLab → ADO webhook 已通當作反向取碼也通。已有[無憑證 connectivity pipeline](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)可獨立核對 HTTP response，但其 .NET HTTP 路徑與 Git/proxy 不一定相同，亦不代表 authenticated fetch 成功。

**目前的下一步改跑短時匿名連通，不再重等一次 fetch 的 300 秒**：更新 ADO 原 repo／`poc/webhook-smoke` 的 `/azure-pipelines-gitlab-connectivity.yml`，完整使用[新版 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)。沿用 `GitLab-Connectivity-VM1`；若尚未建立，就 New pipeline → 同一 repo／同一 ADO branch／Existing YAML 選此檔。這不是 ZIP 交付 pipeline，沒有 credential group、checkout、Git executable 或 VM2 工作，只在 `SECSVR004-086T` 做 request timeout 15 秒的匿名 HTTP probe（job 上限 2 分鐘）。

回報 Agent.Name 與 `Anonymous GitLab HTTP status:`，或 `No HTTP response ... WebExceptionStatus=...`；proxy 只顯示有／無，不回報值。收到 200／401／403 只證明收到 HTTP 回應；沒有回應才先查此 Agent 的 route／proxy／服務。若 probe 成功而 Git 仍無進度，再比對 Git 與 .NET 的 proxy／認證／Server Git backend 等證據。不能用互動式登入者瀏覽器可開頁面，代替 Agent 服務帳號的連線驗收。本機已用 loopback HTTP fixture 執行同一段 inline probe，確認 401 接收、302 不跟隨、404 拒絕、無 Authorization／Cookie header、proxy 值不輸出；沒有連公司 endpoint。

這是診斷增補，**不是已解決現場 fetch timeout**。本機用受控 executable 重現實際 runner 的 timeout／終止路徑（縮短至 1 秒），另以 16 秒等待驗 heartbeat，並檢查憑證及 remote 文字不出現在日誌；沒有連公司 GitLab。

## 本機檢查與現場故障排查

本機 Windows PowerShell 5.1：Git process 診斷檢查 **13/13 通過**（受控 executable 驗 timeout／heartbeat／安全分類／數字進度及 stderr 不洩漏，未測公司 GitLab）；task entrypoint 檢查 **8/8 通過**（實際 YAML wrappers、real Git ZIP／manifest／Copy／hash、Get 入口前置驗證、helper import 不執行 main）；原生 artifact upload 檢查 **12/12 通過**（直接執行 YAML inline code：固定 artifact／root、只發一次目錄指令、path escaping、缺檔／額外檔案／假 ZIP 目錄不發上傳指令、不修改 package；未測 Server 傳輸）。Git bootstrap 檢查 **7/7 通過**（正常 Git、無法啟動的 executable、exit 0 但沒有版本、完全無可用 Git、PATH 輸出及 checkout 前順序）；這不是 ADO Agent 的現場重現。既有取碼回歸 **19/19 通過**。

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
| Read task 約 5 分鐘 timeout | 更新 `/scripts/Get-GitLabSource.ps1` 取得 fetch operation／pack bytes／安全摘要；不先增加 timeout、不換成 latest，現場根因尚未確定。 |
| ZIP task 綠燈但 source package directory missing | 更新交付 YAML 的三個 inline `&` wrappers；確認 Get／ZIP 的實際 SHA、包名與完整目錄輸出，不只看 task 綠燈。 |
| VM1 Publish 缺少 `externals\node16\bin\node.exe` | 更新同一份 YAML，使用 PowerShell 發出原生 Build Artifact upload 指令；不重新建 token 或自動安裝 Node。 |
| DownloadBuildArtifacts@1 不存在／缺 runtime | 查 VM2 的 Server task／Agent runtime；VM1 上傳修正不代表 VM2 已驗收，提供該下載 task 的非敏感錯誤再定位。[1] |
| D: absent／Access denied | 查 VM2 本機 D: 與 Agent 服務帳號 ACL，不給 GitLab VM 密碼或改成 VM1 share copy。 |
| LFS／submodule／symlink refused | 本 POC 未支援；先定義需求，不略過檢查當完整交付。 |
| ZIP hash／run／SHA mismatch | 停止，查是否下載錯 run 或 artifact 被替換；不 fallback 到 latest。 |
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

原 Publish task 的 [Container 分支](https://github.com/microsoft/azure-pipelines-tasks/blob/master/Tasks/PublishBuildArtifactsV1/publishbuildartifacts.ts) 發出 `artifact.upload`；[FileContainerServer source](https://github.com/microsoft/azure-pipelines-agent/blob/v2.214.1/src/Agent.Worker/Build/FileContainerServer.cs) 處理目錄內容與相對路徑。

Microsoft 文件列明 [`System.PreferGitFromPath`][8] 可覆寫 Windows Agent 的內附 Git 選用；這不會修復 Git 安裝本身。

觸發方式的第一方來源與版本限制見[研究筆記](../research/gitlab-ado-file-delivery-trigger.md)。
