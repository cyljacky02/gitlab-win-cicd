# Local MCP｜AI 分享簡報來源查核筆記

研究日期：**2026-11-06**（本機時區 +08:00）。用途：供另行製作繁體中文 **8 張**分享簡報《AI × MCP 打造可控、可授權的 AI 智慧執行助手》；本檔是研究筆記，不是實作或簡報成品。

## 0. 固定版本、方法與證據邊界

- 第一手來源：<https://github.com/cyljacky02/local-mcp>。以 Git clone 取得完整 source；以下 GitHub 連結全部固定在 **`280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6`**，不以會漂移的 `master` 作證據。
- 該 HEAD author／committer 日期均為 **2026-11-06T09:44:43+08:00**；subject：`docs: configure engineering agent skills`。[固定 commit](https://github.com/cyljacky02/local-mcp/commit/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6)。這是研究時取得的版本，不代表作者現場使用的版本。
- Clone 絕對路徑：**`C:/Users/bread-laptop/AppData/Local/Temp/local-mcp-talk-research`**（Git Bash 的 `/tmp/local-mcp-talk-research` 實際對應此處）。
- 已讀根目錄 `AGENTS.md` 與 `docs/agents/domain.md`；clone 中未見 `GLOSSARY.md`／`docs/adr/`。未操作 Issues、未更改研究對象的 tracked source；只在 temp 安裝擴充依賴／執行離線檢查。
- **I（實作）**：追到執行分支、參數、權限與資料處理 source。**D（專案文件）**：作者文件中的使用要求／自述，不取代實作。**T（本次實測）**：本機可重現的離線／stdio discovery 結果。**U（未驗證）**：真實 ChatGPT 登入、Outlook profile、MySQL、外部 Web BAT、完整 UI／人審流程。
- 沒有登入作者帳號、讀私人 `.env`、操作實際 DB／郵件／網站或真的套用 DEV 提案；**沒有完成端到端驗收**。

### 最重要的簡報修正

1. **不是 ChatGPT 原生接 MCP，也不是 OpenAI API client。** 目前是 Python／Playwright 操作 Chrome，擷取 ChatGPT Web 的 DOM，再解析自訂工具文字協定；本機工具子程序才使用 MCP SDK／stdio（C1–C2）。
2. **此 HEAD 找不到 userscript／Tampermonkey 實作。** 搜尋 tracked source 的 `userscript`、`Tampermonkey`、`GM_xmlhttpRequest` 均無命中；正面證據是 Worker 的 CDP 連線與 `ChatGPTClient.send()`。請勿把其他版本／作者口述的 userscript 畫進現況圖（C1）。
3. **「唯讀」不是「不出本機」。** Outlook metadata、查詢資料、授權讀取的原始碼會進入工具結果／ChatGPT Web 對話；本機執行與資料不外傳是兩回事（C1、C3、C5、C6）。
4. **不是所有寫入都逐筆人工核准。** 密碼重設、Web 測試及正式程式碼套用需要核准；有效 Development Workflow 中的受限 BugList 寫入是例外（C7、C8）。
5. **公開 clone 不是開箱即用。** 本次實際找到 MCP tool module 在 import 時便要求 MySQL／預設密碼設定，與「DB optional」文件印象有落差；因此只演示 Outlook／列 scenario 也要先處理啟動依賴（C10）。

## 1. 逐項主張與 source 證據

### C1｜瀏覽器文字橋接，不是原生 ChatGPT MCP

**I：** `worker.py` 建立 Playwright，`connect_over_cdp(CDP_URL)`，再建立 `ChatGPTClient`／`PageScriptRunner`。送訊息時直接找到 textbox、`fill(prompt)`、按 Enter；回應讀取器回傳 `source: 'chatgpt_dom'`，並檢查 MCP／DEV 結尾標記。`response_handler.py` 僅解析純文字：一組 `[[MCP:REQUEST]]`／`[[MCP:END]]`、`TOOL name`、逐行 `ARG key = JSON值`；BugList 使用另外的 FIELDS 區塊。

- [Worker／CDP 與 page script runner，worker.py L240–272](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/worker.py#L240-L272)
- [在 ChatGPT composer 輸入及按 Enter，chatgpt_client.py L511–607](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/chatgpt_client.py#L511-L607)
- [DOM reader 回應／identity，assistant_response_api.py L1–30](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/assistant_response_api.py#L1-L30)
- [文字 parser 與 JSON ARG，response_handler.py L118–220](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/response_handler.py#L118-L220)
- [專案 Instructions／能力文件的人工設定要求，docs/PROJECT_INSTRUCTIONS.md L9–25](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/docs/PROJECT_INSTRUCTIONS.md#L9-L25)

**可說：**「讓 ChatGPT Web 以文字提出工具請求，由本機 Relay 解析與授權，再代為執行。」

**不可說：**「ChatGPT 官方原生連上我的 MCP Server」、「安裝 userscript 就完成」、「改用 Network API 直接驅動工具」。Network Shadow 是旁路，不是正式回答來源；本次既有測試也確認 shadow 不取代 DOM（§3）。DOM 改版、登入與生成完成判定仍可能失敗。

### C2｜本機真正的 MCP transport：stdio 子程序

**I：** `MCPExecutor` 每次工具執行以 `sys.executable` 啟動 `mcp_runtime/mcp_server.py`；`stdio_client → ClientSession → initialize → list_tools → call_tool`，呼叫前先確認工具名存在。不是讓 ChatGPT 直接發送 MCP wire protocol，也不是 Relay 的 HTTP／SSE 等於 MCP transport。`dev.*` 另由 Runtime dispatch，不走 MCP 子程序。

- [啟動參數／stdio／tool discovery 與 call，mcp_runtime/mcp_executor.py L223–315](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_executor.py#L223-L315)
- [MCPServer SDK import，mcp_runtime/mcp_server.py L60–82](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_server.py#L60-L82)
- [Server 的 run，mcp_runtime/mcp_server.py L587–616](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_server.py#L587-L616)
- [dev.* 分流與工具結果 transport，relay_runtime.py L1051–1091](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/relay_runtime.py#L1051-L1091)

**建議現況圖：** GUI／VS Code → HTTP Relay／Session／SSE → Workflow／Worker → Playwright／CDP → ChatGPT Web DOM → 文字 parser → 工具政策／必要時人審 → MCPExecutor／stdio → 固定業務工具 → 結果回填 ChatGPT。Development 分支則走授權 Root 的 local／VS Code remote dispatch。

### C3｜Outlook：今天收件匣未讀信的 metadata，不是讀全文／自動回信

**實際 tool：`get_outlook_unread_today()`，無參數。** Windows COM 初始化後，連 `Outlook.Application`／MAPI 的預設 Inbox（folder 6），依 ReceivedTime 由新至舊掃描，以本機今天日期與 `UnRead` 篩選。回傳 `date`、`count`、`messages`；每封僅 `sender`（SenderName）、`subject`、`received_time`。沒有 Body、附件、寄送、回覆或標成已讀的操作；單筆項目錯誤會略過，因此 count 不是無條件保證完整。

- [註冊名稱，mcp_runtime/mcp_server.py L152–192](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_server.py#L152-L192)
- [COM／Inbox／排序／日期，mcp_runtime/function/outlook_tools.py L37–118](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/outlook_tools.py#L37-L118)
- [metadata、跳過項目與回傳，mcp_runtime/function/outlook_tools.py L120–218](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/outlook_tools.py#L120-L218)

**可說：**「整理今天未讀信的寄件者、主旨與時間。」**不可說：**「摘要每封信全文」、「分析附件」、「跨所有郵件資料夾」、「自動回信」。目前一般政策把此工具列成 AUTO／READ_ONLY，但主旨和姓名仍可能敏感，展示應使用測試信箱。

### C4｜Web automation：執行預先登錄情境，不是 AI 自己上網任意點擊

**實際 tools：** `list_web_automation_scenarios()`；`run_web_automation_test(scenario: str)`。

- `scenario` 在 Server JSON 查找後得到 BAT、report directory、pattern、timeout；使用者／模型不可傳任意 command、BAT path 或 report path。列情境只讀設定；執行情境會啟動 `cmd.exe /c <bat>`。
- Service 在 BAT 前後快照報表（mtime、size、SHA-256），只解析新增／變動報表；沒有新／變動報表會報錯，不能把舊報表當這次執行成功。
- 成敗統計**依報表檔名** `_完成_(成功數-總數)` 解析；總數須 >0 且成功數不大於總數。全成功時不再讀報表內容；有失敗才解析 CSV／XLSX。這不是 AI 獨立判讀整個網站正確性，也不是重新驗證每個 assertion。
- tool function 內部可建出詳細 failure 欄位，但 **真正送往 ChatGPT 的 MCPExecutor allowlist 更窄**：`success`、`process.success/exit_code/duration_seconds`、`summary.passed/failed/total`、每份 report 的 success／counts、failure 的 **`step_number`／`status`**。網站、描述、locator、expected／actual、report 檔名、路徑、stdout／stderr 等不在最終成功結果 allowlist 中。**不可宣稱 AI 現在收到完整 failure 原因或截圖。**

證據：

- [tool 入口與 scenario 查找，mcp_runtime/function/web_automation_tools.py L19–86](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/web_automation_tools.py#L19-L86)
- [設定查找／列情境，infrastructure/web_automation/web_automation_config.py L51–89](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/web_automation/web_automation_config.py#L51-L89)
- [執行／新報表篩選，services/web_automation/web_automation_test_service.py L122–220](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/services/web_automation/web_automation_test_service.py#L122-L220)
- [報表雜湊，services/web_automation/web_automation_test_service.py L259–303](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/services/web_automation/web_automation_test_service.py#L259-L303)
- [檔名 counts／全成功捷徑，services/web_automation/web_automation_report_parser.py L9–11、L60–163](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/services/web_automation/web_automation_report_parser.py#L60-L163)
- [最終傳給 AI 的結果 allowlist，mcp_runtime/mcp_executor.py L414–505](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_executor.py#L414-L505)
- [cmd.exe／輸出限制，infrastructure/process/process_runner.py L12–15、L30–110](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/process/process_runner.py#L30-L110)
- [公開範例僅 example_smoke 與 placeholder 路徑，config.example/web_automation_tests.json L1–10](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/config.example/web_automation_tests.json#L1-L10)

**Demo 邊界：** 實際測試 BAT／網站／報表不是這個公開 clone 提供的完整測試套件；列到 `example_smoke` 不表示 BAT 已存在、更不表示跑過。預先設定的 BAT 自身能做什麼仍須管理，scenario allowlist 不等於 OS sandbox。

### C5｜DB：固定業務 API，不提供任意 SQL；「測試環境」仍須部署保證

**實際 tool：** `search_invs_data(idno=None, branch=None, account=None, acctype=None, max_rows=20)`。

- Service 至少一個條件，預設 20、硬上限 50；Repository 固定表 `invs`、欄位對應、等值 AND 條件與 SELECT 欄位。value／LIMIT 使用 parameter binding。輸出 `count/max_rows/items`，欄位包含 `idno/custname/branch/account/acctype`，不是匿名資料；MCP 一般政策要求每次核准（C7）。
- **不是**讓 AI 生 SQL 或任意連任何表／任意 operator；也**不代表**資料庫連線帳號已實際設 read-only ACL。公開 source 沒有此部署權限證據。

**實際 mutation tool：** `reset_test_user_password(idno: str)`。

- password 取 Server 的 default password 設定，不接受模型指定；固定更新 `mpassdata.pass`，條件 `idno = %s AND pw_type = 'E'`。要求 InnoDB、transaction、`SELECT … FOR UPDATE`、最多一筆，錯誤 rollback；是實際 DB write，不只是產生建議。
- **重要限制：** source 的測試環境命名／文案不能證明 DB 是測試庫。Connection 使用設定的 host/database/user；未見以環境識別強制拒絕 production 的開關。`pw_type='E'` 是 SQL 條件，不能自行解讀為正式／測試環境隔離。

證據：

- [查詢 tool signature，mcp_runtime/mcp_server.py L215–223](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_server.py#L215-L223)
- [Service 條件及 rows 政策，services/invs_service.py L17–20、L66–127](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/services/invs_service.py#L66-L127)
- [固定欄位，repositories/invs_repository.py L11–48](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/repositories/invs_repository.py#L11-L48)
- [WHERE／SELECT／binding，repositories/invs_repository.py L119–308](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/repositories/invs_repository.py#L119-L308)
- [Server password／result，services/mpassdata_service.py L37–123](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/services/mpassdata_service.py#L37-L123)
- [UPDATE、InnoDB、lock／transaction，repositories/mpassdata_repository.py L87–156](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/repositories/mpassdata_repository.py#L87-L156)
- [連線直接使用設定值，infrastructure/mysql/connection.py L21–51](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/mysql/connection.py#L21-L51)

### C6｜VS Code 的授權 Root、讀檔、提案、候選檔、Diff、人審與版本防護

**授權實作：** Session 身分先成立；development mode endpoint 要 `client_type == 'vscode'`，在 Server 記憶體核發綁 Client／Root 的 grant。預設 TTL **90 秒**；擴充每 **30 秒**續期。Workflow scope 再綁 workflow/client/grant；每次工具讀取重驗目前 scope，換 grant／終止 scope 不能沿用舊授權。

**讀取 tools：** `dev.list_files`、`dev.read_file(path, start_line?, end_line?)`；不是 shell／任意 SQL。實作限制為最多 **1000 檔／512 KiB／1000 行**，不是生成文件仍寫的「最多 500 筆」；阻擋 `.env` 等路徑與 symbolic links，但只是路徑 denylist，**不是內容 DLP**。合法名稱的檔案仍可能含敏感內容。

**修改流程：**

1. 模型提出 `[[DEV:PROPOSAL]]`；實作支援 `replace_block` 與 `create_file`，不是 MCP tool。`APPROVAL required` 是格式，不是人已核准的證明。
2. 擴充檢查單一 local workspace、PROJECT 名稱、相對路徑、敏感檔案、未儲存編輯等；`Before` 必須唯一匹配，允許 CRLF／LF 正規化。只有逐行 trim 才匹配時，進入 **preview_only**，不能套用。
3. 組裝完整候選檔，做 JSON parse／TS/JS parse diagnostics／Python `ast.parse`；其他副檔名沒有對等語法驗證。**不是 typecheck、unit test 或 E2E。** 語法不合法仍可產生 Diff 預覽，但禁止套用。
4. 候選檔寫在 extension global storage，原檔尚未動；`vscode.diff` 顯示原檔與候選。正常 UI 在提案回報後會開 Diff；後端 `apply()` 沒有「使用者確實閱讀過 Diff」的證明，不能誇稱系統能強制人已看完。
5. 修改既有檔案：sidebar **「核准並套用」本身就是人工核准**，沒有第二個 modal。新增檔案則另有「核准並建立」modal。
6. Apply 會再驗目前 Grant／Root、dirty state、原檔 SHA-256、候選 SHA-256、候選語法與安全路徑；原檔／候選變更即 conflict，需重新提案。先備份，寫 sibling temp，再 rename；新檔用 `wx`，避免覆蓋已出現的檔案。
7. 成功訊息明示「測試尚未執行」。後續可自動繼續原需求，但每份正式程式碼提案仍須人工核准。

**保護界線：** 是 stale-version 防護，不是 DB 式 CAS／檔案鎖；最後檢查與 rename 之間仍有時序窗口。不能宣稱絕對杜絕所有 concurrent write，也不能說核准代表功能已正確。Parser 無法證明 Before 一定真的來自本次 dev.read_file；這項 provenance 是提示規範，實作主要驗證它與當下原檔的匹配。

證據：

- [VS Code Session／development endpoint，server.py L739–766](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/server.py#L739-L766)
- [90 秒與 Client／Root grant，development_access.py L17–84](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_access.py#L17-L84)
- [scope 目前 grant 驗證，development_workflow_scope.py L80–103](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_workflow_scope.py#L80-L103)
- [擴充 apply grant 重驗，vscode_extension/src/extension.ts L201–250](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/extension.ts#L201-L250)
- [30 秒續期，vscode_extension/src/extension.ts L367–403](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/extension.ts#L367-L403)
- [讀檔上限／denylist／路徑，development_file_reader.py L14–116](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_file_reader.py#L14-L116)
- [remote 讀檔對應限制，vscode_extension/src/remoteDevelopmentToolExecutor.ts L5–78](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/remoteDevelopmentToolExecutor.ts#L5-L78)
- [Before exact／EOL／trim-preview，vscode_extension/src/developmentController.ts L611–723](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L611-L723)
- [候選語法驗證，vscode_extension/src/developmentController.ts L725–914](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L725-L914)
- [收提案／安全檢查／候選／preview-only，vscode_extension/src/developmentController.ts L1199–1539](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1199-L1539)
- [Diff，vscode_extension/src/developmentController.ts L1541–1559](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1541-L1559)
- [收到 pending_review／preview_only 自動開 Diff，vscode_extension/src/extension.ts L175–195](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/extension.ts#L175-L195)
- [Apply／hash／人審語義／備份／rename，vscode_extension/src/developmentController.ts L1631–1854](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1631-L1854)
- [新檔 modal／wx，vscode_extension/src/developmentController.ts L1866–1958](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1866-L1958)
- [逐份核准與自動續行，vscode_extension/src/extension.ts L1179–1257](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/extension.ts#L1179-L1257)

**local／remote 別混淆：** 預設 local development 由 Relay Server 讀可見檔案；remote development 先由 broker 綁 owner／workflow／grant，VS Code claim 後在授權 workspace 執行並回傳。遠端模式不是 Server 可以任意讀取用戶電腦；也不是所有 `dev.*` 都走 stdio。

- [Server local／remote dispatch，server.py L1026–1072](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/server.py#L1026-L1072)
- [Remote claim 的 Session／owner／scope 驗證，remote_development_tool_api.py L41–113](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/remote_development_tool_api.py#L41-L113)

### C7｜工具政策與人工核准：讀取、敏感讀取、mutation、測試不同

| 精確名稱 | 一般政策 | 可用講法 |
| --- | --- | --- |
| `get_outlook_unread_today` | READ_ONLY／AUTO | 一般唯讀可自動，但仍受 Workflow 重複／次數保護 |
| `list_web_automation_scenarios` | READ_ONLY／AUTO | 只列已設定名稱，不執行測試 |
| `search_invs_data` | SENSITIVE_READ／ALWAYS | 唯讀也可能敏感，所以逐次人審 |
| `reset_test_user_password` | WRITE／ALWAYS | 會修改 DB，逐次人審 |
| `run_web_automation_test` | WRITE／ALWAYS | BAT 與網站操作可能有副作用，逐次人審 |

- [完整政策表，tool_loop_guard.py L50–146](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tool_loop_guard.py#L50-L146)
- [unknown／BLOCK／ALWAYS／ONCE_PER_WORKFLOW，tool_loop_guard.py L203–303](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tool_loop_guard.py#L203-L303)

Unknown tool 是 **REQUIRE_APPROVAL**，不是永久拒絕；核准後仍需通過 Server tool discovery。`ONCE_PER_WORKFLOW` 只有 enum／保守 fallback，**沒有「首次授權後同工具永久免問」的實作**。

**身分／核准 routing：** bootstrap 共用 token 換 Bearer Session；核准 endpoint 再檢查 workflow owner、目前 workflow／owner mode，底層 request_id 原子 pop，不能重用同一筆 approval。全域 Chrome 控制另需 Operator credential。這是應用層 token／owner 機制，不是已驗證企業 RBAC、獨立雙人審批或不可冒用的人員身分；Session 的 `client_type` 是 bootstrap client 自己提交，持有共用 bootstrap credential 者不能被當成已驗證的 VS Code 軟體身分。

- [bootstrap 與 Bearer Session，client_session_api.py L26–93](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/client_session_api.py#L26-L93)
- [owner／當前 workflow 核准，client_owner_transport.py L304–376](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/client_owner_transport.py#L304-L376)
- [一次性 pop，server.py L320–345](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/server.py#L320-L345)
- [Operator credential，client_control_api.py L22–35](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/client_control_api.py#L22-L35)

**直接工具 HTTP endpoint 限制：** `/api/vscode/tools/call` 每次建立新 `ToolLoopGuard`，只允許 AUTO／ALLOW 類工具，需 bootstrap token；敏感／寫入不讓它繞過 workflow approval。但這條路由不保留跨呼叫 duplicate／5 次預算，**不能把 Workflow 內的 guard 宣稱為整個 Server 的全域 rate limit**。

- [直接呼叫路由，server.py L857–885](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/server.py#L857-L885)

### C8｜duplicate、budget escalation 與 Development 例外

- 一般 Workflow：工具名稱＋正規化 arguments 做 SHA-256 signature（dict 排序、字串只 trim 頭尾、保留大小寫／list 順序）；已見相同請求，或下一次計數 **>5**，升級為人審，**不是永久阻擋／自動終止**。核准的呼叫也會 record，所以更精確是「已記錄的一般工具呼叫數超過門檻」，不是只算免審那五次。`ALWAYS` 類本來就先要求核准。
- Development read：繞過一般 guard，綁有效 scope 的 `dev.list_files/dev.read_file` 預設 **1000 次**；耗盡後 owner 一次性核准重置，原 pending read 算新額度第 1 次；**不套一般 duplicate 限制**。
- BugList：`dev.buglist_append`、`dev.buglist_update` 在有效 Development Workflow 中自動授權，最多 **200 次**，不用逐筆人審；僅既有 `debug/BugList.csv`、固定欄位／REV 操作，不是一般任意寫檔權。此路徑與正式程式碼修改必須人審不同。

證據：

- [一般 duplicate／budget／record／signature，tool_loop_guard.py L306–438](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tool_loop_guard.py#L306-L438)
- [dev read quota／重置，development_read_policy.py L21–94](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_read_policy.py#L21-L94)
- [Runtime 先分流 dev read／BugList，再一般 guard，relay_runtime.py L822–930](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/relay_runtime.py#L822-L930)
- [拒絕停止 chain、核准 record／quota renew，relay_runtime.py L938–998](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/relay_runtime.py#L938-L998)
- [BugList 200 次／可信身分，development_buglist_policy.py L21–104](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_buglist_policy.py#L21-L104)
- [dispatcher 限定工具及拒絕 model 傳入授權資訊，development_tool_dispatch.py L45–120](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_tool_dispatch.py#L45-L120)

### C9｜有診斷紀錄，但不是完整不可竄改稽核

**已做：** MCPExecutor 配 `execution_id`，記工具名、執行狀態、開始／結束時間、duration、error type；Web BAT 另保存 stdout／stderr／process metadata。Web 工具對外結果有 allowlist，VS Code 預設只記原碼摘要，`debugCode=true` 才把 raw Before／After／candidate 印在本機 Output。

**不能誇大：**

- `ExecutionLogStore` 預設 retention **1 天**、log rotation；cleanup 由 executor 建立時跑一次，不是準時刪除的定時服務。running／損毀 metadata 會保留；不是永久歷史。
- store 支援 `workflow_id`，但 executor 的 `start_execution()` **只傳 tool_name**，所以此 metadata 的 workflow_id 預設 `None`；Runtime 雖另有 workflow/request log，不能說已形成完整持久化關聯。
- `dev.*` 分流不經此 MCPExecutor lifecycle，因此不能說每一種開發工具都有相同 execution_id 稽核。
- 檔案是普通 JSON／rotating text logs，沒看見簽章、append-only／防竄改儲存或逐次核准人的永久身份稽核。`LogStore` 本身是記憶體 list。
- ProcessRunner 保存 bounded raw stdout／stderr，**不是全域去識別化保證**；10 MiB combined output 上限可導致 BAT 被停止，並非無限制「完整輸出」。`process.json` 包含本機路徑；DOM diagnostics／raw code debug 也可能含敏感內容。

證據：

- [executor log dir／cleanup／只帶 tool_name，mcp_runtime/mcp_executor.py L24–65](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_executor.py#L24-L65)
- [metadata／default retention，execution_log_store.py L13–73](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/execution_log_store.py#L13-L73)
- [cleanup／rotation，execution_log_store.py L181–210、L255–265](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/execution_log_store.py#L181-L210)
- [bounded stdout／stderr 與本機 metadata，infrastructure/process/process_runner.py L110–180](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/process/process_runner.py#L110-L180)
- [raw debug opt-in，vscode_extension/src/developmentController.ts L1126–1187](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1126-L1187)
- [記憶體 LogStore，log_store.py L16–35](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/log_store.py#L16-L35)

### C10｜新環境 demo 的重大啟動陷阱：看似 optional 的 DB 設定其實 import-time required

**I＋T：** `mcp_server.py` 無條件 import MySQL tools；該 module 頂層建立 `InvsService()`／`MPassDataService()`，一路建立 Repository／ConnectionFactory／MySQLConfig／DefaultPasswordConfig。Config 立即要求 host／database／user／password／default password。所以即便只想 `list_tools` 或跑 Outlook，也可能在完成註冊前失敗；不是等真的使用 DB tool 才讀設定。

- [無條件 import，mcp_runtime/mcp_server.py L111–139](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_server.py#L111-L139)
- [module 頂層服務，mcp_runtime/function/mysql_tools.py L1–14](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/mysql_tools.py#L1-L14)
- [立即 required MySQL keys，infrastructure/mysql/mysql_config.py L8–33](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/mysql/mysql_config.py#L8-L33)
- [立即 required default password，infrastructure/mysql/set_password/default_pwd_config.py L8–25](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/infrastructure/mysql/set_password/default_pwd_config.py#L8-L25)
- [範例仍標 optional，.env.example L36–44](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/.env.example#L36-L44)
- [未鎖版依賴，requirements.txt L1–14](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/requirements.txt#L1-L14)

本次在 child process 清除相關環境值後 import，**實際失敗 `ValueError: LOCAL_MCP_MYSQL_HOST is required`**。只用合成、不可用的 `db.example.test` 等設定做 stdio discovery 可成功，沒有開 DB connection；**這只能證明 discovery，不得拿假設定去演示 DB 功能。** Outlook COM 模組也無條件 import，因此公開 MCP 子程序仍是 Windows 導向，不是跨平台任意可啟動。

## 2. 業主提供的動機與 repository 證據要分開

**O（owner-provided，非 source 證據）：**「因 Codex 使用額度／quota 考量，想探索用現有 ChatGPT Web 工作流串接本機能力。」可放第 1 張當個人開發起點，標示作者經驗／需求。

**不能由此推論：** 省多少錢／額度、繞過服務限制、無限免費、ChatGPT Web 永遠不受限制、官方保證或授權此自動化方式。本次 source 未見 Codex quota／計費／節省量實作或量測，亦未研究 OpenAI 條款。能由 repository 證明的是「未直接用 OpenAI API、以 Web DOM bridge 運作」及其限制（C1）。

## 3. 本次實際檢查結果（T），不是作者整合驗收報告

環境：Windows；Python **3.12.4**、Node **v24.14.0**、npm **11.21.0**；Git `core.autocrlf=true`。未修改 source 來使測試通過。

| 檢查 | 本次結果 | 能證明／不能證明 |
| --- | --- | --- |
| `python -B -m unittest discover -s tests -v` | **121 tests，120 pass、1 fail** | failure 是 `MigrationTests.test_fresh_setup_copies_safe_example_and_invalid_json_writes_nothing`：產出的 LF bytes 與本機 CRLF `.env.example` 不同；不是「全綠」。其餘涵蓋 env、network decoder/shadow、restore、hygiene、tool settings 等，不等於完整授權／UI E2E |
| `npm --prefix vscode_extension ci --ignore-scripts` | 成功；npm 顯示 **9 vulnerabilities（5 moderate／4 high）** | 是該日 install/audit 輸出，未做 advisory 逐項確認／可利用性判定，未跑 audit fix |
| `npm --prefix vscode_extension test` | **TypeScript compile 成功；18 tests 全 pass** | connection env／Session recovery 等合成測試；不是 VS Code 實際使用者核准套用驗收 |
| `from mcp.server.mcpserver import MCPServer` | 本機已安裝 **mcp 2.3.0** 可 import；`CallToolResult` 欄位包含 `structured_content/is_error` | 不代表 requirements 未來任意 mcp 版本相容 |
| 清掉 MySQL／default-password env 後 import server tool module | **失敗：missing MYSQL_HOST** | 確認 C10 啟動陷阱；未操作 DB |
| 用合成設定建立實際 stdio ClientSession，initialize＋list_tools | **成功列出 5 個一般 MCP tools**，名稱與 C7 相同 | 沒有 call_tool，也沒有操作 Outlook、DB 或 Web BAT；僅 discovery transport 實測 |

Migration failure 對應：[tests/test_env_settings.py L208–215](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tests/test_env_settings.py#L208-L215)。測試 script 對應：[vscode_extension/package.json L78–82](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/package.json#L78-L82)。本機執行結果是本研究觀察，並無 GitHub CI run URL；不應偽裝成遠端 CI 綠燈。

## 4. 建議的誠實 demo：先展示控制，再展示能力

### A. 最低風險主線（需作者事先完成環境）

1. **先交代版本與架構。** 畫出 C2 的兩段協定；展示 `git rev-parse HEAD`。用測試帳號、loopback Relay／CDP，避免投影 `.env`／token／真實客戶資料。
2. **唯讀能力：** 發問「列出目前 Server 已設定的 Web 自動化測試情境」。看 `list_web_automation_scenarios` 真正結果，沒有設定就如實展示設定錯誤；不能硬寫預期回覆。若 Outlook 測試 profile 已驗證，可改問「列出今天未讀信的寄件者、主旨、時間，不要摘要全文」。
3. **敏感／副作用工具：** 只用確認無害的測試 scenario，發問「執行剛才列出的 `<實際名稱>`」。在 approval 出現時先展示工具名、風險與執行範圍；**先拒絕一次**證明沒有執行，再開新 workflow 核准。拿 execution_id 對照 Server log 與 summary；不要讓模型保證能解釋 allowlist 未提供的失敗原因。
4. **Development：** 用單一、可丟棄 workspace 的簡單 Python／JSON 檔。切共同開發模式取得 Root grant；要求先讀指定檔，再只提一個 `replace_block`。展示「原檔未動 → 候選語法／Diff → 退回」；第二次提案才核准套用。核准後手動執行專案自己的測試，畫面分開列「Syntax」「Unit」「E2E」的實際狀態。
5. **安全負例：** 在 pending review 時手動改原檔並存檔，再點 Apply，展示 stale hash conflict／拒絕舊提案；必要時重新讀檔／重新提案。不要為讓 demo 順利而停用比對或語法檢查。

**Demo 是否 ready 的判定：** 本次僅確定 source 分支、離線 compile/tests 與 stdio discovery；以上 UI／外部服務流程皆應在作者機器逐項預演並備錄影。**本研究不能替作者宣告「現在即可端到端現場 demo」。** 若未排除 C10、ChatGPT DOM、私人 BAT 等問題，改用固定版本 source walkthrough＋明確標示的既有錄影，或只示範 discovery／Diff 靜態流程。

### B. 候選命令（在研究對象根目錄的 PowerShell，非本專案）

下列是操作候選，不是全部本次已執行。初始化 `.env`、憑證／帳號操作應由 owner 處理；有既有設定時不要覆蓋。這些指令不包含真實 secret。

```powershell
# 固定版本／前置檢查
 git rev-parse HEAD
 python --version
 node --version
 python -c "import importlib.metadata as m; from mcp.server.mcpserver import MCPServer; print(m.version('mcp'))"

# 離線檢查（本次 Python 有一個 CRLF/LF failure，不能預告全綠）
 python -B -m unittest discover -s tests -v
 npm --prefix vscode_extension ci --ignore-scripts
 npm --prefix vscode_extension test

# 確認設定／SDK／依賴後再啟動；Chrome 首次登入用可見視窗
 .\start_server.bat
 # 另一終端，可選 GUI；VS Code 擴充也能作 client，不需兩者同時演示
 python main.py

# 擴充打包是候選，這次未跑 package／安裝 VSIX
 npm --prefix vscode_extension run package
```

擴充候選 Command Palette：**`Local MCP: Import Connection from .env`**（只選可信任檔案，不投影內容）、**`Local MCP: Test Session Connection`**、**`Local MCP: Open Assistant`**。`Local MCP: Test Session Workflow` 會進入實際 workflow，不當成純離線檢查。[精確 command IDs／titles，vscode_extension/package.json L19–39](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/package.json#L19-L39)。啟動與環境要求的作者文件：[README.md L43–110](https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/README.md#L43-L110)。

候選工具文字（用來辨識畫面／文件，不應宣稱這幾行文字自己就是 MCP wire protocol）：

```text
[[MCP:REQUEST]]
TOOL list_web_automation_scenarios
[[MCP:END]]
```

```text
[[MCP:REQUEST]]
TOOL run_web_automation_test
ARG scenario = "<剛才真實列出的名稱>"
[[MCP:END]]
```

不要讓觀眾直接以任意 SQL、任意 BAT／command、真實 idno 或任意 Root 測試。密碼重設不建議作首次現場主秀；如必須展示，先獨立確認測試庫、一次性測試帳號、DB 權限、復原方式與 approval 拒絕路徑。

## 5. 給 8 張投影片的證據配額（不是完整投影片文案）

| 張次／重點 | 建議核心訊息 | 必須保留的限制／對應證據 |
| --- | --- | --- |
| 1 動機與題目 | 從問答工具走向「受控執行助手」；Codex quota 是作者動機 | O 與 I 分開；不宣稱避開額度或成本成果（§2） |
| 2 真實架構 | Web DOM 文字橋接＋本機 MCP stdio 兩段 | 不畫原生 ChatGPT MCP／userscript（C1–C2） |
| 3 可用工具 | Outlook metadata、固定 INVS 查詢、預設 Web scenario | 無全文郵件／任意 SQL／任意上網操作（C3–C5） |
| 4 授權策略 | 一般讀取、敏感讀取、寫入／測試分級 | 不是所有 read 免問、不是所有 write 逐筆問；BugList 例外（C7–C8） |
| 5 可控開發 | Root grant → 真實讀檔 → 提案 → 候選檔／語法 → Diff | Syntax ≠ unit／E2E；Before provenance 非完全可證（C6） |
| 6 人工掌權 | 核准／退回＋套用前 hash 重驗，展示 stale conflict | 沒有全自動改碼、沒有絕對 race-free 保證（C6） |
| 7 真實 demo | 一般讀取 → 副作用核准 → Diff／退回／核准 | 未預演則只說 source 已有流程，不說 E2E 已驗收（§3–4） |
| 8 收束與下一步 | AI 負責理解／提案；Server 與人負責權限／執行決定 | 私有依賴、C10 import trap、DOM、測試缺口、log 非合規稽核（C9–C10） |

**一句可用結語：**「讓 AI 提出下一步，不讓模型自己決定權限；能執行哪些事、何時必須停下來，由程式政策與人共同決定。」這是本研究對實作的摘要，不是安全認證或未來功能承諾。
