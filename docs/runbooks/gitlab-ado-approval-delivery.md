# 帶核准的 ZIP 交付：核准版 pipeline＋本機核准帳號（POC）

**狀態：檔案與步驟已備，現場尚未設定、尚未驗收。** 前提是[無核准版](gitlab-ado-file-delivery.md)（pipeline 5）已由使用者回報 GitLab push 自動交付成功。

```text
GitLab poc/cicd push
  → Runs REST（新 pipeline ID）
  → Package（VM1）：取確切 SHA → ZIP → ADO artifact，run 標上 zip-sha256
  → ⏸ Environment test-deploy-agent 的「核准」check：核准人登入檢視後核准／拒絕
  → Deliver（VM2）：核准後才開始，下載同一 run 的 ZIP、驗 hash、放到 D:\TestCICD
```

## 已做的決定（使用者確認）

| 項目 | 決定 |
|---|---|
| Pipeline | **另建核准版**，用 [`azure-pipelines-gitlab-file-delivery-approval.yml`](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery-approval.yml)，不改 pipeline 5 的 YAML |
| Environment | **沿用 `test-deploy-agent`／`SECSVR4-80`（選項 A）**，不在 VM2 另註冊 agent |
| pipeline 5 | check 設好後也會被擋；新版驗收後 webhook 改指新 ID，**停用 pipeline 5** |
| 核准帳號 | **先測 ADO Server 主機的 Windows 本機帳號**；AD 帳號以後再說 |
| 核准人 | 2–3 位，可能**共用一個帳號**，核准時在留言填自己的員工編號 |
| 核准人數 | 一位核准即可，不是雙人審批（見 `GLOSSARY.md`） |

核准版 YAML 與 pipeline 5 的差異只有兩處（[離線測試](../../cicd/gitlab-ado/tests/Test-ApprovalPipelineYaml.ps1)確保其餘完全相同）：

1. Run 名稱是 `rayin-approval-<完整 GitLab SHA>-<日期>.<序號>`，核准畫面即可看到版本。
2. Package stage 多一步，把 manifest 的 ZIP SHA-256 加成 run 標籤 `zip-sha256-…`。這只是給核准人看的；真正的檢查仍是 Deliver 對同一 run manifest 的 hash 驗證。

**核准不寫在 YAML 裡。** 它是 Environment 上的原生「核准」check，ADO 在 Deliver stage 開始前評估；等待期間 VM2 沒有 job、checkout、下載或複製。

## 這個 POC 的限制（先講清楚）

- **共用帳號：ADO 只記得「ado-approver 這個帳號」核准。** 留言裡的員工編號是本人自填、ADO 不驗證，UI 也不強制填寫。只能當 POC 的人工紀錄，不是正式稽核身分。正式化時改成每人一個帳號（本機或 AD 皆可），放進同一個群組即可，check 不用改。
- **本機帳號能不能加進 ADO 要現場驗證。** 主機已加入網域時，ADO 的身分選擇器可能只搜得到 AD。第 4 步搜不到就停下回報，改走 AD 帳號。
- **管理者帳號（也是 webhook PAT 的擁有者）可以略過（bypass）或停用 check。** POC 可接受，但管理者**不要**列為核准人、不要自己核准；略過會留下紀錄。
- **HTTP**：網頁登入走 Windows 驗證（NTLM／Kerberos 不送明文密碼），但頁面與 session 不加密。內網不等於加密。
- 密碼只由你在主機上輸入、由你們自己保管與轉交；**不要貼給助理、不要寫進 YAML／GitLab／JSON／文件**。

## 步驟順序

第 5 步加上 check 之後，**pipeline 5（webhook 目前還指向它）的新 run 也會停在等待核准**。從第 5 步到第 8 步之間，盡量不要 push `poc/cicd`；若有，在 pipeline 5 的 run 上直接「拒絕」或取消。

### 第 1 步：ADO repo 放入核准版 YAML

ADO → `Deployment` → Repos → 原 repo → 分支 **`poc/webook-smoke`**（沒有 h）→ 新增檔案：

| ADO repo 路徑 | 內容 |
|---|---|
| `/azure-pipelines-gitlab-file-delivery-approval.yml` | [完整 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-file-delivery-approval.yml) |

三支 `/scripts/*.ps1` 已在同一分支，不用動。不要修改 `/azure-pipelines-gitlab-file-delivery.yml`。

### 第 2 步：建立核准版 pipeline，先不要 Run

