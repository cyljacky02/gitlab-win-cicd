# GitLab → ADO Server → VM：原始碼 ZIP 交付

**目前 POC：GitLab `Cathaysec.Com.Smt.Rayin`／`poc/cicd` 提供來源與 push 事件；VM1 ADO Agent 取碼、封裝原始碼 ZIP 並存版；VM2 接收 ZIP 本身。不編譯、不解壓、不啟停服務，不需要 GitLab Runner／CI artifacts。**

- **[操作指南：先手動 ZIP 交付，再設定 authenticated webhook](../../docs/runbooks/gitlab-ado-file-delivery.md)**：沿用 ADO `Deployment`／原 repo／`poc/webhook-smoke`；VM2 為 Environment `test-deploy-agent` 的 VM resource `SECSVR4-80`，本次目錄 `D:\TestCICD`。使用者已確認 GitLab 有 Custom headers／Custom webhook template。
- **最新現場回報：VM1 Git preflight／ADO checkout 已通過；取碼／ZIP task 綠燈但 package 目錄不存在。** 已在本機重現 `PowerShell@2 filePath` dot-source 使入口 guard 跳過 main；新版把 Get／New／Copy 都改成 inline `&` 呼叫，ZIP 後立即驗 manifest。之前綠燈不能當成實際取碼／封裝驗收。原缺 Node16 的 Publish 已改用 PowerShell 發出 Agent 原生 Container 上傳指令；實際 GitLab 取碼／artifact／VM2 仍待現場重新驗收。
- 已回報通過：[先前 Tools.Rs 專案的 GitLab 手動 Test → ADO agentless probe](../../docs/runbooks/gitlab-ado-webhook-smoke.md)；不等於 Rayin 真 push 自動觸發或來源驗章。
- [VM1 → Rayin 匿名連通、指定 SHA 手動取碼指南](../../docs/runbooks/gitlab-ado-source-build.md)。現有 YAML 已改為新 repo／ref；不直接升級未驗章 smoke。

| 目前檔案 | 用途 |
|---|---|
| [`ado/azure-pipelines-gitlab-file-delivery.yml`](ado/azure-pipelines-gitlab-file-delivery.yml) | **本輪主流程**：精確 SHA → ZIP → Server Build Artifact → Environment VM2 驗 hash／只放 ZIP |
| [`ado/scripts/New-GitLabSourcePackage.ps1`](ado/scripts/New-GitLabSourcePackage.ps1) | 只封裝 tracked regular files，排除 `.git`／untracked，拒絕 LFS pointer／symlink／submodule |
| [`ado/scripts/Copy-GitLabSourcePackage.ps1`](ado/scripts/Copy-GitLabSourcePackage.ps1) | 驗 repo／ref／SHA／run／hash，暫存後 rename，不解壓、不覆蓋不同內容 |
| [`ado/gitlab-file-delivery-push.template.json`](ado/gitlab-file-delivery-push.template.json) | GitLab Custom webhook template；authenticated Runs REST 傳 push SHA，不含 credential |
| [`ado/azure-pipelines-gitlab-connectivity.yml`](ado/azure-pipelines-gitlab-connectivity.yml) | 無憑證、無 checkout 的 VM1 → Rayin 連通檢查 |
| [`ado/azure-pipelines-gitlab-source.yml`](ado/azure-pipelines-gitlab-source.yml) | **手動 source-only**：Rayin／`poc/cicd`、指定完整 SHA，只發來源證據 artifact |
| [`ado/scripts/Get-GitLabSource.ps1`](ado/scripts/Get-GitLabSource.ps1) | PS 5.1 fetch／detached checkout；短時子程序 credential、不持久化、不執行 app code |
| [`ado/azure-pipelines-webhook-smoke.yml`](ado/azure-pipelines-webhook-smoke.yml) | 未驗章 agentless 零動作探針；project filter 已切至 Rayin，不可加入 secret／交付工作 |
| [`tests/Test-GitLabSource.ps1`](tests/Test-GitLabSource.ps1) | 取碼實作的離線測試（本機 Git fixture、假 credential） |
| [`tests/Test-GitCheckoutBootstrap.ps1`](tests/Test-GitCheckoutBootstrap.ps1) | checkout 前的 Git 選用檢查（本機 7/7） |
| [`tests/Test-BuildArtifactUpload.ps1`](tests/Test-BuildArtifactUpload.ps1) | 原生上傳 logging command／檔案範圍的離線檢查（12/12，不連 Server） |
| [`tests/Test-PowerShellTaskEntrypoints.ps1`](tests/Test-PowerShellTaskEntrypoints.ps1) | 執行實際 YAML inline wrappers，驗真實 ZIP／Copy 及入口不空跑（8/8，不連公司 GitLab／ADO） |

