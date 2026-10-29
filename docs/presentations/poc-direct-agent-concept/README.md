# Direct-agent 簡化版｜第 2 頁架構概念

**新增平行版本，不覆蓋原 broker 架構。尚未實作或現場驗收。**

- [架構預覽 preview-02.png](preview-02.png)
- [可編輯單頁 PowerPoint](direct-agent-architecture.pptx) · [同源 PDF](direct-agent-architecture.pdf)
- [文字與講者備註來源](architecture.json)
- [原 broker 版第 2 頁](../poc-implementation-review/preview-02.png)（維持原狀）

沿用原版三區泳道、藍／青綠配色、橙色部署放行與原生線條圖示。主要變動是目標端：專用 Agent 直接呼叫換版／退版腳本，不再透過 broker／JEA；保留來源驗證、PR 審核、五角色分權、部署放行、版本目錄、健康檢查、失敗回復與紀錄。

圖中的「已審腳本」是新版的治理要求，不代表已驗證所有替代分支／YAML／工作執行路徑。實際執行身分、Windows／IIS ACL 與 direct-agent 實作仍待確認；不預設 LocalSystem。指定退版仍須有獨立 Plan 與部署放行，本圖不另展開退版管線。

本頁僅替換概念敘事，原九頁簡報、broker scripts／安裝器／測試與遠端主機均未修改。頁碼保留 `02` 方便對照；輸出的 PPTX／PDF 只有這一頁。

## 重建

在 repo 根目錄：

```powershell
.\.venv-slides\Scripts\python.exe tools/render_direct_agent_concept.py
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -p test_direct_agent_concept.py -v
```

重用 `tools/render_poc_review.py` 的版型與 `tools/export_presentation_pdf.ps1` 的 PowerPoint 匯出流程。PNG 從實際 PDF 產生，並非另一份重畫。需要既有簡報環境的相依套件、Windows 微軟正黑體與桌面 PowerPoint。工具拒絕輸出至原 `poc-implementation-review/` 或歷史 `journey/` 目錄。

視覺參考是既有 `preview-02.png`；本環境未提供 Refero MCP，沒有宣稱進行外部 Refero 搜圖。
