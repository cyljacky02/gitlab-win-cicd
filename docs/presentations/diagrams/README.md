# 可編輯流程圖來源

每張圖提供 `.mmd`（Mermaid）及 `.drawio`（diagrams.net）兩種來源，並以原生圖形呈現在 PPTX 中。

| 投影片 | 圖解 | Mermaid | draw.io |
|---|---|---|---|
| 2 | 正式主機存取邊界 | [mmd](production-boundary.mmd) | [drawio](production-boundary.drawio) |
| 3 | 已否決的直接送檔方案 | [mmd](rejected-delivery.mmd) | [drawio](rejected-delivery.drawio) |
| 4 | 容器現況與 Windows 提案 | [mmd](existing-and-proposed.mmd) | [drawio](existing-and-proposed.drawio) |
| 5 | 測試自動化與正式放行 | [mmd](environment-approval.mmd) | [drawio](environment-approval.drawio) |
| 6 | GitLab 建置產物的發現、下載與匯入 | [mmd](artifact-handoff.mmd) | [drawio](artifact-handoff.drawio) |
| 7 | 正式部署共通流程與責任泳道 | [mmd](common-deployment.mmd) | [drawio](common-deployment.drawio) |
| 8 | Agent 取工作與遠端指令的差異 | [mmd](execution-models.mmd) | [drawio](execution-models.drawio) |
| 9 | 換版與復原步驟 | [mmd](release-lifecycle.mmd) | [drawio](release-lifecycle.drawio) |

- 在 [diagrams.net](https://app.diagrams.net/) 使用「開啟現有圖表」載入 `.drawio`，即可編輯文字、方塊、泳道與連線。
- `.mmd` 可放入支援 Mermaid 的 Markdown 工具或 [Mermaid Live Editor](https://mermaid.live/)。標準 Mermaid 會自行排版，不使用註解中的固定座標。
- 方框表示工作／系統；菱形表示判斷；泳道區分部門／環境。紅色虛線同時有文字標示，代表被禁止或已否決的路徑，不只靠顏色表意。
- 第 6 頁區分輪詢查詢與 API 取回檔案：均由部署管理端主動發起，不代表 GitLab 直接把檔案送進正式主機。Webhook 是可選通知機制，不是產物搬運。
- 第 8 頁特別區分連線方向：ADO Agent 主動連向 ADO Server 取工作，Rundeck 管理端連向 Windows 受限入口下指令；前後頁的箭頭主要表示工作交接。
- 兩路線最後都在 Windows 執行換版；健康檢查與回滾需事先設計，不由 Agent 或遠端方式自動保證。
- 圖由 `windows-cd-initial-plan.md` 重建產生。請將重要修改同步回 Markdown，否則再次渲染會覆寫直接編輯的圖檔。
