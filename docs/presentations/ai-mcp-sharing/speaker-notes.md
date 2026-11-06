# AI × MCP：打造可控、可授權的 AI 智慧執行助手｜講者講稿

6 頁，約 15 分鐘（含 Demo）。

原始碼基準：`280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6`；2026-11-06 原始碼查核；未執行現場整合 Demo。

這是口語講稿，不是 Demo 已執行的紀錄；資料外送與系統操作須先獲公司允許。

## 1｜AI × MCP：打造可控、可授權的 AI 智慧執行助手

建議 2 分鐘。

【開場】今天想分享的，不是另一個聊天模型，也不是要大家換掉原本的 AI 工具。我們遇到的問題其實很日常：行內 Codex 的額度有限，不可能所有需求都依賴同一個工具。另一方面，我們目前使用的 Chat 網頁版很會解釋、整理與推理，但還沒有直接接入自己的地端作業環境。

所以常出現這種情境：AI 告訴我怎麼測，我自己去執行；AI 給我一段程式，我自己貼進 VS Code；出了錯，再把訊息貼回去。真正花時間的，是這段來回接力。

我們因此做了 local-mcp，把 Web 與地端之間的連線接起來，再把既有作業逐步封裝成工具。想做到的只有一句話：讓 AI 從告訴我怎麼做，進一步變成在授權範圍內幫我做。

【講者提醒，不必逐字念】額度有限是分享者提供的背景，不是 GitHub 能證明的公司政策；也不主張 Web Chat 無限額、免費、能取代 Codex，或所有 Chat 產品都無法使用工具。沒有節費／效率量測，不提供虛構百分比。

【轉場】我們想借用 ChatGPT Web 的腦，替它接上能做事的工具。

來源：
- 行內 Codex 額度與使用方式：分享者提供的背景，非公開程式碼證據。
- https://github.com/cyljacky02/local-mcp/tree/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6

## 2｜借用 ChatGPT Web 的腦，接上地端做事的能力

建議 1.5 分鐘。

【口語主線，約 90 秒】我們的構想很單純：想借用 ChatGPT Web 的腦，讓它理解需求、拆解工作，再協助我們處理與實作，而不只是告訴我們怎麼做。

那怎麼接起來？我們選擇用本機 Playwright 連接 Chrome，讀取 Web Chat 的回應，也把工具結果送回對話。中間由自建 Relay 解析約定的工具請求、檢查政策與調度；需要人確認的就停下來問人，再交給地端 MCP 工具或開發通道處理。

最後，真實執行結果回到 Web，AI 才能繼續分析、提出下一步或回覆我們。左邊負責想，右邊負責做，中間把兩邊受控地串起來。這張圖看懂就夠了，今天不展開每個技術元件。

【轉場】有了這條連線，就可以逐步加能力；下一頁只看三類，實際怎麼操作留在 Demo。

【備用技術說明，不必逐字念】圖為邏輯分工，不是網路拓樸。Playwright 透過 CDP 連 Chrome、擷取 ChatGPT DOM，再由文字 parser 辨識工具請求；不是 ChatGPT Web 原生 MCP。一般工具使用 MCP stdio 子程序；dev.* 另行分派，local 模式由 Relay 讀可見的授權檔案，remote 模式由 VS Code 在授權工作區處理，不把每一段都稱為 MCP。登入、DOM 改版與協議格式仍是依賴，不能保證任意 Web AI 隨接即用。

來源：
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/worker.py#L240-L272
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/chatgpt_client.py#L511-L607
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/response_handler.py#L118-L220
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_executor.py#L223-L315
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/server.py#L1026-L1072

## 3｜從日常作業到程式實作，把能力接給 AI

建議 1 分鐘。

【口語主線，約 1 分鐘】目前可以先用三類能力來理解。第一，Web 自動化測試：讓 AI 呼叫已經設定好的測試情境，跑完再整理結果。第二，日常資訊與查詢：像是整理 Outlook 今日未讀信件資訊，或透過固定工具查資料。第三，開發協作：加上 VS Code Extension，讓它讀取授權專案、提出修改，由人確認後再套用。

這裡先知道能幫忙做什麼就好，不在投影片逐步解說功能。待會我們用測試與一個小程式修改，直接看它如何做事。

【備用界線，不必逐字念】Outlook 目前回傳寄件者、主旨與時間，不是全文、附件、寄信或刪信；業務查詢使用固定工具與參數，不是任意 SQL。Web 測試跑預先設定的 BAT 情境，公開 repo 未附完整可跑套件；回傳 AI 的 failure 主要為步驟編號／狀態，不能捏造根因。開發候選語法檢查支援 JSON、TS／JS、Python，不是編譯或功能測試；詳細 Diff、駁回、核准與版本防護移到 Demo。唯讀結果與原始碼回傳 Web AI，仍涉及資料外送。

來源：
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/outlook_tools.py#L120-L218
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/function/web_automation_tools.py#L19-L86
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/repositories/invs_repository.py#L119-L308
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1199-L1559

## 4｜接得上，更要管得住

建議 1.5 分鐘。

