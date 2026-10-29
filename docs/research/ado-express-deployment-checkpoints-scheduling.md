# Azure DevOps Server Express：部署檢查點與排程查核

查核日期：2026-10-14。**僅線上官方資料研究，未操作現場 Server、Agent、IIS 或 F5，未進行實機 POC。** 本次只新增此文件，不改程式或既有文件。

## 0. 基線與三問結論

已完整閱讀 `GLOSSARY.md`、本機架構紀錄 `cdpoc-architecture-ado.md` 與歷史研究 `windows-release-recovery-feasibility.md`。只保留本研究必要的產品資訊，不轉錄環境位址、身分或交接資料。

- 現場紀錄為 **Azure DevOps Server Express，非 Azure DevOps Services**；installer bundle `20.0.37104.1`、TfsConfig product version `20.256.37104.1`。本次比對官方最新 Server、2022、2022 Update 2 release notes 並搜尋兩個完整 build，**未找到可引用的精確 marketing release／patch 對照**；不可命名為現場「Server 2022」，也不可從 Agent 版號反推。[1–3]
- 舊研究的 Server 2022 只是文件基線；F5 REST 是歷史假設。**本案改採服務 health monitor status 控制流量，不要求 F5 REST 或其管理憑證。** 現行應用只是靜態網站 POC，Production 專用 Agent 尚未安裝；本文流程是建議，不是已配置或驗證結果。
- **問題一：可以使用 Windows 或 Linux deployment targets／self-hosted agents。** ADO Server 本體仍是 Windows 產品；Agent OS、目標 OS、各 task／runtime 的支援矩陣是不同問題。[4–8]
- **問題二：Classic 原生能編排部署、測試、人工 checkpoint。** 建議拆 stages，讓「開放 F5 admission」stage 的 predeployment approval 位在測試之後；或在同 stage 使用 agentless `ManualIntervention@8`。真正部署、健康 probe、隔離旗標與功能測試仍需腳本／測試程式；**新版與 rollback 都不能健康即自動納流**。[9–14]
- **問題三：原生有 release creation schedule、stage schedule，以及 REST 單次 scheduled deployment 欄位，但不是同一功能。** 本次取得的 Classic 官方文件不足以證明「同一 stage 的核准一定可在 schedule 前完成」、Classic **Deferred approval** UI 在此未辨識 build 可用，或完整的一次性日期時間 UI 契約。可用「先核准 stage → 後續等待／排程 stage」表達順序；精確時間、過窗與逾期政策仍要 POC 或受控 scheduler。[9,10,15–18]

官方 Express 說明原文：**“It supports all of the same features as Azure DevOps Server”**，且 **“licensing limits use to five active users.”** 這支持 Server 功能適用於同版本 Express，不表示 Services 功能全部可用，也不豁免個別工具／測試產品授權及權限。[4]

## 1. Windows／Linux：要分三層回答

| 層次 | 官方可確認能力與原文 | 本案界線 |
|---|---|---|
| ADO Server application tier | Requirements：**“runs on either a Windows Server operating system or a Windows client operating system and only on a 64-bit operating system”**。[5] | 不支援把 Server 本體裝在 Linux。現行未帶年份的 Server 表列 Windows Server 2025／2022；2022 表列 Windows Server 2022／2019。必須先辨識現場 release 才能套對列；不能用 Agent 支援推論 Server 安裝支援。 |
| 一般 self-hosted agent | Agents：**“You can install the agent on Linux, macOS, and Windows machines.”**；self-hosted agents 適用 Services、Server；Microsoft-hosted agents **“aren't available in Azure DevOps Server.”**。[6] | 測試 VM 可獨立加入專用 agent pool，不必把測試程式裝在 Production，也不能直接用 `ubuntu-latest` hosted pool 當 Server 解法。 |
| Classic Deployment Group target | 文件明列 **“available only in classic release pipelines”**；註冊步驟選 **“Windows or Linux for Type of target to register”**；**“Every target server … requires a deployment agent.”**。[7] | Deployment Group job 的 Agent 就在目標上：Windows target 配 Windows Agent、Linux target 配 Linux Agent。另一台 pool Agent 遠端 SSH／HTTPS 操作目標是不同執行拓撲，並非 Deployment Group 自動跨 OS。 |
| task 與工具 | `PowerShell@2`：**“run a PowerShell script on Linux, macOS, or Windows”**，requirements 列 Classic release、Agent／DeploymentGroup。[11] | 可跨平台的是 task runner，不是每個腳本。IIS／Windows service 操作仍是 Windows 專用；Linux 需符合其 runtime、權限及套件條件。測試 Agent 的 OS 取決於測試工具，不必等於網站 OS。 |

