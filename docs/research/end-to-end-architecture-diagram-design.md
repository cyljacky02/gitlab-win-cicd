# Windows 端到端部署架構圖：設計研究與重畫準則

> 研究後確認：使用者指定替換第 4 頁，並確認下／上 F5 表示退出／恢復負載平衡流量。操作模式與控制身分仍未定。已依研究建立 [可編輯主圖](../presentations/diagrams/windows-deployment-map.drawio)；下文研究建議不等於每項均已實作（例如主圖採容器，未另拆多個圖層）。

## 結論與範圍

**建議：一份可編輯的寬版 `.drawio` 主圖，上半部呈現分區架構與編號交接，下半部展開「任一 Windows Target」的完整換版／復原流程。** 用同一來源輸出完整技術版與可讀的簡報總覽，不讓既有 slide renderer 或 Mermaid 座標限制設計。
本文件只研究，不產生圖檔、不修改簡報或 renderer。既有架構依據：[提案](../presentations/windows-cd-initial-plan.md)、[事件交接研究](gitlab-ado-event-trigger.md)；F5 步驟是待確認的擴充設計，不是既有實作。
以下「官方事實」指文件明載能力／準則；「建議」是本案設計選擇；「待確認」不能畫成已部署或已驗證功能。

## 什麼叫好的架構圖，而非塞滿資訊的「完美圖」？

- **官方事實：** C4 不規定特定繪圖符號，但要求圖能大致獨立理解；標題要交代圖型與範圍，圖例解釋形狀、顏色、框線及箭頭，節點交代型別、責任與適用技術。[C1]
- **官方事實：** 每條關係應為單向、標示具體意圖，標籤須與方向一致；跨程序關係應標技術／協定。C4 checklist 要求讀者能理解每個元素名稱、型別、用途及視覺語意。[C1][C2]
- **官方事實：** C4 的四層是靜態結構的不同縮放層級，不必全部使用；不同受眾需要不同故事。[C3]
- **官方事實：** Microsoft 建議依受眾與問題選圖，逐層揭露而非過載；維持準確性、單向箭頭、標籤、圖例、版本資訊及可及性，不能只靠顏色傳意。[M1]
- **建議：** 本案的品質標準是讀者能回答「誰做、在哪做、交付什麼、誰放行、失敗去哪」，不是產品 logo 數量或能否把所有細節縮進一頁。
- **官方事實／限制：** AWS 官方圖示頁提供架構／部署／拓樸溝通素材，提醒第三方工具圖庫可能過時；這不是一套可證明架構正確的完整標準。本案沒有 AWS 元件，不為裝飾加入 AWS 圖示。[A1]

## 分清四種問題，放在同一畫布但不要混成一種箭頭

| 視圖問題 | 本案應呈現 | 設計依據／限制 |
|---|---|---|
| 系統結構：有哪些角色與服務？ | 人員、GitLab CE、Runner、接收器、ADO、兩類 Agent、產物庫 | 以責任命名；邏輯元件不等於一台實體主機。[C1][M1] |
| 交接流程：什麼依序發生？ | ①～⑧ 主流程，區分控制事件與產物資料 | C4 dynamic 可用自由配置＋編號互動表示順序；編號不是 TCP 封包時序。[C4] |
| 部署位置：軟體在哪裡執行？ | 開發區、管理區、Production；每台 Windows 包含 Agent＋應用 | Deployment diagram 可嵌套部署節點並納入負載平衡器；責任區不能冒充已確認的 subnet／防火牆。[C5][M1] |
| 執行過程：成功、失敗、復原如何分支？ | 下方單機流程，明列健康判斷與終止狀態 | Flowchart 適合條件分支；嚴格呼叫時序才用 sequence diagram。[M1] |

**建議：** 主圖稱「Windows 正式部署端到端架構與換版流程（目標設計）」，不宣稱是純 C4 container diagram；它是有明確分隔的混合視圖。只聚焦 Production，SIT／UAT 分支映射留註記或既有文件，避免再複製三套流程。

## 一張寬圖的具體配置（建議，不是標準尺寸）

