# 手動打通 GitLab Test webhook → ADO smoke pipeline

## 現在只做這件事

```text
GitLab 網頁：Test → Push events
  → ADO Incoming WebHook
  → 已有的 smoke pipeline 自動新增一筆 run
  → agentless Delay@1 0 分鐘成功
```

**不建立 GitLab 分支、不 push、不修改 `.gitlab-ci.yml`／include，不使用 Runner、不取碼、不下載產物、不執行部署、不碰 VM2。** 這次只驗手動 Test 的通知路徑；真 push 與後續建置／部署都等此步通過後再討論。

## 先確認兩個不同概念

| 名稱 | 在哪裡 | 目前要做什麼 |
|---|---|---|
| `poc/webhook-smoke` | **ADO repo 的分支**，存放測試 YAML | 已建立，繼續使用，不重建 |
| `poc/ado-fetch` | 前版為 **GitLab 來源分支**預設的名稱 | 本輪不需要，也不要求建立；已移除其 ref filter |

手動選 ADO 的 `poc/webhook-smoke` 執行，不等於 pipeline 的預設分支自動改成它。Incoming WebHook 必須從 **該 pipeline 的 default branch** 找到資源定義；這是本輪一定要確認的設定。[1]

## 使用者已回報的現況（不是本機代測結果）

- ADO Server：**25H2 20260921.1**；project `Deployment`。
- 已建立 Incoming WebHook connection：`gitlab-ado-smoke-rs`。
- ADO 分支 `poc/webhook-smoke` 已有 YAML，**手動 Run 成功**。
- 原先 GitLab Test 回 HTTP 200、payload 指向 main，但 ADO 沒有新增 run；當時 YAML 的 `poc/ado-fetch` ref filter 不匹配。
- **移除本探針的 ref filter 後，使用者已確認：GitLab 按 Test 會在 ADO 自動新增 run，觸發來源顯示 Webhook。**
- **使用者已確認 task `Webhook probe reached ADO - zero-minute no-op` 為綠色，整筆自動 run 為 Succeeded。本輪「GitLab 網頁手動 Test → ADO agentless probe」驗收通過。**
- 上述為使用者的現場回報；尚未取得 run ID／截圖，沒有宣稱已由本開發機直接稽核。它不代表真 push、來源驗章、ADO → GitLab 讀取或部署驗收通過。
- 本開發機無法連到使用者的公司內網服務，沒有直接操作現場或宣稱代測成功。

## 1. 修改「已有的 ADO YAML」，不是 GitLab CI

進入 ADO `Deployment` project：

**Repos → Files → branch 下拉選 `poc/webhook-smoke` → `/azure-pipelines-webhook-smoke.yml` → Edit**。

若當時用了不同檔名，修改 smoke pipeline 實際指向的那一份檔案，不另外建第二份 YAML。

用下列**完整內容取代**，不要只補貼幾行：

```yaml
trigger: none
pr: none

name: webhook-smoke-$(Date:yyyyMMdd)$(Rev:.r)

resources:
  webhooks:
    - webhook: WebHook
      connection: gitlab-ado-smoke-rs
      filters:
        - path: object_kind
          value: push
        - path: project.path_with_namespace
          value: grp-smt-maint/Cathaysec.Com.Smt.Tools.Rs

jobs:
  - job: WebhookReceived
    displayName: Webhook transport smoke test only
    pool: server
    timeoutInMinutes: 1
    steps:
      - task: Delay@1
        displayName: GitLab webhook received - no deployment
        inputs:
          delayForMinutes: '0'
```

按 **Commit／Save** 時選擇儲存到**已有的 ADO `poc/webhook-smoke` 分支**。不建立新分支、不建 PR、不合併 main。

檔案版本：[azure-pipelines-webhook-smoke.yml](../../cicd/gitlab-ado/ado/azure-pipelines-webhook-smoke.yml)。上述 YAML 與檔案的說明文字可能不同，但資源與兩個 filters 相同。

本輪**沒有 `ref` filter**，所以可以接收 GitLab Test 產生的 main 事件。不等於修改 GitLab main，也不代表測試完成後可以把這個入口接到部署。project filter 只是路由條件，不是來源認證。

## 2. 確認這支 pipeline 的預設分支

