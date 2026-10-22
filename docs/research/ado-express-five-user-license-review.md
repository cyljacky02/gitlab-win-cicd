# Azure DevOps Server Express 五位使用者：跨部門授權審查研究

- **檢索日期：2026-10-22（UTC+08:00）**；由執行環境 `date -Iseconds` 取得，非沿用文件日期。
- **範圍：**多用戶 GitLab CE → Azure DevOps Server Express → Windows VM 部署的授權邊界；不重做 API、功能、測試或安全全面審查。
- **背景：**依委託，POC 已完成；已閱讀 `GLOSSARY.md` 及暫存整合包的 `12-VARIANT-GITLAB-CE-ADO-EXPRESS-5.md`、`02-IDENTITIES-AND-PERMISSIONS.md`。整合包只用來辨識角色與資料流，不作 Microsoft 授權證據，本文不轉錄其真實主機、位址、身分或秘密。
- **判讀標記：**「官方明文」是可定位的原文；「本案判讀」是依原文提出的審查建議；「**待採購／Microsoft 確認**」不是已取得使用權。本研究不是法律意見或個案授權核准。

## 0. 給審查會的結論

1. **「僅 5 位 active users」不能改寫為「最多五人同時在線」或「五個角色帳號供多人輪用」。** Learn 的確使用 *five active users*；Express EULA 則以需 CAL 的存取情境，限制最多五個 **users or devices**，不是以登入 session 或 PAT 數定義授權。[1–3]
2. **必須計算真實使用者／裝置與用途，不能只算 ADO identity。** User CAL 是一位使用者使用任意裝置的權利；共用角色帳號、PAM 借出或單一機器／PAT 代理，均不能單憑減少直接連線數就主張減少必要授權。[2–5]
3. **也不能反過來斷言「每個服務帳號一席」或「所有 GitLab 開發者都一定要 CAL」。** Microsoft 明載 Server service accounts 不需另購授權，Express EULA 也有 Build Services 使用權及「另一整合應用／服務的 pooled connection」CAL 例外；但沒有公開條文逐項認定本案的 CI 觸發、代理人員動作、部署 broker 與觀察資料流。[2,3,6]
4. **此 topology 的總數仍是「待採購／Microsoft 確認」。** 尤其是整合連線例外和一般 multiplexing 規則如何切分。官方文件同時列有整合例外，以及「網站代人觸發 build 仍需個別 CAL」的例子；不得只挑其中一句宣稱所有 PAT proxy 合規，或忽略例外宣稱所有自動化都違規。[2–5]

> **建議簡報用語：**「多用戶 GitLab CE＋ADO Server Express（官方標示五位 active users；依實際人員／裝置、存取用途及 Express 例外逐項盤點）。POC 技術完成不等於授權認定完成；共用角色帳號與整合服務的計數邊界待 Microsoft 書面確認。」[1–6]

## 1. 證據優先序與版本界線

本次直接讀取兩份官方 EULA：**2022** 與**現行未帶年份的 Server**；兩者 Express 段落的五人／裝置、Build Services、兩項 CAL 例外文字一致。兩份文件都有明確的 Express 專段，再另列 **FULL-USE LICENSE TERMS**，不能把後者所有例外直接加到 Express 上。[2,3]

本研究**未辨識現場安裝所適用的確切 EULA／取得通路**，也不把現場直接命名為 Server 2022。正式簽核須附安裝版本、安裝時接受的條款及採購合約。Microsoft licensing guidance 自述 **“it is not your agreement”**；volume licensing 的最終依據是適用合約與 Product Terms，而非本研究或 Learn 功能說明。[4]

