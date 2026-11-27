# 續期 Bot 的 Claude 登入：登入 → 自動存 token → 重啟 Bot。雙擊 renew_claude_token.cmd 即可。
$ErrorActionPreference = "Stop"
$exe = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $exe) {
    $exe = (Get-ChildItem "$env:LOCALAPPDATA\Claude-Data\claude_*\claude-code\*\*\claude.exe",
                          "$env:APPDATA\Claude\claude-code\*\*\claude.exe" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime | Select-Object -Last 1).FullName
}
if (-not $exe) { Read-Host "找不到 claude.exe，請先安裝 Claude 桌面版。按 Enter 結束"; exit 1 }

Write-Host "1) 等一下會開瀏覽器，請登入並按「授權」。" -ForegroundColor Cyan
& $exe setup-token
Write-Host "`n2) 把上面印出的 sk-ant-oat... 那串複製起來（反白後按右鍵就是複製），再回來按 Enter。" -ForegroundColor Cyan
Read-Host | Out-Null
$token = ([regex]::Match((Get-Clipboard -Raw), "sk-ant-oat[\w-]+")).Value
if (-not $token) { $token = ([regex]::Match((Read-Host "剪貼簿裡沒找到 token，請直接貼上"), "sk-ant-oat[\w-]+")).Value }
if (-not $token) { Read-Host "沒有拿到 token，沒有做任何變更。按 Enter 結束"; exit 1 }

[Environment]::SetEnvironmentVariable("CLAUDE_CODE_OAUTH_TOKEN", $token, "User")
$env:CLAUDE_CODE_OAUTH_TOKEN = $token
& powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\bot_service.ps1" restart
Write-Host "`n✅ 完成：token 已儲存、Bot 已重啟，約一年後會再私訊提醒你。" -ForegroundColor Green
Read-Host "按 Enter 關閉" | Out-Null
