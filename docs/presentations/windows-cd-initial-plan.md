# Windows 正式部署治理計劃
> 保留 GitLab 建置，讓正式換版由授權部門掌握

## Azure DevOps Server 導入提案
- Express 作為 POC 起點｜正式版本另行確認
- 跨部門討論稿｜目標 12/31，時程待共同確認

<!-- notes
共 7 頁：封面、議程、5 頁內容（包含最後的建議時程），無附錄。僅討論 Azure DevOps Server；Express 是 POC 起點，不代表最終採購決策。保留 GitLab CE 作版本控制與 CI。其他部門已有 ADO 運行先例，是使用者提供的背景，不是本案整合或合規已通過的證據。12/31 年份未指定，不自行補年份。產品能力依官方文件查證，尚未完成本架構的實機驗證。
-->

---

# 今天看五件事：原因、架構、環境、換版與時程
> 先對齊責任邊界，再確認如何導入

## 為什麼改
- 01｜正式主機存取限制
- 02｜建置到部署的完整架構

## 如何運作
- 03｜三分支、三環境
- 04｜授權換版與失敗復原

## 如何落地
- 05｜POC 到正式上線
- 以 12/31 為目標倒排里程碑

<!-- notes
先交代開發端直接送檔的方案為何不可行，再用同一張完整架構圖依編號說明。為守住總共 7 頁，不增加重複圖頁或動畫頁；第 4 頁上半部以 ①～⑧ 說明交付架構，下半部展開單台換版與復原。圖的組織區域、人員與工具分開呈現，詳細閱讀可放大獨立 PDF／draw.io。
-->

---

# 只送檔、不換版，仍然越過正式主機存取邊界
> 原方案已否決：建置端不能直接碰正式主機

```mermaid
flowchart LR
%% @name production-boundary
%% @lane dev 0 0 420 260
%% @lane prod 465 0 415 260
subgraph dev["開發部門：建置候選版本"]
 A["開發人員<br/>提交程式碼"]
 B["GitLab Runner<br/>建置／測試"]
end
subgraph prod["正式環境：僅指定部門可存取"]
 C["Production 主機<br/>送檔也算存取"]
end
%% @node A 20 95 170 80
%% @node B 225 95 175 80
%% @node C 555 95 295 80
%% @label B C 403 55 155
A --> B
B -.->|"禁止直接送檔"| C
class A control
class C blocked
classDef control fill:#FFF1DA,color:#80501F,stroke:#C57227
classDef blocked fill:#FCE8E6,color:#A63030,stroke:#A63030
```

## 改變方向
- 保留建置自動化；檔案送入正式主機與換版，都改由授權流程執行。

<!-- notes
本頁合併舊版第 2、3 頁。只送檔、不執行換版的提案已被否決，原因是正式主機僅允許指定部門存取，複製檔案也屬存取；不是技術做不到，也不是宣稱 GitLab CE 沒有權限控制。虛線代表禁止路徑。現有 Container 鏈 GitLab → Harbor → Argo CD → OCP／Docker 可作責任分工類比，本案補上 Windows 的受控部署流程，不要求使用相同工具。建置端不能透過共用目錄、帳號或中繼腳本繞過 Production 邊界。
-->

---

# Windows 正式部署：從提交程式碼到多機換版與復原
> 放行指定版本後才部署；健康才恢復 F5 流量，復原失敗保持隔離

![Windows 正式部署端到端架構：開發人員提交 GitLab，Runner 建置測試；成功後透過串接通知 ADO，管理側下載並保存可選版本，部署人員選版、選目標並放行，由多台 Windows Target 的 Agent 執行；下方展開 F5 換版與復原流程。](diagrams/windows-deployment-map.png)

