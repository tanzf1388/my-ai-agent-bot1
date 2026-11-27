# 更新紀錄

每次更新 Bot 都會同步到這個 repo，並在這裡記一筆。較早的功能（PR #2–#11）請看 GitHub 上的 PR 說明。

## 2026-11-27：同步電腦上正在跑的版本

### 新功能
- **`!hf [schnell|krea|qwen] 描述`**（限擁有者）：Claude 先寫英文提示詞，再用 Hugging Face 免費 Space 生圖，不佔本機 GPU。schnell 快速（預設）、krea 寫實質感、qwen 適合圖中有文字。
- **長時間運行自我檢查 `!selfcheck`**：Bot 連續運行約 6 小時會自動檢查日誌與健康狀態，發現問題時請 Claude 擬修補並私訊擁有者，擁有者用 `!selfcheck apply` 才會套用（`run` 立即檢查、`drop` 放棄）。
- **`!quiz 作業 [科目] [題數]`**：用 `reference_docs/作業` 裡的作業，以及老師模式出過的回家作業原題出題。
- **Claude 長效登入**：Bot 呼叫 Claude 時改用 `CLAUDE_CODE_OAUTH_TOKEN`（`claude setup-token` 產生，約一年），不再受桌面版登入過期影響。到期前 14/7/3/1 天與過期後每天私訊提醒。
  - 新增 `renew_claude_token.cmd`／`.ps1`：雙擊後登入、自動存 token 並重啟 Bot。

### 改進
- **本機模型**：模型清單加入 `qwen3.6:27b` 與本機建置的 `qwen3.6:27b-q3`（16K 上下文，約 13.7 GB），目前預設使用後者。
- **每日自我學習**：開機／重啟當下不立刻學習，避免一開機就載入大模型。
- **GPU 守護**（取代 PR #13）：使用率門檻改為 55%，且要持續超過 10 秒才暫停，忽略瞬間峰值。
- **語音頻道**：加入語音頻道逾時（網路不穩）時改為回覆提示，不再讓指令直接出錯。

### 其他
- `.gitignore` 加入 `selfcheck/`、`claude_token_state.json`、`*.Modelfile.bak`，避免上傳狀態檔與備份。

## 2026-10-17：每日自我進化（PR #12）
- 每天上網學新技巧並自我測試，每週產出報告；`!evolve` 看狀態、`!evolve run` 立即學習、`!evolve report` 看週報、`!evolve undo` 退回上一版。
