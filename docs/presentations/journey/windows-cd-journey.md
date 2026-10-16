# 從程式建置到受控部署 建立可追蹤的換版流程
> GitLab 建置  →  Azure DevOps Server 管理放行

## Windows 自動化部署實作計畫
- 正式換版，由授權部門掌握。
- 建置候選版本
- 選版與授權
- 受控換版
- Express 作為 POC 起點
- 預計 12/28 前完成

<!-- notes
本版依使用者手改 PPT 精簡為 6 頁：封面、預期效益、端到端目標架構、分支與環境、換版與復原、預計行程。議程、獨立存取邊界頁與需求狀態頁不再放入簡報，並非取消其治理要求。原版與先前九頁版本另行保留。
標題依手改版採「Windows 自動化部署實作計畫」。尚未完成本案實作或 POC 驗證；官方文件支持工具能力，不代表本架構已完成整合、通過合規或獲上線批准。保留 GitLab CE 作版本控制與 CI；Azure DevOps Server 負責部署管理，Express 只是 POC 起點，正式版本另行確認。
使用者在手改 PPT 將完成目標由 12/31 調整為 12/28，本版據此同步，年份仍未指定，不自行補年份。12/28 是本輪導入／正式試辦的預計完成目標，不是「後續發展」中所有專案串接的截止日；各階段日期、資源與正式批准仍需跨部門共同確認。
POC 與跨部門討論的暫定區間為 10/12 ~ 10/23；此為行程規劃，不表示 POC 已完成。其他部門已有 ADO 運行先例是討論背景，不是本案整合或合規已通過的證據。
-->

---

# 讓換版不再每次重新摸索
> 完成導入並通過驗收後，預期帶來三項改善

## 維運更一致
- 一致流程，少搬檔、少漏步。
- 人員、時間、主機與版本可追查。

## 降低操作風險
- 版本與目標綁定放行。
- 備份與復原演練，降低失敗影響。

## 複用到其他專案
- 留下治理與操作範本。
- 各專案的服務與復原方式，仍需個別驗證。

<!-- notes
本頁為預期效益，不是已達成的成果；目前沒有導入前後量測數據，不承諾節省比例、復原時間或零停機。POC／試辦時記錄人工步驟、換版耗時、版本追查所需時間與復原演練結果，再與既有流程比較。
備份與復原需實作及演練，不能因採用 ADO／Agent 就視為風險已消除。可複用的是治理與操作框架，不是將同一套腳本直接套用所有 Windows 專案；IIS／Windows Service、設定、資料相容及 F5 範圍須個別確認。
-->

---

# 從程式碼出發，在放行後抵達正式環境
> 端到端目標架構／待 POC：建置、版本管理與正式部署，各自守住責任邊界。

## 開發／CI 區
- 開發人員｜提交程式碼
- GitLab CE
- 版本控制／CI 編排
- Runner 建置／測試
- 產物留存於 GitLab

## 授權部門管理區
- Azure DevOps Server
- 接收成功通知
- 驗證後啟動匯入
- 下載並保存版本
- 管理 Build Agent
- 部署人員
- 選版＋應用／目標
- 確認授權放行
- 放行才部署
- 指定版本／指定目標
- 放行後取指定版本

## Production
- Windows Targets｜01 … N
- 每台主機的部署 Agent
- 各主機的應用服務
- F5｜應用流量
- Agent 主動連 ADO 取得換版檔案