<!-- notes
本頁管理區改以三段關係說明：「成功通知 → 取得並保存版本 → 人員選版／選目標、確認放行」。這是簡化的業務流程視圖，不是取消中間串接元件；ADO 管理側包含受保護接收器及管理 Build Agent，不能將平台標題誤讀成全部由 ADO Server 本機執行或已有原生 GitLab 直連。技術細節保留於以下備註及研究文件，不要求所有聽眾理解 API、Importer 或 hash。
本頁 v0.7 改為完整架構圖圖片，PPTX 中是高解析圖片，可編輯節點、容器與連線的原檔為 docs/presentations/diagrams/windows-deployment-map.drawio；獨立 PDF 可放大閱讀。圖內主架構與單台換版流程是兩個明確分隔的視圖，不是假裝一張純網路拓樸。圖面研究見 docs/research/end-to-end-architecture-diagram-design.md。
使用者確認：替換第 4 頁；「下 F5／上 F5」分別表示將目標服務退出／恢復負載平衡流量。具體 pool/member、Disabled 或 Forced Offline、連線等待／逾時、F5 操作位置與身分仍待網路及主機團隊確認。不能從圖推論每台 Agent 持有 F5 管理權；實作時需接上受保護、可稽核的維護操作。F5 流量線指向應用，不是 Agent；一台主機可能有多個 pool members，須確認完整範圍。
上半部是交付架構：開發人員 push GitLab CE；GitLab 編排 CI，GitLab Runner 建置／測試並上傳 artifact。GitLab pipeline 成功事件通知受保護接收器，接收器驗證、耐久入列、API 複核後，以 Queue Build REST API 排入固定 importer。接收器與驗證／去重邏輯需實作，不是原生 GitLab artifact connector，也不需要新增 GitLab Runner。
ADO 管理區的 self-hosted Build Agent 重驗專案、pipeline、ref、SHA 與必要品質 jobs，按確切 project/pipeline/job ID 下載 GitLab 產物，驗 ZIP／hash 並保存 manifest，以 PublishBuildArtifacts@1 發布 Server Build Artifacts。不能抓 latest 或使用 Services-only Pipeline Artifacts。GitLab 唯讀憑證只留管理區；管理 Agent、接收器和 CI 都無 Production 存取權。
ADO 全名 Azure DevOps Server；Express 為 POC 起點，Server 2022／REST 7.0 作文件基線。ADO 控制面、版本庫、管理 Agent 是邏輯元件，不等於必須各有一台 VM。這是文件支持的目標設計，不是現況或實機測通的證明。
Production 關閉 artifact 自動 release trigger，授權人員選確切 importer build、應用與目標建立 Classic Release，stage 設 Manual only 與具名 pre-deployment approval；允許同一人發起與放行。任何版本／目標變更須重新放行。SIT/UAT 的三分支分流留下一頁說明。
放行後，各 Windows Target 上的專用 Deployment Group Agent 才取指定工作與產物，在本機執行受保護的部署腳本。Agent 主動連 ADO 取工作；派工箭頭不代表 Server 主動登入 Windows。放行前不得預拷，包含 Production Agent 工作目錄。管理 Agent 與目標 Agent 必須隔離帳號、pool／Deployment Group、主機與憑證，不能執行開發者提供的特權部署腳本。
Production 圖示 01、02、…、N，可涵蓋數十台主機；不代表所有主機同時換版，也不是 Agent 互相傳檔。暫建議逐台或受控分批，健康後繼續，任一失敗停止後續目標；批次大小、最低容量、先前成功目標是否回復仍待確認。不承諾零停機或跨主機原子交易。
下半部更新為白話版並統一使用 ①～⑧ 圈號：① 取得已放行版本 → ② 下 F5 → ③ 停止服務 → ④ 備份舊版本 → ⑤ 安裝新版本 → ⑥ 重啟服務 → ⑦ 服務正常？ → ⑧ 上 F5。失敗路徑是還原舊版本、重啟與再檢查；成功恢復後仍記本次換版失敗。原本的鎖、前置閘門、有效備份、流量狀態核對與例外要求仍需實作，僅不放進主流程的長標籤。Agent／主機失聯不是同一個 Agent 能保證自動復原的情況，須另有監控及受控人工／獨立復原手段。
下半部對每個核准目標重複：放行後下載／驗證、部署鎖與前置檢查 → 下 F5 並確認流量隔離條件 → 停止服務 → 備份目前版本 → 執行換版 → 重啟服務 → 檢查狀態。正常才上 F5，確認恢復成功後記錄新版本完成。
換版、啟動或健康檢查失敗時，保持隔離，依受控腳本停止失敗版本、回復有效備份、重啟，再做復原健康檢查；正常才上 F5 並記錄「換版失敗、復原成功」，不能記為新版本部署成功。復原不健康或無可用備份時，保持隔離、停止後續換版、告警並交人員處理。
下 F5／隔離確認失敗時不能繼續停止服務；停止或備份失敗時不能覆寫版本，由受控復原／人工程序決定後續。上 F5 操作或確認失敗不能算完成。檔案備份不等於資料庫回復，資料相容與復原另行設計。服務停止／重啟需依 IIS／Windows Service 細化。備份與復原腳本必須演練，ADO／Agent 不自動提供完整應用復原。
安全與可靠性驗收：測試 PAT／definition ACL／群組繼承、queue 參數與來源覆寫、build service／OS 身分、特權腳本保護；測試事件偽造、重送、晚到舊版本、Queue 回應遺失、產物到期、零預拷、拒絕或復原失敗時不恢復流量。版本、人員、目標、hash 與結果可追溯。
完整串接依據：docs/research/gitlab-ado-event-trigger.md。
換版／復原可行性查核：docs/research/windows-release-recovery-feasibility.md。官方支援核准、指定 Build Artifact、Deployment Group 與 PowerShell／失敗條件，但不內建本案完整 rollback。POC 建議受保護 PowerShell 控制腳本換版失敗時嘗試復原，復原成功也保留原部署 failed；不要在 finally 無條件上 F5。Agent／主機失聯時需獨立監控及復原手段。限制同時部署比例不等於保證失敗停止所有後續主機；初期採單台 canary，下一台另設成功相依／人工放行，正式 fail-stop 需驗證或受控編排。匯入完成後，部署與退版不必再回 GitLab 取 latest。上述為文件查證，未完成實機 POC。
https://c4model.com/diagrams/notation
https://learn.microsoft.com/en-us/azure/well-architected/architect-role/design-diagrams
https://docs.gitlab.com/user/project/integrations/webhook_events/#pipeline-events
https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-rest-7.0
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-2022
https://techdocs.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/big-ip-local-traffic-management-basics-14-0-0/05.html
-->