**新 ZIP／VM2 流程已提供，本機實際 Git／ZIP／copy 操作檢查通過；現場手動整條線與 authenticated 真 push 均尚未驗收。** source-only pipeline 仍只發 metadata，不會送檔。完整流程請只建新的 `GitLab-Rayin-Zip-Delivery`，不把舊 smoke 改成有權限的工作。不要求 solution／SDK／MSBuild／publish command。來源目前 HTTP，預設拒絕送 credential；HTTPS 優先，隔離 HTTP 例外必須明確允許並使用短效專案唯讀 token；GitLab → ADO PAT 傳輸要獨立核准。

## 較早的 GitLab CI artifact 交接備選（不是本輪必做）

以下保留原先「GitLab CI 建好 ZIP → ADO importer 驗證存版」實作供參考。它不是目前選定的 source-build 路線，不能把兩種產物／provenance 契約混用。[歷史操作指南](../../docs/runbooks/gitlab-ado-integration.md)。

| 檔案 | 用途 |
|---|---|
| [`gitlab/gitlab-ci.example.yml`](gitlab/gitlab-ci.example.yml) | **Linux GitLab Runner** 的隔離測試 pipeline；沿用現有 Runner |
| [`gitlab/ci/new-release-candidate.sh`](gitlab/ci/new-release-candidate.sh) | Linux 封裝入口，加入 release.json、產生 manifest |
| [`gitlab/ci/send-ado-candidate.sh`](gitlab/ci/send-ado-candidate.sh) | Linux 通知入口，保存 ADO run ID 後立即結束 |
| [`gitlab/ci/bridge.py`](gitlab/ci/bridge.py) | 上述入口共用的 Python 3.9+ 標準函式庫實作；不需 PowerShell／jq／curl／zip CLI |
| [`ado/azure-pipelines-import.yml`](ado/azure-pipelines-import.yml) | **import-only** ADO YAML，使用 VM1 Build Agent |
| [`ado/import-policy.example.json`](ado/import-policy.example.json) | CD 管理的來源／分支／必要 jobs／大小限制 |
| [`ado/scripts/Import-GitLabCandidate.ps1`](ado/scripts/Import-GitLabCandidate.ps1) | API 複核最終 success、下載固定 job 產物、驗 hash／ZIP，失敗不發布 |
| [`ado/scripts/Test-ImportedCandidate.ps1`](ado/scripts/Test-ImportedCandidate.ps1) | 日後放行後下載的指定 build／candidate 複驗，不執行換版 |
| [`shared/Bridge.Common.ps1`](shared/Bridge.Common.ps1) | PS 5.1 HTTP／驗證共用函式，不跟隨 redirect，不略過 TLS |
| [`tests/Test-Bridge.ps1`](tests/Test-Bridge.ps1) | Windows ADO／既有 PS 實作的離線測試 |
| [`tests/test_linux_jobs.py`](tests/test_linux_jobs.py) | Linux CI 實作的離線測試，含 loopback 通知及與 ADO ZIP 契約互通 |

## 執行位置決定語言（以下為較早的 CI artifact 備選）

| 執行端 | 預設使用 |
|---|---|
| GitLab Server（Linux） | 排程與儲存，不執行本套件的建置／通知 script |
| 既有 GitLab Runner（Linux） | `.sh` 入口＋Python 3.9+；**不需要裝 PowerShell，也不需新增 Windows Runner** |
| VM1 ADO Build Agent（Windows） | `ado/scripts/*.ps1` 驗證／匯入候選版本 |
| VM2 ADO Deploy Agent（Windows） | 放行後才執行 Windows 驗證／既有換版工具 |