### 版本相容不是「Agent 能 online 就全部能用」

1. 官方 Server agent 升級規則是 **“We update the agent software with every Azure DevOps Server update”**；task／平台需要新版時可能要求升級，較新 major 可能要手動更新。[6] 官方 v4 FAQ 更直接寫 **“Azure DevOps Server versions support the version of the agent that is deployed with that version.”**，表列最新未帶年份 Server → 4.x、2022.2 → 3.238.0。[8] 因此選實際 Server 提供／支援的套件，不盲目裝下載站最新 major。
2. Windows／Linux agent prerequisites 頁目前以 Server／2022 分 moniker；例如 Server Linux 清單包含 Debian 12、Ubuntu 24.04／22.04／20.04 等，**不能把「Linux 支援」擴張成任意 distro／版本（例如 Debian 13）的正式支援保證**。[8a,8b] 須核對選定 agent major 的 OS、CPU 架構與 .NET native dependencies。
3. Task 另查其 Server moniker、major／minor inventory、minimum agent、handler（Node／PowerShell）、demands 與外部工具。`ManualIntervention@8`、`Delay@1` 的 “Runs on: Server” 指 **agentless execution location**；Server 產品適用證據來自其 `azure-pipelines-server`／2022 moniker，而不是只看這個欄位。[12,16]
4. v4 指南頁目前頂層 moniker 偏 Services，且含 v5 轉換提示；本文只援引其**明確回答 Server 的 FAQ**，不把其他 Services 升級說法一律套現場。現場既有管理 Agent 可 online 不證明新 Production Agent、所有 tasks 或 distro 已相容。[8]

## 2. 部署後測試 → 人工 checkpoint → 才允許納流

### 建議：用 stages 清楚隔開「部署」和「納流」

```text
Release 固定候選版本／目標
  ↓ 部署放行（如需）
Deploy-Isolated：關閉 admission → 確認摘流／drain → 部署 → 啟動／app health
  ↓ 成功
Functional-Test：專用測試 VM 的 agent pool job → 直連該節點測指定版本
  ↓ 成功
Admit-Traffic：predeployment approval（檢視測試及版本／目標證據）
  ↓ 真正人員核准且仍在有效期／窗口內
重新確認 app health、版本與隔離狀態 → 開啟 admission → 觀測 F5／實際流量
```

- Classic 官方 stage trigger 的 **After stage** 是 **“after successful deployments to selected stages”**；predeployment approval 可放 stage 開頭。這是 Server 可引用的原生流程，不需借用 YAML Environment Approvals/checks。[9,10]
- 測試 VM 使用專用 pool 的 **agent job**，不是把 Production Deployment Group 當一般 build pool。可透過 `PowerShell@2` 執行 HTTP smoke／測試 runner；若選 VSTest，需 `vstest` capability、相符 test platform／adapter；有桌面 UI 測試時還需 interactive agent／Autologon，不能默認背景 service 可跑。[11,13]
- **原生只提供編排及記錄，不替你判定業務健康。** 靜態網站 POC 最少驗 TLS、正確 site、release／commit／內容 markers；這不是完整功能測試。較完整應用還需明訂依賴與業務斷言、測試資料及清理策略。
- 不要讓 Admit stage 的「已在前 stage 核准則自動略過」政策吞掉這個新 checkpoint；部署放行與部署後納流確認是不同決策。關閉不適當的 approval reuse，審閱 stage permissions／override 權限。[10]