| 證據層次 | 本文用途與限制 |
| --- | --- |
| 官方 Express EULA [2,3] | 五人／裝置及 Express 自身例外的核心依據；與 full-use 段分開引用。 |
| 適用通路的合約、Microsoft Product Terms [5,7] | 核對 CAL 指派、multiplexing、訂閱附帶權利；不能假定所有 Product Terms 條款一律取代免費 Express EULA。本文 [7] 頁面選的是 OL，僅作條文示例，非替公司選購通路。 |
| Microsoft Visual Studio Licensing Whitepaper／Guidance [4] | 解釋直接／間接存取、User／Device CAL、整合例外與案例；屬指引，不能擴張 EULA。 |
| Microsoft Learn（Server moniker）[1,6,8–10] | 證明技術身分、功能權限與官方摘要；不是以 API 可呼叫推定合法授權。 |
| Azure DevOps Server pricing [11] | 尋找可採購的 Server 路徑；不是拿 Services 免費方案替代 Express 條款。 |

## 2. 「五位 active users」的原文與不能推導的事

### 2.1 Learn 摘要

官方安裝文件原文：

> “Azure DevOps Server Express licensing limits use to five active users.” [1]

官方下載文件亦寫：

> “limited by licensing agreements to five or fewer active users.” [1]

這兩頁並未在該敘述定義 *active* 的觀察期間、離線多久不計、月底重算、停用後何時能換人或 session 併發算法。**本次未找到可引用的 Express active-user 時窗定義；不得自行補成 30／90 天，也不得改成 concurrent users。**[1–3]

### 2.2 更直接的 Express EULA

兩份 EULA 的 **USE OF AZURE DEVOPS SERVER EXPRESS → Running Instances of the Server Software**：

> “You may use only one instance of the server software assigned to either one physical or virtual operating system environment.”
>
> “For purposes of this Express license grant each user or device connected to the server software is considered a Client Access License (CAL).”
>
> “You may connect any combination of up to five (5) users or devices to access the one instance of the server software **in cases where a CAL is required** …” [2,3]

同一 Express 專段的 **Usage Not Requiring a Client Access License** 僅列：

> “to view, edit or enter work items; or”
>
> “for accessing Azure DevOps Server through a pooled connection from another integrated application or service.” [2,3]

**本案判讀：**不能只讀五人上限而漏掉 *in cases where a CAL is required*；也不能因存在 pooled-connection 例外，就自行宣布任意 CI／portal／PAT 代理都符合它。是否屬上述例外、哪些真實人員／裝置仍在非例外存取路徑內，要逐條確認。[2–5]

### 2.3 User CAL、Device CAL、concurrent 是三件事

| 概念 | 官方原文／依據 | 審查含義 |
| --- | --- | --- |
| User CAL | “Each user CAL permits **one user, using any device** …” [2,3，full-use CAL 段]；Product Terms 訂閱附帶 CAL 為 “the sole use of the Licensed User” [7]。 | 一個人跨電腦，不是多人共享一個登入帳號就成一位。 |
| Device CAL | “Each device CAL permits **one device, used by any user** …” [2,3，full-use CAL 段]。白皮書補充同一 device 一次只能一位使用者。[4，頁 27] | 可研究真正共用裝置的授權，不可把替多人轉送要求的 Web server／GitLab runner 當成一台已授權終端就一筆帶過；白皮書有明確反例。[4] |
| Concurrent user／session | Express 摘要與專段沒有授予「任意人數、最多五個同時登入」的文字。[1–3] | **不採此解讀。** 上線／下線排班不是本研究確認的合法擴充方案。 |
| Concurrent job／deployment | 白皮書另以 “one release at a time” 討論 Release Management 併發。[4，頁 27] | 工作併發與人員存取授權分開；不能把 pipeline 排隊數當成 active users。本文不查核本案 job 配額。 |

**共用角色帳號的結論：**PAM、借出名單、評語及稽核對帳可作內控，但沒有任何上述來源說這些控制能把多位實際使用者合併為一個 User CAL。不可把「五個帳號」報成「五位人員」，也不可拿短期輪替帳號當既定授權模式。[2–5,7]

## 3. 服務身分與實際部署人員：如何盤點

Microsoft Learn 的 **Server service accounts** 文件說：

> “Service accounts don't require a separate license.” [6]

Server 的 access levels 文件更明確：

> “Service accounts don't require a CAL or other purchase.” [8]