1. 以約 **2400 × 1400** 的可延伸畫布起稿，外框留白；標題列寫範圍、版本、更新日期及「待 POC 驗證」。不先縮到 16:9。
2. 上半部約 55% 高度分三欄：**開發／CI 區約 25% → 授權部門管理區約 40% → Production 約 35%**；區塊標示責任與存取規則，不用顏色暗示實體網段。
3. 人員放在各區頂部獨立角色列：左為開發者，中為授權部署人員。下方才是服務／主機；人員不畫進 Server 內。
4. 管理區將「ADO Server 控制面」「Build Artifacts 固定版本庫」「管理 Build Agent／importer」分成節點，避免誤認 Server 本身下載 GitLab 檔案或所有元件必須同機。
5. Production 放一個 **Deployment Group：N 台 Windows Targets** 容器，只畫 `Windows 01`、`Windows 02`、`…`、`Windows N`；每個代表節點含「Deployment Agent＋應用服務」。N 可為數十台，不複製數十套箭頭。
6. 用一條「授權工作／指定版本」關係進入 target 群組，再用群組內短分支表達套用到已核准目標；**群組箭頭不代表同時部署，也不代表某一 Agent 再派送其他主機**。
7. F5 放在 Production 的「應用流量」側，應用流量線連向應用而非 Agent；「F5 維護控制：執行身分／位置待確認」另設註記，不預設每台 Agent 都有 F5 管理權。
8. 下半部約 35% 是加框的「⑧ 單一 Target 換版流程，對各核准目標重複」，用放大參照線連至 target 群組；參照線不是資料流。
9. 底部約 10% 留給圖例、不可越過的限制、版本追溯及未決問題；長篇 ACL／API 參數留研究文件，不塞進節點。

## 上半部必須完整保留的編號交接

以下是**本案目標編排**，技術依據與待驗證限制詳見既有事件研究；並非宣稱所有整合已測通。

| 編號 | 箭頭／動作 | 必須看得出的意義 |
|---|---|---|
| ① | 開發人員 → GitLab CE：push | 程式碼來源；不是部署權限。 |
| ② | GitLab CE → Runner：CI 編排；Runner → GitLab：上傳產物 | Runner 執行建置／測試；成功後 artifact 存 GitLab。這是派工語意，不表示 Server 主動登入 Runner。 |
| ③ | GitLab → 受保護接收器：pipeline success webhook | 接收器驗證、耐久入列、去重及 API 複核；成功通知不等於 Production 放行。[G1] |
| ④ | 接收器 → ADO：排入固定 importer | Queue Build 是排程匯入，不是觸發正式部署；接收器為需實作元件。[M2] |
| ⑤ | 管理 Agent → GitLab：API 請求；GitLab → 管理 Agent：確切 job artifact | 分開標「請求」與「內容返回」；管理 Agent 下載、驗 ZIP／hash／來源 manifest，不碰正式主機。 |
| ⑥ | 管理 Agent → ADO Build Artifacts：發布固定 build 產物 | Server 使用 Build Artifacts；不替換為 Services-only Pipeline Artifacts，不抓 latest。[M3][M4] |
| ⑦ | 授權人員 → Production Classic Release：選版、目標、放行 | 關閉 Production artifact 自動 release trigger，Manual only＋部署前核准；匯入成功本身不能放行。[M5][M6] |
| ⑧ | Classic Release → Deployment Group：已授權工作；固定產物 → 各 target Agent | Agent 在各 Windows 本機換版；只在放行後下載指定版本。圖旁註記「Agent 主動連 ADO 取工作」，不是 Server 遠端登入。[M7][R1] |

**建議圖例：** 實線＋「資料」標籤＝程式碼／產物；虛線＋「控制」標籤＝通知／派工／授權；細點線＝放大參照；獨立標籤「應用流量」＝F5 到應用。每線單箭頭，不用同一條雙向線同時表示請求與回傳。
**建議安全註記：** CI／接收器／管理 Agent 無 Production 存取；放行前不得把候選檔案預拷至正式主機，包含 Agent 工作目錄。該限制須實測，不把圖上的邊界當成 ACL 已生效。[R1]

## 下半部：單一 Target 的完整生命週期（擬議流程）

入口先標「⑧ 已放行指定版本 → Agent 取檔／驗證 → 取得目標部署鎖／前置檢查」。以下主幹由左至右，復原分支放下一列，避免線條交叉。

**正常路徑：** `退出 F5 流量服務 → 確認隔離／既有連線處理條件達成 → 停止服務 → 備份目前版本 → 部署 → 啟動服務 → 健康檢查？ → 健康：恢復 F5 流量 → 確認恢復成功／留存結果`。
**失敗路徑：** `部署／啟動／健康檢查失敗 → 保持隔離 → 回復已驗證備份 → 重啟 → 復原健康檢查？`。
- 復原健康：才可恢復 F5 流量；結果標「部署失敗、復原成功」，**不是新版本部署成功**。
- 復原不健康／無有效備份／復原失敗：保持隔離、停止後續換版、告警並交人工處理；不可有繞過健康檢查的回池線。
- 隔離未成功／等待逾時：不得繼續停止服務；停止流程並告警。停止或備份失敗：不覆寫版本，保持隔離，由復原／人工程序確認健康後才恢復流量。
- 恢復 F5 流量操作或確認失敗：不得標記完成；告警並核對實際狀態，不假設控制請求成功就等於流量已恢復。
- 「停止服務」需依 IIS／Windows Service 實際型態細化；檔案復原不等於資料庫復原，資料相容性與資料回復另行設計。[R1]