### 替代：同一 stage 中途暫停

用依序的 **Deployment Group job → 測試 agent job → agentless job（`ManualIntervention@8`）→ admission job**；不是把 ManualIntervention 放進 Production agent job。官方 Classic job 文件明述 **“Multiple jobs in a release pipeline run in sequence”**，並示範 agent → Manual Intervention server job → 下一個 agent job；拒絕時後續 job 不跑。[14]

`ManualIntervention@8` 原文 **“can only be used in an agentless job”**、**“intended for use in a classic release pipeline”**。需 **Manage deployment** 權限才可 resume／reject；通知信收件者不自動成為核准者。設 `onTimeout=reject`、task／parent job 有界 timeout，不能用 timeout 自動 resume。Task 頁稱最長 60 天，但通用 server job 頁寫最大 30 天；應採較短已核實上限，實際 Classic build 再驗，不承諾可等 60 天。[12,14]

Stages 方式較容易把「納流授權」呈現在獨立 stage；ManualIntervention 是中途操作確認，不應在治理／稽核上假裝與 predeployment approval 完全等價。不同 job 可選到不同 Agent，狀態需存受保護且可對帳的 evidence／journal，不靠前一 job 的工作目錄。[14]

### F5 health monitor：app 健康不等於允許納流

**風險判斷：若 F5 與測試都看同一個「app healthy」結果，而且 monitor 自動恢復，app 啟動健康時就可能在人工 checkpoint 前被標 up。** F5 官方 HTTP monitor 的 `manual-resume` 預設 disabled，會在成功檢查後自動 up；`time-until-up=0` 的原文為 **“marked up immediately after a valid response”**。[19] 這是條件風險，不是對現場 F5 設定的觀測。

建議自製契約：

- `/health/app`：供部署控制器／測試驗證的**應用健康**，隔離期間也可回健康。
- `/health/admission`：供 F5 monitor 檢查，只有 **appHealthy AND admissionAllowed** 才回符合 monitor 的狀態／內容。Admission 旗標預設／重啟／錯誤時關閉；唯有本次 release＋target＋候選版本的有效人工續行才可開啟。不要以修改 app health 來模擬人工批准。
- 端點路徑只是設計範例，尚未實作；靜態網站可由受控 adapter／IIS 規則提供 admission 訊號，不宣稱現有網站已能動態切旗標。需防 cache／CDN、舊健康檔殘留、重啟後旗標遺失及任意低權限寫入。
- F5 需明訂 **send／recv 判斷**，不能只假設 HTTP 200／503 自動符合現場 monitor。官方 `recv` 是回應文字比對；未設定 send／recv 時可退化為 connect-only。`recv-disable` 另有 session-disabled 語意，不能當成一般 down 的同義詞。[19]
- F5 `manual-resume=enabled` 也可避免監測自動恢復，但官方要求另行人工 mark up；這會改變「僅端點狀態控制」流程，**不是本文前提或必需方案**。所有 monitor、multiple-monitor 邏輯、interval／timeout、HA、persistence 與既有連線 drain 需 F5 owner 確認；probe down 不等於所有既有連線已停止。[19]

**測試必須直連待上線節點，不可經 VIP 讓舊節點代答。** 保留 URL hostname，使 Host／TLS SNI 與憑證驗證正確，再把連線目的限定到該 target；curl 官方 `--resolve` 可指定 host:port 的 address，`--connect-to` **“does NOT affect the hostname/port number … used for TLS/SSL (e.g. SNI, certificate verification)”**。[20] 測試需處理 redirect／proxy，不可被導回 VIP；browser runner 也要等效 hostname mapping，不能只替 HTTP header。每次記錄實際 target 與版本 marker，不使用 skip TLS。

**Rollback 路徑同樣：保持 admission 關閉 → 精確復原 → 舊版 app health／功能測試 → 人工 checkpoint → 重新驗證 → 才開 admission。** Reject、timeout、斷線、目標不明、證據過期時不納流；不能在 `finally` 或無條件成功清理步驟開旗標。這是需實作的安全政策，不是 ADO 原生 rollback 保證。