這支持區分「基礎設施服務身分」與「使用產品的人」，**但不是任意新建 AD 使用者、取名 service、禁止互動登入後，背後所有人就豁免**。該服務帳號頁列出的脈絡是 Server／Build／Proxy 等部署相依服務；本案自建觸發整合帳號是否落在相同範圍，仍須把用途提交確認。[6，Service accounts、Q&A；2–5]

### 3.1 不同身分不能混為同一席位計算法

| 本案抽象角色／路徑 | 可引用的官方證據 | 本案盤點／判定 |
| --- | --- | --- |
| ADO 應用層、背景工作、資料庫服務 | Server service accounts 文件列出服務及 runtime account，並說不需另購授權。[6] | 獨立列為基礎設施，不直接將每個 OS service identity 算成人員一席。此不等於 Windows／SQL 產品自身免授權。[4，頁 24–26] |
| Agent 註冊人員 | 註冊需要 agent-pool administrator；該身分 “needed only at the time of registration and isn't persisted on the agent”。[9] | 盤點實際做管理的人與管理用途；不要把註冊 PAT 長期等同 agent runtime。是否適用 Express 管理例外另待確認，見下列管理人員。 |
| Agent runtime（Windows service account／機器身分） | Agent 文件：runtime credentials 與註冊 credentials 不同；完成註冊後使用 listener token／job-specific OAuth token。[9] | 不因一台 VM 有數個服務身分就自行加數席，也不因 runtime 無人登入就豁免操作者的人員授權。 |
| Project／Collection Build Service、job token | token 是 “dynamically generated … for each job at run time”；權限由 job scope 與 build service account 權限決定。[10] | 技術執行身分，不是放行人員，也不是「一個 token 可代無限人」的授權證明。 |
| Build server／Build Services | Express EULA 允許 “any number of instances … on any number of devices”；白皮書明載 build server 不需 ADO Server CAL 或 server license。[2,3；4，頁 29] | Build Services 元件本身有明文依據；但不能未經確認就把部署目標、客製 broker、一般 artifact 消費裝置全部類推成 build server。**部署 runtime／target 的精確範圍待採購／Microsoft 確認。** |
| GitLab CI 專用 ADO 觸發身分／PAT | PAT 是 “an alternative password”；“A PAT identifies you”；權限不能超過持有人。[12]；Express 有整合 pooled connection 例外。[2,3] | 另列持有人、程式用途及背後的實際發版／觸發人員。**待採購／Microsoft 確認：**本案機器對機器整合符合哪個例外，或是否實為代理人員存取。不能單憑 PAT 數作總數。 |
| CD repo 維護者、PR reviewer、人工 queue／重跑／管理部署者 | 一般原則是每位直接或間接存取者需 CAL，除特定例外；白皮書指管理／設定 release 對具 CAL 使用者開放。[4，頁 25、27] | 逐一列真實人員，包含代理人及跨部門支援，不以角色群組或共用帳號數代替。PR 審核不是 Express work-item 例外。[2,3] |
| 只核准部署放行的人 | **2022 full-use** 段有 “providing approvals to stages as part of the Release Management pipeline”；白皮書也列核准例外／Stakeholder 免費核准。[2；4，頁 26–27] | **不可直接套到 Express：**2022 與現行 EULA 的 Express 例外清單均未另列 approval；現行未帶年份 full-use 清單也未列此項。是否涵蓋本案 YAML Environment approval、以及是否另做 repo review／讀 artifact，**待採購／Microsoft 確認**。[2,3,8] |
| 純系統管理者 | full-use CAL 段列 “up to two users or devices to administer”；Product Terms 通則限 “solely for administrative purposes”。[2,3,5] | Express 自身例外清單未列此項；不可直接得出「Express 五人外再加兩個 admin」。日常改 CD 程式、queue、核准是否仍屬純管理，也須分開；**待採購／Microsoft 確認**。[2,3] |
| 唯讀觀察者／稽核 | 白皮書有特定 Server Reporting／報表例外，但 Express 專段沒有籠統的 read-only 例外。[2–4] | Readers 是權限，不是免費授權名稱。查 run／log／repo／artifact、看報表、收自動通知要分列，不能全稱「唯讀所以不計」。 |
| 只用 GitLab 的開發者 | 一般 CAL 原則針對直接／間接存取 ADO；Express 又列整合例外。[2–4] | **不是因為出現在 GitLab 名冊就全部計入，也不是沒 ADO 帳號就全部排除。** 辨識誰的操作實際觸發 ADO、誰讀其自動回傳資料；取得整合邊界的書面認定。 |

