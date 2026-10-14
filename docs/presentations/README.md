# Windows 正式部署治理｜初步計劃簡報

## 交付

- [Markdown 內容與流程圖來源](windows-cd-initial-plan.md)
- [可編輯 PPTX](windows-cd-initial-plan.pptx)
- [固定版面 PDF](windows-cd-initial-plan.pdf)
- [Mermaid／draw.io 圖源](diagrams/README.md)
- [簡報設計研究與官方參考資料](../research/presentation-design-guidance.md)

**v0.5：共 10 頁，包含首頁封面，無附錄；8 頁使用流程圖／責任泳道。** 面向非開發讀者，以「誰建置、誰放行、如何在正式主機完成換版」為主線。ADO 為主方案，Rundeck 為備案。第 5 頁展示 `master → SIT`、`pre-production → UAT`、`production → Production`；第 6 頁說明部署側輪詢、GitLab API 下載與受控產物匯入。第 7 頁合併 ADO／Rundeck 的正式部署共通流程，第 8 頁集中比較 Agent 主動取工作與受限遠端操作。

[串接可行性查證](../research/gitlab-cd-artifact-handoff.md) 依 GitLab、Microsoft 與 Rundeck 官方文件，區分支援的產品功能和必須自行實作的 Collector／Importer。推薦受保護的排程 Collector，只在新候選出現時排入固定 ADO Import Build，轉存 Server Build Artifacts 後接 Classic Release；SIT／UAT 自動，Production 由指定人員建立 Release 並放行。不把 ADO repository 的 `main` 當成 GitLab 來源分支。查證不是現場整合測試。

原第 9／11／12 頁已移除，不以個人提前測試的環境狀態或測試版限制作為對外敘事。其他部門 ADO 的運行先例是主要規劃方向的背景，不等於本提案已獲正式上線批准。

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

- PPTX／PDF 均為 10 頁，無附錄，逐頁具獨立標題與講者備註。
- 8 份 Mermaid 圖源已通過 Mermaid 官方套件語法解析。
- PDF 中文可選取、字型已嵌入；正文／圖中文字至少 18 pt，頁眉頁腳除外。
- 已檢視 PDF 全頁縮圖與重點流程圖；PPTX 使用原生圖形／箭頭，無整頁圖片。
- 未使用桌面 PowerPoint 播放，也未在 diagrams.net UI 中逐圖匯入檢查；會前請在簡報電腦確認字型與版面。

原有四份 `cdpoc-architecture-*.md` 未覆寫。統一架構文件與正式選型結論仍是後續交付。
