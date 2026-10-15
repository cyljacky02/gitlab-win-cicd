# GitLab CE → Azure DevOps Server Express：事件驅動的候選版本交接

## 結論與證據範圍

**建議：GitLab Pipeline success webhook → 管理側受保護接收器／耐久佇列 → 固定 ADO importer Build → Build Artifacts → Classic Release → 各環境 Deployment Group。** 不以定時掃描作為主要觸發機制；GitLab CI 不持有 ADO PAT、Release 權限或 Production 主機憑證。接收器只有排入固定 importer 的權限；匯入候選版本不等於部署放行。

本文件重新查核官方線上文件，補充 `gitlab-cd-artifact-handoff.md` 的輪詢方案，依 `GLOSSARY.md` 區分候選版本通知、部署放行與部署派送。**這是文件支持的目標架構，不是已通過的實機 POC。** Microsoft 明載 Express 與 Server 功能相同、授權限制五位 active users；Server 2022 支援 REST 7.0，因此可採 **Server Express 2022／REST 7.0** 為 POC 基線。安裝版本、修補層級、身分授權與下列 ACL 負向測試仍須實測，不能把 Services 文件範例直接當成 Express 實測結果。[1][2]

## 兩條事件路徑的取捨

| 路徑 | 官方基礎能力 | 必須自行完成／風險 | 判斷 |
|---|---|---|---|
| 最後一個 CI job 呼叫 ADO Queue Build REST | GitLab job 可執行 HTTP 呼叫；ADO 有 Build Queue 7.0、Server PAT、逐 build definition 的 Queue builds ACL。[3–6] | CI 需持有「排程匯入」權限；通知執行時整個 pipeline 尚未成功。須限制輸入與定義、非同步排入後退出、管理側等待最終狀態。 | **可作簡化備案，不是天生等於 Production 授權**；只有確認無越權且接受事件後有限狀態重查時才採用。 |
| Pipeline webhook → 受保護接收器 → Queue Build | GitLab pipeline 狀態改變會發 webhook，payload 有 pipeline ID、ref、SHA、status；ADO 同一 Queue API。[3][7][8] | 驗證來源、耐久入列、GitLab API 複核、去重、重送、限流、路由皆為自製 glue。 | **首選**：收到最終 success 才處理；ADO 憑證完全留在管理側，避免 CI job 的完成競態。 |

### 為何「最後一個 job」不是 pipeline-success 事件

GitLab `when: on_success` 表示前面 stages 沒有失敗，不表示包含自己在內的 pipeline 已經成功；`allow_failure` 和 skipped manual jobs 也影響這個判斷。官方 stages 範例在最後 stage 的 jobs 成功後才將 pipeline 標為 passed。[6]

因此通知 job 排入 importer 時，importer 若立刻要求 pipeline `status=success`，可能看到 `running`；若通知 job 等 importer 完成，而 importer 等 pipeline 成功，會形成循環等待。**不可靠 sleep 幾秒就當成功，也不可讓 importer 忽略整體結果。** 直呼備案須：先排入、保存 build ID、立即結束通知 job；管理側對該 pipeline 有界重試查詢，直到 success 或失敗／取消／逾時，只有 success 才發布 artifact。這仍是事件啟動，但包含針對單次事件的狀態輪詢；若要求完全沒有此種等待，選 success webhook。通知後 job 失敗、pipeline 取消都不得發布候選版本。[6][9]

## Server／Express 支援：不能混用的概念