**建議盤點表（內部受控保存，不放公開簡報）：**實際人員／裝置、具名或共用帳號、直接／間接路徑、動作、是否人員代理、所讀資料、擬援引例外、證據／已持有 CAL、確認人及日期。角色重疊時對人員去重，但一個帳號背後多位人員不可先合併為一人。此為本研究建議的核算工作底稿，不是 Microsoft 已認定的計數公式。[2–7]

## 4. Indirect／multiplexed access：通則與產品例外都要呈現

### 4.1 通則不能忽略

EULA full-use 段原文：

> “Multiplexing or pooling to reduce direct connections with the software does not reduce the number of required CALs.” [2,3]

Product Terms 的 **Multiplexing** 包含硬體、軟體或自動化減少直接／間接使用者或裝置等情境，結論為：

> “does not reduce the number of Licenses of any type that a customer needs.” [5]

白皮書更具體說直接／間接存取都需適當授權，但保留前述不需 CAL 情境；其 **頁 27 Example 1** 描述 intranet 網站讓使用者 **“trigger builds through the Web site”**，即使只有 Web server 直接連 ADO，例子仍要求相關實際人員有 CAL。[4]

**本案判讀：**用共同密碼、機器身分或一個 PAT 接收多人「queue／重跑／檢視」要求，不足以證明只算一位；把 UI 換成 GitLab 按鈕／API 並不自行解除授權問題。[2–5,12]

### 4.2 但 Express 明文確有整合 pooled-connection 例外

Express EULA 直接列出「另一整合 application／service 的 pooled connection」免 CAL；白皮書的 **頁 26** 也說這是為 LOB、ticketing 及 **“other ALM solutions”** 整合減少授權摩擦。[2–4]

**尚無法由公開條文自行解決的交界：**

- GitLab CI 只在候選版本完成時自主送出 ADO 觸發，是否屬整合應用例外？
- GitLab 的人工發版按鈕／重跑／選環境若轉成相同 REST 呼叫，是否變成人員間接存取，而非免 CAL 整合？
- 單純自動通知、回填 run 狀態、完整 log／artifact 鏡像，是否具有不同授權處理？
- 真正 service runtime 不需另購 CAL，是否也完全不占本版 Express 的五人／裝置額度？

**以上均為待採購／Microsoft 確認。** 本次未找到 Microsoft 針對「GitLab CE → PAT → Express queue → 人員 Environment 放行 → Windows agent／broker」的具體適用裁示。不能把通則讀成消滅明文例外，也不能把例外讀成允許所有人透過機器帳號使用 ADO。[2–6]

### 4.3 自動回傳不等於任意免費外部閱覽

Microsoft 的 Multiplexing guidance 對 ADO Server 說，自動提供 files／content／data 的存取或部署需考慮 CAL；其 server-farm 例子要求自動接收端／使用者授權。相對地，白皮書列出人工散發的靜態資料及特定報表免 CAL。[4，頁 25–27；13，頁 5]

**本案判讀：**整合包中的「通知寄到團隊信箱不占授權」不能直接當已證實條款；人工轉交一次性靜態摘要與自動化狀態／log／artifact feed 要分開審查。上述 guidance 的泛用自動化例子也不能凌駕 Express 明文整合例外、Build Services 權利或直接用來斷言所有網站終端用戶必須有 ADO CAL。此資料流界線待書面確認。[2–4,13]

## 5. Stakeholder、Basic 五人、Express 五人的混淆

