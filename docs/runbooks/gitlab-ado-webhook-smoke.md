# 實測：GitLab 原生 webhook → ADO Server（不經 GitLab Runner）

## 目的、已知現況與證據界線

**這次只測事件能否進入 ADO 並建立一筆 probe run，不取碼、不建置、不下載產物、不派送 VM2。**

- 使用者回報：ADO Server **25H2 20260921.1**、collection `DefaultCollection`、project `Deployment`。
- GitLab 測試專案：`grp-smt-maint/Cathaysec.Com.Smt.Tools.Rs`；限定來源 `poc/ado-fetch`，不改 GitLab 應用 `main`。
- 改用 ADO **agentless server job**，完全不用 GitLab Runner，也不用 VM1 `Default` pool。這同時避免尚未核實 pool 成員時誤派 VM2。
- 本文件記錄操作方案，不是已成功的現場紀錄。本機對使用者提供的兩個內網服務做匿名 HEAD 均連線逾時；**不代表 GitLab 服務端到 ADO 不通**，也沒有測到認證／端點能力。
- GitLab Server 版本尚未確認；已知 `16.11.1` 是 **Runner** 版本，不能反推 Server 版本。
- 本原生 webhook 探針是使用者本輪要求的新測試入口，**不是 FINAL ZIP 已驗證的通知方式**，也不取代其中的部署程式。

```text
GitLab 服務端（發 webhook）
  → ADO collection 的 Incoming WebHook endpoint
  → 專用 pipeline：pool: server → Delay@1 0 分鐘
  → 記錄 HTTP response 與新的 probe run

不使用：GitLab CI job / PAT / GitLab read token / source checkout / Agent pool / VM2
```

## 重要：本輪是「短時未驗章連通探針」，不是安全整合

Microsoft Incoming WebHook 的可選 Secret 用於 **HMAC-SHA1 payload 驗章**。GitLab 傳統 Secret token 是 `X-Gitlab-Token` 的原值；新文件的 signing token 是另一種 HMAC-SHA256 格式。**不能在兩邊填同一字串，就假設可以互通。**[1][2]

這次另建一個**全新的、測後即刪** service connection，Secret/Header 留空，只為確認 native endpoint 能否接到事件。它只訂閱本頁的零動作 server job：

- **任何能連到端點、知道名稱且能偽造 JSON 的人，都可能排入 probe run。** 分支／專案 filters 是路由，不是來源認證；此測試也不驗 JSON 是否來自真 push。
- 沒有 secret、PAT、script、checkout、artifact、部署或 webhook 內容插入可執行文字；不可以把 Fetch／Deploy／其他有副作用的 job 接到這個入口。
- 現場 URL 是 HTTP；本輪不傳 secret／程式碼。不得在 HTTP 上放入 PAT／正式 webhook secret。
- 不更動既有 webhook、既有安全檢查、IIS Basic／Anonymous Authentication 或全域 GitLab outbound 安全限制來硬闖。
- **只有在允許這種短時、內網、未驗章探針時才繼續。若公司禁止，停在此處，改規劃驗章接收器或經核准的閘道。** 不應把本頁當成取消認證的上線建議。
- 測試完成立即按第 7 節移除入口。禁止向所有 pipelines 開放此 service connection。

## 1. ADO：建立專用 Incoming WebHook connection

在使用者提供的 ADO collection 下，開啟 `Deployment` project：

**Project settings → Pipelines → Service connections → New service connection → Incoming WebHook**。

若找不到 Incoming WebHook，先停，提供選項清單／截圖；不要改用 **Service hooks**（那是出站通知）或隨便選 Generic。

填寫：

| 欄位 | 本次值 |
|---|---|
| WebHook Name | `gitlab-ado-smoke-rs` |
| Service connection name | `gitlab-ado-smoke-rs`（故意和上面一致，減少誤填） |
| Secret | 留空；僅此隔離探針例外 |
| HTTP Header | 留空；不把 `X-Gitlab-Token` 當成 HMAC |
| Grant access permission to all pipelines | **不要勾**；之後只授權這支新 probe pipeline |
| Description | `Temporary unauthenticated transport-only probe; no source, secrets, agents or deployment; delete after test` |