- **REST 與認證：** Server 支援 PAT、Windows authentication／.NET client；Microsoft Entra／Azure DevOps OAuth 整合不是 Server 的替代方案。PAT 以 HTTPS `Authorization: Basic base64(:PAT)` 使用；這不等於開啟 IIS Basic Authentication，官方反而要求 IIS Basic 關閉以免 PAT 驗證失效。PAT 不會賦予超過持有人 ACL 的權限。[4][5]
- **原生 incoming webhook 不是一律 Services-only：** Microsoft 的 YAML resources 文件明確註記 **Azure DevOps Server 2020.1 已推出 webhooks**。所以不能聲稱 Server 2022 沒有 webhook 能力。但該文件範例用 `dev.azure.com` URL，驗證格式是 payload 的 **HMAC-SHA1**；GitLab 傳統 `X-Gitlab-Token` 是明文共享值，現行文件新增的 signing token 是 **HMAC-SHA256／Standard Webhooks**，都不能直接假設相容。不要把無驗證的公開 incoming endpoint 當成安全捷徑。Server URL、該安裝版 UI、簽章互通性需要另外實測；本建議使用自有接收器＋已文件化的 Queue REST，不依賴此互通性。[8][10]
- **沒有查得第一方原生 GitLab CI artifact source：** Classic release artifact sources 文件列出 Azure Pipelines、Azure Repos/GitHub/TFVC、Azure Artifacts、容器來源、Jenkins，未列 GitLab CI。這不等於證明所有外掛不存在；只是不把第三方外掛或 Git repository checkout 說成原生 GitLab artifact 整合。先匯入成 ADO Build Artifacts，再以 Azure Pipelines source 綁定特定 importer build。[11]
- **Build Artifacts，不是 Pipeline Artifacts：** 使用 `PublishBuildArtifacts@1`，`PathtoPublish: $(Build.ArtifactStagingDirectory)`、`ArtifactName: drop`、`publishLocation: Container`。`PublishPipelineArtifact@1` 明載不支援 on-premises；不要用會展開成 Pipeline Artifact tasks 的 YAML `publish`／`download` 捷徑代替。[12][13]
- **Agent 角色不同：** importer 在管理區專用 self-hosted Build Agent 執行，從 GitLab 讀取並發布 artifact；目標 Windows 上的 Deployment Group Agent 在 Classic Release 中執行該主機的部署工作。Deployment Group jobs 不能用於 Build pipeline。即使底層同屬 agent 軟體，也應分開主機／服務帳號／pool、檔案 ACL、網路路徑與註冊權限；管理側 importer 不得使用 Production agent 或 Production 共用目錄。[14][15]

## Queue builds 權限真正能限制到哪裡

官方 permissions reference 明載可在 project 或**各個 pipeline definition** 設定 Build 權限；`Build, QueueBuilds` 允許排入 build，也可停止自己排入的 build。因此「只能 queue 固定 importer」有官方 ACL 基礎，但**PAT 本身不是綁定單一 definition 的 capability token**。[16]

POC 建議使用專用非管理員帳號，PAT 選 **Build：Read & execute**，不選 Full access／Release／Agent Pools 管理等額外 scope；Build execute scope 仍比「單一 importer 的 queue」寬，真正的 definition 邊界由帳號有效 ACL 決定。官方 scope 描述 `vso.build_execute` 包含 queue、讀取 build artifacts/results/definitions 等，不能宣稱 scope 本身只有 queue。[5][17]

- 在允許的 importer definition 授予必要 View 與 Queue builds；其他 definitions 不得有有效 Queue 權限。檢查 project／folder／群組繼承，避免把專用帳號加入 Contributors、Build Administrators、Project Administrators 等廣權限群組。不要先做會覆蓋子層 Allow 的廣域 Deny，再假設例外必定有效。[16][18]
- 拒絕 Edit build pipeline、管理權限、任意 Release 建立／編輯／部署／核准、Production Deployment Group 使用／管理、Production 憑證讀取。接收器、importer 的 build service 身分與 agent OS 帳號分別盤點，不能只檢查呼叫 API 的 PAT。[18]
- **Queue 權限不代表輸入安全。** Queue API 支援 `parameters`、`sourceBranch`、`sourceVersion` 等欄位。受保護 importer 不可讓呼叫者選執行 script、repo、branch、agent pool、下載 URL、目標路徑或環境；只收有格式限制的 GitLab pipeline ID（job ID 僅供提示）。使用 CD 管理的固定 Classic definition／固定來源與信任版本；若用 YAML，必須防止 queue 時替換 YAML 分支／版本。把驗證器放在不可由 queue 輸入換掉的信任位置。單純「預設分支受保護」並不足夠。[3][16]
- 官方 permissions 文件中的 **Edit queue build configuration** 屬 Services moniker，不能當成 Server 2022 一定存在的防線。必須實測惡意覆寫參數、來源與權限繼承；若無法封住，直呼 CI 方案 no-go，改由受保護接收器固定組裝 queue request，仍保護其憑證。[16]