| 說法 | 查證結果 |
| --- | --- |
| 「Server 可以免費給 unlimited Stakeholders」 | **Server access-level 技術文件有此文字**：“Provides partial access, can assign to unlimited users for free.”[8] 但這不是 Express 專屬授權附約；不能因此宣稱 Express 五位非例外使用者外，任何功能都能再加無限 Stakeholders。[2,3] |
| 「Stakeholder 能核准，所以本案核准者一定不計」 | 功能表說可 “view releases and act on assigned approvals”，不能 author／manage release。[8] 白皮書亦說 Stakeholder 核准不收費。[4，頁 27] **功能、full-use 核准例外、Express 五人上限是不同層；本案精確核准機制待確認。** 同一核准者若兼 PR reviewer，更不能只按核准用途判斷。[2,3] |
| 「Basic 是五個免費名額，超過加錢即可繼續用 Express」 | Server 的 Basic 是 access level；官方 Server 欄位要求配合 CAL／訂閱等 entitlement。[8] EULA **full-use Initial Users** 才列五位免 CAL、第六位起需要 CAL；Express 段是最多五個需 CAL 的 user／device。[2,3] 不足以支持「Express 直接加 CAL 即無限擴充」；先確認是否轉 full-use。[11] |
| 「Services 首五位 Basic 免費＝Express 五位 active users」 | 不是同一規則。白皮書將雲端 account 的 **“five free users”** 與後續 **Azure DevOps Server Licensing** 分章討論。[4] 本研究不以雲端 organization 免費名額推導 Express 使用權。 |
| 「設為 Readers／有 API scope／HTTP 成功＝已授權」 | Access level 控制功能；security groups 控制允許／拒絕動作。[8] PAT 控制驗證與可用操作。[12] EULA 另外規範使用權。[2,3] 三者不可互相代替。 |

**背景文件應在新簡報中重新定性（本研究不修改原檔）：**

- 「每個登入或有 PAT 的帳號算一位」：只能當粗略技術清單，不能當法律公式；須納入 service account 例外及背後人員。[2–6]
- 「agent／內建／機器身分都不算」：Build Services、Server service accounts 有依據，但不能把所有自建部署服務一律類推。[2,3,6]
- 「多人共用角色帳號維持五席」：不能作已合規方案；PAM 內控不改變 User CAL 的一人原則。[2–5,7]
- 「最低四席／五個帳號就完成計數」：目前沒有足夠證據；實際人數、裝置及例外認定未完，不應作採購承諾。[2–7]

## 6. 超過已確認限制時，可提交審查的選項

以下是**待評估選項**，非變更指示或已核准採購。

| 選項 | 授權依據與審查條件 |
| --- | --- |
| **A. 保持 Express，限縮非例外存取範圍** | 依 Express “up to five … users or devices … in cases where a CAL is required”。[2,3] 使用具名人員、列完整代理名單；服務／整合／Stakeholder 各項豁免先取得書面結論，才決定真正餘額。不得以「同時不超過五人」或共用角色帳號控額。 |
| **B. 改 full-use ADO Server＋相應 CAL** | EULA 將 full-use 與 Express 分段；full-use 第六位及後續使用者需 CAL。[2,3] Server pricing 提供傳統 server license／user CAL 向授權經銷商採購的路徑。[11] 由採購確認版本、取得通路、五位初始免 CAL 是否適用，以及實際轉版／支援方式；不要先假定買單一 CAL 即可原樣解除 Express 上限。 |
| **C. 利用公司已持有或新購的合適 Visual Studio 訂閱** | Product Terms 列特定訂閱附一份 Server License 及一份專屬 Licensed User 的 User CAL。[7] 核對版本、組織歸屬、持有人與有效狀態；不是一位訂閱者可替全隊共用 CAL。Windows／Windows Server 等相依產品另行核對。[4,11] |
| **D. 依官方 Server 路徑按月購買** | **Server pricing** 明列透過 Visual Studio subscriptions 取得 server license／subscriber CAL，再替其他人購買 Basic 或 Basic + Test Plans，並有 Server 使用權說明。[11] 這是可請採購報價的 Server entitlement 路徑，不代表一般 Services 免費 Basic 自動授權 Express 擴充；適用現場版本與條款仍需書面確認。 |
| **E. 真正的 Device CAL 使用模式** | full-use EULA 及白皮書允許 User／Device CAL 混用。[2–4] 僅在實際共用裝置與使用方式符合條款時研究；不能把 GitLab／Web proxy／runner 當 device CAL 的多人聚合漏洞。亦先確認 Express／full-use 選型與公司通路可購 SKU。[4，頁 27] |
| **F. 重劃治理工具邊界** | 若無法確認或接受新增 CAL 成本，可另案評估讓不應存取 ADO 的人員完全不走其直接／間接操作及資料路徑，再重畫放行與稽核設計。這是架構替代提案，不是「把入口移到 GitLab 就免授權」；仍須對照整合例外及 multiplexing 規則。[2–5] |

