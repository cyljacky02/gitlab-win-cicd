# GitLab 放原始碼，ADO VM1 取碼／建置：下一階段操作指南

## 本輪採用的分工

```text
GitLab：原始碼＋webhook 通知，不執行 GitLab CI jobs
  → ADO VM1 Build Agent：取得指定 commit → 建置／測試 → ADO Build Artifact
  → 授權部署人員選確切版本、放行
  → ADO VM2 Deploy Agent：換版／驗證
```

**本輪不是下載 GitLab CI 產物。** 後續應用產物由 ADO 建置產生；沒有必要為這條路建立 `.gitlab-ci.yml` 或申請 GitLab Runner。

證據與交付分開：

| 階段 | 狀態／本輪提供 |
|---|---|
| GitLab 網頁 Test → ADO agentless probe | 使用者已回報 Webhook 自動 Run／Delay task／整筆 Succeeded；不等於取碼完成 |
| VM1 → GitLab 匿名連通 | 新的手動測試 YAML，待現場跑 |
| VM1 → GitLab 指定 SHA 取碼 | 新的手動取碼 YAML＋一支 CD-owned PS 5.1 script；待現場驗證憑證／TLS／Git |
| 真正應用建置／測試／產物 | **尚未接入**；需要實際 build command、工具鏈／版本、輸出目錄，不能把原始碼 ZIP 說成建置產物 |
| webhook 自動觸發有憑證的取碼／建置 | **本輪不接**；目前未驗章 smoke 不能直接升級成這條有權限的入口 |
| VM2／正式部署 | 不變，本輪不派工、不預先送檔 |

這是對原 FINAL 包「GitLab CI 建好產物，ADO 再匯入」的**明確流程調整**。原包的部署／rollback 仍保留參考，但不能繼續拿 GitLab job ID 當新建置的產物身分。

## 名稱／位置固定，不再額外建立 GitLab 分支

- ADO project：`Deployment`；現有 ADO 測試分支：**`poc/webhook-smoke`**。下面新檔案也放這個已有的 ADO 分支，不合併 main。
- GitLab 專案：`grp-smt-maint/Cathaysec.Com.Smt.Tools.Rs`。
- 這次先**唯讀取得 GitLab 既有 main 的某個完整 SHA**，不 commit、不 push、不建 GitLab 分支、不改其 main／CI include。
- `main` 是允許讀取的 GitLab source branch，`poc/webhook-smoke` 是 ADO 的流程定義分支；不是同一個 repo，也不是同一個版本。
- ADO pool 是 `Default`，但必須再用 **VM1 Build Agent 的 Agent.Name** 限定主機。pool 名不是 agent 名；不能假設 pool 裡永遠只有 VM1。

## 第一步：確認 VM1 Build Agent（已取得名稱）

使用者已確認 VM1 Build Agent 的 **Name 是 `SECSVR004-086T`**。下面兩份 YAML 已填好，不用再替換 placeholder：

```yaml
- Agent.Name -equals SECSVR004-086T
```

可在 ADO **Project settings → Agent pools → Default → Agents** 確認它 online。這是 Agent.Name，不是 Windows service 名或 pool 名；不要把 demand 移除，也不要改成 VM2 Agent。換環境時才重新核對並修改此值。

## 第二步：新增 VM1 → GitLab 的無憑證連通 pipeline

1. ADO **Repos → Files → branch `poc/webhook-smoke`**。
2. 新增根目錄 `/azure-pipelines-gitlab-connectivity.yml`，完整內容用 [此 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)。
3. YAML 已填好 `SECSVR004-086T`，直接 commit 到同一個 ADO 分支。
4. **New pipeline → Azure Repos Git → 同一 ADO repo → Existing YAML**，選 `poc/webhook-smoke` 與此新檔；命名 `GitLab-Connectivity-VM1`。不要覆蓋 `GitLab-Webhook-Smoke`。
5. 手動 Run，此 pipeline 沒有 `resources.webhooks`、variable group 或 secrets，只做：
   - 顯示 Agent.Name／電腦名，核實確實在 VM1。
   - 找 Git for Windows（PATH，或 ADO Agent bundled Git），顯示版本。
   - 對既定 GitLab Git HTTP endpoint 做匿名 GET，不送系統認證、不跟隨 redirect、不記錄 response body。