<!-- notes
第 3 頁只呈現端到端交付與權限分工；單機換版、人工功能確認與復原集中於第 5 頁，不在架構頁重複。依手改版移除圖面說明行與底部圖例／安全提示文字，但虛線、版本產物實線及 F5 應用流量線的語意與治理要求不變。三個分區是責任邊界，不代表已驗證網段、ACL 或固定的 VM 配置。
建置端與管理側均不能直接存取正式主機；只送檔也算正式環境存取。放行前不得預拷，包含 Production Agent 工作目錄；不能用共用目錄、帳號或中繼腳本繞過邊界。
管理區以「收到成功通知 → 取得並保存版本 → 人員選版／選目標、確認放行」說明。實際包含受保護接收器、管理 Build Agent、固定 importer、Server Build Artifacts 與 Classic Release，並非全部由 ADO Server 本機執行，也不是原生 GitLab artifact connector。
開發人員 push GitLab CE；GitLab 編排 CI，Runner 建置／測試並上傳 job artifact。Pipeline 成功事件通知受保護接收器；接收器須驗證、耐久入列、去重與 API 複核，再以 Queue Build REST API 排入固定 importer。通知不是部署放行，建置成功不會直接部署 Production。
管理區 self-hosted Build Agent 重驗 project、pipeline、精確 ref、SHA 與必要品質 jobs，按確切 project/pipeline/job ID 下載 GitLab 產物，驗 ZIP／hash、保存 manifest，並以 PublishBuildArtifacts@1 發布 Server Build Artifacts；不能抓 latest 或使用 Services-only Pipeline Artifacts。GitLab 唯讀憑證只留管理區。接收器與管理 Agent 均無 Production 存取權。
Azure DevOps Server 2022／REST 7.0 為文件基線，Express 為 POC 起點。Production 關閉 artifact 自動 release trigger；授權部署人員選確切 importer build、應用與目標建立 Classic Release，stage 設 Manual only 與具名 pre-deployment approval，允許同一人發起與放行，不要求雙人審批。版本或目標變更須重新放行。
各 Windows Target 上的專用 Deployment Group Agent 主動連 ADO，放行後才取指定工作與版本，在本機執行受保護部署腳本。圖面「取得換版檔案」是白話摘要，不是只需取檔、不需授權工作。派工及產物箭頭是邏輯語意，不代表 ADO 或管理 Agent 主動登入正式主機。管理與目標 Agents 須隔離帳號、pool／Deployment Group、主機與憑證；不能執行開發者提供的特權部署腳本。
堆疊 Windows 卡片代表每台各自有專用 Agent 的多台主機，不是集中代部署主機，也不是主機互傳檔案。01 … N 可涵蓋數十台，不代表同時部署。暫建議逐台或受控分批、健康後繼續、失敗停止後續；批次、最低容量與已成功目標是否回復仍待確認。限制同時部署比例不等於保證 fail-stop，需實測或受控編排。
F5 流量線連到應用服務，不是 Agent。下／上 F5 表示退出／恢復負載平衡流量；pool/member、Disabled／Forced Offline、連線等待與逾時、控制身分與操作位置待網路及主機團隊確認。不預設每台 Agent 持有 F5 管理憑證。
通知驗證、受保護匯入、可靠交接、權限、特權腳本、備份、健康檢查、人工等待與復原均需實作及驗證。POC 須測偽造事件、重送、亂序、Queue 回應遺失、來源覆寫、產物到期、有效 ACL、零預拷、失聯與拒絕／逾時不回池；保留人員、版本、目標、hash 與結果證據。
串接依據：docs/research/gitlab-ado-event-trigger.md。
換版／復原查核：docs/research/windows-release-recovery-feasibility.md。
原始完整架構仍保留於 docs/presentations/diagrams/windows-deployment-map.drawio／PNG／PDF，並非本版的重建來源。第 1～5 頁的原生物件版型以 inputs/windows-cd-journey-manual-six.pptx 為手改快照，重建不會覆寫使用者正在編輯的 PPTX。
https://docs.gitlab.com/user/project/integrations/webhook_events/#pipeline-events
https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-rest-7.0
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-2022
https://techdocs.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/big-ip-local-traffic-management-basics-14-0-0/05.html
-->

---

# 不同 branch，各走合適的部署路線
> 規劃示意／待 POC：各分支各自建置；正式部署仍須授權。