## 3. 先 approve，再在指定日期時間部署

### 3.1 三種排程／延後，證據不能互換

| 機制 | 官方確認到哪裡 | 對一次性指定日期時間的限制 |
|---|---|---|
| Artifacts 區的 **Scheduled release trigger** | **“create new releases at specific times”**；可設多個 schedule。[9] REST `ReleaseSchedule` 是 daysToRelease、startHours／startMinutes、timeZoneId。[17] | 是定期**建立 release**，不是先批准的某個 release 等到某日期才部署。每次新 release 的候選版本選擇與批准都要重新處理。 |
| Stage **Pre-deployment conditions → Schedule** | **“Set a specified time to trigger a deployment to this stage.”**，文件同時列 After release／After stage／Manual only。[9] | 支持 stage 定時 primitive，但本文來源未列完整一次性 date-picker、missed-window 或 schedule／approval 精確先後契約；不能把它稱作已證實的「approve now, deploy exactly at T」。 |
| 單一 release environment 的 scheduled deployment | REST request `scheduledDeploymentTime`: **“Gets or sets scheduled deployment time”**，型別 `string(date-time)`；API 的操作狀態含 scheduled／deferred。[17] | 支持特定 release＋environment 的時間欄位；不等於證明 Classic UI 有 Deferred approval，亦未保證設時間後保留既有 approval／不產生新 attempt。需 POC 生命週期。 |
| **Deferred approval**（process/approvals 頁） | 描述 **“set the time the approval becomes effective”**。[18] | 這是 resource Approvals/checks 文件，不是 Classic release approval 文件。該頁頂層標 Services，但部分 moniker 已含新 Server；不可籠統斷言所有 Server 永遠不支援，也**不可用來證明本案 Classic／Express UI 支援**。本研究不採其 YAML defer／ManualValidation 當解法。 |

### 3.2 能確認與尚不能確認的時序

- Classic predeployment approval 是 stage 開始前等待，不是「release 一建立所有下游 stages 都能先核准」。官方多 stage 教學示範前 stage 完成後，下一 stage 才要求 approval。[10,15] **不能保證同 stage 同時設 schedule＋approval 就會提早送出批准請求。** 本次官方文字不足以判定該未辨識 build 的完整先後；保守設計不依賴此行為，也不把它反過來宣稱一定到點才可批准。
- **Gates 順序有明文**：predeployment 預設先 manual approvals 再 gates；postdeployment 預設先 gates 成功再 approvals。可調 gates／approvals order。[21] REST enum 更區分 `beforeGates`、`afterSuccessfulGates`、`afterGatesAlways`；最後一個不代表 gate 失敗可部署，只代表何時顯示 approval。[17]
- 若設 **after successful gates**，核准請求本就會等 gates 成功；不能承諾在其前完成核准。Gate stabilization delay 不是指定時間部署，overview 寫上限 48 小時。[21,22]
- Approval timeout 原文 **“If no approval is granted within the Timeout period, the deployment is rejected.”**；gate timeout 也會 reject。[10,21] Task／job timeout 另算，不能用延長 approval timeout 代替等待 job 的 timeout。
- **Timezone**：REST 的 recurring schedule 明列 `timeZoneId`、local hour／minute，單次 timestamp 用明確 offset／UTC；不要把 YAML cron 的 UTC 規則套 Classic。UI 顯示時區、DST、Server clock／scheduler 停機恢復需現場驗證。[17]
- **Window missed／遲到核准／Agent queue**：本文官方來源未給足完整 Classic 行為，不能保證會丟棄、補跑或隔日重排。即使 T 時被 trigger，Agent 排隊／gates／核准仍可能讓實際部署晚於 T；job timeout 不含等待 Agent 時間。[14] 需求應寫成 `notBefore ≤ actualStart ≤ expiresAt`，超窗 fail closed／重新批准，不能把 schedule 當精準啟動 SLA。

### 3.3 建議依需求選擇，不假裝等價

**A. 原生組合優先，時間精度與 UI 待驗：**