1. Pipelines → New pipeline → Azure Repos Git → 同一 repo → Existing Azure Pipelines YAML file。
2. Branch `poc/webook-smoke`，path `/azure-pipelines-gitlab-file-delivery-approval.yml`。
3. 用 Run 旁的下拉選 **Save**，重新命名為 `GitLab-Rayin-Zip-Delivery-Approval`。
4. 記下網址裡的 **`definitionId=`** 數字（新 pipeline ID），第 8 步要用。

### 第 3 步：在 ADO Server 主機建立本機核准帳號

在 **ADO Server 那台主機**（`10.92.4.86`，不是 VM1／VM2、不是你的筆電）以系統管理員開 Windows PowerShell，整段貼上：

```powershell
$name = 'ado-approver'
$password = Read-Host "為 $name 設定密碼（輸入時不顯示）" -AsSecureString
New-LocalUser -Name $name -Password $password -FullName 'ADO Deployment Approver (POC shared)' -Description 'ADO environment approval only; not admin' -AccountNeverExpires
Add-LocalGroupMember -SID 'S-1-5-32-545' -Member $name   # 內建 Users 群組
$password = $null
Write-Host "第 4 步在 ADO 輸入的帳號：$env:COMPUTERNAME\$name"
Get-LocalGroup | Where-Object { @(Get-LocalGroupMember -Group $_ -ErrorAction SilentlyContinue | Where-Object Name -eq "$env:COMPUTERNAME\$name").Count -gt 0 } | Select-Object Name, SID
```

- Description 上限 48 字元（目前 40）。
- 密碼需符合主機的密碼原則；失敗就換一組重新執行 `New-LocalUser` 那行。
- 最後一段只應列出 Users（SID `S-1-5-32-545`）。**不要加入 Administrators 或 Remote Desktop Users。**
- 記下印出的 `主機名\ado-approver`。之後有人離開或密碼外流，就在這台主機改密碼。

### 第 4 步：把帳號加入 ADO，只給檢視權限

以管理者帳號登入 ADO 網頁：

1. **存取層級**：伺服器／集合的管理設定 → 「存取層級（Access levels）」→ 選 **Stakeholder** → 新增 → 輸入第 3 步印出的 `主機名\ado-approver`。
   - 搜尋不到 → **停在這一步並回報**（本機帳號在已加入網域的主機上不可用，改走 AD）。
   - 預期 Stakeholder 不佔 Express 的 5 個 Basic 名額；若 UI 顯示要佔用，回報實際畫面。
2. **專案群組**：`Deployment` → Project settings → Permissions → 新增群組 **`Rayin Deployment Approvers`** → Members 加入 `主機名\ado-approver`。
3. 同一頁打開內建 **Readers** 群組 → Members → 加入 `Rayin Deployment Approvers`。不要加入 Contributors、Build Administrators 或 Project Administrators。

### 第 5 步：在 Environment 加上「核准」check

Pipelines → Environments → **`test-deploy-agent`** → 右上「⋮」→ **核准與檢查** → 「+」→ **核准** → 下一步：

| 欄位 | 設定 |
|---|---|
| 核准者 | `Rayin Deployment Approvers`（群組，不選管理者帳號） |
| 給核准者的指示 | 下方文字整段貼上 |
| 進階 → 最少核准者人數 | 1 |
| 進階 → 允許核准者核准自己的執行 | **不勾** |
| 控制選項 → 逾時 | **24 小時** |

```text
核准前請確認：
1. Run 名稱中的 GitLab SHA 就是要交付的版本。
2. Package stage 成功；run 標籤 zip-sha256-… 與 Package 日誌「Approval evidence」的 SHA-256 一致。
3. 目標：VM2 SECSVR4-80 的 D:\TestCICD。
核准或拒絕時，留言第一行填入自己的員工編號。
```

建立後到同一 Environment 的 **Security**（安全性）頁籤確認：

- `Rayin Deployment Approvers`／`ado-approver` **不是**「管理員」「使用者」或「建立者」角色（這些角色可能可以修改或略過 check）。沒列出或只是「讀者」都可以。
- 截圖：使用者角色清單＋Pipeline permissions 清單，之後回報用。

### 第 6 步：手動 Run 驗收「核准」

1. 新 pipeline → **Run pipeline** → Branch `poc/webook-smoke` → `gitlabCommitSha` 填一個已知的完整 SHA（例如上次自動成功的那個）→ **勾** `allowInsecureHttpLab` → Run。
2. 若出現「需要權限才能存取資源」，管理者按 View → **Permit**（variable group `gitlab-source-readonly`、pool `Default`、Environment `test-deploy-agent`）。這是資源授權，**不是核准**。
3. 確認：
   - Run 名稱含完整 SHA；Package 成功；run 頁面有 `zip-sha256-…` 標籤。
   - Deliver 顯示「等待中／需要核准」，沒有開始任何 job。