**多機建議：** 群組註記「依核准清單逐台執行；失敗停止後續目標」，與既有提案一致；批次大小、最低剩餘容量、是否回復已成功主機另行確認。`01 → 02 → … → N` 代表編排順序，不是主機間傳檔。不得宣稱零停機或跨主機原子交易。[R1]

## F5：可以引用的概念，以及不能自行填補的假設

**官方事實（BIG-IP LTM 14.0 文件）：** pool member 是特定 node＋service（例如 IP:port），不是整台 Windows 的同義詞；停用一個 member 不代表該主機所有應用／pool 都已退出流量。[F1]

| 狀態 | 官方文件的概念行為 | 本圖應避免的誤讀 |
|---|---|---|
| Disabled | 仍處理 active 及 persistence 相關連線；既有 persistence session 可帶來新連線。 | 「Disable 後已沒有任何新請求」不成立。[F1] |
| Forced Offline | 不接受新連線，但容許既有 active connections 完成。 | 不是立即切斷所有連線，也不保證應用 session 已結束。[F1] |

**結論：** 圖上使用中性動作「退出 F5 流量服務／確認隔離條件」，不要寫死 Disabled 或 Forced Offline，更不產生命令。官方概念不能推論本案已配置自動 graceful drain、固定等待幾秒足夠或停服務必然不中斷使用者。[F1]
**待使用者／網路團隊確認：** BIG-IP 實際版本、目標 pool/member 對應、多服務／多 pool 範圍、persistence 與長連線、既有連線處理與等待上限、超時決策、應用及 F5 monitor 的健康門檻、回池判定、F5 操作的執行位置／權限及稽核方式。
**證據限制：** 已讀取 F5 官方 14.0 概念文件全文；MyF5 知識庫頁面受 JavaScript 載入限制，未把其搜尋摘要當作本案版本驗證。以上不代替實際設備配置確認。

## draw.io 可編輯性與輸出策略

- **官方事實：** draw.io 圖層可顯示／隱藏；連接線可跨圖層連結節點，但每個物件僅屬於一個圖層。把容器子元素移到其他層會使它離開原容器，不能假設群組內任意跨層仍保持包含關係。[D1]
- **官方事實：** container table 可容納形狀及連線，移動時一起帶走；cross-functional flowchart 可用橫縱泳道表達角色／分類。[D2][D3]
- **建議：** 原始 `.drawio` 保存真正文字、節點、容器與連接線，不以一張 PNG 冒充可編輯圖。圖層拆為「主架構」「交接線」「單機流程」「技術註記」，但每個容器與其子物件留同層；不同層的外框只作背景，不假稱父容器。
- **建議：** 完整版保留全部內容，供縮放閱讀；簡報總覽隱藏技術註記，保留三區、①～⑧、01／02／…／N 及「隔離→換版→健康才回池；失敗復原／告警」摘要。必要時用同源第二頁排版總覽，不強縮完整圖。
- **建議：** 在實際投影片尺寸驗收，主標籤以約 18–24 pt 可讀性為起點；仍不可讀就刪減總覽細節，而非繼續縮字。此數值是本案排版起點，不是官方保證。
- **建議驗收：** 不靠講者能辨識控制／資料流、兩種 Agent、授權門檻與多機關係；任何不健康出口皆無回池捷徑；編輯節點後線仍相連；黑白與投影可辨識；圖上待確認內容未冒充已完成能力。[C1][C2][M1]

## 官方來源

[C1]: https://c4model.com/diagrams/notation
[C2]: https://c4model.com/diagrams/checklist
[C3]: https://c4model.com/diagrams
[C4]: https://c4model.com/diagrams/dynamic
[C5]: https://c4model.com/diagrams/deployment
[M1]: https://learn.microsoft.com/en-us/azure/well-architected/architect-role/design-diagrams
[A1]: https://aws.amazon.com/architecture/icons/
[D1]: https://www.drawio.com/docs/manual/layers/how-layers-work/
[D2]: https://www.drawio.com/docs/manual/shapes/tables/container-tables/
[D3]: https://www.drawio.com/docs/diagram-types/cross-functional-flowcharts/
[F1]: https://techdocs.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/big-ip-local-traffic-management-basics-14-0-0/05.html
[G1]: https://docs.gitlab.com/user/project/integrations/webhook_events/#pipeline-events
[M2]: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/queue?view=azure-devops-rest-7.0
[M3]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines
[M4]: https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-pipeline-artifact-v1?view=azure-pipelines
[M5]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/triggers?view=azure-devops-2022
[M6]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/approvals/approvals?view=azure-devops-2022
[M7]: https://learn.microsoft.com/en-us/azure/devops/pipelines/release/deployment-groups/?view=azure-devops-2022
[R1]: gitlab-ado-event-trigger.md