若同名 connection 已存在，**不要覆寫／重用**；先確認所有權與訂閱 pipeline，再決定換新名稱並同步修改 YAML／URL。

產出：一個新 connection。尚未建立訂閱 pipeline 時，HTTP endpoint 仍可能找不到或不會排程，**不是此時就已打通**。

## 2. ADO：儲存最小 YAML，建立新 pipeline

程式來源：[azure-pipelines-webhook-smoke.yml](../../cicd/gitlab-ado/ado/azure-pipelines-webhook-smoke.yml)。

1. 在 **ADO 的 CD／測試 repo** 建 `poc/webhook-smoke` 分支（或使用獨立測試 repo）。這不是修改 GitLab 應用 `main`。
2. 只將上面的 YAML 複製到該 ADO 分支根目錄 `/azure-pipelines-webhook-smoke.yml`。不複製 FINAL deploy template、不引用 secrets／variable groups，不放應用程式碼。
3. ADO **Pipelines → New pipeline → Azure Repos Git → 選該 ADO repo → Existing Azure Pipelines YAML file**，選 branch `poc/webhook-smoke`、path `/azure-pipelines-webhook-smoke.yml`。
4. 建立全新 pipeline，命名例如 `GitLab-Webhook-Smoke`；不要覆蓋既有建置／部署 pipeline。
5. **此 pipeline 的 Default branch for manual and scheduled builds 必須指向存有 webhook YAML 的分支**，例如 `refs/heads/poc/webhook-smoke`。這不是修改整個 repo 的 default branch。[1]
   - 官方 troubleshooting 路徑：pipeline **Edit → … → Triggers → YAML → Get sources → Default branch for manual and scheduled builds**。現場 UI 若不同，先提供截圖確認，不改全域 repo 設定。
6. 在新 connection 的 **Pipeline permissions** 只授權此 pipeline；或初次執行依 ADO 的 resource authorization 提示只授權本支。
7. 先手動 Run 一次、選上述 ADO 分支，應只有 `WebhookReceived`／`Delay@1`，立即完成。手動 bootstrap 成功只證明 YAML／connection 授權／task 能用，**尚不代表 webhook 已送達**。

YAML 不讀任何 webhook payload 到 shell／PowerShell；只用三個 filters：

```text
object_kind = push
ref = refs/heads/poc/ado-fetch
project.path_with_namespace = grp-smt-maint/Cathaysec.Com.Smt.Tools.Rs
```

如果 GitLab Recent events 顯示 canonical project path 與提供的 URL 大小寫不同，經人工確認同一專案後，調整這個**固定 allowlist 值**；不要直接移除 project filter。

## 3. 先從 VM1／能到 ADO 的工作站送「假 push JSON」（選做、建議）

這一步排除 ADO URL／註冊問題，但**不驗 GitLab 網路來源，不聲稱真 push**。

ADO Server 的候選 URL 為：

```text
{ADO_COLLECTION_URL}/_apis/public/distributedtask/webhooks/gitlab-ado-smoke-rs?api-version=6.0-preview
```

`ADO_COLLECTION_URL` 請用本次已提供的 collection URL（結尾不要重複 `/`）。**Webhook URL 沒有 `/Deployment/`，也不是 `/pipelines/{id}/runs`。** Endpoint 尾端用 **WebHook Name**，不是 pipeline ID。

證據界線：官方 Server 資源文件支持 Incoming WebHook；官方 YAML 範例使用 `6.0-preview`，本例將 cloud org base 改成現場 collection base。現行 REST 頁面會回到 cloud `7.2-preview.2`，**不能用其 URL 範例證明本機版號／collection 路由已成功**；實際 URL／version 以本輪 response 驗證。[1][3]

將 [webhook-smoke-push.example.json](../../cicd/gitlab-ado/ado/webhook-smoke-push.example.json) 放在能連到 ADO 的工作站。以 PowerShell 執行（填入已提供的 collection URL）：