1. 固定 release／artifact／target／預定 T；獨立 **Authorize** stage 不設定未來 schedule，先做 predeployment approval，再跑無 Production 副作用的完成步驟。
2. 後續 **Deploy** stage 設 After stage(Authorize)，再使用 stage schedule；這以 stage 邊界表達「先批准，再等待」，避免依賴同 stage schedule／approval 的未知排序。[9,15]
3. 但 recurring stage schedule 不自動變成一次性日期。若現場可在**單一 release instance** 設 scheduled deployment，僅修改該 instance 並核對 snapshot／nextScheduledUtcTime／approval attempt；不要為一次部署改所有未來 releases 的 definition。精確一次性 UI 仍列待 POC。[17]
4. 一次性日期、授權 expiry 與 missed window 需執行前 guard；一週後同星期時段不是同一次放行。此組合不是完全零腳本保證。

**B. Server 實際有的 agentless `Delay@1`：**

- 在核准後用 agentless job 等固定分鐘數，再進部署。Task 明列 Classic release／Server moniker；**“maximum value is 86400 (60 days)”**，parent job 預設 **60 minutes**，需比 delay 更長；但 server jobs 概念頁寫 **maximum … 30 days**，以有效較短上限及現場可設值為準，不聲稱能等待 60 天。[14,16]
- **這是相對延遲，不是日期排程。** 若核准完成時間改變，固定 delay 的部署時間也會變；要逼近 T，需受控腳本在等待開始時算剩餘分鐘，向上取整以免早於 T，並在部署前再驗 notBefore／expiresAt。要把等待 job 的啟動延遲納入誤差；不能用 Production shell sleep 佔住 Agent。
- 拒絕、取消、逾期、排隊超窗要 fail closed；不適合長期預約或要求秒級啟動的場景。本文沒有配置或實測此方案。

**C. 精確一次性 T／重啟耐受需求：受控外部 scheduler + Server REST（需腳本）**

- Scheduler 保存不可變 releaseId／environmentId／artifact 身分／target／T／expiresAt／原始人員批准證據；到點才以最小權限啟動既有 release stage，或使用該 instance 的 `scheduledDeploymentTime`。REST 明有該欄位與 PATCH operation，不需借用 Azure DevOps CLI（Server 不支援 CLI）或 Services-only scheduler。[6,17]
- 官方 REST 範例 URL 是 Services；Server 需換 Server collection base URL，且選實際 Server 支援的 API version。REST 總覽明列 Server／API mapping；文件提供 7.0（Server 2022）介面**不是把現場判定成 2022**。[23]
- 不讓 scheduler 自動代人 approve、不因 REST queue 成功就假設授權有效；處理 idempotency／重試對帳、撤銷、已部署 attempt、防重複、改版失效、跨工具部署鎖、過窗拒絕與稽核。POST/PATCH 時間欄位對 preapproval／redeploy 的影響必須實測，不能把重排視為保留原批准的保證。[17]

## 4. 交付分類與最小 POC

| 分類 | 可交付結論 |
|---|---|
| **原生** | Windows／Linux Deployment Group；Windows／Linux self-hosted pool Agent；Classic stages、pre/post approvals、agentless ManualIntervention、Delay；release creation／stage schedule primitive。[4–17] |
| **需腳本／測試程式** | 部署及精確回復、app health、admission 旗標與受控切換、直連特定版本的功能測試、有效期／窗口 guard、跨工具鎖、durable journal；必要時受控 REST scheduler。 |
| **待 POC／管理者核實** | build→release／patch mapping、實際 OS／Agent／task 支援；Classic Deferred approval／單次日期 UI；同 stage schedule／approval 順序、missed window／timezone／停機補跑、重排是否重建 approval；實際 F5 monitor／drain 行為。 |

非正式隔離環境最小驗證：

