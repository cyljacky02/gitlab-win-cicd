# POC 落地審查｜配套說明、API／憑證清單與決策工作單

**資料基準：2026-10-22。** 本文件配合 [九頁主簡報](gitlab-ado-poc-review.pptx)，不取代正式環境驗收、Microsoft 授權認定或上線批准。

## 1. 先說證據範圍

### 本次做了什麼

- 審讀 `CDPOC-CD-20261022.zip` 的文件、YAML、部署／退版腳本與匯出測試證據；**沒有重新操作遠端 POC、查目前 ACL 或驗證現存秘密**。
- ZIP SHA-256：`b273ba0f8d37430c6a9953cdccee51a6638763cc407278bc7d39e268c597bbf1`。在 repo 外暫存目錄解包，包內 manifest 的 **91 個檔案 hash／大小全部一致**。這是包內一致性檢查，不是來源簽章。
- 新交付僅使用去識別化角色、路徑與測試 ID；不轉錄密碼、token 值、私網位址、真實主機名稱或個人身分。不將原包／解壓資料納入新交付。

### 四種狀態不可互換

| 狀態 | 本案可支持的結論 | 依據（以下路徑相對於 ZIP 根目錄） |
|---|---|---|
| **POC 實測紀錄** | CI 產物、ADO 反查、人工部署放行、目標部署與失敗回復；角色／PR 分權；Agent 降權；獨立指定版本退版 | `evidence/e2e-phase-a-result.json` 至 `e2e-phase-c5-rollback-result.json`；`docs/05`、`13`、`14` |
| **本機沙箱測試** | 下一階段 338＋7＋63＝408 案，匯出結果零失敗；覆蓋本機 fixture、暫存檔替換、部分 DACL／快照／取消／程序中斷等契約 | `evidence/e2e-next-local-summary.json` 及三份明細；`docs/16-NEXT-STAGE-LOCAL-TEST-REPORT.md` |
| **已接受的下一階段設計** | main／production 分流、完整部署快照、交易還原、部署前與導流核准分開 | 包內 `docs/15`、`docs/adr/0001-transaction-restore-and-go-live.md`、`source/GLOSSARY.md` |
| **待正式建置／整合驗收** | 正式應用、F5、業務驗測、多節點、長時間等待與失聯恢復、SQL／ADO DR、授權及營運交接 | 包內 `docs/06`、`07`、`11`、`15`、`16` 的缺口與下階段關卡 |

**下一階段程式未接入現行 CI、ADO pipeline 或現行 broker。** `source/cdpoc-win/broker/next/` 限本機 sandbox，不是可直接替換現場的安裝包；408 案不是 408 次遠端 E2E，也不是覆蓋率。

### 代表實測，包含「如預期被拒」

| 證據 | 可說的結果 | 不可擴張的結論 |
|---|---|---|
| A：#3／#5／#6，#4 | 靜態站部署成功；#4 健康失敗後有實際驗證切回 | #2 曾有回復驗證捷徑，不能單獨當成功復原證據；不支持資料庫還原／零影響 |
| B、C-1／C-2：#7、#10／#12／#14 | 核准後部署；自核遭拒；部署核准逾時／拒絕不部署，修正後 run 會失敗 | #9 曾出現未部署卻 succeeded；不能只看歷史 run 的總結果 |
| C-3：#15、R1–R10 | 五帳號分權、CD repo PR／必要審核、直推被拒、非核准角色遭拒 | 不等於五人授權已確認；核准評語不是系統必填 |
| C-4：#17、P-01–P-09 | 低權限 Agent 經 SYSTEM broker 部署；入口拒絕、部署健康失敗回復等測試 | P-09 只核對排程 ACL，未由其他低權限身分實際嘗試啟動；故障探測可能短暫影響站台 |
| C-5：#18／#19 | 從未成功部署／目前已在線的目標被 Plan 拒絕，零核准請求 | 不是成功退版 |
| C-5：#20、RB-05–RB-07 | Plan → 人工核准 → 成功退回既有版本；觸發者自核被拒 | rollback 本身的核准拒絕／逾時、健康失敗後回復未在真目標重測 |
| C-5：#21、RB-08–RB-09 | 退版後再往前部署成功，歷史判斷更新 | 不是另一筆成功退版；deploy＋rollback 並行仍未測 |

