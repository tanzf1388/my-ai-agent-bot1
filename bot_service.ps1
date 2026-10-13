# Discord x Ollama Bot - 開機自動啟動與背景執行管理
# 用法（在 bot.py 所在資料夾的 PowerShell 執行）：
#   powershell -ExecutionPolicy Bypass -File .\bot_service.ps1 install
#   動作：install | uninstall | start | stop | restart | status | log
# Token：install 時會自動讀取同資料夾的 TOKEN.txt；沒有這個檔案才會請你手動貼上
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "uninstall", "start", "stop", "restart", "status", "log")]
    [string]$Command = "status"
)

$ErrorActionPreference = "Stop"
$TaskName = "DiscordOllamaBot"
$BotDir   = $PSScriptRoot
$BotFile  = Join-Path $BotDir "bot.py"
$LogFile  = Join-Path $BotDir "bot.log"
$TokenFile = Join-Path $BotDir "TOKEN.txt"
$StartDelay = "PT2M"   # 登入 Windows 後延遲多久啟動（PT2M = 2 分鐘，PT30S = 30 秒）
$Me       = "$env:USERDOMAIN\$env:USERNAME"

function Get-PythonW {
    # 優先使用 .venv 裡的 Python；沒有 .venv 時改用系統安裝的 Python
    $pyw = Join-Path $BotDir ".venv\Scripts\pythonw.exe"
    if (Test-Path $pyw) { return $pyw }
    $sys = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($sys) { return $sys.Source }
    throw "找不到 pythonw.exe。請建立 .venv，或確認 Python 已安裝並加入 PATH。"
}

function Read-TokenFile {
    # 讀取 TOKEN.txt 第一個非空白行；也接受 DISCORD_TOKEN=xxxx 的寫法
    if (-not (Test-Path $TokenFile)) { return $null }
    $line = Get-Content $TokenFile -Encoding UTF8 | Where-Object { $_.Trim() } | Select-Object -First 1
    if (-not $line) { return $null }
    $line = $line.Trim() -replace '^\s*DISCORD_TOKEN\s*=\s*', ''
    return $line.Trim().Trim('"', "'")
}

function Stop-BotProcesses {
    # 保險：工作排程器停止後，確認沒有殘留的 Bot 程序
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($BotFile) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Test-TaskExists {
    return [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
}

switch ($Command) {

    "install" {
        $pyw = Get-PythonW
        if (-not (Test-Path $BotFile)) { throw "找不到 $BotFile" }

        # 1) Token：存成「使用者環境變數」，不寫進 bot.py，也不放在這支腳本裡
        #    有 TOKEN.txt 就直接讀取（TOKEN.txt 已列在 .gitignore，不會上傳到 GitHub）
        $current = [Environment]::GetEnvironmentVariable("DISCORD_TOKEN", "User")
        $replace = $true
        $fileToken = Read-TokenFile
        if ($fileToken) {
            [Environment]::SetEnvironmentVariable("DISCORD_TOKEN", $fileToken, "User")
            Write-Host "🔑 已從 TOKEN.txt 讀取 Token 並存成使用者環境變數。"
            $fileToken = $null
            $replace = $false
        } elseif ($current) {
            $ans = Read-Host "已有 DISCORD_TOKEN 使用者環境變數，要更換嗎？(y/N)"
            $replace = ($ans -match '^(y|yes)$')
        }
        if ($replace) {
            $secure = Read-Host "請貼上 Discord Bot Token（輸入時不會顯示）" -AsSecureString
            $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
            finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
            if ([string]::IsNullOrWhiteSpace($plain)) { throw "Token 不能是空的。" }
            [Environment]::SetEnvironmentVariable("DISCORD_TOKEN", $plain.Trim(), "User")
            $plain = $null
        }

        # 2) 工作排程器：登入 Windows 後延遲 $StartDelay 啟動、無視窗、不限執行時間、不重複啟動
        $taskAction    = New-ScheduledTaskAction -Execute $pyw -Argument "`"$BotFile`" --supervised" -WorkingDirectory $BotDir
        $taskTrigger   = New-ScheduledTaskTrigger -AtLogOn -User $Me
        $taskTrigger.Delay = $StartDelay
        $taskSettings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                            -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
        $taskPrincipal = New-ScheduledTaskPrincipal -UserId $Me -LogonType Interactive -RunLevel Limited

        Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $taskTrigger `
            -Settings $taskSettings -Principal $taskPrincipal -Force `
            -Description "Discord x Ollama AI Agent（登入後自動在背景執行）" | Out-Null

        Stop-BotProcesses
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "✅ 已安裝並啟動。之後每次登入 Windows，2 分鐘後會自動在背景執行。"
        Write-Host "   記錄檔：$LogFile"
        Write-Host "   管理：.\bot_service.ps1 status | stop | restart | log | uninstall"
    }

    "uninstall" {
        if (Test-TaskExists) {
            Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        }
        Stop-BotProcesses
        Write-Host "✅ 已移除開機自動啟動，並停止 Bot。"
        if ([Environment]::GetEnvironmentVariable("DISCORD_TOKEN", "User")) {
            $ans = Read-Host "要一併刪除儲存的 DISCORD_TOKEN 環境變數嗎？(y/N)"
            if ($ans -match '^(y|yes)$') {
                [Environment]::SetEnvironmentVariable("DISCORD_TOKEN", $null, "User")
                Write-Host "✅ 已刪除 Token 環境變數。"
            }
        }
    }

    "start" {
        if (-not (Test-TaskExists)) { throw "尚未安裝，請先執行：.\bot_service.ps1 install" }
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "▶️ 已啟動。"
    }

    "stop" {
        if (Test-TaskExists) { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
        Stop-BotProcesses
        Write-Host "⏹️ 已停止（下次登入 Windows 仍會自動啟動；要完全取消請用 uninstall）。"
    }

    "restart" {
        if (-not (Test-TaskExists)) { throw "尚未安裝，請先執行：.\bot_service.ps1 install" }
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Stop-BotProcesses
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "🔄 已重新啟動。"
    }

    "status" {
        if (-not (Test-TaskExists)) {
            Write-Host "尚未安裝開機自動啟動。執行：.\bot_service.ps1 install"
        } else {
            $info = Get-ScheduledTaskInfo -TaskName $TaskName
            $task = Get-ScheduledTask -TaskName $TaskName
            Write-Host "工作排程：$($task.State)　上次執行：$($info.LastRunTime)　上次結果：$($info.LastTaskResult)"
        }
        $procs = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($BotFile) }
        if ($procs) { Write-Host "Bot 程序：執行中（$(@($procs).Count) 個，含守護程序）" } else { Write-Host "Bot 程序：未執行" }
        if (Test-Path $LogFile) {
            Write-Host "--- 最近的記錄 ($LogFile) ---"
            Get-Content $LogFile -Tail 8 -Encoding UTF8
        }
    }

    "log" {
        if (-not (Test-Path $LogFile)) { throw "還沒有記錄檔：$LogFile" }
        Write-Host "（按 Ctrl+C 離開）"
        Get-Content $LogFile -Tail 40 -Wait -Encoding UTF8
    }
}