任何選項都不能只檢查 ADO：白皮書明載 OS license，並在適用的 Windows Server Server/CAL 情境要求 Windows Server CAL。ADO 的 service／work-item／integration 例外不自動豁免其他產品。本研究不計算 Windows、SQL 或 RDS 的個案金額。[4，頁 24–26；11]

## 7. 送採購／Microsoft 的書面問題清單

請附**去識別化拓撲與動作清單**，不要只問「五帳號可不可以」。要求回覆指出適用版本、條款標題、例外及限制：

1. **版本／通路：**本實例適用 [2]、[3] 或其他哪份 EULA？有無合約修訂？若屬 volume licensing，應選哪個 Product Terms program／日期？
2. **active users：**五位如何核算？有無 active 時窗、離職／調職／代理替換規則？User 與 Device 混合怎麼記錄？不以 concurrent sessions 為前提。
3. **服務帳號：**Server 內部服務、Build Service、agent listener／job token、自建 GitLab 觸發帳號、部署 agent／broker 各是否需 CAL／是否占 Express 額度？請分別作答，不能以名稱通稱 service。
4. **整合例外：**GitLab CI 的自主事件通知與人工按鈕／重跑／選目標，哪些符合 Express pooled connection 例外？白皮書網站觸發 build 案例與本案差異為何？
5. **放行與管理：**Express 是否可援引 full-use 的純管理兩人或 Release Management approval 例外？目前具體的 Environment approval 是否屬該例外？同一人還做 PR review／看 log／下載 artifact 時如何處理？
6. **資料與目標：**自動通知信、GitLab 回填狀態、log／artifact 鏡像、部署目標與 broker 是否另有直接／間接存取授權？哪些可援引報表、Build Services 或整合例外？
7. **擴充：**超過確認後的額度，須轉 full-use 嗎？所需 server license、CAL 版本、既有訂閱可抵用權利、月付選項、Windows／SQL 相依授權與可接受的證據為何？

**建議簽核門檻：**取得可追溯的 Microsoft／授權採購書面答覆、完成實際人員／裝置映射及 entitlement 清單，再把「預定五位」改標為「已確認合規」。POC 功能 PASS、REST 成功、權限拒絕測試及五個帳號的截圖均不替代此門檻。[2–5,8,12]

## 8. 官方來源索引（原文短引用）

除明載版本的 EULA／PDF 外，線上頁面可能持續更新；以下皆於 **2026-10-22** 檢索。正文的 `[n]` 對應本索引，原文標題亦供查找。

### [1] Express 官方摘要（Server，不是 Services 免費方案）

