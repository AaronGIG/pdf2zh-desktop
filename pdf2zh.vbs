Dim appDir, pythonw, script, shell, fso
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = appDir & "\core\runtime\pythonw.exe"
script = appDir & "\_launcher.py"

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = appDir

If Not fso.FileExists(pythonw) Then
    MsgBox "Python not found: " & pythonw & vbCrLf & "Please run install.bat first.", vbCritical, "pdf2zh"
    WScript.Quit 1
End If

Dim vcInstalled
vcInstalled = False
On Error Resume Next
shell.RegRead "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64\Version"
If Err.Number = 0 Then vcInstalled = True
Err.Clear
On Error GoTo 0

If Not vcInstalled Then
    Dim vcRedist
    vcRedist = appDir & "\VC_redist.x64.exe"
    If fso.FileExists(vcRedist) Then
        Dim msg
        msg = "Visual C++ not installed." & vbCrLf & "Install it to enable AI layout detection?" & vbCrLf & vbCrLf & "(Requires admin rights)"
        Dim answer
        answer = MsgBox(msg, vbYesNo + vbQuestion, "pdf2zh")
        If answer = vbYes Then
            shell.Run Chr(34) & vcRedist & Chr(34) & " /install /passive /norestart", 1, True
        End If
    End If
End If

shell.Environment("Process")("PYTHONHOME") = ""
shell.Environment("Process")("PYTHONPATH") = ""
shell.Environment("Process")("PYTHONDONTWRITEBYTECODE") = "1"
shell.Environment("Process")("PYTHONIOENCODING") = "utf-8"

Dim cmd
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34)
shell.Run cmd, 1, False