## master
- 符合條件自動觸發
- Azure DevOps Server + Agent
- SIT

## pre-production
- 符合條件自動觸發
- Azure DevOps Server + Agent
- UAT

## production / production-bq1 production-bq2 / production-nh …
- 選版＋選目標
- 授權放行
- Azure DevOps Server + Agent
- 依目標採不同換版策略
- Production

<!-- notes
第 4 頁沿用使用者手改的精簡分支標示。production、production-bq1、production-bq2、production-nh 是平行分支示例，不是 Git 子分支，不推定名稱所代表的地點。來源允許清單必須精確，不將任何 production 前綴自動視為已授權。
各分支各自建置，不宣稱同一份產物跨環境晉升。正式分支合併顯示不代表共用同一 pipeline；建置、測試、產物、目標集合、逐台／分批、F5／服務操作與復原方式可不同，實際映射待共同確認。不要求每分支獨立 YAML。
邏輯流程不宣稱 GitLab 原生編排 ADO。擴充分支須同步調整精確來源允許清單與受保護的目標／策略映射；API 複核專案、精確 ref、pipeline source、SHA 與必要 jobs，不信任事件或參數自稱的環境。ADO importer 程式庫的 main 等分支不等於 GitLab 來源分支，不能以 ADO Build.SourceBranch 或原生 branch filter 推論來源環境。
SIT／UAT 可符合條件自動觸發；Production 關閉 artifact 自動 release trigger，由授權人員選定確切 importer build、應用與目標建立 release、手動 stage 並通過 pre-deployment approval。單人放行並執行符合需求；開發者不能編輯部署定義、批准者或 Agent 資源繞過控制，只限制 Deploy 按鈕並不足夠。
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-2022
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022
-->

---

# 放行後才送檔，流量恢復前再確認
> 規劃／待 POC：Agent、備份、人工等待與復原腳本均須實作及演練。

## 人員選版／目標
- 授權放行
- Agent 取檔驗證
- 下 F5，確認隔離
- 停止、備份
- 安裝新版並重啟
- 健康檢查正常
- 人工確認功能
- 上 F5 並確認
- 換版完成、留紀錄
- 換版／啟動／檢查／新版功能驗證失敗
- 保持隔離 → 還原舊版 → 再檢查
- 舊版健康且人工確認，才可上 F5。復原成功仍記為「換版失敗」。
- 未確認、逾時或復原失敗：不恢復流量
- 停止後續目標並通知；主機失聯另需復原手段。

<!-- notes
第 5 頁集中呈現單機換版與復原，第 3 頁只保留端到端交付架構。順序是選定版本／應用／目標並放行 → Agent 取檔與內容核對 → 下 F5、確認流量隔離 → 停止服務 → 有效備份 → 安裝新版 → 重啟服務／排程 → 自動健康檢查 → 部署人員在隔離狀態驗證功能、人工確認 → 上 F5 並確認流量恢復，最後才記錄新版本完成。
放行前產物只在管理區保存，不能預拷到 Production，包含 Agent 工作目錄。放行後取固定 importer build 的 artifact，重驗 hash，保存目前版本與復原資料；服務操作與設定依 IIS／Windows Service 個別細化，不承諾零停機或跨主機原子交易。
初始 Release 的部署前核准不能代替中途人工功能關卡。必須設計 Classic 支援的強制等待／分階段核准或受控外部編排，並驗證通過、拒絕、逾時、Agent 失聯與回線對帳。人工決定綁定 release、target、版本與本次檢查結果；等待期間保持隔離與部署鎖，不能因逾時自動同意，也不為測試預先上 F5。隔離測試入口與驗證項目仍待確認。
換版、啟動、健康檢查或新版功能驗證失敗時，保持隔離，依已演練受控腳本停止失敗服務、還原有效舊版備份、重啟並再次健康檢查。舊版須另一次人工功能確認，不能沿用新版確認；健康且人工確認後才恢復流量，仍記「換版失敗、舊版服務已恢復」，不能記新版本部署成功。復原不健康、無有效備份或舊版功能不通過，保持隔離、停止後續目標並通知。
下 F5／隔離確認失敗時不繼續停服務；停止或備份失敗不得覆寫版本。未確認、拒絕、逾時均不恢復流量；上 F5 操作或確認失敗不能結案，不能在 finally 無條件上 F5。
主機／Agent 失聯不是同一 Agent 可保證自動復原的情況，需獨立監控及受控人工／獨立復原手段。逐台或受控分批需驗證失敗停止，已成功目標是否回復依授權程序。部署鎖避免衝突，晚到舊版本不可自動降版；顯式授權退版另留紀錄。檔案復原不等於資料庫或資料回滾，資料相容與復原須另設計。
ADO／Agent 不內建本案完整應用 rollback；備份、健康檢查、F5 操作、人工等待及復原腳本均須實作與演練。詳細查核見 docs/research/windows-release-recovery-feasibility.md。
-->