```powershell
$collection = 'REPLACE_WITH_ADO_COLLECTION_URL'
$uri = $collection.TrimEnd('/') + '/_apis/public/distributedtask/webhooks/gitlab-ado-smoke-rs?api-version=6.0-preview'
Invoke-WebRequest -UseBasicParsing -Method Post -Uri $uri `
  -ContentType 'application/json' `
  -InFile '.\webhook-smoke-push.example.json' `
  -MaximumRedirection 0 -TimeoutSec 15
```

不加 `UseDefaultCredentials`、PAT 或 Basic header。檢查兩件事：HTTP response（status／body）＋ADO 是否多一筆 **非手動**的 probe run。HTTP 200 仍可能匹配零支 pipeline，不能單看綠燈。

## 4. GitLab：新增 project webhook，不改 `.gitlab-ci.yml`

到測試專案：**Settings → Webhooks → Add new webhook**；需要該 project 的 Maintainer／Owner 權限。[2]

| 欄位 | 本次值 |
|---|---|
| URL | 第 3 節 ADO incoming webhook URL |
| Secret token / Signing token | 本輪皆不設定；不是將 PAT 放這裡 |
| Trigger | 只勾 **Push events**；不是 Pipeline events |
| Push events branch filter | `poc/ado-fetch`（若 UI 支援）；ADO 仍保留自己的固定 branch filter |
| SSL verification | 保留正常設定；目前 HTTP 不會因此變 HTTPS，不用關閉 TLS 驗證 |
| Custom headers / Custom payload template | 本輪不使用 |

不要修改現有 webhook；這是一筆全新的 probe。沒有 `.gitlab-ci.yml` 修改，也沒有呼叫 CI job。

### 先按 Test → Push events

1. 新 webhook 選 **Test → Push events**。
2. 打開 **Recent events → View details**，看 response status/body、request body 的 `ref`／`project.path_with_namespace`。
3. **有些 GitLab 版本的 Test payload 用 default branch**，即使 webhook 限定測試分支，也可能送 `refs/heads/main`。這時 ADO 正確的行為是**不啟動 run**；不能為了讓測試過就拿掉 branch filter。
4. 只有 request body 確實符合三個固定 filters，且 ADO 多一筆相對應的新 run，才算目前這筆 GitLab → ADO 通知匹配成功。

GitLab 在網頁按 Test 的來源可能是 Rails；真實事件通常從 Sidekiq 發送。因此 **Test 成功還要第 5 節的真 push 成功**，不能只測其中一種路徑。[2]

## 5. 真實測試分支 push，但跳過 GitLab CI jobs

不需要 Runner，也不改 main。先確認其他 webhook／自動化對測試分支的影響；`[skip ci]` 只控制 GitLab CI，不會關掉其他整合。

在這個 GitLab 專案的本機 clone、乾淨 working tree、確認 remote 正確且測試分支沒有既有 MR 的情況下：

```bash
git remote -v
git status --short
# 確認 origin 是測試專案、working tree 沒有改動；再建立全新測試分支。
git switch -c poc/ado-fetch
git commit --allow-empty -m "test: webhook transport probe [skip ci]"
git push -o ci.skip origin HEAD:refs/heads/poc/ado-fetch
```

- 如果 branch 已存在，不 force push、不刪除既有分支，先檢查它的用途再決定如何測。
- 不修改應用檔案、不編輯 CI include、不開 MR、不合併 main。
- GitLab 可能仍出現 **skipped pipeline 紀錄**；本測試的要求是沒有 CI job 需要 Runner 執行，不是 UI 一定完全沒有 pipeline 紀錄。[4]
- `[skip ci]`／`ci.skip` 不是跳過安全稽核的上線機制，只用於本次無程式變更的受允許通知測試；若公司禁止使用，先停並請管理者提供不啟用 CI 的隔離專案。

驗收：本次 Push Hook 的 request `ref` 正確、response 成功，ADO 新增 probe run，且 VM1／VM2 agent 都沒有新 job。記錄 GitLab Recent event 時間／event UUID（若有）、ADO run ID、branch／commit SHA；手動 run 與真 webhook run 分開記。

## 6. 錯誤判讀（先看 response，不盲改設定）

| 現象 | 下一步 |
|---|---|
| GitLab 顯示 local network／URL blocked | GitLab 的 outbound 安全限制可能擋內網 IP；由管理者針對 ADO 目的地做核准 allowlist。不要全域允許所有內網／SSRF 目的地。[5] |
| Test timeout／connection refused | 查 **GitLab Rails／Sidekiq → ADO** 的網路、HTTP port、proxy；不是 Runner 網路。 |
| 404／Cannot find webhook | 核對 URL 無 project segment、WebHook Name、collection base、pipeline default branch、YAML resource 已存入並 bootstrap；先不要加 PAT。 |
| 401／403 | 查看是哪一層回應（IIS／proxy／ADO）。本探針預期公開 controller；不要開 IIS Basic／全域 Anonymous 或給 Full access PAT 來硬闖。若環境強制認證，先回報，改經核准的代理／接收器路線。 |
| unsupported API version | 保存完整非敏感 error 與 supported versions；依該安裝版調整，不把 cloud `7.2-preview.2` 當保證。 |
| HTTP 200，但沒有 ADO run | 先比對實際 payload 三個 filters、connection 訂閱、default branch；200 只代表 endpoint 處理，不保證排入。 |
| 找不到 Incoming WebHook／Delay@1 | 取得實際 UI／task availability；功能要按已安裝 Server 實測，不能由版本字串推斷全部已配置。 |
| bootstrap 提示 resource authorization | 只授權專用 probe pipeline，別勾所有 pipelines。 |
| Run 要求 agent／checkout，或執行 script／取 artifact | 停止；這不是本探針 YAML，不應用舊部署 template 代替。 |
| webhook Test 用 main | 不啟動正確；保留 filter，改做第 5 節真實測試分支 push。 |
| 一次 push 多筆 probe run | 重送／多個 hooks／多個訂閱可能造成；本探針不宣稱 exactly-once，先記錄並去查，不連部署。 |

請回報：**是哪一步、HTTP status、非敏感 response body、request 的 ref／project path、ADO 有沒有新 run／run ID**。不要貼完整 cookies、Authorization headers 或真 token。

## 7. 測後清理與下一關

1. 刪除本次新增的 **GitLab webhook**。
2. 停用／刪除 `GitLab-Webhook-Smoke` 專用 pipeline。
3. 刪除本次專用 Incoming WebHook service connection（保留必要的非敏感驗收紀錄；不刪別人的資源）。
4. ADO／GitLab 測試分支是否保留按所有權決定；不自動刪 repo，不動 main、舊 POC 或既有部署。
5. 需要驗證清理時，送同樣假 payload 應不再產生 run；HTTP status 仍以實際平台回應為準。

**通過本輪只代表 GitLab → ADO 的事件路徑成立，不代表 ADO → GitLab 取碼／下載產物已通，也不代表來源認證、最終 pipeline success、版本綁定或部署放行已完成。** 下一輪另做 HTTPS＋可互通的來源認證／驗章；若需要，再用 VM1 對 GitLab 做固定資源的唯讀驗證。未完成前不可把此未驗章連線接到 Fetch／Deploy。

## 官方來源

[1]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/resources?view=azure-devops-server#webhooks-resource
[2]: https://docs.gitlab.com/user/project/integrations/webhooks/
[3]: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/resources-webhooks-webhook?view=azure-pipelines-server
[4]: https://docs.gitlab.com/ci/pipelines/#skip-a-pipeline
[5]: https://docs.gitlab.com/security/webhooks/

- [Incoming WebHook／default-branch troubleshooting][1]、[YAML filters／HMAC-SHA1／未設 secret 的公開入口][3]。
- [Delay@1：YAML＋server job、0 分鐘為無延遲](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/delay-v1?view=azure-pipelines-server)。
- [GitLab webhook 設定、Test／Recent events、Rails／Sidekiq 發送來源][2]；GitLab 文件為滾動版，不能將所有新選項套到未知 Server 版號。
