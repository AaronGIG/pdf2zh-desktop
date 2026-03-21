@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版智能启动脚本
title pdf2zh 桌面版

:: 设置颜色和编码
chcp 65001 >nul 2>&1
color 0F

:: 显示启动横幅
echo.
echo ================================================================
echo   pdf2zh 桌面版 v1.9.9
echo   PDF 文档翻译工具
echo ================================================================
echo.

:: 设置工作目录
cd /d "%~dp0"
set "APP_DIR=%~dp0"

:: 检查系统环境
call :check_system

:: 检查核心模块
call :check_core_modules

:: 设置环境变量
call :setup_environment

:: 启动应用程序
call :start_application

goto :eof

:: ============================================================================
:: 函数定义
:: ============================================================================

:check_system
echo [检查] 系统环境...
for /f "tokens=4-5 delims=. " %%i in ('ver') do set VERSION=%%i.%%j
echo [✓] 操作系统: Windows %VERSION%

if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo [✓] 系统架构: x64
) else (
    echo [错误] 不支持的系统架构: %PROCESSOR_ARCHITECTURE%
    pause
    exit /b 1
)
goto :eof

:check_core_modules
echo [检查] 核心模块...

if not exist "core\runtime\python.exe" (
    echo [错误] Python 运行时未找到
    echo        请运行 install.bat 进行安装
    pause
    exit /b 1
)
echo [✓] Python 运行时

if not exist "core\site-packages\pdf2zh" (
    echo [错误] pdf2zh 库未找到
    echo        请检查 core\site-packages 目录
    pause
    exit /b 1
)
echo [✓] pdf2zh 库

if not exist "config\app.json" (
    echo [警告] 应用配置文件不存在，将使用默认配置
    call :create_default_config
) else (
    echo [✓] 应用配置
)

:: AI 布局检测模型由 babeldoc 管理，首次翻译时自动下载到用户缓存目录
:: 检查 VC++ 运行库是否已安装（AI 布局检测的前提条件）
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] VC++ 运行库 (AI布局检测可用)
) else (
    echo [!] VC++ 运行库未安装 (AI布局检测不可用，翻译功能不受影响)
    echo     运行 VC_redist.x64.exe 或 install.bat 安装
)
goto :eof

:setup_environment
echo [设置] 运行环境...

set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONHOME="
set "PYTHONPATH="
set "PATH=%APP_DIR%core\runtime;%PATH%"

if not exist "pdf2zh_files" mkdir "pdf2zh_files"
if not exist "cache" mkdir "cache"
if not exist "logs" mkdir "logs"

echo [✓] 环境变量已设置
goto :eof

:start_application
echo [启动] pdf2zh 桌面版...
echo.

set "LOG_FILE=logs\app_%date:~0,4%%date:~5,2%%date:~8,2%.log"

"%APP_DIR%core\runtime\python.exe" "%APP_DIR%_launcher.py" 2>&1

if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出 (代码: %errorlevel%)
    echo 请查看日志获取更多信息
    echo.
    pause
)
goto :eof

:create_default_config
echo [创建] 默认配置文件...
mkdir "config" 2>nul
(
echo {
echo   "app": {
echo     "name": "pdf2zh 桌面版",
echo     "version": "1.9.9"
echo   },
echo   "features": {
echo     "core_translation": true,
echo     "pdf_preview": true
echo   }
echo }
) > "config\app.json"
goto :eof
