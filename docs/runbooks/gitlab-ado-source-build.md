# ADO VM1 → GitLab：先驗連通與指定 SHA 取碼

> 本檔保留原路徑供既有連結使用；本次 POC **不做應用建置／編譯**。完整目標與 VM2 設定見[原始碼 ZIP 交付指南](gitlab-ado-file-delivery.md)。

## 固定來源與執行位置

| 設定 | 值 |
|---|---|
| GitLab repo | `http://10.93.19.25/grp-smt-maint/Cathaysec.Com.Smt.Rayin.git` |
| GitLab source ref | `refs/heads/poc/cicd` |
| ADO project／repo | 沿用 `Deployment` 與現有測試 repo |
| ADO YAML branch | 沿用 `poc/webhook-smoke`，不是 GitLab branch |
| VM1 pool／Agent.Name | `Default`／`SECSVR004-086T` |

不新增 GitLab branch、不改 main／共用 CI include；不要求 GitLab Runner、job ID 或 GitLab artifacts。VM1 同時承載 ADO Server，本次不執行應用程式碼、build targets 或 application scripts。

已回報成功的是先前 Tools.Rs 專案的 GitLab 網頁 Test → ADO agentless probe。**Rayin 的 VM1 連通、token 取碼、真 push 與 VM2 放檔仍待現場驗收。**

## 第一步：VM1 → 新 GitLab project 的匿名連通

1. ADO **Repos → Files → 現有 repo → branch `poc/webhook-smoke`**。
2. 新增或更新根目錄 `/azure-pipelines-gitlab-connectivity.yml`，完整內容用[此 YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-connectivity.yml)。本版 URL 已改為 Rayin。
3. 若已有 `GitLab-Connectivity-VM1`，沿用，不重建；若尚未建立，**New pipeline → Azure Repos Git → 同一 repo → Existing YAML**，選同一分支與檔案。
4. 手動 Run，預期只有 Git version 與匿名 HTTP response，不帶 secret、不 checkout、不使用 VM2。

```text
ADO agent: SECSVR004-086T; computer: <VM1>
git version ...
Anonymous GitLab HTTP status: 200 或 401 或 403
HTTP response received. This does NOT prove authenticated source checkout.
```

401／403 只代表收到 HTTP 回應，不代表 token 可讀 repo。302 先確認 canonical clone URL／HTTPS；timeout 查 VM1 出站路由／proxy。這與已通過的 GitLab → ADO 是反方向。

## 第二步：唯讀 Git credential 與傳輸

優先使用經核准的 HTTPS clone URL，正常驗 TLS／CA；不要關閉 `sslVerify` 或 hostname 驗證。目前提供的 URL 是 HTTP，取碼 script 預設會在送 credential 前拒絕。

若現場只有 HTTP，僅可在**明確允許的隔離 POC**使用短效專案唯讀 credential，手動 Run 勾選 `allowInsecureHttpLab`。Git token 和原始碼會明文傳輸；測後撤銷 token。ADO Library 管理頁若也是 HTTP，輸入 secret 的管理通道同樣要單獨核准。

在 **Rayin 專案**使用已有的合適唯讀 credential，或由有權人員建立 project deploy token：[1]

- GitLab **Settings → Repository → Deploy tokens → Add token**。
- 名稱例如 `ado-source-poc`；不要用有特殊 CI 行為的 `gitlab-deploy-token`。
- 設明確短效到期日；scope 只勾 `read_repository`。
- 保存平台產生的 Username＋Token；**不貼給助理、不放 YAML、Git URL 或 GitHub**。

先前 Tools.Rs 的 project deploy token 不應假定可讀 Rayin。Git 協定取碼需要 `read_repository`，不是舊 importer 的 `read_api`，也不是 ADO PAT。

ADO **Pipelines → Library → variable group `gitlab-source-readonly`**：

```text
GITLAB_GIT_USERNAME = <Rayin deploy token Username>
GITLAB_GIT_TOKEN    = <Token，設為 secret 鎖頭>
```

只授權受控的取碼 pipeline，不勾所有 pipelines，**不授權未驗章 smoke**。若此 group 已被其他工作使用，先盤點影響，再更新或另建專用 group 並同步 YAML，不能覆蓋仍在使用的 credential。

## 第三步：手動取碼，不是 ZIP／交付 pipeline

在同一 ADO repo 的 **`poc/webhook-smoke`** 新增或更新：

| ADO repo 路徑 | 完整內容 |
|---|---|
| `/azure-pipelines-gitlab-source.yml` | [YAML](../../cicd/gitlab-ado/ado/azure-pipelines-gitlab-source.yml) |
| `/scripts/Get-GitLabSource.ps1` | [PowerShell 5.1 script](../../cicd/gitlab-ado/ado/scripts/Get-GitLabSource.ps1) |

