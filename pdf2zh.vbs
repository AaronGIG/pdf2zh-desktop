Dim appDir, pythonw, script, shell
appDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pythonw = appDir & "\core\runtime\pythonw.exe"
script = appDir & "\_launcher.py"

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = appDir

' 检查运行时是否存在
If Not CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    MsgBox "找不到 Python 运行时: " & pythonw & Chr(13) & Chr(10) & _
           "请先运行 install.bat 初始化环境。", vbCritical, "pdf2zh 桌面版"
    WScript.Quit 1
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
