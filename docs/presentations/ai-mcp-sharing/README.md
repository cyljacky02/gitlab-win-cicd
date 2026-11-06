# AI × MCP｜內部分享簡報

目標：讓非開發與開發同仁在 15–20 分鐘內理解，為什麼借用 ChatGPT Web 的腦、如何透過 Playwright／Relay 接上地端工具，以及人如何保留控制權。共 **6 頁、約 15 分鐘，其中 8 分鐘留給 Demo**；原第 2＋3 頁合為想法／架構，原第 4＋5 頁合為能力總覽，不另增封面／附錄。

## 設計鎖定（實作前）

主參照：既有 `../poc-implementation-review/overview.png` 與 `tools/render_poc_review.py`。使用者明確要求延續既有框架與主題，不另開風格探索。環境沒有 Refero MCP，未聲稱完成外部 Refero 搜圖。

| 決定 | 參照與角色 | 本版用途 |
|---|---|---|
| 1200×675、暖白底、微軟正黑體、深墨標題 | 既有 POC 簡報 | 同一套投影與原生 PPTX 語言 |
| 藍色＝理解／請求；青綠＝工具／執行；橙色＝人工授權 | POC 架構圖、Journey 分流頁 | 分工可辨識，顏色不代表成功／安全認證 |
| 圓角路線、白芯線、編號節點 | Journey 行程頁與 POC 首頁 | 記住「理解 → 檢查 → 執行 → 結果回來」 |
| 一頁一個主張、細節進講者備註 | `../../research/presentation-design-guidance.md`；Refero typography craft | 不把研究報告搬上投影片 |
| 圖示、流程、文字均為原生物件 | 現有 JSON → Python → PPTX 架構 | 可編輯；不以生成圖片冒充產品畫面 |
| PDF 與 PNG 從實際 PPTX 匯出 | 現有 PowerPoint COM 匯出器 | 預覽與交付同源，重建不觸及舊版 |

媒體策略：只用對應真實角色的原生圖形與線條圖示；Demo 頁是操作路線，**不是已執行的截圖或結果**。拒絕新增漸層、裝飾性大圖、虛構效益百分比或「已全面合規」徽章。

## 封面插畫更新：AI 小助手

右上角原有的三節點路線改成原創向量插畫：友善 AI 小助手從瀏覽器探出身，一手連接程式工具、一手拿工具箱，旁邊是橙色授權勾勾。這是概念插畫，不是產品畫面或安全認證。

- **參照鎖定**：保留本版封面版式與暖白留白；瀏覽器採既有藍色、助手採青綠、橙色只用在授權徽記／少量細節。借用既有 outline 圖示的圓角與線寬，增加表情、肢體動作與對話泡泡，不改整份視覺主題。
- **媒體選擇**：目前沒有可用的影像生成工具，因此直接繪製與既有風格一致的原創原生向量，不宣稱使用外部 AI 生圖。圖源為 `tools/illustrate_ai_helper.py`，PPTX 中群組為 `Cover illustration: AI helper`，可整組移動或取消群組編輯。
- **範圍**：只更換第 1 頁右上插畫；其他頁的可見內容與講稿不變。
- **預覽**：[封面](preview-01.png) · [獨立插畫 PNG](cover-ai-helper.png)。兩者皆由實際 PPTX 匯出的 PDF 產生；已確認插畫不遮擋標題、內容卡或頁尾，無多餘的小字。

## 交付與重建

- [deck.json](deck.json)：6 頁可見文字、來源與完整講者備註。
- **[ai-mcp-sharing.pptx](ai-mcp-sharing.pptx)**：原生可編輯 PowerPoint。
- **[ai-mcp-sharing.pdf](ai-mcp-sharing.pdf)**：桌面 PowerPoint 匯出；不含備註。
- [overview.png](overview.png)、`preview-01.png`～`preview-06.png`：PDF 同源預覽。
- [speaker-notes.md](speaker-notes.md)：從 JSON 同步產生的逐頁講稿。
- [demo-runbook.md](demo-runbook.md)：會前檢查、Demo 提示詞、觀察點與失敗備案。
- [原始碼查核](../../research/local-mcp-ai-sharing-source-notes.md)：固定 commit 的證據與限制。