預期 log：

```text
ADO agent: <你指定的VM1 agent>; computer: <VM1>
git version ...
Anonymous GitLab HTTP status: 200 或 401 或 403
HTTP response received. This does NOT prove authenticated source checkout.
```

401／403 在這一步表示有收到 HTTP response，**不是錯把匿名讀取當成功取碼**；真正的 token 驗證在下一步。timeout 要查 VM1 出站路由／proxy，這和已通過的 GitLab → ADO webhook 是反方向。

若 302 等 redirect：先確認 canonical Git URL／HTTPS 入口；不自動跟去登入頁、不隨便加 PAT。

**請先把這一步的 Agent 名、Git version、HTTP status 回報，再進行憑證步驟。**

## 第三步：決定原始碼的傳輸／唯讀憑證

目前提供的 GitLab URL 是 HTTP；token 和私有原始碼會明文傳輸。預設取碼 script 會在送 credential 前拒絕 HTTP。

### 優先使用已核准的 HTTPS

向 GitLab 管理者取得實際 **HTTPS Git clone URL**（主機名／port／CA 要對），替換下節取碼 YAML 的固定 `SOURCE_REPOSITORY_URL`。Git for Windows 使用 Schannel／Windows 憑證存放區正常驗 TLS；不要 `sslVerify=false`、改 IP 規避 hostname、停用撤銷檢查或關閉驗章。

若單位使用 SSH deploy key，需另外提供 SSH URL／受核實的 host-key，另做相應 checkout 設定；本支 script 只處理 HTTP(S)，不假裝支援所有認證方式。

### 若只有 HTTP：明確的隔離 POC 例外

只有經允許的隔離 POC，才使用**專案限定、短效、測後撤銷**的唯讀 credential，並在手動 Run 明確勾 `allowInsecureHttpLab`。預設為 false；這不是正式環境驗收。不得用個人登入密碼／管理 PAT／可重用正式 token。

即使 GitLab 取碼端改 HTTPS，**ADO 網頁目前也是 HTTP**：在 ADO Library 輸入／傳送 secret 本身同樣要走受核准的管理路徑（HTTPS 或公司允許的隔離管理例外）。不能只保護 Git fetch 那段就宣稱秘密全程已加密。

### 建立專案 deploy token（不改 GitLab 原始碼）

若已有經核准的適用唯讀 credential，可沿用；否則 GitLab 專案 **Settings → Repository → Deploy tokens → Add token**（需 Maintainer／Owner）：[1]

- 名稱建議 `ado-source-poc`；**不要叫 `gitlab-deploy-token`**，避免 GitLab 的特殊名稱自動將它曝露到 CI 變數的行為。
- 設定明確的短效到期日（GitLab deploy token 預設可能不過期）。
- scope 只勾 **`read_repository`**；不勾 registry、package、write。
- 保存平台產生的 **Username＋Token**，下一步只放 ADO Library，**不要貼給助理或放 YAML／URL**。

這次是 Git 協定取碼，`read_repository` 適用；舊 artifact importer 的 `read_api` 不是此需求。Project deploy token 不是 ADO PAT，也不是 webhook secret；其 scope 能力限於該 project 的 Git read，不能因此拿它去用一般 GitLab API。[1]

## 第四步：ADO 的獨立手動取碼 pipeline

### 4.1 新 variable group

ADO **Pipelines → Library → + Variable group**：

```text
gitlab-source-readonly
  GITLAB_GIT_USERNAME = <GitLab deploy token 的 Username>
  GITLAB_GIT_TOKEN    = <GitLab deploy token 的 Token，設為 secret 鎖頭>
```

只授權下面新建的 `GitLab-Source-Read-VM1`，**不要授權 smoke pipeline，也不要開放所有 pipelines**。檢查誰能 queue／edit／改 ADO CD 分支／變更 variable group，credential 不能靠 UI 隱藏當作安全隔離。

### 4.2 同一 ADO 分支新增兩個檔案

到 ADO **Repos → Files → `poc/webhook-smoke`**：