ADO 並未強制使用 PowerShell；保留 `.ps1` 是因目前 ADO Agent 在 Windows。GitLab job 則已改為 Linux 範本，兩端透過 HTTP＋JSON＋ZIP 交接。

範本 tag `gitlab-bridge-linux` 要改成現有 Runner 的實際 tag。Docker executor 須有 Python 3.9+ 的已核准 Linux image（範例 `python:3.12-alpine`，正式使用依內部規範釘 digest／內網 mirror）；shell executor 忽略 `image:`，host 須已安裝 Python。不要在這一步重註冊現有 Runner。

`gitlab/ci/New-ReleaseCandidate.ps1`、`Send-AdoCandidate.ps1` 與 `config.windows.example.toml` 只是保留的 Windows 替代版／回歸測試參考，**你們的 Linux pipeline 不使用它們**。

## 與既有 ZIP 的關係

參考最新 `CDPOC-DIRECT-AGENT-FINAL-20261028T050503Z.zip` 的 Direct-agent 路線；較早三包作歷史比對，沒有匯入其現場位址、憑證或 installer。此套件是**獨立、縮小範圍的交接實作**，不是重新包裝整套舊 POC。

- 保留 `out/site.zip`、`out/manifest.json`、camelCase manifest、根目錄 `release.json` 與六個 Runs API template parameters。
- 加強：ADO 等待 GitLab **整條 pipeline 最終 success**，確認 CD 政策列出的 jobs 確實成功且非 allow_failure；通知 job 不等待 ADO。
- ADO artifact 名稱仍為 `release`，內含 `site.zip`、`manifest.json`、`verification.json`。
- **verification.json 是本套件的 snake_case 稽核格式，不相容舊部署模組的 envelope。不可只把舊 Deploy stage 接在本 YAML 後面。** 檔名相同不代表可互換；接 VM2 時先驗證／明確轉接其讀取契約。
- 沒有 broker、IIS 操作、WinCD 呼叫、Production 自動觸發、假核准或回報 commit status。既有 VM2 流程保持不動。
- 沒有耐久去重／exactly-once；重送可能多一筆 importer build，所以本階段不能開自動部署。

## 本機驗證

目前手動取碼實作（Windows PowerShell 5.1）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-GitLabSource.ps1
```

本機離線 **19/19 通過**，另驗 Git client 對 loopback 送出暫時 URL-scoped header；未連公司 GitLab、未完成現場取碼或 VM2 ZIP 交付。

以下則為保留的舊 CI artifact 實作回歸測試，不是本輪 Runner 前置要求：

Linux CI 實作（Python 3.9+，只用標準函式庫；通知測試只打 localhost）：

```sh
python3 -m unittest discover -s cicd/gitlab-ado/tests -p test_linux_jobs.py -v
```

本輪在目前 Windows 開發主機驗證 Python CI 實作：**10 項通過、1 項 symlink 建立測試因主機權限略過**；已驗證 Python 產物可通過 Windows ADO 的 ZIP／release.json 檢查，shell 入口通過 `sh -n`。尚未在你們實際 Linux Runner／container 做真 push 驗收，不能把這個結果說成 Linux 現場 E2E。

在 Windows repo 根目錄以 Windows PowerShell 5.1 驗證 ADO／既有 PS 實作：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\cicd\gitlab-ado\tests\Test-Bridge.ps1
```

已在 Windows PowerShell 5.1 重跑：**99 項通過、0 項失敗**。Importer API 使用假資料；通知 API 使用本機 loopback HTTP 與假 token，不連 GitLab／ADO 現場。涵蓋成功、等待／取消／逾時、來源錯配、必要 job、ZIP／hash、通知失敗與指定版本複驗。

`Bypass` 只作用於這個測試程序；不需要改機器永久 ExecutionPolicy。測試成功不代表現場 TLS、token、ACL、Server tasks、Agent 或部署放行已驗收。
