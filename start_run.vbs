' ===========================================================================
'  Hidden launcher for the Discord AI bot (used by Windows auto-start).
'  1. Waits STARTUP_DELAY_SECONDS (2 minutes) after login before doing anything
'  2. Exits if the bot is already running (avoids double replies)
'  3. Waits until Ollama answers on http://localhost:11434 (max 5 minutes)
'  4. Starts run_background.bat with no visible window
' ===========================================================================
Option Explicit

Const OLLAMA_URL = "http://localhost:11434/api/tags"
Const MAX_WAIT_SECONDS = 300
Const STARTUP_DELAY_SECONDS = 120

Dim fso, shell, scriptDir
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Optional argument "nodelay" skips the startup delay (used for manual start)
Dim skipDelay
skipDelay = False
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "nodelay" Then skipDelay = True
End If
If Not skipDelay Then WScript.Sleep STARTUP_DELAY_SECONDS * 1000

If IsBotRunning() Then WScript.Quit 0

WaitForOllama

shell.CurrentDirectory = scriptDir
shell.Run "cmd /c """ & scriptDir & "\run_background.bat""", 0, False

Function IsBotRunning()
    Dim wmi, procs
    IsBotRunning = False
    On Error Resume Next
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    Set procs = wmi.ExecQuery("SELECT ProcessId FROM Win32_Process WHERE " & _
        "((Name = 'python.exe' OR Name = 'pythonw.exe') AND CommandLine LIKE '%discord_ai.py%') " & _
        "OR (Name = 'cmd.exe' AND CommandLine LIKE '%run_background.bat%')")
    If Err.Number = 0 Then
        If procs.Count > 0 Then IsBotRunning = True
    End If
    On Error GoTo 0
End Function

Sub WaitForOllama()
    Dim waited, http
    waited = 0
    Do While waited < MAX_WAIT_SECONDS
        On Error Resume Next
        Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
        http.setTimeouts 2000, 2000, 2000, 2000
        http.Open "GET", OLLAMA_URL, False
        http.Send
        If Err.Number = 0 Then
            If http.Status = 200 Then
                On Error GoTo 0
                Exit Sub
            End If
        End If
        Err.Clear
        On Error GoTo 0
        WScript.Sleep 5000
        waited = waited + 5
    Loop
    ' Ollama still not ready: start anyway, the bot will retry on each request
End Sub
