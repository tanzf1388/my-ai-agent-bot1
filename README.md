# my-ai-agent-bot1

Discord + Ollama AI Agent Bot（主程式：`bot.py`）。

## 常用指令

| 指令 | 用途 |
| --- | --- |
| `!ask 問題` | 直接問 AI，在伺服器頻道不用 @Bot（可附上圖片一起問） |
| `!help` | 查看所有指令 |

私訊 Bot 或在頻道 @Bot 也可以直接對話。

## 開機自動背景執行（Windows）

`bot_service.ps1` 會用 Windows「工作排程器」在**登入後 2 分鐘**自動於背景執行 `bot.py`，
不會出現視窗，也不會重複啟動。不需要系統管理員權限。

### 安裝

1. 在 `bot.py` 所在資料夾放一個 `TOKEN.txt`，內容是 Discord Bot Token
   （直接寫 Token 或 `DISCORD_TOKEN=...` 都可以）。
   - `TOKEN.txt` 已列在 `.gitignore`，不會上傳到 GitHub。
   - 沒有 `TOKEN.txt` 時，安裝過程會請你手動貼上 Token。
2. 在該資料夾開啟 PowerShell 執行：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\bot_service.ps1 install
   ```
3. 之後每次登入 Windows，Bot 都會在 2 分鐘後自動於背景執行。

Python 會優先使用資料夾內的 `.venv\Scripts\pythonw.exe`，沒有 `.venv` 時改用系統安裝的 Python。

### 管理指令

| 指令 | 用途 |
| --- | --- |
| `.\bot_service.ps1 status` | 查看排程、Bot 是否執行中與最近的記錄 |
| `.\bot_service.ps1 log` | 即時查看記錄檔 `bot.log`（Ctrl+C 離開） |
| `.\bot_service.ps1 start` / `stop` / `restart` | 啟動 / 停止 / 重新啟動 |
| `.\bot_service.ps1 uninstall` | 移除開機自動啟動並停止 Bot |

想調整啟動延遲，修改 `bot_service.ps1` 開頭的 `$StartDelay`（例如 `PT2M` = 2 分鐘、`PT30S` = 30 秒）後重新執行 `install`。
