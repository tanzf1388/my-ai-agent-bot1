# my-ai-agent-bot1

Discord + Ollama AI Agent Bot（主程式：`bot.py`）。

## 常用指令

| 指令 | 用途 |
| --- | --- |
| `!ask 問題` | 直接問 AI，在伺服器頻道不用 @Bot（可附上圖片一起問） |
| `!image 描述` | 用本機 ComfyUI 生成圖片（`!img` 也可以） |
| `!video 描述` | 用本機 ComfyUI 生成約 3 秒的短影片（RX 9070 XT 約 15 分鐘） |
| `!help` | 查看所有指令 |

私訊 Bot 或在頻道 @Bot 也可以直接對話。

## 生圖 / 生影片（ComfyUI）

`!image`、`!video` 會呼叫本機 ComfyUI Desktop 的 API（預設 `http://127.0.0.1:8188`）。
ComfyUI 沒開時 Bot 會在背景自動啟動它，生成完就關閉；若是你自己開著 ComfyUI Desktop，則只請它卸載模型。
生成前會先把 Ollama 模型移出顯存，生成期間 AI 對話會排隊等候，兩者不會同時佔用顯存。

| 用途 | 模型（放在 ComfyUI 的 models 資料夾） |
| --- | --- |
| 圖片 | Z-Image Turbo：`diffusion_models/z_image_turbo_bf16.safetensors`、`text_encoders/qwen_3_4b.safetensors`、`vae/ae.safetensors` |
| 影片 | Wan 2.2 TI2V 5B：`diffusion_models/wan2.2_ti2v_5B_fp16.safetensors`、`text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors`、`vae/wan2.2_vae.safetensors` |

影片模型可在 ComfyUI Desktop 開啟「Wan 2.2 5B」影片範本後下載。Bot 啟動 ComfyUI 時會加上 `--bf16-unet`（AMD 顯卡用 fp16 會產生全灰影片）。ComfyUI 不在預設位置時，
可設定環境變數 `COMFY_URL`（API 位址）或 `COMFY_HOME`（Comfy-Desktop 資料夾）。

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