---

# 三分支各自建置；正式環境多一道人工放行
> master → SIT；pre-production → UAT；production → Production

```mermaid
flowchart LR
%% @name environment-approval
 A["GitLab CI<br/>建置固定版本"]
 B{"來源分支<br/>驗證與分流"}
 C["master → SIT<br/>匯入後自動換版"]
 D["pre-production → UAT<br/>匯入後自動換版"]
 E["production<br/>部署人員選版放行"]
 F["正式主機<br/>執行換版"]
%% @node A 0 90 195 85
%% @node B 250 85 190 95
%% @node C 555 0 325 75
%% @node D 555 95 325 75
%% @node E 505 190 215 80
%% @node F 760 190 120 80
%% @route B C 480 132 480 37
%% @route B E 460 132 460 230
A --> B
B --> C
B --> D
B --> E
E --> F
class C,D,F target
class E control
classDef control fill:#FFF1DA,color:#80501F,stroke:#C57227
classDef target fill:#087F8C,color:#ffffff,stroke:#087F8C
```

## 分流原則
- 成功通知不是正式放行；正式放行綁定確切版本與目標。

<!-- notes
保留舊版第 5 頁的三分支映射。三個分支各自建置，不主張同一份內容由 UAT 晉升 Production。接收器與 importer 用 GitLab API 複核固定專案、精確 ref、pipeline source=push、非 tag、SHA、成功狀態與必要 jobs，再路由到三組固定 importer＋單環境 Classic Release。Webhook 與 queue 參數只是提示，不是可信任的環境判斷。
ADO importer 儲存串接程式的 repository branch（例如 main）不等於 GitLab 來源分支；不得以 ADO Build.SourceBranch 或原生 build branch filter 推論來源環境。SIT/UAT 自動觸發，Production 關閉 artifact 自動 release trigger，授權人員選固定 importer build 建立 release、手動 stage 並通過 pre-deployment approval。開發者不能編輯部署定義、批准者或 Agent 資源繞過控制；只限制手動 Deploy 按鈕並不足夠。單人放行並執行符合目前需求。
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-2022
https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022
-->

---

# 放行後才送入正式主機，換版失敗須能復原
> 固定版本 → 準備檔案 → 切換 → 健康檢查 → 留存結果

