Dim appDir, pythonw, script, shell, fso
Set fso = CreateObject("Scripting.FileSystemObject")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = appDir & "\core\runtime\pythonw.exe"
script = appDir & "\_launcher.py"

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = appDir

' 检查运行时是否存在
If Not fso.FileExists(pythonw) Then
    MsgBox "找不到 Python 运行时: " & pythonw & Chr(13) & Chr(10) & _
           "请先运行 install.bat 初始化环境。", vbCritical, "pdf2zh 桌面版"
    WScript.Quit 1
End If

' 检查 VC++ 运行库（首次启动自动安装）
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
        Dim answer
        answer = MsgBox("检测到尚未安装 Visual C++ 运行库。" & Chr(13) & Chr(10) & _
                        "安装后可启用 AI 智能布局检测功能，提升翻译质量。" & Chr(13) & Chr(10) & Chr(13) & Chr(10) & _
                        "是否现在安装？（需要管理员权限）", _
                        vbYesNo + vbQuestion, "pdf2zh 桌面版")
        If answer = vbYes Then
            shell.Run Chr(34) & vcRedist & Chr(34) & " /install /passive /norestart", 1, True
        End If
    End If
End If

' 设置环境变量
shell.Environment("Process")("PYTHONHOME") = ""
shell.Environment("Process")("PYTHONPATH") = ""
shell.Environment("Process")("PYTHONDONTWRITEBYTECODE") = "1"
shell.Environment("Process")("PYTHONIOENCODING") = "utf-8"

' 静默启动（窗口样式 0 = 隐藏控制台）
Dim cmd
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34)
shell.Run cmd, 0, False