【口語主線，約 90 秒】接上能力之後，還要管清楚範圍。第一，開發操作限定在授權的專案，不是整台電腦。第二，依工具分級，敏感查詢、密碼重設與測試需要人確認，部分唯讀工具可以自動。第三，程式修改先看 Diff，人接受才套用，而且套用前會重新確認檔案版本。第四，留下工作狀態與診斷，讓我們知道執行到哪裡；一般工具重複或超額呼叫會轉人工。

但受控執行不等於資料就可以外送，仍要符合公司的 AI 與資安政策。核心是：允許 AI 在明確範圍協作，不是把整台電腦交給它。接下來直接 Demo，看看這些控制怎麼出現在操作裡。

【問答備用，不必逐字念】專案路徑限制不能自動套到所有 MCP 工具，新增工具要定義自己的邊界。不是所有寫入都逐筆核准：有效 Development Workflow 下的固定 debug/BugList.csv 受限寫入有自動授權例外。一般 Workflow 的重複／次數政策不是全 Server rate limit；dev 讀取有自己的額度。執行紀錄預設保留一天，並非永久、防竄改或所有 dev 工具共用的稽核鏈。這次查核原始碼，不是正式資安驗收；企業身分、網路、憑證、惡意提示、資料外洩與正式部署仍需另外驗證。

來源：
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tool_loop_guard.py#L50-L146
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/tool_loop_guard.py#L306-L438
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/development_buglist_policy.py#L21-L104
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/execution_log_store.py#L13-L73

## 5｜看它如何做事，也看人如何保留控制權

建議 8 分鐘。

【切換畫面前】先說明：今天使用測試資料與預先驗證的環境，不讀真實郵件、查正式業務資料或操作正式系統。這頁是展示計畫，不是本次製作已跑過的成功紀錄。前面沒有逐項展開的能力細節，現在配著畫面說。

【Demo A，約 3 分鐘】先說這不是任意操作網站，而是呼叫預先設定的情境。輸入『幫我執行指定測試情境，整理成敗與失敗步驟；資訊不足請明說』，填入已彩排的名稱。讓大家看到工具請求與人工確認，再核准執行。結果回來後，核對總數、成功／失敗與失敗步驟編號／狀態，說明資訊不足就不能猜根因；不要捏造未回傳的錯誤描述、locator 或截圖。也不要把程序跑完等同所有測試成功。工具不可用就切已標示的預錄／截圖；沒有備份就講流程，不捏造成功。

【Demo B，約 5 分鐘】在一次性測試專案建立有效開發授權，先讀小檔案，再提出一個單檔低風險修改。以此畫面說明：它讀真實檔案，而不是只給人一段程式自行複製貼上；先形成候選檔，原檔還沒動。展示候選語法狀態與 Diff，讓大家看清楚差異。可先駁回一次，確認原檔未變；重新提案後再核准。既有檔案側欄『核准並套用』本身就是人審，沒有第二個 modal；新增檔另有確認。套用後讀回檔案或看 Git diff，分開說已套用、語法檢查與功能測試；沒有執行的檢查就是尚未執行。

【開發細節，配畫面選講】候選語法檢查支援 JSON、TS／JS、Python，不是 typecheck、專案編譯或 unit／E2E。Diff 供人檢視，但程式不能證明人真的看完。套用前比對原檔與候選版本，避免舊提案誤覆蓋；不是跨程序檔案鎖或絕對 race-free 保證。若時間足夠，可在 pending review 後改原檔並存檔，展示舊提案被拒絕，再重新讀檔／提案。

【中斷原則】工具無回應、授權失效、結果不明或版本衝突都停下來如實說明，不盲目重試、不繞過檢查，也不拿正式環境救場。完整準備與備案見 demo-runbook.md。

【轉場】我們要的不是 AI 自己決定權限，而是它能協作、人仍掌握決定權。

來源：
- demo-runbook.md
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/config.example/web_automation_tests.json#L1-L10
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/mcp_runtime/mcp_executor.py#L414-L505
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L725-L914
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/developmentController.ts#L1631-L1854
- https://github.com/cyljacky02/local-mcp/blob/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6/vscode_extension/src/extension.ts#L1179-L1257

## 6｜從一個聊天工具，走向可擴充的執行助手

建議 1 分鐘。

【收斂】對同仁來說，最直接的價值，是少一些在聊天視窗、系統與工具之間搬來搬去的接力。對團隊來說，可以把已有的工具逐步封裝接入，而不是每次重新開發一個入口。對管理來說，AI 能做什麼、什麼時候必須人確認，應該有明確界線。這些是希望達成的價值，不是已量測的改善比例。

最後兩句話：成本限制是起點，讓 AI 真正參與工作才是目的。我們不是讓 AI 自由控制電腦，而是讓它在授權下，成為能幫忙做事的助手。

【問答備用】若問能不能取代 Codex：這是補充工作入口，不保證模型品質、上下文與 IDE 整合相同。若問是不是全部在本機：不是；Web AI 在外部服務端，工具結果會回到 Web，資料外送仍須允許。若問是否直接正式導入：還需部署、身分、資安、資料與實機驗證，不能因原始碼有控制就視為驗收完成。

來源：
- https://github.com/cyljacky02/local-mcp/tree/280b6257cc4d59ee7d0bdbb77717fa07de2ba7b6
- ../../research/local-mcp-ai-sharing-source-notes.md
- 效益與推進方向為分享敘事，非已量測成果。