**成效說法：**已形成一致、有來源／核准／部署紀錄的可追溯路徑。沒有比較基線，不報人力節省比例、零停機、RTO／RPO 或生產吞吐量；單次靜態站耗時也不是正式 SLA。

## 2. 現況架構、責任與信任邊界

大型圖見 [第 2 頁預覽](preview-02.png)。圖中的箭頭區分「請求發起方向」與「檔案／工作回應方向」，不是把資料向右流誤畫成 ADO 連入 Windows。

1. **GitLab CE／Runner**：開發者具名提交；default branch 的 `build` job 產生可追溯的候選版本識別，產出 `site.zip`、manifest 與內含 `release.json`；目標端 broker 拒絕同 ID 目錄覆寫。目前 YAML 只走 default branch 且排除 MR pipeline，並非已實作雙分支晉升。
2. **GitLab 只通知，不派送部署**：`trigger-ado` 送 project／pipeline／job／commit／releaseId／hash。這些欄位都不直接當成可信來源或人工授權。
3. **ADO Fetch agent**：以自己的唯讀 GitLab token 反查釘選 project 與指定 job，檢查成功、job 名、非 tag、default branch、pipeline、commit；下載 ZIP／manifest，核對 hash、大小及版本內容。
4. **ADO 存版**：使用 **Server Build Artifacts，type Container**，保存 ZIP、manifest、verification。不是 Pipeline Artifacts，也不是 Docker container。原始候選版本已可在管理側入庫，**未放行前不向目標預拷**。
5. **Environment 人工部署放行**：綁定本次 pipeline run 的版本與目標；核准者群組、觸發者不可自核、12h 逾時是 POC 設定。checks 在資源管理面，不是 YAML 一行註解就會自動存在。
6. **目標 VM Agent**：主動連 ADO 取工作，放行後下載指定產物、重算 SHA-256；只能寫 staging／inbox、讀取 outbox／設定並啟動受控 broker 排程工作。
7. **SYSTEM broker**：本機唯一能 materialize releases、切換 IIS、驗健康、失敗切回及寫 journal 的元件。Agent 降權不等於整套系統沒有高權限；broker 是必須審查的信任核心。

### 邊界與剩餘信任

- **內容與 CI 秘密**：誰能修改 GitLab default branch／CI／runner，就可能控制產出內容及使用 CI 的觸發 PAT。CE 的 optional MR approval 不能說成平台強制雙人覆核。
- **CD 程式與放行**：ADO CD repo 的 PR／必要審核限制 agent 執行的 YAML／腳本；pipeline allowlist、資源 ACL 與 Environment check 是不同控制。具管理權者仍可改 policy／check，需變更管理與稽核。
- **本機高低權限**：broker 檢查格式、檔案／hash、目錄及 journal，但**不獨立向 ADO 查核批准，也不向 GitLab 驗證來源／簽章**；不能把它描述為可抵抗被完全控制的合法 Agent 的獨立授權服務。
- **部署鎖**：現行 broker mutex 只序列化本機 broker 執行。它不等同跨 ADO／Rundeck、跨 agentless 人工等待的持久交易鎖；也不防較舊 run 後來才部署。
- **既有治理不自動合併**：本 POC 是獨立 IIS site，既有 Rundeck／JEA 路線未變更，不宣稱已共用鎖或授權紀錄。

### 實際網路發起方向

