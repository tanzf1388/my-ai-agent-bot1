# my-ai-agent-bot1

Discord + Ollama AI Agent Bot。

## 開機自動背景執行（Windows）

| 檔案 | 用途 |
| --- | --- |
| `install_autostart.bat` | 開啟開機自動啟動（在「啟動」資料夾建立捷徑，不需系統管理員權限） |
| `uninstall_autostart.bat` | 關閉開機自動啟動，並可選擇同時停止 Bot |
| `stop_bot.bat` | 停止正在背景執行的 Bot |
| `start_run.vbs` | 隱藏視窗啟動器：避免重複啟動 → 等待 Ollama 就緒（最多 5 分鐘）→ 背景啟動 |
| `run_background.bat` | 背景執行 `discord_ai.py`，輸出寫入 `logs\bot.log`，當機後 15 秒自動重啟 |
| `run_ai.bat` | 前景手動執行（有視窗，方便除錯） |

### 設定步驟

1. 確認 Ollama 已設定為開機自動啟動（Ollama 安裝後預設即會自動啟動）。
2. 雙擊 `install_autostart.bat`。
   - 若尚未設定永久的 `DISCORD_TOKEN` 環境變數，腳本會請你貼上 Token 並以 `setx` 保存
     （PowerShell 的 `$env:DISCORD_TOKEN` 只在當下視窗有效，開機後會失效）。
3. 之後每次登入 Windows，Bot 都會在背景自動執行，不會出現任何視窗。
4. 執行紀錄請看 `logs\bot.log`。

> 專案資料夾可以放在任何位置，腳本會自動使用自己所在的資料夾；
> 但若之後搬移資料夾，請重新執行一次 `install_autostart.bat`。