到 **Pipelines → 原本那支 smoke pipeline**，不要 New pipeline。

找到 **Default branch for manual and scheduled builds**，設定／確認為：

```text
refs/heads/poc/webhook-smoke
```

如果 UI 的下拉只顯示短名稱，選 `poc/webhook-smoke` 即可。

官方 troubleshooting 路徑為：**Edit → … → Triggers → YAML → Get sources → Default branch for manual and scheduled builds**。[1]

- 這是**此 pipeline 的設定**，不是 Repos 的 repo default branch。
- 不更動其他 build／deploy pipeline。
- 若現場 UI 不同，提供 smoke pipeline 編輯畫面的截圖再確認，別為了找欄位去改 repo main。

## 3. 手動 Run「更新後」的同一支 pipeline

- Branch 選 `poc/webhook-smoke`，使用第 1 步剛儲存的版本。
- 若提示 connection resource authorization，只授權本支 smoke pipeline，不勾所有 pipelines。
- 預期只有 `WebhookReceived`／`Delay@1`，立即成功。`pool: server` 是 agentless，不用 `Default` pool，也不會派送 VM1／VM2 agent。
- 記下這筆**手動 run 的 ID／時間**，避免下一步把它誤認為 webhook 自動觸發的 run。

此步只驗更新後 YAML 能執行，不算 GitLab 通知通過。

## 4. 回到「已有的 GitLab webhook」再按 Test

在 `grp-smt-maint/Cathaysec.Com.Smt.Tools.Rs` 專案：

**Settings → Webhooks → 找到指向 ADO 的那一筆**。不用重新 Add webhook。

核對 URL 為本輪 connection 的 endpoint（沒有 `/Deployment/` project segment）：

```text
{ADO_COLLECTION_URL}/_apis/public/distributedtask/webhooks/gitlab-ado-smoke-rs?api-version=6.0-preview
```

`ADO_COLLECTION_URL` 使用先前已提供的 collection URL；endpoint 的 `gitlab-ado-smoke-rs` 是 **WebHook Name**，不是 pipeline ID。

本輪設定：

| 項目 | 值 |
|---|---|
| Trigger | Push events |
| Push events branch filter | 手動探針可選 All branches；若既有 Test 已能送達，也不必為此額外調整 |
| Secret token／Signing token／Custom headers／Custom payload | 不設定；保持此短時未驗章探針範圍 |
| SSL verification | 保留正常設定；HTTP 不會因此變 HTTPS，不需關閉驗證 |

按 **Test → Push events**，然後開該 webhook 的 **Edit → Recent events → 最新一筆 → View details**。

檢查：

1. HTTP response status／body。
2. request body 的 `object_kind` 應為 `push`。
3. `project.path_with_namespace` 應與 YAML 固定值**完全相同**，包括大小寫。若不同，先確認同一專案，再修正固定值；不要拿掉 project filter。
4. `ref` 可能是 `refs/heads/main`；**本輪不再以 ref 限制，不用建立測試分支**。

## 5. 看 ADO 是否「另外自動新增」一筆 run

回 **Pipelines → 同一支 smoke pipeline → Runs**，重新整理。

| 結果 | 意義 |
|---|---|
| GitLab HTTP 200 ＋按 Test 後新增非手動 run ＋Delay 成功 | **本輪手動 Test → ADO smoke 觸發通過** |
| GitLab HTTP 200，但沒有新 run | 尚未通過；核對 pipeline default branch、YAML path／儲存版本、兩個 filters、connection 名稱／權限 |
| 只有第 3 步的手動 run | 不算 webhook 觸發成功 |
| 出現 Agent 工作、取碼、下載／部署 | 停止；不是本輪的零動作 YAML，不可用 FINAL deploy template 代替 |

請回覆：**GitLab response status／body、ADO 是否新 run／run ID**。若仍無 run，再提供 request 的 `object_kind`／`project.path_with_namespace` 和 pipeline default branch；不要貼 tokens／cookies／Authorization headers 或整份含使用者資料的 payload。

## 故障排查：不盲目放寬權限