```powershell
.\.venv-slides\Scripts\python.exe tools/render_ai_mcp_sharing.py --previews
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -p test_ai_mcp_sharing.py -v
```

使用既有 `tools/requirements-poc-review.txt`。需 Windows 微軟正黑體與桌面 PowerPoint。`--pptx-only` 僅產 PPTX／講稿，不更新 PDF／PNG；不能與 `--previews` 合用。重建會覆寫本版生成檔，若人工修改 PPTX，請先另存快照或指定 `--output-dir`。

## 內容與證據邊界

- 行內 Codex 額度有限，是分享者提供的使用背景，不是 GitHub 程式碼證明的事實。
- Web 端自訂文字協議／Relay 與一般 MCP 工具連線分開說明，不稱為 ChatGPT Web 原生直連本機。
- 源碼存在的控制，不等於現場整合測試、滲透測試或行內合規認證。
- 工具結果會回到 Web AI；可否傳送資料／程式碼仍須遵循公司政策。使用測試資料，不展示信件、個資、憑證或正式系統。
- 本次製作不操作業務系統、不使用 Outlook、不執行現場 local-mcp Demo；會前需依小抄彩排。

## 分享路線（約 15 分鐘）

| 頁 | 主旨 | 時間 |
|---|---|---|
| 1 | 從額度與手動接力的痛點出發 | 2 分鐘 |
| 2 | ChatGPT Web 的腦 → Playwright／Relay → 地端執行，結果回傳 | 1.5 分鐘 |
| 3 | 能力輕帶：Web 自動化、日常查詢、VS Code 開發協作 | 1 分鐘 |
| 4 | 工具範圍、分級核准、版本防護、留痕與限制 | 1.5 分鐘 |
| 5 | Demo：測試情境（3 分鐘）＋程式提案與確認（5 分鐘） | 8 分鐘 |
| 6 | 從聊天工具走向可擴充的執行助手 | 1 分鐘 |

架構與能力各一張帶過，不把兩頁的字硬塞進一頁。語法檢查、Diff、駁回、核准與套用等操作細節移至第 5 頁 Demo 講稿；技術限制保留在「備用」備註與操作小抄，不逐字念成主講內容。

## 品質驗證

本次已完成：

- 查核 local-mcp 固定 commit `280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6`；研究筆記包含固定版本行號連結，各頁講者備註另附相關來源。
- 產出 **6 頁原生可編輯 PPTX**，無整頁點陣圖；繁體中文講稿嵌在 PPTX 備註，另同步為 Markdown。
- 由桌面 PowerPoint 匯出 **6 頁 PDF**，逐段驗證可見文字均存在；逐頁 PNG 與總覽由該 PDF 生成。
- 已檢視 6 頁總覽與合併頁的完整 PNG，標題、行距、對比、流程與頁尾無可見裁切／重疊；延續既有暖白／藍／青綠／橙授權主題。
- **本 repo 42 項 unittest 通過，其中本版 11 項**；涵蓋六頁敘事、Playwright 橋接、精簡能力、幾何邊界、文字重疊、對比、原生物件、備註、歷史路徑保護、匯出失敗不覆寫、PDF／講稿同步及確認沒有多餘的第 7／8 頁預覽。
- 修改僅在本版來源、生成檔與測試，不更改其他歷史簡報。

未做：在會議電腦投影／播放、完整 local-mcp UI／人審／網站／Outlook／DB 端到端驗收。研究環境曾做離線檢查與 stdio discovery，結果與限制見查核筆記，不與本 repo 的簡報測試混為一談。**公開 repo 不含完整可跑 Web BAT 情境，會前必須另備並彩排；本次沒有附預錄影片。**
