WScript.Sleep 60000 ' 延遲 15 秒，等候網路與 Ollama 服務載入完成

Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """C:\discord ai\run.bat""", 0, False
