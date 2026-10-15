# Windows Classic Release：換版與復原可行性查核

> 後續需求更新：新版與退版路徑在恢復 F5 流量前，都新增部署人員的功能驗證／確認關卡。下文原先「健康才回池」應讀為「自動啟動檢查通過＋人工功能驗證通過才回池」。單一 PowerShell controller 不可直接沿用為自動回池實作，必須增加可強制等待、拒絕／逾時不回池及綁定 target/version 的續行機制；Server Classic 的具體等待／分階段核准配置仍待驗證。部署前核准不是這個中途功能驗證關卡。

## 結論與範圍

**可以實作，但不是設定 Deployment Group 後就內建完整 rollback。** Azure DevOps Server Express 2022 提供核准、固定版本 artifact、目標 Agent 執行 PowerShell 與任務失敗條件；備份、健康判定、F5 控制、復原狀態機與跨目標停止政策仍須自行實作。Express 官方聲明功能與 Server 相同，限制五位 active users；不代表現場安裝、帳號或腳本已驗證。[1–7]

已閱讀 `gitlab-ado-event-trigger.md` 與 `tools/build_deployment_map.py` 的生命週期。生成器只是畫圖，不是部署程式；圖上的「失敗停止後續」是待落實的政策，不是目前已有的產品保證。**本次只有官方文件查核，未執行 Server／Windows／F5 實機 POC。**

GitLab 成功事件與 importer 的自製串接沿用前份研究。完成匯入後，Release 使用 ADO 保存的指定 Build Artifacts；每台部署及檔案復原不需要再回 GitLab 取 latest、觸發 pipeline 或取得核准。保留 GitLab project／pipeline／job／SHA 作來源證據即可；復原來源是已驗證的已知良好備份，而非再次建置。

## 逐項能力與來源矩陣

| 項目／官方來源 | 文件支持的 primitive | 自製部分／未驗證邊界 |
|---|---|---|
| Express [1] | 與 Server 相同功能、五位 active users | 確認實際 2022 修補版、agent／task 版本與有效權限 |
| Classic Deployment Group [2] | Release 的 tasks 在所選目標執行；tags 篩選；限制同時部署比例 | 不能把 YAML `rolling.maxParallel`／`on: failure` hooks 當 Classic UI 功能；逐台數值選項與排程實測 |
| Release artifacts [3] | 建立 Release 時指定 artifact 版本；版本化下載至執行 Agent | 固定 importer build ID、manifest/hash、retention；不能每台重新選 latest |
| Pre-deployment approvals [4] | stage 部署前核准；未在期限核准則拒絕 | 所有正式目標下載工作置於此 stage；拒絕／等待時零預拷須檔案稽核，不只看 UI |
| DownloadBuildArtifacts@0 [5] | 2022 task 文件列 Classic release、DeploymentGroup；`specific`＋`buildId` | 明確下載可綁 Release 選定的 build；避免自動下載與手動下載不同版本。v1 文件未列原始 2022 moniker，不能直接照最新版抄 |
| PowerShell@2 [6] | 2022 可在 Classic release／DeploymentGroup 執行腳本及傳回失敗 | 停／啟服務、備份、檔案部署、健康檢查皆可寫腳本，但不是 task 內建應用交易或 rollback |
| Task control options [7] | Classic 可選先前失敗仍執行、僅失敗執行、取消仍執行與 custom condition | 條件只決定任務是否排入；不保證 Agent 離線、程序被殺或主機斷電時能執行 |
| Agent 行為 [8] | Agent 主動連 Server 取工作／回報；Windows 取消可能最終 `Process.Kill` | 需獨立監控／復原路徑；`finally` 或 always 不是斷電復原機制 |
| F5 member REST [9] | member 資源可 GET／PATCH；`session` 控制新 sessions，`state=user-down` 強制離線 | pool/member/partition 對應、drain、驗證、HA 與重試策略須依實際 BIG-IP 版本實測 |
| F5 流量／認證文件 [10][11] | Disabled 與 Forced Offline 不可當同義詞；F5 API 需獨立認證與授權 | [10] 是 BIG-IQ 管理說明、[11] 是 AS3 認證範例；不能推論所有 BIG-IP 版本的 ACL 或直接採 AS3 管理員權限 |

Microsoft 概念文件使用 `azure-devops-2022`；task 使用 `azure-pipelines-2022`。不採 Services-only 的 Pipeline Artifacts 捷徑、核准 MFA 或服務端新功能作 Server 證據。[3–6] [3] 現行頁面混有 Pipeline Artifacts 措辭且下載時序文字不精確，因此指定 Build Artifacts 的可執行依據採 [5]，核准邊界採 [4]，實際自動下載時點仍須 POC。