| 呼叫者 → 接收者 | 協定／用途 | POC 記載與正式建置差異 |
|---|---|---|
| GitLab Runner → ADO | HTTPS 443；通知候選版本 | POC 走私有 DNS／內網；正式依網段與來源最小化放行 |
| ADO Fetch agent → GitLab | HTTPS 443；API 反查及檔案下載 | **POC 經公網 Cloudflare**；不是全程內網。正式建議內網／內部 PKI |
| Windows Agent → ADO | HTTPS 443；long-poll、工作／artifact 回應、log | ADO 不需對目標開 WinRM／RDP 入站；既有其他管理需求另議 |
| 核准者瀏覽器 → ADO | HTTPS 443；以核准者登入／放行 | 管理來源、身分驗證與可歸責性另驗，不以 CI PAT 代人核准 |
| Agent → 本機 broker | staging／inbox／outbox＋排程工作 ACL | **不是額外 REST endpoint，不需要第三把 broker API key** |
| broker → 本機 IIS | HTTPS localhost:8443；版本／首頁 probe | POC 自簽憑證 thumbprint 釘選；不是通用跳過 TLS，也不是業務完整驗測 |

POC 還有 runner 拉取外部 image／套件及安裝 agent 的下載路徑；離線正式環境須內部散佈、預建 image／digest 與 CA 信任，不能把原 YAML 直接稱為離線可用。尚未接 F5，**目前沒有 F5 REST 呼叫或 F5 管理憑證需求**。

## 3. 實際自訂執行期 API 清單

`{c}`＝ADO Server collection base URL，`{p}`＝ADO project。以下均為 placeholder，不放現場 URL。這是 **source 可直接確認的自訂呼叫**；不聲稱已追出產品 SDK、agent、checkout、task 所有內部路由。

| ID | Method／Endpoint | 呼叫者／目的 | 認證與必要授權面 | Source |
|---|---|---|---|---|
| A1 | `POST {c}/{p}/_apis/pipelines/{pipelineId}/runs?api-version=7.0` | GitLab `trigger-ado`；傳 `templateParameters` 通知版本 | ADO PAT，Basic `base64(:PAT)`；Build Read & execute；擁有者的指定 pipeline QueueBuilds | `source/gitlab-project/.gitlab-ci.yml`，`trigger-ado` |
| G1 | `GET /api/v4/projects/:id` | Fetch；比對釘選 `path_with_namespace`、取得 default branch | project access token；`PRIVATE-TOKEN`；`read_api`＋Reporter | `source/ado-repo/scripts/Get-GitLabRelease.ps1` |
| G2 | `GET /api/v4/projects/:id/jobs/:job_id` | Fetch；檢查 job 名／成功／ref／tag／pipeline／commit | 同 G1；private project／CI 可見性另受角色設定影響 | 同上 |
| G3 | `GET /api/v4/projects/:id/jobs/:job_id/artifacts/out/site.zip` | Fetch；讀取指定 job 的單檔 artifact | 同 G1；artifact ACL、保留狀態亦須允許 | 同上 |
| G4 | `GET /api/v4/projects/:id/jobs/:job_id/artifacts/out/manifest.json` | Fetch；讀 manifest，與實檔／參數一致性比對 | 同 G3 | 同上 |
| R1 | `GET {c}/{p}/_apis/build/builds?definitions={deployDef},{rollbackDef}&statusFilter=completed&$top=200&api-version=7.0` | Rollback Plan；讀兩支 pipeline 歷史 | **System.AccessToken／Bearer**；Build Service scope／build read ACL，不新增 PAT | `source/ado-repo/scripts/Plan-Rollback.ps1`，`$builds` |
| R2 | `GET {c}/{p}/_apis/build/builds/{id}/timeline?api-version=7.0` | Rollback Plan；確認 Deploy／Rollback stage 真正 succeeded | 同 R1；對各候選 build 呼叫，次數不是固定一次 | 同上，`Stage-Succeeded` |

**數量口徑：**正常自訂整合是 1 支 POST＋4 支 GET；退版另有兩種 GET 路由，其中 timeline 可能多次呼叫。agent／artifact task 的平台內部流量不在這個「5」之內。

