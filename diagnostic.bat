@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版系统诊断工具
title pdf2zh 桌面版 - 系统诊断

echo ================================================================
echo   pdf2zh 桌面版 - 系统诊断工具
echo ================================================================
echo.

set "REPORT_FILE=diagnostic_report_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.txt"
set "REPORT_FILE=%REPORT_FILE: =0%"

echo 正在生成诊断报告...
echo 报告文件: %REPORT_FILE%
echo.

:: 开始生成报告
(
echo ================================================================
echo   pdf2zh 桌面版 - 系统诊断报告
echo   生成时间: %date% %time%
echo ================================================================
echo.

echo [系统信息]
echo 操作系统:
ver
echo.
echo 系统架构: %PROCESSOR_ARCHITECTURE%
echo 处理器: %PROCESSOR_IDENTIFIER%
echo.

echo [内存信息]
for /f "skip=1" %%p in ('wmic computersystem get TotalPhysicalMemory') do (
    set /a MEMORY_GB=%%p/1024/1024/1024
    echo 总内存: !MEMORY_GB! GB
    goto :memory_done
)
:memory_done

for /f "skip=1" %%p in ('wmic OS get FreePhysicalMemory') do (
    set /a FREE_MEMORY_GB=%%p/1024/1024
    echo 可用内存: !FREE_MEMORY_GB! GB
    goto :free_memory_done
)
:free_memory_done
echo.

echo [磁盘空间]
for /f "skip=1" %%p in ('wmic logicaldisk where size^>0 get size^,freespace^,caption') do (
    if not "%%p"=="" (
        echo %%p
    )
)
echo.

echo [网络连接]
ping -n 1 google.com >nul 2>&1
if !errorlevel! == 0 (
    echo 网络连接: 正常
) else (
    echo 网络连接: 异常
)
echo.

echo [Visual C++ 运行库]
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if !errorlevel! == 0 (
    echo VC++ Redistributable x64: 已安装
) else (
    echo VC++ Redistributable x64: 未安装
)
echo.

echo [Python 环境]
if exist "core\runtime\python.exe" (
    echo Python 运行时: 已安装
    "core\runtime\python.exe" --version 2>nul
    if !errorlevel! == 0 (
        echo Python 版本检查: 正常
    ) else (
        echo Python 版本检查: 异常
    )
) else (
    echo Python 运行时: 未安装
)
echo.

echo [核心模块]
if exist "core\site-packages\pdf2zh" (
    echo pdf2zh 库: 已安装
) else (
    echo pdf2zh 库: 未安装
)

if exist "core\site-packages\PyQt5" (
    echo PyQt5 库: 已安装
) else (
    echo PyQt5 库: 未安装
)

if exist "core\site-packages\requests" (
    echo requests 库: 已安装
) else (
    echo requests 库: 未安装
)
echo.

echo [可选模块]
if exist "models\layout" (
    echo AI模型包: 已安装
) else (
    echo AI模型包: 未安装
)

if exist "plugins\translators_extended" (
    echo 扩展翻译服务: 已安装
) else (
    echo 扩展翻译服务: 未安装
)
echo.

echo [配置文件]
if exist "config\app.json" (
    echo 应用配置: 存在
) else (
    echo 应用配置: 不存在
)

if exist "config\user.json" (
    echo 用户配置: 存在
) else (
    echo 用户配置: 不存在
)
echo.

echo [目录结构]
echo 安装目录: %~dp0
dir /b
echo.

echo [进程信息]
tasklist | findstr python.exe
tasklist | findstr pdf2zh
echo.

echo [最近错误日志]
if exist "logs" (
    echo 日志目录: 存在
    for /f %%f in ('dir /b /o-d logs\*.log 2^>nul') do (
        echo 最新日志: logs\%%f
        echo --- 最后10行 ---
        powershell -command "Get-Content 'logs\%%f' -Tail 10"
        goto :log_done
    )
    :log_done
) else (
    echo 日志目录: 不存在
)
echo.

echo [环境变量]
echo PYTHONPATH: %PYTHONPATH%
echo PATH: %PATH%
echo.

echo ================================================================
echo   诊断完成
echo ================================================================
) > "%REPORT_FILE%"

:: 显示诊断结果
echo 诊断完成！
echo.
echo 诊断报告已保存到: %REPORT_FILE%
echo.

:: 分析问题
echo [问题分析]
set "ISSUES_FOUND=0"

if not exist "core\runtime\python.exe" (
    echo [!] 问题: Python 运行时未安装
    set /a ISSUES_FOUND+=1
)

if not exist "core\site-packages\pdf2zh" (
    echo [!] 问题: pdf2zh 库未安装
    set /a ISSUES_FOUND+=1
)

reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 问题: VC++ 运行库未安装
    set /a ISSUES_FOUND+=1
)

for /f "skip=1" %%p in ('wmic computersystem get TotalPhysicalMemory') do (
    set /a MEMORY_GB=%%p/1024/1024/1024
    goto :check_memory
)
:check_memory
if %MEMORY_GB% LSS 4 (
    echo [!] 问题: 系统内存不足 (%MEMORY_GB%GB^<4GB)
    set /a ISSUES_FOUND+=1
)

ping -n 1 google.com >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 问题: 网络连接异常
    set /a ISSUES_FOUND+=1
)

if %ISSUES_FOUND% == 0 (
    echo [✓] 未发现明显问题
) else (
    echo [!] 发现 %ISSUES_FOUND% 个问题
)

echo.
echo [建议操作]
if not exist "core\runtime\python.exe" (
    echo - 运行 install.bat 安装核心组件
)
if not exist "core\site-packages\pdf2zh" (
    echo - 运行 module_manager.bat 安装 pdf2zh 库
)
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %errorlevel% neq 0 (
    echo - 安装 Visual C++ Redistributable
)
if %MEMORY_GB% LSS 4 (
    echo - 考虑增加系统内存或关闭其他程序
)

echo.
choice /c YN /m "是否查看完整诊断报告"
if %errorlevel% == 1 (
    notepad "%REPORT_FILE%"
)

echo.
choice /c YN /m "是否将报告复制到剪贴板"
if %errorlevel% == 1 (
    type "%REPORT_FILE%" | clip
    echo [✓] 报告已复制到剪贴板
)

echo.
echo 感谢使用 pdf2zh 桌面版诊断工具！
pause