Queue 請求概念如下；主機、collection 路徑與 definition ID 由管理側固定設定，沒有本機秘密：

```http
POST https://ado.example/Collection/CDProject/_apis/build/builds?api-version=7.0
Authorization: Basic <由安全儲存中的 PAT 產生，禁止寫入日誌>
Content-Type: application/json

{"definition":{"id":42},"parameters":"{\"GitLabPipelineId\":\"123\"}"}
```

API 7.0 文件提供 Queue primitive；Server base URL 依實際 collection 設定替換。HTTP 成功只代表已排入，需保存回應 build ID，不能當成匯入成功或部署成功。[2][3]

## 建議的可稽核事件流程（以下流程編排是自製 glue）

1. **接收／持久化：** GitLab project webhook 啟用 Pipeline events。只受理固定 GitLab instance／project 的 pipeline hook；驗證 TLS、認證、payload 大小、格式與重放，寫入耐久 inbox 後快速回應 200/201，再由 worker 處理。官方建議快速回應、非同步 queue 並處理重複事件；webhook 可能被停用，不提供 exactly-once 保證。[7][8]
   - 新版支援時依官方方式驗 HMAC-SHA256 signing token、原始 body 與 timestamp；先確認實際 GitLab CE 版本，**不把目前線上文件功能倒推至舊版**。
   - 舊版使用 HTTPS＋`X-Gitlab-Token` 常數時間比對、固定來源網路限制及 API 複核；共享 token 不是 payload 簽章，也不是部署放行。不要把 webhook 管理權視為 Production 權限。[8]
2. **成功與來源複核：** webhook `status=success` 只是通知；管理側以自己的最小 GitLab API 讀權限查 `GET /projects/P/pipelines/L`、`GET /projects/P/pipelines/L/jobs?include_retried=false`、必要的 job detail。核對固定 project、pipeline ID、`status=success`、精確 ref、SHA、`source=push`、非 tag、非 child／MR pipeline，以及所需測試／封裝 job 真正成功。API 回傳不一致、仍 running、無權限或不存在時暫停／拒絕，不能 fail open。`allow_failure` 使 pipeline success 不等於所有品質檢查通過；必要 job 清單由 CD 管理政策固定。[6][7][9][19]
3. **固定來源分支路由：** 接收器與 importer 都使用下表的 CD-owned 映射，不信任 payload／queue parameter 所聲稱的環境。

   | 已複核的 GitLab ref | 固定 importer | 固定單環境 Classic Release | 放行方式 |
   |---|---|---|---|
   | `master` | SIT importer | SIT | 匯入成功後自動 |
   | `pre-production` | UAT importer | UAT | 匯入成功後自動 |
   | `production` | Production candidate importer | Production | 授權部署人員選確切版本並放行 |

   這些是 **GitLab 來源分支**，不是 importer 的 ADO repo branch。Classic release 的 build branch filter 看到的是 ADO build 的來源分支，不能拿它判斷原始 GitLab ref。以三組固定 definition/source 綁定避免混流；importer 即使被誤排入也須驗證自己唯一允許的 ref。保留各分支分別建置，不宣稱已做同一 artifact 的環境晉升。[3][11][20]