1. About／Admin Console／受信 installer provenance 對官方 release；盤點 tasks、Agent major／OS，不因 online 就結案。
2. 一個不可變 release／單 target：隔離、部署、test VM 直連、approval／ManualIntervention resume 與 reject／timeout；等待期間 app 可健康但 F5 admission 必須保持失敗。
3. 新版失敗後 rollback，**仍停在人員納流 checkpoint**；取消／Agent 斷線／重啟不自動納流；不把此 POC 視為已通過。
4. 選近未來 T，比對同 stage 與分 stages 的 approval 建立時間、scheduled time、實際 task start。測遲到核准、錯過窗口、無 Agent、gates before／after、DST／timezone、Server 重啟、手動重新部署及改排。
5. 驗證單次只觸發一次，超窗拒絕；改 artifact／target／時間超出批准範圍就失效。保留人員批准者、attempt、target／版本與時序，不以假帳號或通知信取代批准證據。

## 官方來源與適用界線

本文引用均為產品官方文件／官方 CLI reference／curl 官方手冊；搜尋結果中的討論串未作能力保證。Microsoft 共用頁可能混有 Services-only 小節；應以本文標出的 Classic／Server 範圍及現場 build 為準。

[1]: https://learn.microsoft.com/en-us/azure/devops/server/release-notes/azuredevopsserver?view=azure-devops-server
[2]: https://learn.microsoft.com/en-us/azure/devops/server/release-notes/azuredevops2022?view=azure-devops-server
[3]: https://learn.microsoft.com/en-us/azure/devops/server/release-notes/azuredevops2022u2?view=azure-devops-server
[4]: https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-server
[5]: https://learn.microsoft.com/en-us/azure/devops/server/requirements?view=azure-devops-server
[6]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-server
[7]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-server
[8]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/v4-agent?view=azure-devops#does-azure-devops-server-support-the-4x-agent
[8a]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/linux-agent?view=azure-devops-server
[8b]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/windows-agent?view=azure-devops-server
[9]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-server
[10]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-server
[11]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/powershell-v2?view=azure-pipelines-server
[12]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/manual-intervention-v8?view=azure-pipelines-server
[13]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/vstest-v2?view=azure-pipelines-server
[14]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/phases?view=azure-devops-server&tabs=classic
[15]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/define-multistage-release-process?view=azure-devops-server
[16]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/delay-v1?view=azure-pipelines-server
[17]: https://learn.microsoft.com/en-us/rest/api/azure/devops/release/releases/update-release-environment?view=azure-devops-rest-7.0
[18]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/approvals?view=azure-devops
[19]: https://clouddocs.f5.com/cli/tmsh-reference/latest/modules/ltm/ltm_monitor_http.html
[20]: https://curl.se/docs/manpage.html#--resolve
[21]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/gates?view=azure-devops-server
[22]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/?view=azure-devops-server
[23]: https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.0

[1] [最新 Server release notes][1] · [2] [2022 release notes][2] · [3] [2022.2 release notes][3]：未找到兩個現場完整 build 的對照，列未解而非推定。

[4] [Express 功能／五位 active users][4] · [5] [Server 安裝 OS][5] · [6] [Agent／Server 升級／CLI 界線][6] · [7] [Classic Deployment Groups Windows／Linux][7] · [8] [v4 指南中 Server FAQ][8] · [8a] [Linux Agent prerequisites][8a] · [8b] [Windows Agent prerequisites][8b]。

[9] [Classic release／stage triggers][9] · [10] [Classic approvals 與 timeout][10] · [11] [PowerShell task][11] · [12] [ManualIntervention task][12] · [13] [VSTest task][13] · [14] [Classic jobs／server job 有界等待][14] · [15] [Classic multi-stage][15] · [16] [Delay task][16]：task 頁明含 Server／2022 monikers；不以 YAML 範例推導 Classic UI。

[17] [Release environment scheduling REST schema][17] · [18] [Resource approvals/checks，非 Classic 證據][18] · [19] [F5 HTTP monitor 官方 tmsh reference][19]（實際 BIG-IP 版本未辨識，不保證版本細節）· [20] [curl hostname mapping][20] · [21] [Classic gates 時序][21] · [22] [Classic gates overview／48 小時 delay][22] · [23] [Server REST version mapping][23]。