---

# 從第一個 POC，走向受控的正式上線
> 暫定里程碑順序；階段日期、資源與上線批准，待相關部門共同確認。

## 預計行程
- POC & 跨部門討論｜(10/12 ~ 10/23)｜驗證架構可行性
- 協調架構部門｜安裝／配置 Azure DevOps
- 串接 CI/CD Pipeline｜以 雷影 系統為首發驗證標的
- SIT & UAT 驗測｜整合與例外測試
- Production 正式環境｜依程序取得核准後試辦上線
- 後續發展｜陸續串接其他專案｜實現可複製的自動化換版

<!-- notes
本頁以使用者手改的六站行程為準；保持起伏路線，只微調圖示、符號與配色。圖示依序為跨部門討論、主機與配置、Pipeline 串接、雙項檢核、正式試辦旗幟及多專案擴展。色彩表示階段分組，不代表已完成或已核准；擴展段以不同線型區別後續範圍，不新增工期或完成承諾。
使用者將本輪導入預計完成目標調整為 12/28，年份未指定。除 POC & 跨部門討論的 10/12 ~ 10/23 外，不自行補其他階段日期。階段起迄、工期、資源、正式版本及上線批准需跨部門確認；必要驗收未通過時調整範圍／資源或時程，不因日期目標繞過門檻。
01 POC & 跨部門討論（10/12 ~ 10/23）：先使用隔離 Express 評估環境，驗證架構可行性、通知與受控匯入、最小權限、正式環境零預拷及失敗復原。此區間是暫定行程，不是完成證據。
02 協調架構部門：確認主機、網路／TLS、帳號、權限、管理責任、備份監控及資源，再安裝／配置受管理 Azure DevOps Server。Express 只是 POC 起點，不預定正式採購版本。
03 串接 CI/CD Pipeline：以「雷影」系統為首發驗證標的，完成受保護接收器、管理 Build Agent、固定 importer／Release、目標 Agents、產物保留與稽核。首發標的不代表架構或應用已驗證。
04 SIT & UAT 驗測：依手改版將 SIT 與 UAT 合併為一站，仍包含各自的整合／例外／權限負向測試、授權部署人員驗收、人工功能確認與復原演練，不取消其中任何門檻。驗證路由、事件偽造、重送／亂序／中斷、版本與授權一致性、失聯、拒絕／逾時不恢復流量等。
05 Production 正式環境：驗收與復原演練通過後，依組織程序取得核准再試辦上線；本輪預計 12/28 前完成，不表示已獲批准，不承諾零停機。
06 後續發展：陸續串接其他 Windows 專案，複用權限、交付、放行與紀錄模式；各專案的服務、F5、資料相容與復原仍需個別驗證。本階段未指定截止日期，不包含在 12/28 全部完成承諾內。
完整 go/no-go 依據：docs/research/gitlab-ado-event-trigger.md。
-->
