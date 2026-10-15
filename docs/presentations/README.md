# Windows 正式部署治理｜初步計劃簡報

## 交付

- [Markdown 內容與流程圖來源](windows-cd-initial-plan.md)
- [可編輯 PPTX](windows-cd-initial-plan.pptx)
- [固定版面 PDF](windows-cd-initial-plan.pdf)
- [Mermaid／draw.io 圖源](diagrams/README.md)
- [簡報設計研究與官方參考資料](../research/presentation-design-guidance.md)

**v0.6：共 7 頁＝封面＋議程＋5 頁內容（含時程），無附錄。** 面向非開發讀者，只討論 Azure DevOps Server，Express 作為 POC 起點，不預定正式採購版本。

| 頁 | 主旨 |
|---|---|
| 1 | 封面：保留 GitLab 建置，正式換版由授權部門掌握 |
| 2 | 議程：原因、架構、環境、換版與時程 |
| 3 | 合併舊版第 2–3 頁：只送檔也算正式主機存取 |
| 4 | 一張完整架構：成功通知、受控接收器、ADO、管理 Agent、部署人員、目標 Agent |
| 5 | 三分支各自建置；SIT／UAT 自動，Production 人工選版放行 |
| 6 | 放行後取檔、換版、健康檢查與復原 |
| 7 | 建議時程：POC → 協調架構部門安裝 ADO → GitLab 整合 → SIT → UAT → Production |

使用單張架構圖的 ①～⑤ 帶領說明，不增加重複頁或動畫頁。時程以 **12/31** 為目標，年份未指定；各階段日期、資源與上線批准待共同確認。

[事件驅動串接查證](../research/gitlab-ado-event-trigger.md) 是本版架構依據：**GitLab 成功 webhook → 受保護接收器 → 固定 importer → Server Build Artifacts → Classic Release**。管理 Agent 執行匯入，每台 Windows 的專用 Deployment Group Agent 執行部署；正式放行前不得預拷。接收器／匯入驗證／可靠交接是需實作的邏輯，不宣稱原生 GitLab artifact 整合。Server 有 incoming webhook 支援，但 GitLab 驗證互通仍需另測；本版不依賴該互通性。

CI job 直呼 Queue API 有文件化能力基礎，但存在 pipeline 尚未成功的競態及憑證暴露面，故不作首選。[前版輪詢研究](../research/gitlab-cd-artifact-handoff.md) 保留為歷史比較，不再是本版推薦。查證不是現場整合測試；有效 ACL、Express 安裝版行為與零預拷均列入 POC。

不以個人測試環境狀態為對外敘事。其他部門已有 ADO 運行先例是規劃背景，不等於本案通過驗收。

用途是跨部門討論可行性與合規要求，不是正式選型、合規認證或上線批准。技術細節、資料來源與證據範圍留在 Markdown／PPTX 講者備註，不另加附錄投影片。PDF 不含講者備註。

## 可編輯性

PPTX 文字、流程方塊、判斷菱形、泳道與箭頭均為原生物件，不是整頁圖片。箭頭代表工作交接／執行順序，不一定代表網路連線方向；尤其 ADO Target Agent 一般主動連線取得工作。

Mermaid 適合文字版控；draw.io 適合人工調整節點與泳道。圖源由同一份 Markdown 生成。不同工具可能重新排線，因此不保證 Mermaid、draw.io、PPTX 的像素級一致。

## 從 Markdown 重建

在 repo 根目錄執行（Windows PowerShell）：

```powershell
python -m venv .venv-slides
.\.venv-slides\Scripts\python.exe -m pip install -r tools/requirements-slides.txt
.\.venv-slides\Scripts\python.exe tools/render_slides.py docs/presentations/windows-cd-initial-plan.md
```

不需啟用虛擬環境。若希望啟用，PowerShell 使用 `.\.venv-slides\Scripts\Activate.ps1`；CMD 使用 `.venv-slides\Scripts\activate.bat`。

需要 Windows 的 `msjh.ttc`／`msjhbd.ttc`；可用 `--font-dir` 指定合法取得的字型檔目錄。PDF 嵌入字型子集；PPTX 使用 Microsoft JhengHei，未嵌入字型，在沒有該字型的電腦可能出現替代字型及版面差異。

重建會覆寫同名 PPTX、PDF、Mermaid 與 draw.io 檔。重要修改請回寫 Markdown；直接修改 PPTX／draw.io 不會自動回寫來源。

## Markdown 格式

這是專用 Markdown／Mermaid 子集渲染器，不是任意文件轉換器：

- `---`：換頁；`#`：標題；`>`：本頁重點。
- `##`／`-`：1–3 張內容卡片。流程圖頁只保留一段短解釋。
- `mermaid` fenced block：`flowchart LR`、雙引號節點、`<br/>` 換行、判斷菱形、`subgraph`、有標籤箭頭、虛線、預設色彩類別。
- `%% @name`：圖名；`@node`／`@lane`：在 880×280 圖區內的座標與尺寸；`@route`：轉折點；`@ports`：連線進出邊；`@label`：箭頭標籤位置。這些是標準 Mermaid 註解，其他 Mermaid 工具忽略座標，會自行排版。
- `<!-- notes ... -->`：講者備註，不顯示在投影片與 PDF 中。

PPTX／PDF 使用同一份版面資料各自渲染，PDF 不是 PowerPoint 另存，因此不同 PowerPoint／字型環境不保證像素級一致。

## 品質檢查

- PPTX／PDF 均為 7 頁，無附錄，逐頁具獨立標題與講者備註。
- 5 份 Mermaid 圖源已通過 Mermaid 官方套件語法解析。
- PDF 中文可選取、字型已嵌入；正文／圖中文字至少 18 pt，頁眉頁腳除外。
- 已檢視 PDF 全頁縮圖與重點流程圖；PPTX 使用原生圖形／箭頭，無整頁圖片。
- 未使用桌面 PowerPoint 播放，也未在 diagrams.net UI 中逐圖匯入檢查；會前請在簡報電腦確認字型與版面。

原有四份 `cdpoc-architecture-*.md` 未覆寫。統一架構文件與正式選型結論仍是後續交付。