4. **固定 artifact 身分：** 只接受政策指定封裝 job 名稱、stage 與唯一有效 job ID，驗證它屬於該 pipeline／SHA，且 success；拒絕重複同名候選、意外 parallel job 或任意使用者提供 job。下載 `GET /projects/P/jobs/J/artifacts`，或固定允許的內部 artifact path；不用 `latest`／ref-based latest-successful URL。重試 job 會改變 job ID，需重新建立候選版本，不得覆蓋已放行版本。[19][21]
5. **受控匯入：** 在管理區驗證 ZIP 路徑穿越、連結、大小與 layout，不執行 artifact／GitLab repo 附帶的部署 script。對確切部署 payload 計算 SHA-256，保存 manifest：project、pipeline、job、ref、commit SHA、hash、大小、GitLab 驗證時間、CD policy/script 版本、ADO importer build ID。hash 是完整性證據，不會使開發者產出的程式變成可信。發布 payload＋manifest 至該 build 的 `drop`，保留到部署、稽核及回復所需期限；artifact 過期時 fail closed，不換成最新版本。[12][21]
6. **成功交接與部署：** 只有驗證／下載／hash／發布全部成功，才完成 importer 成功狀態並記錄候選版本。SIT/UAT 的固定 artifact source 開啟 continuous-deployment trigger，stage 設 After release、PR triggers 關閉。Production 關閉 artifact 自動 release trigger，授權人員建立 release 選定 importer build，stage 設 Manual only＋具名 pre-deployment approvers，並限制 release edit／create／deploy 權限。允許同一授權人員發起與核准，不要求雙人審批；不可自動沿用另一候選版本的核准。[11][18][20][22]
7. **Production 邊界：** 放行對象是應用程式＋Production＋確切候選版本。**放行前 bytes 只存在管理側，不能預先複製至 Production**（包含 Deployment Group Agent 的工作／artifact download 目錄）。只有被放行的 Production stage 才可派送工作並下載固定 build 的 artifact，部署前重驗 hash。不得另設較早的 Production staging/copy job；以實機檔案與工作稽核證明預設下載時機沒有越過放行。[11][14][15][22]

## 重複、亂序與中斷：不是原生 exactly-once

- 以 `(GitLab instance, project ID, pipeline ID, job ID)` 為候選版本唯一鍵，另存 webhook event ID、ADO build ID、狀態與每環境部署紀錄。Webhook ID 用於訊息去重，但不能代替 artifact identity；同一 pipeline 可發多次狀態事件／重送。[7][8][19]
- 耐久狀態至少涵蓋 received → validated → queueing → queued → imported／rejected。Queue REST 逾時可能已成功排入：先對帳既有 build 再重試；Build Queue 沒有在此文件中提供可直接依賴的 GitLab exactly-once 契約。Importer 再取得唯一鍵鎖，只有一個能發布；重複執行不發布新 `drop`，避免再次觸發 release。[3]
- 每來源分支維護匯入序列與每環境部署 high-water mark；晚完成的舊 pipeline 不可覆蓋已部署的新候選版本。部署前再次檢查、同環境序列化；Production 顯式授權的 rollback 是另外記錄的例外，不是靠事件到達時間推論新舊。不同分支的 pipeline ID 不用來證明 artifact 晉升。
- 接收器持久化前不可成功 ACK；持久化後 worker crash 可恢復。監控 webhook 停用、dead-letter、PAT 到期、artifact retention。正常流程不定時掃 GitLab；漏事件由有權限操作人員從 GitLab Recent events／API 重送，或指定 pipeline ID 補交並走相同驗證。若另加低頻對帳，應明列為復原機制，不能宣稱完全零輪詢。[8]

## POC go／no-go 清單

以下**尚未執行**；全部通過才可宣稱目標架構可運作。

