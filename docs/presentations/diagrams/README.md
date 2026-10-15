# 可編輯流程圖來源

v0.7 共 5 張圖：第 4 頁為獨立 draw.io 主圖，其餘四張仍由簡報 Markdown 生成。

| 投影片 | 圖解 | 來源／輸出 |
|---|---|---|
| 3 | 正式主機存取邊界／已否決路徑 | [Mermaid](production-boundary.mmd) · [draw.io](production-boundary.drawio) |
| 4 | 端到端交付架構、多台 Target、F5 換版與復原 | **[draw.io 可編輯主檔](windows-deployment-map.drawio)** · [高清 PNG](windows-deployment-map.png) · [向量 PDF](windows-deployment-map.pdf) |
| 5 | 三分支與環境放行 | [Mermaid](environment-approval.mmd) · [draw.io](environment-approval.drawio) |
| 6 | 換版與復原概覽 | [Mermaid](release-lifecycle.mmd) · [draw.io](release-lifecycle.drawio) |
| 7 | 建議導入時程 | [Mermaid](proposed-timeline.mmd) · [draw.io](proposed-timeline.drawio) |

## 第 4 頁：可直接修改的架構圖

1. 到 [diagrams.net](https://app.diagrams.net/) 選「開啟現有圖表」，載入 `windows-deployment-map.drawio`。
2. 節點、文字、容器和連接線都是真正可編輯物件。移動容器可連同主機內容移動；線標籤是獨立文字，移線後也需檢查標籤位置。實際 GUI 仍請檢查字型與排線。
3. 儲存 draw.io，再匯出白底、整頁 16:9 PNG（至少 2800 像素寬），覆蓋 `windows-deployment-map.png`，同時更新獨立 PDF。
4. 執行簡報 renderer 將 PNG 放入第 4 頁。僅儲存 draw.io 不會自動更新簡報。

**簡報重建不會覆寫此架構圖。** `tools/build_deployment_map.py` 只是初始產圖種子，不要在手改後重新執行；它會覆寫 draw.io、PNG、獨立 PDF。種子生成的 PDF 是向量圖，PNG 為 2800×1575。簡報內第 4 頁是圖片，其可編輯性由 draw.io 提供。

## 圖意與限制

- 上半部：開發／CI → 受控接收器 → ADO importer 與固定版本 → 人員放行 → 各 Windows Target。下半部：對每個核准目標重複的單台換版／退版流程。
- 01、02、…、N 可表示數十台；不是所有主機同時部署或主機間互傳檔案。建議逐台，失敗停止後續；批次與最低容量待定。
- 虛線為控制／授權、實線為程式碼／產物、粗線為 F5 應用流量，另有文字圖例；責任區不等於已驗證的網段或 ACL。
- 工作箭頭**不是完整網路拓樸**。管理 Agent 主動下載 GitLab artifact，所有 ADO Agents 主動連 Server 取工作；正式放行前不預拷。
- 使用者已確認下／上 F5 是退出／恢復負載平衡流量。模式、連線等待、pool/member 範圍與控制身分／位置仍待確認，不能假定每台 Agent 都有 F5 憑證。
- 復原健康才恢復流量，並記錄「部署失敗／復原成功」；復原失敗保持隔離、告警、人工處理，不可記新版本部署完成。任一恢復流量操作／驗證失敗也不得結案。
- 設計參考與證據範圍見 [架構圖研究](../../research/end-to-end-architecture-diagram-design.md)。尚未完成部署整合、F5 操作或復原實機測試。

## 其他四張圖

`.mmd` 可於 [Mermaid Live Editor](https://mermaid.live/) 使用；標準 Mermaid 忽略座標註解，自行排版。這四張圖由 `windows-cd-initial-plan.md` 重建，請修改 Markdown；直接修改其 draw.io 會在重建時被覆寫。
