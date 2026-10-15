# 可編輯流程圖來源

v0.6 共 5 張圖，每張提供 Mermaid、draw.io 圖源及 PPTX 原生可編輯物件。

| 投影片 | 圖解 | Mermaid | draw.io |
|---|---|---|---|
| 3 | 正式主機存取邊界／已否決路徑 | [mmd](production-boundary.mmd) | [drawio](production-boundary.drawio) |
| 4 | 事件驅動的完整架構 | [mmd](event-driven-architecture.mmd) | [drawio](event-driven-architecture.drawio) |
| 5 | 三分支與環境放行 | [mmd](environment-approval.mmd) | [drawio](environment-approval.drawio) |
| 6 | 換版與復原 | [mmd](release-lifecycle.mmd) | [drawio](release-lifecycle.drawio) |
| 7 | 建議導入時程 | [mmd](proposed-timeline.mmd) | [drawio](proposed-timeline.drawio) |

- 在 [diagrams.net](https://app.diagrams.net/) 開啟 `.drawio` 可編輯；`.mmd` 可於 [Mermaid Live Editor](https://mermaid.live/) 使用。標準 Mermaid 忽略座標註解，自行排版。
- 架構圖的泳道表示責任／安全區域，橘色節點具「人員」文字；其餘節點為工具／系統。虛線標出禁止路徑，不只靠顏色表意。
- 架構圖箭頭表示工作／資料交接，**不是完整網路拓撲**。ADO Agents 主動連 Server 取工作；管理 Agent 主動呼叫 GitLab API 下載，正式主機 Agent 在放行後才取得檔案。
- 事件接收器是需實作的管理服務，不是額外 GitLab Runner；管理 Agent 與每台目標的部署 Agent 是隔離的角色。正式部署前不能先送檔。
- 單張圖以 ①～⑤ 講解，不增加重複頁或動畫頁；復原腳本需另行設計與演練。
- 圖由 `windows-cd-initial-plan.md` 重建。請修改 Markdown；直接編輯圖檔會在重建時被覆寫。