- [ ] **版本／功能：** 確認 Express 2022 的實際 build、授權五人限制、REST 7.0；用合適版本 agent 跑通 Build Artifacts、Classic release、Deployment Group 與 pre-deployment approval。GitLab CE 實際版本的 webhook 認證方式已確認。[1][2]
- [ ] **PAT／ACL 正反測試：** 專用帳號可 queue 三個指定 importer；queue 其他 build、改 definition／queue 來源／script／pool、建／改／執行 Production release、核准、讀取 Production secret 全部失敗。檢查群組繼承及 build service／OS 帳號；不以 UI 隱藏按鈕代替 REST 測試。
- [ ] **偽造與失敗：** 假 success payload、錯 project／ref／SHA／job、tag、MR、child、失敗／取消 pipeline、allowed-failure 品質 job、錯 token／簽章、重放、惡意 URL／路徑，均不得產生可部署候選版本。
- [ ] **競態：** webhook success → importer 成功；直呼備案額外驗證通知 job 還在 running、通知後取消、job 失敗、逾時，且無循環等待／提前發布。若只靠立即 success 檢查或 sleep，no-go。
- [ ] **重送／亂序／崩潰：** 同事件重送、兩 worker 同時處理、Queue HTTP 回應遺失、發布前後 crash、舊 pipeline 晚到，都不造成重複部署或降版；漏事件可稽核補送。
- [ ] **路由與內容：** 三分支到固定三環境；修改 ADO repo branch 不改變路由。GitLab job ID → ADO build ID → release ID → target hash 可追溯；過期 artifact 不得悄悄改抓 latest。
- [ ] **正式環境零預拷：** 未放行／拒絕／逾時時 Production 無任何候選檔案寫入或部署工作；CI、receiver、importer 均無 Production 存取。放行後只有指定 Windows target 收到指定 hash；更換 candidate 必須重新放行。
- [ ] **保護與復原：** importer/release definitions、部署 scripts、來源路由與 service connections 由授權 CD 管理者保護；開發者不能改寫特權腳本。憑證輪替、retention、dead-letter 與事件補送經測試。任一 CI 可取得 Production 權限或放行前送檔情形皆 no-go。

## 官方第一手來源

[1]: https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-2022
[2]: https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rest-api-versioning?view=azure-devops-2022
[3]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-rest-7.0
[4]: https://learn.microsoft.com/en-us/azure/devops/integrate/get-started/authentication/authentication-guidance?view=azure-devops-2022
[5]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022
[6]: https://docs.gitlab.com/ci/yaml/
[7]: https://docs.gitlab.com/user/project/integrations/webhook_events/#pipeline-events
[8]: https://docs.gitlab.com/user/project/integrations/webhooks/
[9]: https://docs.gitlab.com/api/pipelines/
[10]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/resources?view=azure-devops-2022#webhooks-resource
[11]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/artifacts?view=azure-devops-2022
[12]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines
[13]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines
[14]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-2022
[15]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-group-phases?view=azure-devops-2022
[16]: https://learn.microsoft.com/en-us/azure/devops/organizations/security/permissions?view=azure-devops-2022
[17]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/authorizedresources/authorize-project-resources?view=azure-devops-rest-7.1
[18]: https://learn.microsoft.com/en-us/azure/devops/pipelines/policies/permissions?view=azure-devops-2022
[19]: https://docs.gitlab.com/api/jobs/
[20]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-2022
[21]: https://docs.gitlab.com/api/job_artifacts/
[22]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022

[1] [Express 功能與授權][1] · [2] [REST 相容版本][2] · [3] [Queue Build 7.0][3] · [4] [Server 認證][4] · [5] [PAT／IIS 限制][5] · [6] [GitLab job/stage 成功語意][6] · [7] [Pipeline events][7] · [8] [Webhook 驗證與重送][8] · [9] [Pipelines API][9] · [10] [Server incoming webhooks][10] · [11] [Classic artifact sources][11] · [12] [Build Artifacts task][12] · [13] [Pipeline Artifacts 限制][13] · [14] [Deployment Groups][14] · [15] [Deployment Group jobs][15] · [16] [Definition ACL][16] · [17] [Build execute scope 定義；僅用作 scope 說明，非採用 7.1 API][17] · [18] [Pipelines 權限管理][18] · [19] [Jobs API][19] · [20] [Classic release triggers][20] · [21] [Artifact identity API][21] · [22] [部署前核准][22]