```mermaid
flowchart LR
%% @name release-lifecycle
 A["部署人員<br/>選版並放行"]
 B["Agent 取檔<br/>驗證版本內容"]
 C["執行換版<br/>切換程式版本"]
 D{"健康檢查<br/>是否正常？"}
 E["換版完成<br/>留存執行紀錄"]
 F["回復前一版本<br/>檢查復原結果"]
%% @node A 0 40 180 90
%% @node B 220 40 180 90
%% @node C 440 40 180 90
%% @node D 690 35 190 100
%% @node E 715 200 165 70
%% @node F 440 200 220 70
%% @ports D F bottom top
%% @route D F 785 170 550 170
%% @label D E 797 153 75
%% @label D F 588 138 90
A --> B
B --> C
C --> D
D -->|"正常"| E
D -->|"異常"| F
class A control
class E target
class F blocked
classDef control fill:#FFF1DA,color:#80501F,stroke:#C57227
classDef target fill:#087F8C,color:#ffffff,stroke:#087F8C
classDef blocked fill:#FCE8E6,color:#A63030,stroke:#A63030
```

## 執行原則
- 每台主機由部署 Agent 執行受控腳本；記錄人員、版本、目標與結果。

<!-- notes
本頁是換版與復原概覽；完整的下 F5、停服務、備份、換版、重啟、健康檢查、恢復流量及復原失敗分支已展開於第 4 頁。復原健康才回池，復原成功仍屬換版失敗，不記新版本部署完成。保留並調整舊版第 9 頁。放行前產物只在管理區保存，不能預拷到 Production（包含 Agent 工作目錄）；放行後部署 Agent 取固定 importer build 的 artifact，重新核對內容 hash，保存目前版本與復原資料，再依 IIS／Windows Service 的需求停止或切換、套用環境設定、啟動及健康驗證。不承諾零停機或跨主機原子交易。
換版或健康檢查失敗時，依事先驗證的腳本回復前一可用版本並檢查；復原失敗則停止並通知負責人，不能記為成功。資料庫／資料格式變更須另設相容與資料復原方案，不能把回復程式檔案等同資料回滾。多台逐台執行、失敗停止後續換版，是否回復已成功目標由授權人員依既定程序決定。部署鎖避免同一目標衝突，晚到舊版本不可自動降版；顯式授權的回復另留紀錄。Agent 與 ADO 不會自動提供應用程式專用的復原，腳本、資料保留及演練必須實作。
-->

---

# 建議以 12/31 為目標，逐關驗證後再正式上線
> 暫定里程碑順序；各階段日期與資源由相關部門共同確認

```mermaid
flowchart LR
%% @name proposed-timeline
 A["01｜POC<br/>驗證通知與權限"]
 B["02｜協調架構部門<br/>安裝／配置 ADO"]
 C["03｜整合 GitLab<br/>串接通知與產物"]
 D["04｜SIT<br/>整合與例外測試"]
 E["05｜UAT<br/>驗收與復原演練"]
 F["06｜Production<br/>目標 12/31"]
%% @node A 0 15 260 90
%% @node B 310 15 260 90
%% @node C 620 15 260 90
%% @node D 620 175 260 90
%% @node E 310 175 260 90
%% @node F 0 175 260 90
A --> B
B --> C
C --> D
D --> E
E --> F
class F target
classDef target fill:#087F8C,color:#ffffff,stroke:#087F8C
```

## 上線門檻
- POC 先證明「未放行不能送檔」；驗收與復原演練通過後，才申請正式上線。

<!-- notes
依使用者授權提出暫定階段，不是跨部門承諾。截止目標是 12/31，年份未指定，階段起迄日、工期、資源與正式核准均待共同確認。若必要驗收未通過，應調整範圍／資源或重新協調時程，不能因日期目標繞過上線門檻。
01 POC：使用隔離的 Express 評估環境，驗證 success webhook、受控 importer、最小 ACL、Production 零預拷、三分支分流與失敗復原。此處先使用評估環境，02 才與主機／Server 團隊（架構部門）協調受管理的 ADO 安裝，不暗示尚未安裝就可跑 POC。
02 協調：確認架構、主機、網路／TLS、服務帳號、管理責任、備份與監控；Express 僅為 POC 起點，正式版本另行確認。
03 整合：完成受保護接收器、管理 Agent、固定 importer／Release、目標 Agents、產物保留與稽核串接。
04 SIT：三環境路由、偽造事件拒絕、重送／亂序／中斷復原、版本一致性與權限負向測試。
05 UAT：由授權部署人員驗收選版放行、操作紀錄與實際應用的回復演練。
06 Production：依組織程序取得上線批准，先試辦再觀察；目標 12/31，不代表目前已批准。所有詳細 go/no-go 條件見 docs/research/gitlab-ado-event-trigger.md。
-->
