# GitLab CE × ADO Server｜POC 落地與跨部門審查

**新的九頁簡報，保留全部舊版。** 資料基準為 2026-10-22 整合包；本次核對檔案與既有證據，未重跑遠端 POC。

## 開會先看這些

- **[可編輯 PowerPoint](gitlab-ado-poc-review.pptx)** · **[PDF](gitlab-ado-poc-review.pdf)**
- [九頁總覽](overview.png) · **[大型架構圖（第 2 頁）](preview-02.png)**
- **[配套說明／完整 API 與憑證清單／決策工作單](review-notes.md)**
- [Express 授權官方查核](../../research/ado-express-five-user-license-review.md) · [API／token／CE 能力查核](../../research/poc-runtime-api-credential-review.md)

主體簡單講分工與決策，詳細端點、scope／role、resource ACL、持有／輪替、歷史問題及證據放配套與講者備註。

| 頁 | 主題 | 預覽 |
|---|---|---|
| 1 | POC 成果與本次審查目的 | [01](preview-01.png) |
| 2 | GitLab CE → ADO Server → Windows VM，大型責任／信任邊界圖 | [02](preview-02.png) |
| 3 | 已驗證結果與證據界線 | [03](preview-03.png) |
| 4 | 兩把跨平台長效秘密的 API、scope、ACL 與持有位置 | [04](preview-04.png) |
| 5 | 多用戶 GitLab＋五個 ADO 角色帳號的理由與授權門檻 | [05](preview-05.png) |
| 6 | 已測自動回復／獨立退版，與未整合的交易／導流設計 | [06](preview-06.png) |
| 7 | 正式試辦前，各部門要補的防線 | [07](preview-07.png) |
| 8 | 五關落地路線：Owner 與出場條件，不虛構工期 | [08](preview-08.png) |
| 9 | 會議要形成的四個決定 | [09](preview-09.png) |

## 三個必須保留的界線

1. **後期 POC 已有降權 Agent＋SYSTEM broker、PR 分權及獨立退版。** 不再沿用初版「SYSTEM agent／無 branch policy」的舊描述。
2. **408 案只有本機沙箱，未接入現行 Pipeline／broker。** 不宣稱 F5、失聯、多節點、業務資料或 DR 已驗收，也不承諾零停機、節省比例或 RTO。
3. **五個角色帳號不是五人授權結論。** 官方 Express 有五人／裝置限制及整合 pooled-connection 例外；實際人員、服務與間接存取用途須取得書面認定，不把共用帳號或服務 PAT 當成已合規捷徑。

## 編輯與重建

- [deck.json](deck.json)：九頁可見內容、證據註記與完整講者備註的來源。
- `tools/render_poc_review.py`：獨立的九種版型；文字、卡片、線條與自繪圖示都是原生 PowerPoint 物件，**不是整頁圖片**。
- `tools/export_presentation_pdf.ps1`：由桌面 PowerPoint 輸出實際 PPTX 的 PDF。沿用唯讀／未命名暫存複本模式，不儲存或關閉使用者原簡報，也不 Quit PowerPoint。
- PNG 與總覽只由該 PDF 產生；不是另一套重畫的投影片。
- [review-notes.md](review-notes.md)：人工維護的配套，變更內容時應一起校對。

在 repo 根目錄的 Windows PowerShell：

```powershell
.\.venv-slides\Scripts\python.exe -m pip install -r tools/requirements-poc-review.txt
.\.venv-slides\Scripts\python.exe tools/render_poc_review.py --previews
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -p test_poc_review.py -v
```

已配置原專案相依套件的環境可跑全部測試：

```powershell
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -v
```

字型為 Windows `Microsoft JhengHei`（`msjh.ttc`／`msjhbd.ttc`），**PPTX 未嵌字型**；可加 `--font-dir` 指定字型目錄。無桌面 PowerPoint 時可用 `--pptx-only`，但不更新 PDF／PNG，不能把既有 PDF 當作已同步。`--previews` 不可與 `--pptx-only` 同用。

`--output-dir` 可指定另一個新目錄；工具拒絕寫入歷史 `journey/` 路徑。輸出先於暫存區完成與驗證，再逐檔 atomic replace；輸出被占用會報錯。**若手改過本版 PPTX，請先另存快照或改輸出目錄，再重建**：程式不會讀回人工修改。這是特定敘事版型，不是任意 JSON／Markdown 自動排版工具。

## 驗證與限制

本次已完成：

- 原包 91 份檔案 hash／大小核對；實作與 A～C-5、下一階段 JSON／報告交叉閱讀。
- 官方 Express EULA／授權指引、API、PAT／job token、GitLab Free 能力查核，來源附在研究筆記；不是現場授權裁示。
- **25 項 unittest 通過**（既有 14＋新增 11）。包含原生可編輯物件、完整備註、文字／路線不越界、文字不重疊、對比度、方向／憑證／證據界線、防寫舊版、基本敏感資訊掃描。
- 9 頁 PDF 由本版 PPTX 經 PowerPoint 匯出；逐段檢查可見文字均存在，PNG 與 PDF 同源。
- 檢視九頁總覽與逐頁 PNG；修正行程 Owner 與節點重疊。
- **64 個既有簡報／相關生成測試檔案的前後 hash 無變更**，全部原有 tracked files 保持未修改。

沒有做：遠端功能重測、目前 token／ACL 稽核、正式系統／F5／備份還原演練、Microsoft 個案授權批准，以及會議電腦投影／人工逐頁播放。機密掃描只是基本防護，不取代公司對外發布審查。原 ZIP、解壓內容與參考照片不納入 Git；CDPOC ZIP 已列入 `.gitignore`。

## 視覺依據

為架構、資安、IAM、維運、應用與採購製作，目的是「看懂已完成的分工，決定下一步怎麼落地」，不是宣稱正式上線已成功。沿用既有三頁本地參照：Journey 的架構、分流、行程；環境沒有 Refero MCP，沒有聲稱完成外部 Refero 搜圖。

| 已確認參照 | 抽出的具體做法 | 本版用途 |
|---|---|---|
| Journey 架構頁 | 藍色 CI、淡中性色管理側、青綠目標三區 | 第 2 頁責任與信任邊界，不重複塞入單機完整換版流程 |
| Journey 架構頁 | 橙色授權關卡與線條 shield 圖示 | 區分人工部署放行與檔案到達；不是用顏色代表測試成功 |
| Journey 分流頁 | 同一行對齊來源、策略與執行者 | 第 6 頁將回復、指定退版、下一階段三路分開，附文字狀態 |
| Journey 行程頁 | 起伏圓角路線、白芯粗線、編號節點 | 第 8 頁五個出場關卡；不沿用歷史日期 |
| Journey 行程頁 | 統一自繪 outline 人物／主機／Pipeline／檢核／旗幟 | 不貼照片或泛用裝飾；圖示對應責任與行動 |

暖白 `#FCFBF7`、深墨 `#18394B`，藍／青綠／橙暗化文字符合對比需求。以來源註記＋測試 ID 作信任線索，不用虛構徽章或數字；可記住的核心是「通知不是授權，Agent 主動取工作；高權限留在受控 broker」。