沿用已建的 `GitLab-Source-Read-VM1`，或以同一 repo／分支／YAML 新建此 pipeline。先儲存，再僅授權它使用 variable group。保留 VM1 demand：

```yaml
pool:
  name: Default
  demands:
    - Agent.Name -equals SECSVR004-086T
```

1. GitLab **Code → Commits → branch 選 `poc/cicd` → Copy full SHA**。
2. ADO 手動 Run，branch 選 **ADO 的 `poc/webhook-smoke`**。
3. `gitlabCommitSha` 填 GitLab 完整 40 碼 SHA；不填 `latest`、分支名、短 SHA 或 ADO repo 的 commit。
4. 只有已核准 HTTP 隔離例外才勾 `allowInsecureHttpLab`。

成功 log：

```text
Checked out exact GitLab commit <40碼SHA> on the selected VM1 agent. No application build or deployment executed.
```

script fetch 固定 `poc/cicd`，核對 SHA 可達性並以 detached HEAD checkout；不把排隊後的新 tip 偷換成所選版本。若 SHA 不存在／被 force rewrite，失敗即停止。

此 pipeline **只發布 `source-provenance` metadata artifact**，包含 repo、ref、SHA、ADO build ID／工具 commit 等；沒有 ZIP、VM2 job 或放檔。取碼 credential 只在 fetch 子程序的 URL-scoped runtime config 中存在，不保留到 `.git/config`／URL／argv；不執行 app scripts、hooks、LFS smudge 或 submodules。[2]

## 第四步：使用新的原始碼 ZIP 交付 pipeline

不要求 solution、SDK、MSBuild 或 publish command。完整流程已另提供：

```text
已驗 SHA 的原始碼 → ZIP＋SHA-256／provenance → ADO Server Build Artifact
  → test-deploy-agent / SECSVR4-80 → 驗證同一 run 的包 → D:\TestCICD（ZIP 本身）
```

完整操作見[ZIP 交付指南](gitlab-ado-file-delivery.md)：同一 ADO repo／分支另存 `azure-pipelines-gitlab-file-delivery.yml` 與三支 scripts，建立 `GitLab-Rayin-Zip-Delivery`。先手動驗整條線，再用 GitLab Custom headers／template 呼叫有認證的 Runs REST。使用者已確認這兩個 UI 欄位存在，但 token、傳輸及現場真 push 尚未驗收。這份 source-only YAML 保留作診斷，不把 source-provenance 當成已完成送檔。

自動觸發必須使用有來源認證的入口與確切事件 SHA；**不把 `gitlab-ado-smoke-rs` 的公開 probe 加上 token／Agent 工作／VM2 job**。原生 GitLab token 與 ADO incoming-webhook HMAC 不能填相同字串就當作互通。

## 故障排查

| 現象 | 檢查 |
|---|---|
| Waiting for agent | `Default` pool、VM1 online、精確 Agent.Name、pipeline pool authorization；不放寬成任意 agent。 |
| 匿名 HTTP 401／403 | 有 HTTP response；下一步才驗 Rayin token，不提升為管理員。 |
| Fetch 401／403 | Rayin 的 deploy token Username、期限、`read_repository`、URL／proxy；不要誤用 Tools.Rs token。 |
| HTTP refused before credential | 預期預設；確認 HTTPS 或明確核准的隔離 lab 例外。 |
| Git 2.31+ required | 依工具管理流程升級，不把 token 放 CLI 繞過 runtime config。 |
| Redirect／登入頁 | 先確認 canonical Git URL／HTTPS endpoint，script 不自動跟隨 redirect。 |
| SHA 不存在／非固定 ref 歷史 | 確認是 GitLab `poc/cicd` 的完整 SHA；不 fallback 到 latest。 |
| Source／evidence output already exists | 使用 clean job workspace；script 不接管或刪除原有目錄。 |
| 沒有 ZIP／VM2 檔案 | 目前 source-only 是預期行為，不是封裝／交付驗收。 |

## 本機回歸與證據界線

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitLabSource.ps1
```

既有測試使用本機 Git fixture 與假 credential，核對確切 SHA、拒絕錯誤、清理與 credential 不持久化，不連公司 GitLab。本機通過不等於現場 token、網路、Environment 權限或 VM2 交付成功。

[1]: https://docs.gitlab.com/user/project/deploy_tokens/
[2]: https://git-scm.com/docs/git-config

- [GitLab project deploy tokens][1]。
- [Git runtime config、credential helper、TLS／redirect][2]。
- [PublishBuildArtifacts@1：Azure DevOps Server Build Artifact](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-build-artifacts-v1?view=azure-pipelines-server)。