| 現象 | 下一步 |
|---|---|
| 200，但沒有 run | 先核對第 2 步：手動 Run 選分支不代表已設定 default branch。再檢查事件種類／project path／connection 訂閱。 |
| Test 的 ref 是 main／ref_protected 為 true | 本輪不擋 main；分支保護 metadata 不是驗章，也不用解除 main 保護。 |
| 404／Cannot find webhook | 核對 collection URL、WebHook Name、沒有 project segment、default branch、YAML 已 bootstrap；不要先加 PAT。 |
| local network／URL blocked | 由 GitLab 管理者核准目的地 allowlist，不全域開放所有內網 SSRF 目的地。[4] |
| timeout／connection refused | 查 GitLab Rails → ADO 的路徑；不是 Runner 網路。之後真事件的 Sidekiq 來源需另外驗收。[2] |
| 401／403 | 分辨 IIS／proxy／ADO 哪層回應；不開 IIS Basic／全域 Anonymous，也不給 Full access PAT 硬闖。 |
| API version 錯誤 | 保存 supported-versions 等非敏感 error，依安裝版驗證；不能把 cloud 最新版本當現場保證。 |
| 同一次多筆 run | 查多個 hooks／多個訂閱／重送；這個 probe 不宣稱 exactly-once。 |

## 安全限制、測後清理與後續（本輪不做真 push）

- **這是短時未驗章的內網連通探針。** Incoming WebHook Secret 是 HMAC-SHA1，不是 GitLab `X-Gitlab-Token` 原值；不可兩邊填同字串就假設相容。GitLab 新文件的 HMAC-SHA256 signing 格式也不能直接當作相容。[2][3]
- 任何能連 endpoint、知道名稱並偽造相符 payload 的人都可能排入 probe run。它沒有 source checkout、script、secret、artifact、Agent 或部署；**不允許把 Fetch／Deploy 接到未驗章入口**。
- 本輪 HTTP 不送 PAT 或 webhook secret。若公司禁止未驗章測試，停止並改做核准的驗章接收器／閘道方案，不改既有正式入口或全域安全設定。
- 不向所有 pipelines 開放 connection；只訂閱／授權此專用 probe。
- 完成本輪後，刪除本次測試 GitLab webhook、停用／刪除專用 smoke pipeline、刪除專用 Incoming WebHook connection；保留非敏感驗收紀錄，不刪別人的資源／repo／分支。
- **手動 Test 成功不等於真 push 成功**：GitLab UI Test 可能由 Rails 送出，真事件通常來自 Sidekiq。也不代表 ADO → GitLab 取碼、來源驗章、版本綁定或部署放行已完成。[2]
- 真 push 是否要測、GitLab 來源分支怎麼命名、是否改由 ADO 建置等，等手動路徑通過後再另行確認；不要現在建立 `poc/ado-fetch` 或變更應用 main。

**下一步：[ADO VM1 → GitLab 指定 SHA 取碼／建置路線](gitlab-ado-source-build.md)。** 使用另外的手動 pipeline，先做無憑證連通，再做唯讀取碼；不把這個未驗章 probe 加上 secrets／build。

可選假 payload：[webhook-smoke-push.example.json](../../cicd/gitlab-ado/ado/webhook-smoke-push.example.json)。它只供之後針對 ADO endpoint 的人工 HTTP 測試，**不代表必須建立同名 GitLab 分支**；不是此流程的必要步驟。

## 官方來源與版本界線

[1]: https://learn.microsoft.com/en-us/azure/devops/pipelines/process/resources?view=azure-devops-server#webhooks-resource
[2]: https://docs.gitlab.com/user/project/integrations/webhooks/
[3]: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/resources-webhooks-webhook?view=azure-pipelines-server
[4]: https://docs.gitlab.com/security/webhooks/

- [Incoming WebHook、pipeline default-branch troubleshooting][1]；[filters／HMAC-SHA1／不設 secret 的公開入口][3]。
- [Delay@1：YAML＋server job、0 分鐘無延遲](https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/delay-v1?view=azure-pipelines-server)。
- [GitLab webhook 設定、Test／Recent events、Rails／Sidekiq 發送來源][2]；GitLab 文件為滾動版，Runner 16.11.1 不是 GitLab Server 版號。
- URL 以官方的 `6.0-preview` incoming webhook 範例加現場 collection base 實測；不能把現行 cloud `7.2-preview.2` 的文件 redirect 當成本機路由／版號已驗收證據。
