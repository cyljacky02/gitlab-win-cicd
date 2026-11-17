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

先前通過的是 Tools.Rs 的網頁 Test → ADO 零動作探針。**Rayin 真 push、VM1 取碼、ADO Server task 可用性及 VM2 放檔均待現場驗收。** 本機未連公司內網，沒有代設 credentials 或操作 VM。

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
- **目前提供的 GitLab HTTP URL 預設會拒絕送 credential。** 只有明確核准的隔離 POC 才在手動 Run 勾 `allowInsecureHttpLab`，使用專案限定、短效唯讀 token，測後撤銷。這次使用者確認 UI 欄位，不等於已核准 HTTP credential 例外。
- ADO Library 管理頁及下節的 webhook／PAT 傳輸也要使用 HTTPS／受核准管理通道；Git 取碼例外不會一併核准 ADO PAT 的 HTTP 傳輸。
- 不關閉 TLS、不加 PAT 到公開 incoming-webhook endpoint，也不開 IIS Basic 來硬闖。

## 第四步：手動 Run 完整交付（會寫入 VM2）

確定 VM2 是本次允許寫入的測試目標後：

1. GitLab → Rayin → Code → Commits → branch `poc/cicd` → 複製完整 **40 碼 SHA**。
2. ADO → **新的 `GitLab-Rayin-Zip-Delivery` → Run pipeline**。
3. ADO branch 選 `poc/webhook-smoke`；`gitlabCommitSha` 填上述 GitLab SHA。
4. HTTP lab 例外只有已核准才勾；否則先取得 HTTPS，不要為了綠燈直接勾選。
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

## 本機檢查與現場故障排查

本機 Windows PowerShell 5.1：三支 script parser、YAML／JSON parsing、既有取碼回歸 **19/19 通過**。另以暫存 real-Git fixture 實際執行新 ZIP／Copy 腳本，確認 tracked dotfile／Unicode filename 可封裝、untracked 不入包、`export-ignore` 不漏包、只放 ZIP、hash 相同及相同包重試不覆蓋；手動拒絕檢查涵蓋篡改 ZIP、不同內容同名檔保留、`..` 目的路徑、錯誤 run、全零 SHA、LFS pointer 與失敗後不發布／清理暫存。這是本機操作檢查，不是新正式測試套件或現場 E2E 證據。

| 現象 | 檢查 |
|---|---|
| HTTP refused | 預期安全預設；改 HTTPS 或先取得明確隔離 lab 例外，不直接關 TLS。 |
| Fetch 401／403 | Rayin 的 token Username／期限／`read_repository`；勿誤用 Tools.Rs project token。 |
| Environment/resource not found | `test-deploy-agent`、`SECSVR4-80`、case-sensitive `virtualMachine`、Agent online／pipeline resource authorization。 |
| DownloadBuildArtifacts@1 不存在 | 核對現場 Server task inventory／版本；本機 YAML parser 不能驗證 task 可用性。[1] |
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

觸發方式的第一方來源與版本限制見[研究筆記](../research/gitlab-ado-file-delivery-trigger.md)。