**正常管線沒有第三把跨平台 PAT：**checkout、`PublishBuildArtifacts@1`（Container）、`DownloadBuildArtifacts@1`（current）使用平台的 agent／job 認證。退版 Plan 明確映射 `SYSTEM_ACCESSTOKEN: $(System.AccessToken)`；`PLAN_LOCAL_TEST=1` 才能以 Windows default credentials 作本機測試，不能把該例外當 runtime 認證。

### 建置、管理與測試接口：不要混入每次部署最小需求

包內 `docs/03`、`source/tools/Provision-*.ps1`、`Enable-RoleModel.ps1`、相關 `Get-*`／`Test-*` 記錄的管理接口另包括下列類別。**此處是用途分類，不宣稱每個腳本分支已執行，也不宣稱窮舉產品內部 API。**

| 類別／路徑族 | 用途、呼叫者與認證 |
|---|---|
| GitLab `/api/v4/projects`、`.../repository/commits`、`.../access_tokens`、`.../variables`、runner／pipeline／job 查詢、`/version` | GitLab 建置／測試工具建立資源、變數及觀察執行；曾用建置期 GitLab 管理者 `api` PAT。不是 Fetch 唯讀 token 的權限 |
| ADO `{p}/_apis/git/repositories/...`、`build/definitions`、`distributedtask/environments`、`distributedtask/variablegroups` | 建 CD repo、pipeline、環境與 secret group；建置工具以 Windows 整合管理身分操作，不交給 CI 觸發身分 |
| ADO `{p}/_apis/pipelines/pipelinePermissions/{type}/{id}`、`checks/configurations`；collection 的 identities／securitynamespaces／accesscontrolentries | 配置 pipeline 資源 allowlist、checks、群組與 ACL；資源管理者／建置工具操作。部分 source 使用 `7.0-preview.*`，不能由 runtime `7.0` 自動推論支援 |
| ADO `{p}/_apis/pipelines/approvals`（GET 指定 approvalIds／PATCH）及 build timeline／artifact／agent 觀察 | 包內測試以對應人員 Windows 整合身分驗核准／越權；**不是讓觸發 PAT 自動代人批准**。日常核准走瀏覽器，沿用資源端 check |
| Agent 註冊／package、pool／VM 管理 | 安裝、註冊、查狀態；使用管理期身分或短期註冊 PAT。註冊 credentials 與 runtime listener／job token 分開 |

### 官方支援與版本限制

完整逐條引文見 [API／credential 官方查核](../../research/poc-runtime-api-credential-review.md)。重要原文與入口：