## 建議可實作的單機流程（自製部署狀態機）

1. **核准後取檔：** Release 綁定單一 importer build；Target Agent 下載 `drop` 與 manifest，驗 hash／磁碟空間／權限／目標對應，取得部署鎖。所有寫入正式主機的工作均在核准 stage 內；取檔失敗不隔離、不停服務。[3–6]
2. **先確認隔離：** 向管理側流量控制器要求隔離指定 member，讀回實際狀態並驗證既有連線／等待上限。隔離失敗或狀態不明不得停服務；HTTP timeout 不是「一定沒套用」。[9][10]
3. **停止、備份再覆寫：** 等服務確實停止；驗證目前版本身分及部署前健康證據，再備份 binaries、必要設定／ACL 至 agent 工作目錄外的版本化位置。建立完整性標記後才允許覆寫；半份備份不可標為有效。沒有有效已知良好備份就中止，不進行破壞性更新。
4. **換版與啟動：** 部署指定 payload，明確處理殘留舊檔／鎖定檔；啟動服務並以有界 timeout 驗證本機服務、版本與業務健康。PowerShell 的 Stop/Start/Copy 能力不等於應用一致性保證。[6]
5. **新版本健康才回池：** 由流量控制器恢復 member，讀回狀態並驗證實際流量；只有全部成功才記「新版本部署成功」。不要在無條件 `finally` 內 up F5。
6. **換版／啟動／健康失敗：** 保持隔離，停止失敗服務，還原有效備份，再啟動、驗證舊版健康；健康後才要求回池並驗證。結果為「部署失敗／復原成功」，不是新版本部署成功。復原、健康或回池驗證失敗時，停止後續並告警；不得假裝已恢復隔離或流量。

上述每步須保存 release/build/target、步驟狀態、備份路徑／hash、原始錯誤、F5 觀測狀態與操作識別碼；管理側也保存紀錄，不能只存於可能斷電的目標。步驟必須可對帳、可重入，不能將自動重試等同冪等。[7]

**檔案 rollback ≠ DB rollback。** 若版本包含資料庫 migration，先制定向前／向後相容及獨立資料復原方案；還原 binaries 不會還原 schema、資料或外部副作用。停止服務／備份失敗時不覆寫，保持隔離；若要恢復既有服務，也須另外驗健康才回池。

## 失敗後 rollback task 如何真的執行

可採兩種方式；第一個 POC 建議先做 A，再故障注入驗 B。[6][7]

- **A：單一 PowerShell deployment controller。** `$ErrorActionPreference='Stop'`；每個 native command 明確判斷符合該工具語意的 exit code。`try` 做換版／健康；`catch` 記住原始失敗，再嘗試復原／健康／回池。即使復原成功，最後仍 `throw` 或 `exit 1`；另存 recovery outcome，不能用最後一個成功命令覆蓋部署結果。`finally` 只作安全記錄／清理，不無條件恢復流量。
- **B：拆 Deploy/Health 與 Recover tasks。** Deploy/Health 保持 **Continue on error 關閉**且真正回報 failed；Recover 設 Classic **Only when a previous task has failed**，或 **Even if a previous task has failed, unless the build was canceled**（對應 `succeededOrFailed()`，腳本內再判斷是否需復原）。Recover 必須檢查本次 durable journal、已隔離及有效備份，不能遇到「下載失敗」就盲目回復。復原成功不抹除先前 failed；後續結案依部署／復原兩個結果記錄。
- Classic **Even if a previous task has failed, even if the build was canceled** 對應 `always()`；這只涵蓋條件語意，還需要可工作的 Agent、已啟動的 job 與足夠取消處理時間。取消會中斷／殺死當前程序，不能承諾一定跑完 rollback；人工取消也不應無條件觸發回池。[7][8]
- 腳本正常回報失敗通常可進入上述復原路徑；PowerShell 子程序 crash 而 Agent 尚活著時，下一個 recovery task 是可驗證的補救方式。Agent service crash、斷網、主機斷電或強制終止整個 job，則不可依賴同機下一步自救。

## 「失敗停止後續主機」的真實邊界

[2] 文件支持控制同時部署比例，**未提供足以承諾「任何 target 失敗，所有未來批次必定立即停止」的 Classic 排程契約**。最大併行只是容量限制；不是跨主機交易，也不撤回已派送的工作。設為逐台也須確認失敗後是否仍派下一台；跨 phase/job/stage 的條件、Continue on error、取消與在途工作都會影響結果。[2][7]