- Microsoft Learn：[Install and configure Azure DevOps Server](https://learn.microsoft.com/en-us/azure/devops/server/install/get-started?view=azure-devops-server)，Installations for evaluation or personal use。
  - 引用：“Azure DevOps Server Express licensing limits use to five active users.”
- Microsoft Learn：[Azure DevOps Server Download](https://learn.microsoft.com/en-us/azure/devops/server/download/azuredevopsserver?view=azure-devops-server)。
  - 引用：“limited by licensing agreements to five or fewer active users.”

### [2] Azure DevOps Server Express 2022 EULA（主要條款）

- [官方條款入口](https://visualstudio.microsoft.com/license-terms/azure-devops-server-2022/)
- [入口內嵌的官方 DOCX](https://visualstudio.microsoft.com/wp-content/uploads/2022/11/ENU_EULA.1033.docx)，EULA ID：`AZUREDEVOPS2022_ENU`。
- Express 專段：
  - “up to five (5) users or devices … in cases where a CAL is required”
  - “any number of instances of Azure DevOps Server Build Services … on any number of devices”
  - “for accessing Azure DevOps Server through a pooled connection from another integrated application or service.”
- **另屬 full-use 的段落，勿默認擴張至 Express：**
  - “Each user CAL permits one user, using any device”
  - “The sixth and other additional users each require a CAL”
  - “up to two users or devices to administer the software”
  - “for providing approvals to stages as part of the Release Management pipeline”
  - “Multiplexing or pooling … does not reduce the number of required CALs.”

### [3] 現行未帶年份 Server／Express EULA（交叉核對）

- [官方條款入口](https://visualstudio.microsoft.com/license-terms/azure-devops-server/)
- [入口內嵌的官方 DOCX](https://visualstudio.microsoft.com/wp-content/uploads/2025/11/ENU_EULA.1031.docx)，EULA ID：`AZUREDEVOPS_ENU`。檔名雖為 `1031`，實際內容為英文標題 `MICROSOFT SOFTWARE LICENSE TERMS`。
- Express 引用與 [2] 相同：“up to five (5) users or devices … in cases where a CAL is required”；免 CAL 清單是 work items 與另一整合 application／service 的 pooled connection。
- full-use 仍有 User／Device CAL、初始五位、純管理及 multiplexing 段；其 Usage Not Requiring a CAL 清單未列 [2] 的 stage approval 項。此差異是不能混版本、混段落推論的理由，不代表本研究已判定現場核准者需／不需 CAL。

### [4] Microsoft Visual Studio Licensing Whitepaper／Guidance

- [官方 PDF：November 2025](https://visualstudio.microsoft.com/wp-content/uploads/2025/11/Visual-Studio-Licensing-Whitepaper-November2025.pdf)
- [官方網頁版 Visual Studio Licensing Guidance](https://www.microsoft.com/licensing/guidance/Visual-Studio)（持續更新，版本可能晚於上述 PDF）。本文涉及頁碼的引文以 PDF 為準。
- 頁 24：“Server/Client Access License (CAL) licensing model”；“except as noted” 的 Express 適用提醒。
- 頁 25：“each user or device directly or indirectly accessing Azure DevOps Server must have a User CAL or a Device CAL.”
- 頁 26：“other ALM solutions”；“Viewing static data that has been manually distributed outside of Azure DevOps Server”；“Providing approvals to stages as part of the Release Management pipeline.”
- 頁 27：“other than the When a Client License is not Required scenarios”；網站代人 “trigger builds” 的 CAL 案例；“There is no charge for users whose access level is configured as Stakeholder to approve releases.”
- 頁 29：“no Azure DevOps Server CAL or server license is required for the build server.”
- Disclaimer：“it is not your agreement”；“the terms and conditions of your agreement control.”

### [5] Microsoft Product Terms：通用軟體條款

- [Universal License Terms for all Software](https://www.microsoft.com/licensing/terms/product/ForallSoftware/all)，Multiplexing、Administrative and Support Rights。
- 引用：“reduce the number of devices or users that directly or indirectly access or use a Product” 仍 “does not reduce the number of Licenses of any type”。
- 管理例外引用：“two users without CALs solely for administrative purposes”。適用性須配合實際合約，不自行加到 Express 額度外。

### [6] Microsoft Learn：Server service accounts

- [Service accounts and dependencies](https://learn.microsoft.com/en-us/azure/devops/server/admin/service-accounts-dependencies?view=azure-devops-2022)，Service accounts、Q&A。
- 引用：“Service accounts don't require a separate license.”
- 文件列 Server Web Services、background job、Build、Proxy 等服務脈絡，不是對所有客製 PAT proxy 的個案授權裁示。

### [7] Microsoft Product Terms：Visual Studio 訂閱附帶 Server／CAL

- [Visual Studio Subscriptions — OL](https://www.microsoft.com/licensing/terms/productoffering/VisualStudioSubscriptions/OL)，License Grant for Azure DevOps Server 2022。
- 引用：“one Server License for Azure DevOps Server and one Azure DevOps Server User CAL”；“The CAL is for the sole use of the Licensed User.”
- 此 URL 顯示 OL program，正式採購須另選公司適用 program／合約日期。

### [8] Microsoft Learn：Server access levels（注意頁內 moniker）

- [About access levels](https://learn.microsoft.com/en-us/azure/devops/organizations/security/access-levels?view=azure-devops-2022)，使用 Server／2022 內容，不採雲端專屬欄位。
- 引用：“Access levels supplement security groups”；Server Stakeholder：“can assign to unlimited users for free”；Basic：“Assign to users with an Azure DevOps Server CAL”。
- Service account access：“Service accounts don't require a CAL or other purchase.”
- 功能表：“Stakeholders can view releases and act on assigned approvals, but they can't author release pipelines or manage releases.”

### [9] Microsoft Learn：Agent 的註冊與 runtime 身分

- [Azure Pipelines Agents](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/agents?view=azure-devops-2022)，Communication、Authentication、Interactive vs. service，援引 Server 適用段落。
- 引用：“needed only at the time of registration and isn't persisted on the agent”；“listener OAuth token”；“job-specific OAuth token”。
- Windows runtime credentials：“different from the credentials that you use when you register the agent”。

### [10] Microsoft Learn：Build Service／job token

- [Understand job access tokens](https://learn.microsoft.com/en-us/azure/devops/pipelines/process/access-tokens?view=azure-devops-2022)，Scoped build identities、Manage build service account permissions。
- 引用：“dynamically generated … for each job at run time”；“permissions you set on project or collection build service account”。

### [11] Microsoft 官方 Server 採購路徑

- [Azure DevOps Server Pricing](https://azure.microsoft.com/en-us/pricing/details/devops/server/)，頁面標題為 Azure DevOps Server 2022 licensing。
- 引用：“pay month-to-month through Azure”；“one server license plus a user CAL for the subscriber”；“Buy Azure DevOps Basic or Basic + Test Plans for your other users”；“order through your authorized Microsoft software reseller.”
- 本文只引用其明列的 **Server** entitlement／採購路徑；不以 Services 首五位免費、價格或 cloud hosted-job 配額取代 Express 條款。

### [12] Microsoft Learn：PAT 是驗證憑證，不是授權單位

- [Use personal access tokens](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops-2022)，開頭及 Prerequisites／Server 建立步驟。
- 引用：“A personal access token (PAT) is an alternative password”；“A PAT identifies you”；“A PAT can't grant more permissions than its owner has.”
- 本文不引用該頁的雲端 Entra／managed identity 建議來宣稱 Server Express 一律支援，也不使用雲端 PAT 政策推定 Server 授權。

### [13] Microsoft Multiplexing guidance／licensing brief

- [現行官方網頁：Multiplexing Licensing Guidance](https://www.microsoft.com/licensing/guidance/Multiplexing)，Azure DevOps Server、Examples 1–2。
- [官方 PDF：Multiplexing—Overview，March 2021](https://download.microsoft.com/download/3/D/4/3D42BDC2-6725-4B29-B75A-A5B04179958B/Licensing_Brief_PLT_Multiplexing.pdf)，頁 5。
- 引用：“Any device/user that accesses or deploys files, content, and data that is made available in an automated way … requires a CAL”；人工傳遞對照：“manually posted or emailed files”。
- 這是一般間接存取風險的證據；須與 Express 產品例外及適用合約併讀，不能以這段舊 brief 逕自否定 [2,3] 的明文例外。

### 檢索與擷取紀錄

以官方網域查詢 Express active users、User／Device CAL、service accounts、pooled／multiplexing、Server 採購路徑；排除經銷商及社群答覆作結論依據。EULA 入口的可讀擷取未顯示內嵌內容，因此追蹤其 Office iframe 至上述官方 DOCX，於記憶體解壓 `word/document.xml` 查讀；PDF 以記憶體文字擷取核對頁碼及案例。沒有把頁面摘要當作完整 EULA，也沒有為本研究下載或改寫其他 repo 檔案。