| ADO repo 內的路徑 | 本 repo 對應檔案 |
|---|---|
| `/azure-pipelines-gitlab-source.yml` | [完整 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-source.yml) |
| `/scripts/Get-GitLabSource.ps1` | [完整 script](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1) |

這支 script 沒有其他模組依賴；不要把整套舊 importer／Python／GitLab CI 套件一起複製。YAML 的 VM1 Agent.Name 已填好；HTTPS 可用時更改固定 repo URL。**不修改原本的 webhook smoke YAML。**

建立新 pipeline，選同一 ADO repo／`poc/webhook-smoke`／`/azure-pipelines-gitlab-source.yml`；命名 `GitLab-Source-Read-VM1`。先只儲存，再授權它使用 variable group；空 SHA 的自動初次 Run 可取消，它不應成功取碼。

此 YAML 沒有 webhook resource／排程／CI trigger，固定 `Default`＋VM1 demand，僅限授權操作人員手動執行；有權使用該 pool 的其他 pipelines 也要盤點，不能只靠一份 YAML 當成全域安全防線。

### 4.3 取得並輸入「完整 GitLab commit SHA」

在 GitLab **Code → Commits → branch 選 main → 選一筆 commit → Copy full SHA**，取得完整 40 碼。

- 不用 GitLab pipeline ID／job ID，也不是 ADO CD repo 的 commit。
- 不填 `latest`、`main` 或前 8 碼。
- 取碼 script 只接受該固定 GitLab main 的歷史中可達的 commit；如已 force-rewrite／無法 fetch，就拒絕，不偷換成較新版本。

### 4.4 手動 Run

選 ADO `poc/webhook-smoke`，輸入 `gitlabCommitSha`。HTTP lab 例外只在經允許時明確勾選；HTTPS 正常流程不勾。

成功後應看到：

```text
Checked out exact GitLab commit <40碼SHA> on the selected VM1 agent.
No application build or deployment executed.
```

實際來源位於該 job 的 `$(Pipeline.Workspace)/gitlab-source`，HEAD 是 detached、精確匹配輸入 SHA。不執行 application scripts、Git hooks、LFS smudge 或 submodules；Git symlink 以一般檔案表示，不建立 Windows 連結。有需要時另外明確設計，不自動拿 credential 跨 repo。

ADO 只發布 **`source-provenance` artifact**，內含一份 `source-provenance.json`：repo URL、source ref、GitLab SHA、ADO build ID、ADO tool commit、Git version、時間。**這只是來源取碼證據，不是應用建置產物或已獲部署放行的候選版本。** 不上傳原始碼、`.git`、token 或 response body。

Credential 只透過受限制的 Git 子程序 environment／runtime config 傳入固定 repo 的 fetch，不放 argv／clone URL／檔案；fetch 完成後，verify／checkout 子程序不再帶 credential。Git 不跟隨 redirect、不使用既有 credential helper、不保留 header 在 `.git/config`。這些措施不表示能抵抗同 Windows 帳號或主機管理員讀取執行中程序；VM1 檔案 ACL／Agent 服務帳號與主機權限仍要管控。[2]

## 第五步：確認真實 build contract，才產生 ADO 應用產物

取碼成功後，請提供以下非敏感資料，再把 **固定、受控的 build steps** 接在後面，而不是 webhook payload 傳任意 shell command：

1. 應用技術與工具版本：例如 .NET Framework＋MSBuild，或 .NET SDK＋版本。
2. 實際 solution／project 路徑，以及目前人工或 CI 使用的 build／test／publish 命令。
3. 需要部署的輸出目錄與檔案規格；是否有 NuGet／內部依賴 feed、LFS 或 submodule。

後續應由 ADO：

```text
固定 GitLab SHA → restore → build → test → publish
  → 封裝真正的應用輸出＋SHA-256＋source/build provenance
  → PublishBuildArtifacts@1（Server Container），固定 ADO build ID
```

不得在 build 命令尚未知時把 raw source 壓成 `site.zip` 冒充應用程式；也不從 webhook URL／message 直接執行 script。建置與部署分離，候選版本需要新的放行對象（應用＋環境＋確切 ADO build／hash）。