4. **核准前**，在 **VM2** PowerShell 確認這個 run 還沒有檔案（run ID 是網址 `buildId=` 後的數字）：

   ```powershell
   $runId = Read-Host 'ADO run ID'
   Get-ChildItem -LiteralPath 'D:\TestCICD' -Filter "Rayin-$runId-*.zip"
   ```

   沒有任何輸出才正確。目錄裡有其他舊 ZIP 是正常的。
5. 管理者**不要**按核准。開瀏覽器無痕視窗 → ADO 網址 → 登入 `主機名\ado-approver` → 打開這個 run → **檢閱** → 留言填員工編號 → **核准**。
6. Deliver 完成後，在 VM2 再執行一次第 4 小步的指令，這次應出現一個檔案；再比對 hash：

   ```powershell
   Get-ChildItem -LiteralPath 'D:\TestCICD' -Filter "Rayin-$runId-*.zip" | Get-FileHash -Algorithm SHA256
   ```

   結果應等於 run 標籤 `zip-sha256-` 後面的值（大小寫不同沒關係）。

### 第 7 步：驗收「拒絕」與權限

1. 再 Run 一次（同一 SHA 可以）→ 用 `ado-approver` 按 **拒絕**並留言 → Deliver 應為略過／失敗，VM2 用第 6 步指令查這個 run ID **沒有檔案**。
2. 用 `ado-approver` 登入時確認：看不到「略過 check（Bypass）」、不能編輯 pipeline、不能修改 Environment 的核准設定、不能按 Run pipeline。
3. 用管理者帳號看待核准畫面，記錄是否出現 Bypass（預期會有）——**不要使用**。
4. 逾時（24 小時）不必刻意等；之後有自然逾時的 run 再補紀錄。

### 第 8 步：GitLab webhook 改指向核准版

先處理掉 pipeline 5 還在等待中的 run（拒絕或取消）。然後 GitLab Rayin → Settings → Webhooks → 編輯**現有那一筆** → **只改 URL 裡的 pipeline ID**：

```text
原本：http://10.92.4.86/DefaultCollection/Deployment/_apis/pipelines/5/runs?api-version=7.1
改成：http://10.92.4.86/DefaultCollection/Deployment/_apis/pipelines/新ID/runs?api-version=7.1
```

例如新 ID 是 7，就把 `/5/` 改成 `/7/`。Custom headers（同一個 PAT）、Push events、`poc/cicd` filter、Custom webhook template **全部不變**。

存檔後在 `poc/cicd` 做一次真 push：核准版出現新 run（名稱含這次 push 的 SHA）→ Package 完成 → 等待核准 → 用 `ado-approver` 核准 → VM2 收到同一 hash 的 ZIP。pipeline 5 不應出現新 run。

### 第 9 步：停用 pipeline 5

`GitLab-Rayin-Zip-Delivery`（pipeline 5）→ 右上「⋮」→ 設定 → 處理新的執行要求：**已停用** → 儲存。不要刪除，保留歷史。之後可在 Environment → Security → Pipeline permissions 移除 pipeline 5。

### 第 10 步：回報（不要包含密碼或 PAT）

- 新 pipeline ID
- 第 6 步：run ID、SHA、ZIP SHA-256、核准帳號＋留言、核准時間（Checks 面板）、核准前 VM2 查詢無輸出
- 第 7 步：拒絕的 run ID 與 VM2 無檔案；`ado-approver` 看不到的功能
- 第 8 步：真 push 的 run ID 與結果
- 第 4／5 步若有任何畫面跟本文不同，附截圖

收到後再把本文與主 runbook 的狀態改成「已驗收」。

## 之後改用 AD 或個人帳號

把個人帳號（本機或 AD）加入 `Rayin Deployment Approvers`、存取層級設 Stakeholder，再把 `ado-approver` 從群組移除並在主機停用（`Disable-LocalUser -Name ado-approver`）即可。Environment check 指向群組，不用改。

## 參考

- Microsoft，[Approvals and checks](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals?view=azure-devops-2022)：check 在 stage 使用資源前評估；核准者、指示、是否允許核准自己的 run、逾時後 stage 略過；只有資源管理權限可 bypass。
- Microsoft，[Stakeholder access](https://learn.microsoft.com/en-us/azure/devops/organizations/security/stakeholder-access?view=azure-devops-2022)：Stakeholder 不限人數，可檢視與核准 pipeline。Express 實際行為依第 4 步現場確認。
- 既有研究：[`gitlab-ado-server-integration.md` §10.2](../research/gitlab-ado-server-integration.md)。