首輪以一台 canary 為唯一目標；第二台放在另一個明確成功相依／人工放行的 stage，先證明失敗不前進。正式若要求強制 fail-stop，可自製管理側編排器：每次只授權一個 target／有界批次，確認「新版本健康＋流量恢復」才發下一個 permit；失敗或狀態未知即關閉派送。全域鎖、剩餘容量、permit 對帳與已在途目標的安全收尾都屬自製責任，不能只在每台開始時讀一次共用旗標。

## F5 與失聯處置

- PowerShell 可呼叫 REST，不等於有 Microsoft 原生 F5 rollback task。本方案不依賴未查證的內建 task 或 Marketplace 外掛。[6][9]
- **F5 憑證留在受保護管理側控制器**；Target 只取得呼叫該控制器的受限身分，控制器驗證 release/target/operation allowlist。F5 帳號角色、partition／資源範圍、TLS、token 期限與管理網段另行核定；不把 F5 管理員密碼發給每個 Agent，也不把 Agent 註冊權限當 F5 授權。[8][11]
- `down/up F5` 應解讀為政策動作，不預設等於 Disabled 或 Forced Offline。需確認 persistence、現存連線、drain 上限及 monitors；讀回 enabled 並不等於應用已健康。[9][10]
- 斷網不一定代表腳本停止，Agent 掉線也不一定代表 F5 已隔離。獨立控制器／監控應停止新派送、查 F5 實際狀態與應用健康；無法確認安全時告警、採安全隔離政策並交由人工或獨立復原通道處理。F5 本身不可達時只能記「狀態未知」，不能宣稱隔離成功。
- Agent 回線／主機重啟後先核對 journal、實際檔案／服務與 F5；不可自動重跑部署或直接回池。這是需實作的復原規格，不是 ADO 自動保證。

## 第一個 POC：由小到大，全部尚未執行

1. 確認 Express 2022 實際版本與 task/agent 相容；一台非正式 Windows、測試服務、已知良好 v1、候選 v2，先不連正式 F5。
2. ADO importer 保存 Build Artifacts；核准前／拒絕時查 Target 無候選檔案，核准後核對指定 build/hash；artifact 過期即失敗、不改抓 latest。
3. 完成單機 stop → backup → deploy → start → health；注入 copy／啟動／健康失敗，驗證舊版可恢復且 Release 仍 failed；無有效備份不得覆寫。
4. 接上測試 F5 與管理側控制器，測隔離／drain、rollback 後健康才回池、錯 member 拒絕、token 過期、API timeout 後對帳；Agent 無 F5 秘密。
5. 測 task failed、PowerShell 被殺、Agent 停止、取消、斷網／斷電；確認哪些 recovery task 有跑，哪些須獨立處置，不用 happy path 推論災難復原。
6. 才加入第二台與分開 stage；第一台部署或復原失敗／狀態未知時第二台不得換版。測實際 Classic rolling 排程；若不滿足 fail-stop，即採單目標編排，未通過前不擴至數十台。

## 官方來源

[1]: https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-2022
[2]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-group-phases?view=azure-devops-2022
[3]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/artifacts?view=azure-devops-2022
[4]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022
[5]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/download-build-artifacts-v0?view=azure-pipelines-2022
[6]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/powershell-v2?view=azure-pipelines-2022
[7]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/tasks?view=azure-devops-2022&tabs=classic
[8]: https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-2022
[9]: https://clouddocs.f5.com/api/icontrol-rest/APIRef_tm_ltm_pool_members.html
[10]: https://techdocs.f5.com/en-us/bigiq-8-0-0/monitoring-managing-applications-using-big-iq/monitoring-application-services/identify-app-issues-require-mitigation-appadmin/mitigating-traffic-performance-issues/solve-performance-problem-from-pool-member-issues.html
[11]: https://clouddocs.f5.com/products/extensions/f5-appsvcs-extension/latest/userguide/authentication.html

[1] [Express][1] · [2] [Classic target jobs][2] · [3] [Artifact versions][3] · [4] [Approvals][4] · [5] [Build Artifact download][5] · [6] [PowerShell task][6] · [7] [Classic failure conditions][7] · [8] [Agent／取消][8] · [9] [F5 member REST][9] · [10] [F5 流量狀態][10] · [11] [F5 認證][11]

證據限制：[9] 雖為 F5 官方網域，頁尾明示 API reference 含社群貢獻內容；[10] 為 BIG-IQ 文件，其 Force Offline 段落也有 persistence 措辭歧義，不據此保證 drain 行為。實際 BIG-IP 型號／版本、授權及連線行為仍以對應版本文件與封閉測試確認。
