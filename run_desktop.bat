@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版启动脚本 (精简版)
title pdf2zh 桌面版

:: 设置工作目录
cd /d "%~dp0"

:: 检查核心模块
if not exist "core\runtime\python.exe" (
    echo [错误] 核心运行时未找到
    echo 请运行 install.bat 进行初始化安装
    pause
    exit /b 1
)

if not exist "core\site-packages\pdf2zh" (
    echo [错误] pdf2zh 库未找到
    echo 请检查 core\site-packages 目录
    pause
    exit /b 1
)

:: 设置环境变量
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONHOME="
set "PYTHONPATH="

:: 设置 DLL 搜索路径
set "PATH=%~dp0core\runtime;%PATH%"

:: 检查配置文件
if not exist "config\app.json" (
    echo [警告] 配置文件不存在，使用默认配置
)

:: 创建输出目录
if not exist "pdf2zh_files" mkdir "pdf2zh_files"

:: 启动应用
echo 正在启动 pdf2zh 桌面版...
"%~dp0core\runtime\python.exe" -c "from pdf2zh.gui_pyqt5 import main; main()"

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出
    echo 请检查错误信息或联系技术支持
    pause
)
