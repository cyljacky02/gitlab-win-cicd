# 可編輯流程圖來源

v0.7 共 5 張圖：第 4 頁為獨立 draw.io 主圖，其餘四張仍由簡報 Markdown 生成。

| 投影片 | 圖解 | 來源／輸出 |
|---|---|---|
| 3 | 正式主機存取邊界／已否決路徑 | [Mermaid](production-boundary.mmd) · [draw.io](production-boundary.drawio) |
| 4 | 端到端交付架構、多台 Target、F5 換版與復原 | **[draw.io 可編輯主檔](windows-deployment-map.drawio)** · [高清 PNG](windows-deployment-map.png) · [向量 PDF](windows-deployment-map.pdf) |
| 5 | 三分支與環境放行 | [Mermaid](environment-approval.mmd) · [draw.io](environment-approval.drawio) |
| 6 | 換版與復原概覽 | [Mermaid](release-lifecycle.mmd) · [draw.io](release-lifecycle.drawio) |
| 7 | 建議導入時程 | [Mermaid](proposed-timeline.mmd) · [draw.io](proposed-timeline.drawio) |

## 拆分圖：獨立編輯與使用

依需求將上、下半部拆為兩份獨立圖，保留可編輯節點與連線，不是裁切圖片假裝圖源：

| 圖 | draw.io 原檔 | 高清 PNG | 向量 PDF |
|---|---|---|---|
| 上半部：端到端部署架構（2800×990） | [編輯](windows-deployment-architecture.drawio) | [圖片](windows-deployment-architecture.png) | [PDF](windows-deployment-architecture.pdf) |
| 下半部：單台換版與復原（2800×695） | [編輯](windows-target-release-flow.drawio) | [圖片](windows-target-release-flow.png) | [PDF](windows-target-release-flow.pdf) |

兩張都保留標題、圖例及必要限制，可單獨放入文件／投影片；尺寸依內容裁切，不強制補成 16:9。原完整圖與簡報第 4 頁保留不變，簡報仍為 7 頁。三份 draw.io 可分別手改，**修改不會自動同步至其他圖或圖片輸出**。

## 第 4 頁：可直接修改的架構圖

1. 到 [diagrams.net](https://app.diagrams.net/) 選「開啟現有圖表」，載入 `windows-deployment-map.drawio`。
2. 節點、文字、容器和連接線都是真正可編輯物件。移動容器可連同主機內容移動；線標籤是獨立文字，移線後也需檢查標籤位置。實際 GUI 仍請檢查字型與排線。
3. 儲存 draw.io，再匯出白底、整頁 16:9 PNG（至少 2800 像素寬），覆蓋 `windows-deployment-map.png`，同時更新獨立 PDF。
4. 執行簡報 renderer 將 PNG 放入第 4 頁。僅儲存 draw.io 不會自動更新簡報。

**簡報重建不會覆寫此架構圖。** `tools/build_deployment_map.py` 只是初始產圖種子，不要在手改後重新執行；它會覆寫完整圖及兩份拆分圖的 draw.io、PNG、獨立 PDF，共九個檔案。種子生成的 PDF 是向量圖，PNG 為 2800×1575。簡報內第 4 頁是圖片，其可編輯性由 draw.io 提供。

## 圖意與限制

- 上半部管理區簡化為「收到成功通知 → 取得並保存版本 → 部署人員選版／選目標、確認放行」，保留開發／CI 與 Production 兩區。圖中「ADO 管理側」涵蓋實際接收器與管理 Agent 的角色，不是宣稱 Server 本機包辦或 GitLab 原生直連；API、Importer、驗證與權限細節保留在第 4 頁講者備註及串接研究。下半部仍為每個核准目標的單台換版／退版流程，未變更。
- 01、02、…、N 可表示數十台；不是所有主機同時部署或主機間互傳檔案。建議逐台，失敗停止後續；批次與最低容量待定。
- 虛線為控制／授權、實線為程式碼／產物、粗線為 F5 應用流量，另有文字圖例；責任區不等於已驗證的網段或 ACL。
- 工作箭頭**不是完整網路拓樸**。管理 Agent 主動下載 GitLab artifact，所有 ADO Agents 主動連 Server 取工作；正式放行前不預拷。
- 使用者已確認下／上 F5 是退出／恢復負載平衡流量。模式、連線等待、pool/member 範圍與控制身分／位置仍待確認，不能假定每台 Agent 都有 F5 憑證。
- 復原健康才恢復流量，並記錄「部署失敗／復原成功」；復原失敗保持隔離、告警、人工處理，不可記新版本部署完成。任一恢復流量操作／驗證失敗也不得結案。
- 設計參考與證據範圍見 [架構圖研究](../../research/end-to-end-architecture-diagram-design.md)。尚未完成部署整合、F5 操作或復原實機測試。

## 載入相容性檢查

已修正 `setId is not a function`：mxGraph codec 使用陣列作 ID cache，裸 ID `push` 與陣列方法撞名。主圖的自訂 cell ID 及全部引用已統一使用 `wdm-` 前綴；內容、座標及圖面未改。已用 mxGraph 4.2.2 真正解碼、檢查所有 cell 的 parent/source/target，再重新編碼／解碼驗證；這不是僅驗 XML 格式，也不等於已用目前 diagrams.net GUI 完整驗證。

回歸測試（repo 根目錄，需 Node.js）：

```powershell
npm install --prefix .venv-slides/mermaid-check jsdom
curl.exe -L --fail -o .venv-slides/mermaid-check/mxClient.js https://raw.githubusercontent.com/jgraph/mxgraph/v4.2.2/javascript/mxClient.js
node tests/check_drawio_codec.cjs
```

測試包含可重現原錯誤的最小 fixture，以及所有七份圖的物件引用與 codec roundtrip。依賴存放於 ignored `.venv-slides/`，不提交第三方套件。

## 其他四張圖

`.mmd` 可於 [Mermaid Live Editor](https://mermaid.live/) 使用；標準 Mermaid 忽略座標註解，自行排版。這四張圖由 `windows-cd-initial-plan.md` 重建，請修改 Markdown；直接修改其 draw.io 會在重建時被覆寫。
