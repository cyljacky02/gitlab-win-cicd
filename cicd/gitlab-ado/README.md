# GitLab → ADO Server Express：候選版本交接套件

**用途：接通 GitLab CI → VM1 驗證／ADO 存版；不排程 VM2，不做換版。**

> **本輪先做原生 webhook 連通測試：**請改從 [不經 Runner 的 agentless probe 指南](../../docs/runbooks/gitlab-ado-webhook-smoke.md) 開始，使用 [`ado/azure-pipelines-webhook-smoke.yml`](ado/azure-pipelines-webhook-smoke.yml)。它只驗事件接收，不建置／取碼／部署；下面的 CI 交接套件不是本輪實測的必要步驟。

從這份[繁體中文操作指南](../../docs/runbooks/gitlab-ado-integration.md)開始。現場版號、URL、pool、Deploy Agent 類型仍須確認；此套件不是已在你的 VM 通過驗收的部署包。

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

## 執行位置決定語言，不是 GitLab Server 的 OS

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