- [ADO PAT](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022)：**“A PAT can't grant more permissions than its owner has.”** Scope 上限不能代替 resource ACL；管理者的 Build-only PAT 不等於專用低權限帳號。
- [Run Pipeline 7.0](https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/run-pipeline?view=azure-devops-rest-7.0)、[Server URI／版本矩陣](https://learn.microsoft.com/en-us/rest/api/azure/devops/?view=azure-devops-rest-7.0)：Server 要用 collection base URL。REST 7.0 有 Server 2022 起的官方基線，**不表示現場就叫 Server 2022**，更不證明各 preview API／task 可用。正式重建要取得精確 Server／patch／agent／task inventory。
- [GitLab single artifact API](https://docs.gitlab.com/api/job_artifacts/#download-a-single-artifact-file-by-job-id)：依 job ID 讀單檔。Reporter 適用此 private project 的 POC 設定，不能保證正式改成較嚴 `artifacts:access` 後仍成立。
- [GitLab project tokens](https://docs.gitlab.com/user/project/settings/project_access_tokens/)：Self-Managed **“available with any license”**。bot 的 role 與 scope 都生效；`read_api` 不是僅讀 artifact。**Internal visibility／token 建立者可能擴大跨專案可讀範圍**，不能無條件宣稱完全限於單 project。
- [Pipeline Artifact task](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines-2022)：**“supported on Azure DevOps Services only”**，Server 應用 Build Artifact task；實際 task major／minor 仍須盤點。

## 4. 憑證數量、持有、最小權限與清理

### 4.1 不混算的盤點

口徑是**一個 GitLab private project、一條正常 CD、兩個已註冊 Agent**的包內 POC；擴增 project／環境／Agent 時需重盤點。下表不是「目前仍有效秘密總數」：本次沒有查驗秘密有效狀態。

| 類型／數量口徑 | 發行／身分與權限 | 持有位置／取得者 | 設計理由與輪替／撤銷 |
|---|---|---|---|
| **1 把 ADO 觸發 PAT**（長效整合秘密之一） | 專用非管理觸發身分；Build Read & execute（`vso.build_execute`）；Readers＋只在正常 CD 的 QueueBuilds；rollback 明確拒絕 | GitLab CI `ADO_TRIGGER_PAT`，masked＋protected；POC 另有 Windows DPAPI 副本 | 只通知版本、不管理資源、不核准；POC 30 天，正式期限由政策定。新建→更換受保護變數／驗收→撤銷舊值；清掉非必要副本 |
| **1 把 GitLab project access token**（長效整合秘密之二） | project bot；`read_api`、Reporter；目標 private project。其他 Internal 可見性例外另驗 | ADO secret variable group 的 `GITLAB_TOKEN`；正常 pipeline Fetch job 掛載，Deploy／rollback 不引用 | ADO 自主反查，不信任通知來源。避免個人廣域 PAT、避免 `api` 寫權；非 `read_repository` clone。到期前依相同 role／scope 輪替，重驗 API／其他專案拒絕 |
| **1 個 runner authentication token**（包內一個已用 runner） | GitLab runner 註冊後認證；不是 ADO API token | Runner 設定檔；限制 host／檔案／runner 管理權 | 包內記載曾暴露，**必須重設並留證**。新增 runner 不沿用共同秘密 |
| **2 組 Agent 註冊後憑證／金鑰**（管理側、目標側各一） | agent 身分、RSA／listener 認證；不是人員 PAT，也不等於 Windows service account | 各 Agent 目錄／主機，嚴格 ACL | 註冊後通訊不持續用安裝 PAT。洩漏時撤銷／移除或重註冊 Agent，不能只撤銷註冊 PAT 就認定事件已處理 |
| **每 job 動態發行 token，非固定長效把數** | ADO Build Service、job authorization scope＋其 ACL；Plan 用 Bearer | 執行中 job／必要步驟環境；不要落地或輸出 | 用於 checkout／artifact／內部 API。限制 current project／必要 repo／build read。不是第三把長效 PAT |
| **至少 3 把被明列的管理／bootstrap PAT**（歷史，不是每次需要；非全史總數） | 舊 ADO 管理者觸發 PAT、目標 Agent 一日 Full 註冊 PAT、GitLab 管理者 `api` PAT | 建置操作者／POC 曾有 DPAPI 副本；不移植到正式 pipeline | 包內部分仍標待撤銷；**不能認定已撤銷**。留存撤銷／到期與副本清理證據。Full 是曾使用，不是官方已證明的最低註冊 scope |
| **人員／服務登入**（依實際身分盤點） | POC 有五個 ADO 角色帳號；正式建議具名／AD 群組與專用服務。身分數不是 API key 數，也不是已確認授權席數 | 人員／受控保險庫／OS 服務，依用途與政策 | admin、維護、放行分離；服務禁止不必要互動登入。不得將五帳號直接換算五位使用者 |
| **TLS 私鑰／憑證**（依端點盤點，不列入 API token 數） | ADO、GitLab、目標 IIS；POC GitLab 還有 edge／origin TLS 分層 | 服務主機或 PKI／proxy 管理系統 | 正式內部 PKI、信任鏈／撤銷與續期驗收；本次未稽核有效私鑰總數。健康 probe 的 thumbprint 是信任設定，不是秘密 API key |

**回答「要幾把？」：**自訂跨平台長效整合秘密是 **2 把**；此外有 **1 個 runner token、2 組 Agent credentials、動態 job token** 等不同類型。安裝／測試盤點已明列的 3 把管理 PAT 應收尾，不是正式每次部署要保留的第三至第五把；其他臨時測試憑證仍應以非秘密 metadata 清冊確認。OS 登入與 PKI 必須另盤點，不能給虛構的全系統固定總數。

### 4.2 權限層次要分開驗收

1. **認證**：PAT／project token／job token 證明哪個身分，不代表人員已批准部署。
2. **scope／role**：限制可用能力；GitLab bot 同時受 role 與 scope 影響。
3. **資源 ACL**：ADO 指定 pipeline QueueBuilds、GitLab project／artifact ACL、Build Service 對歷史與 repo 的讀權。
4. **pipeline 資源 allowlist／checks**：哪支 pipeline 可用 pool／environment／secret group／repo；誰可修改 check 是另一個高權限面。
5. **目標 OS 權限**：低權限 Agent、broker 排程啟動 ACL、admin-only broker／設定、releases／journal ACL；不由 API scope 取代。

[GitLab 官方](https://docs.gitlab.com/ci/variables/#cicd-variable-security) 明說 **“malicious code can compromise both masked and protected variables”**。Masked／hidden 是降低 UI／log 暴露，不是阻止合法 CI 讀取並外傳秘密的保證。

## 5. 回復、退版與下一階段的明確界線

| 路徑 | 現況與條件 | 限制 |
|---|---|---|
| **POC 健康失敗自動回復** | broker 切回前一靜態站目錄，重新 probe，journal 記 failed-reverted 或未驗證失敗；部署 job 仍失敗 | 不是業務資料還原；沒有 F5／第二次人工導流關卡；可能短暫提供壞內容 |
| **POC 指定版本退版** | 維護者手動開 rollback；Plan 先查成功 Deploy stage → 同 Environment 核准 → 本機 broker 查成功 deploy journal、非線上版本，再切換／驗健康 | 不能任選 Git commit；不重建／不向 GitLab下載；Plan 只讀近 200 個 completed builds，未分頁，retention／刪史／多 attempt／漂移待補驗 |
| **下一階段 Restore／Rollback／Go-live** | Restore 補償本次未完成交易；Rollback 選同目標曾完成上線的完整 Deployment Snapshot；Readiness 與導流許可分開 | 只有本機程式與測試。新 Windows/IIS/service adapter、真 ADO checkpoint、HTTP／開機恢復、SMTP、F5 drain／重啟斷電尚待整合 |

包內下一階段 ADR 已接受 production **12h 部署前核准＋換版或自動還原後 30 分鐘導流核准**、拒絕／逾時保持 DRAIN。這是**下一階段設計**，不能畫到現況圖當已驗收；DRAIN 只是停止導流意圖，不是既有工作已排空的證明。還原成功不等於允許納流；單節點可能停機等人，沒有零停機承諾。

### 詞彙與時序

本 repo root `GLOSSARY.md` 是治理通用詞彙；包內 `source/GLOSSARY.md` 與 ADR 是較晚的交易／導流語境。本交付只在「下一階段」使用完整快照／Restore／Go-live 等詞，不默默覆寫 root glossary。Root 的部署放行最低條件不要求雙人審批；本 POC 採較嚴的觸發者不可核准，不代表已改寫全專案最低規則。

包內 `01`、`02`、`07`、`11`、`12` 的部分段落仍保留「SYSTEM agent／無 branch policy／待新增 rollback」等初版敘述；**以後期 C-3～C-5 證據與 source 校正**，不據此把已補上的控制再次列成完全未實作。反過來，也不能因後期補了一項就聲稱所有正式缺口都已關閉。

## 6. 正式試辦的安全與驗收門檻

| 負責面 | 保留並重驗 | 尚需完成／決定 |
|---|---|---|
| IAM／採購 | 觸發／維護／核准／唯讀分權；非管理者持有觸發 PAT | 實際人員／裝置與間接存取授權、具名歸責、代理人、舊 PAT 撤銷、runner token 重設 |
| 架構／網路／PKI | Agent 出站取工作、TLS 驗證、最小來源清單 | Fetch 專用 VM／身分、內網 GitLab、內部 CA／CRL／OCSP、主動測不允許來源被拒；離線 image／套件供應 |
| 資安／DevOps | CD repo PR／必要審核、Environment 核准、指定 pipeline 資源授權、Agent 降權 | broker 高權限 TCB 審查／變更完整性、build validation、check 管理防繞過、跨路線部署鎖與舊 run 排序 |
| 開發／供應鏈 | API 反查＋hash／內部版本 marker | 簽章／provenance 是否必要、image digest、runner 隔離、CI 修改權與 secret 外傳控制、CE 強制審核能力缺口 |
| 維運／DBA／應用 | 靜態站 probe、失敗回復、獨立退版、journal | SIEM／告警／到期監控；token／憑證輪替；SQL／ADO 備份還原；正式應用 service／config／資料與 F5 契約 |

**不可互相替代：**hash ≠ 簽章；健康 ≠ 業務功能通過；單一可用 parallel job ≠ 部署鎖；broker mutex ≠ 跨核准等待的交易保留；ADO 歷史推論 ≠ 現場版本真相。

GitLab CE／Free 可以 protected branch；但 [required MR approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/) 與 [Code Owner enforcement](https://docs.gitlab.com/user/project/codeowners/) 有付費 tier 條件。Free optional approvals **“don’t prevent merging without approval”**；正式政策不能只靠寫下 MR／CODEOWNERS 就說平台已強制。

最低驗收集：正常發版；部署核准拒絕／逾時不動目標；自核／非核准者／未授權 pipeline 遭拒；scope＋有效 ACL；惡意 ZIP／reparse／同 release 重跑；rollback 核准拒絕／逾時及健康失敗；deploy＋rollback／舊 run 排隊；agent 斷線／重啟；輪替／稽核對帳；ADO／SQL 還原。F5／下一階段若納入首發範圍，另加 drain、直接指定節點功能測試、導流核准／撤銷／恢復等整合證據。

## 7. 「多人 GitLab CE＋五位 ADO Express」如何審查

### 技術理由成立，不代表授權計數已完成

將應用開發／CI 留在 GitLab，ADO 聚焦部署治理，可降低人員直接操作部署資源的範圍。POC 已驗證五個 ADO **帳號**的權限模型：管理、觸發服務、CD 維護、部署核准、唯讀觀察。這證明分權可行，**不證明五個帳號背後任意多人都合規**。

[Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-server) 原文：**“Azure DevOps Server Express licensing limits use to five active users.”** 不能改寫為最多五人同時在線。

更直接的 [現行 Express EULA](https://visualstudio.microsoft.com/license-terms/azure-devops-server/)（入口的 [官方 DOCX](https://visualstudio.microsoft.com/wp-content/uploads/2025/11/ENU_EULA.1031.docx)）在 Express 專段寫：

> “up to five (5) users or devices … in cases where a CAL is required”

同一專段亦有免 CAL 例外：

> “for accessing Azure DevOps Server through a pooled connection from another integrated application or service.”

因此**不能只挑五人上限，也不能只挑整合例外**。一般 multiplexing 規則、產品例外、取得通路與實際用途須併讀；本次未取得 Microsoft 對此 GitLab CI／人工重跑／Environment 核准／資料回填拓撲的個案裁示。

### 不能先做的假設

- 不將 ADO identity／PAT 數直接視為實際使用者或裝置數；群組或共用角色帳號不會自動把多人合併成一位。
- 不把所有 service／agent／Build Service 都當成人員一席；官方服務身分有相關豁免，但自建觸發代理的用途仍需核對。
- 不把「沒有直接登入 ADO」當成無間接存取，也不因 GitLab 名冊有人就斷言全部需 CAL。
- 不將 Server Basic 免費五人、Stakeholder 功能權、Express 五人及 full-use 的管理／approval 例外混用；**Express 與 full-use 的例外清單及版本需分別讀**。
- PAM／借出／評語／稽核是共用操作補償控制，**不是授權豁免**；本案優先具名放行。系統不強制必填核准評語，不能把評語當唯一歸責機制。
- POC 觀測一個可用 self-hosted parallel job，是現場容量狀態，不是人員上限、產品永遠固定一個的結論或安全鎖。

### 上線前需要的書面產出

依實際**人員／裝置／操作／直接或間接路徑／資料接收方式／擬援引例外／已持有 entitlement**盤點，由採購／Microsoft 明確確認：

1. 適用哪份 Express EULA／合約及版本；active 計數／替換規則為何。
2. GitLab 自主 CI 通知、人工選版／重跑與狀態／log／artifact 回填，哪些適用整合例外。
3. 自建觸發服務、Agent／broker、核准兼 PR reviewer、管理與唯讀各如何計數。
4. 超限是否需轉 full-use Server、相應 CAL／訂閱與相依 Windows／SQL 授權；**不是預設加一把 CAL 就可直接解除 Express 上限**。

完整官方條文、2022／現行 EULA 差異、service accounts、multiplexing 及可採購選項見 [授權研究](../../research/ado-express-five-user-license-review.md)。正式決議前，投影片只能標「採用條件待確認」，不能替方案預先背書。

## 8. 會議工作單與落地關卡

本表是**待填決議**，不是代各部門簽核。

| 決策 | 必須回答的問題 | 建議 Owner | 結果／依據／日期 |
|---|---|---|---|
| 架構與授權 | Express／full-use？實際人員與例外？Server／SQL／Agent／task 版本、Fetch 隔離、容量？ | 架構＋平台＋採購 | 待填 |
| 身分與安全 | 具名與代理人？誰能改 CI／CD／checks？PAT、broker、簽章、部署鎖與稽核接受標準？ | 資安＋IAM＋DevOps | 待填 |
| 試辦與驗收 | 首發應用、目標、變更類型？是否含 F5／下一階段交易？go/no-go、停損與復原證據？ | 應用 Owner＋測試＋維運 | 待填 |
| 營運與資源 | 輪替／告警／SIEM／備份還原／值班負責人？人力何時可投入？ | 維運＋DBA＋專案 | 待填 |

每項另記：**接受的風險、範圍／期限、未決阻擋項、確認人與下次檢查點**。未決不得默認同意。

| 關卡 | 出場條件；未達不往下走 |
|---|---|
| 1 審查定案 | 書面授權意見、架構範圍、安全底線、責任與試辦驗收標準達成共識 |
| 2 正式基礎建置 | 身分／網路／PKI／主機／SQL／備份完成硬化與連線驗收 |
| 3 移植與重驗 | 後期 CI／CD、PR／check／資源 ACL、低權限 Agent／broker、rollback 在正式基線環境重測 |
| 4 SIT／UAT | 正常、越權、拒絕、逾時、回復、退版、並行／失聯及還原演練留證；未整合能力不能借本機 PASS 代替 |
| 5 限範圍試辦 | Owner 明確 go/no-go、回復與聯絡流程、監看／停損；成功後再決定擴展，不預承諾所有專案日期 |

## 9. 本交付與歷史材料的關係

- 舊六頁 Journey 是 POC 完成前的導入敘事，**全部保留，不回頭改寫**。
- 新版主內容／備註來源為 `deck.json`；原生 PPTX 的文字、卡片、圖示與線條均可編輯；PDF 由實際 PPTX 經 PowerPoint 匯出。
- 本配套只整理已審讀證據與建議門檻，不發布原始包或實機機密。不修改原始 `GLOSSARY.md`／ADR 或既有未追蹤研究。
- 視覺沿用已確認的暖白、藍／青綠／橙、路線與編號節點。此環境無 Refero MCP；**沒有聲稱完成外部 Refero 搜圖研究**。版型依據是已存在的 `journey/six-page-v3` 架構／行程頁，不重新引用私人參考照片。