VM1 同時是 ADO Server 與 Build Agent 時，**執行應用 build code（含 MSBuild targets）就有該 Agent 帳號的主機權限**；本輪取碼不執行它。正式接 build 前，核對 service identity／必要工具／檔案 ACL，production 應評估獨立 build host；不可因同機架設方便就把任意 app code 當成平台信任程式。

## 第六步：之後才接 authenticated webhook，自動建置不等於部署放行

目前 `gitlab-ado-smoke-rs` 是短時未驗章入口；只保留原本 agentless Delay，不加入 variable group／checkout／Agent build／Fetch。

- 本輪以**另外的手動 pipeline**先獨立驗 VM1 → GitLab 讀取，避免把通知驗證、私有來源、工具鏈一起混在同一個錯誤裡。
- 後續需 HTTPS／經核准的管理通道、能互通的來源認證／驗章（必要時受保護 receiver）、固定 project／ref／commit、重送／去重與 queue ACL。
- 原生 GitLab token／ADO HMAC 格式不是直接相容；不能靠移除 Secret 或把 `ref_protected` 當成授權。
- 確認事件的 commit 與真正 build 的 commit 一致，不在每次事件排隊後改抓 main latest。
- 先前 smoke 完成後停用／清理其臨時入口；VM2 在正式部署放行前不接收任何候選檔案或工作。

## 故障排查

| 現象 | 下一步 |
|---|---|
| job 一直 waiting for agent | 查 VM1 agent online、pool Default、精確 Agent.Name demand／pool pipeline authorization；不要改成任意 agent。 |
| HTTP 401／403（匿名 connectivity） | 連通有回應；下一輪才驗 token，不先提高為管理員。 |
| HTTP 401／403（實際 fetch） | 驗 project token Username、到期、read_repository、repo URL、外部授權／proxy 政策；不要拿 read_api 當 Git read。 |
| HTTP refused before credential | 預期安全預設；先確認 HTTPS 或隔離 lab 例外，不關 TLS。 |
| Git 2.31+ required | ADO Agent bundled Git／Git for Windows 需符合 runtime config 支援；依正式工具安裝流程升級，不把 token 放 CLI 繞過。 |
| redirect／登入頁 | 取 canonical Git clone URL／HTTPS endpoint，script 刻意拒絕跟隨 redirect。 |
| SHA 不存在／不屬固定 ref | 核對輸入是 GitLab main 可達的完整 SHA，不是 ADO CD commit；不 fallback 到 latest。 |
| source/evidence output already exists | 用 pipeline clean workspace 或新的隔離目錄；script 不接管／刪除既有目錄，避免誤刪。 |
| build 尚未執行 | 正常：此 pipeline 是 source-only；先完成本輪，再補實際 build contract。 |

## 驗證範圍與官方來源

- 現場 ADO／GitLab 連線、token、實際 Git 安裝與取碼仍須由使用者依序驗收；開發機不能代測公司內網。
- 本機 Windows PowerShell 5.1／Git for Windows 離線測試 **19/19 通過**：以假 credential／本機 Git fixture 核對精確歷史 SHA（不換成最新 tip）、錯誤拒絕、失敗清理、credential 不持久化與 manual-only YAML；另以 loopback HTTP 確認實際 Git client 會送出限定 URL 的暫時 header、401 錯誤經消毒。沒有連線公司 GitLab，也沒有宣稱已建置應用或完成現場取碼。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitLabSource.ps1
```

[1]: https://docs.gitlab.com/user/project/deploy_tokens/
[2]: https://git-scm.com/docs/git-config

- [GitLab project deploy token：Username＋Token、read_repository、期限／撤銷、特殊 CI 名稱][1]。
- [Git config：runtime environment、URL-scoped extraHeader、credential helper、TLS Schannel／redirect][2]。
- [Git fetch](https://git-scm.com/docs/git-fetch)、[git merge-base --is-ancestor](https://git-scm.com/docs/git-merge-base)、[detached checkout](https://git-scm.com/docs/git-checkout)。
- [PublishBuildArtifacts@1：Azure DevOps Server Build Artifact](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines-server)。
