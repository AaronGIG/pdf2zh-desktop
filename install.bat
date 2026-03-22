@echo off
chcp 65001>nul 2>&1
setlocal enabledelayedexpansion

:: pdf2zh 桌面版一键安装脚本
title pdf2zh 桌面版 - 安装程序

echo ================================================================
echo   pdf2zh 桌面版 v1.9.9 - 一键安装程序
echo   PDF 文档翻译工具
echo ================================================================
echo.

:: 检查管理员权限
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [信息] 检测到管理员权限
) else (
    echo [警告] 建议以管理员身份运行以确保完整安装
)

:: 设置安装目录
set "INSTALL_DIR=%~dp0"
echo [信息] 安装目录: %INSTALL_DIR%

:: 检查系统要求
echo.
echo [1/6] 检查系统要求...
ver | find "10.0" >nul
if %errorlevel% == 0 (
    echo [✓] Windows 10/11 64位系统
) else (
    echo [✗] 不支持的操作系统版本
    echo 需要 Windows 10/11 64位系统
    pause
    exit /b 1
)

:: 检查 VC++ Redistributable
echo.
echo [2/6] 检查 Visual C++ 运行库...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %errorlevel% == 0 (
    echo [✓] Visual C++ Redistributable 已安装
) else (
    echo [!] 需要安装 Visual C++ Redistributable
    if exist "VC_redist.x64.exe" (
        echo 正在安装 VC++ 运行库...
        VC_redist.x64.exe /quiet /norestart
        if %errorlevel% == 0 (
            echo [✓] VC++ 运行库安装成功
        ) else (
            echo [✗] VC++ 运行库安装失败
            pause
            exit /b 1
        )
    ) else (
        echo [✗] 找不到 VC_redist.x64.exe 安装包
        echo 请从 https://aka.ms/vs/17/release/vc_redist.x64.exe 下载
        pause
        exit /b 1
    )
)

:: 创建目录结构
echo.
echo [3/6] 创建目录结构...
mkdir "%INSTALL_DIR%core" 2>nul
mkdir "%INSTALL_DIR%config" 2>nul
mkdir "%INSTALL_DIR%plugins" 2>nul
mkdir "%INSTALL_DIR%cache" 2>nul
mkdir "%INSTALL_DIR%assets" 2>nul
mkdir "%INSTALL_DIR%pdf2zh_files" 2>nul
echo [✓] 目录结构创建完成

:: 解压核心模块
echo.
echo [4/6] 安装核心模块...
if exist "core_runtime.zip" (
    echo 正在解压 Python 运行时...
    powershell -command "Expand-Archive -Path 'core_runtime.zip' -DestinationPath '%INSTALL_DIR%core' -Force"
    if %errorlevel% == 0 (
        echo [✓] Python 运行时安装完成
    ) else (
        echo [✗] Python 运行时安装失败
        pause
        exit /b 1
    )
) else (
    echo [!] 核心运行时包不存在，跳过安装
)

:: 安装依赖包
echo.
echo [5/6] 安装依赖包...
if exist "site_packages.zip" (
    echo 正在解压依赖包...
    powershell -command "Expand-Archive -Path 'site_packages.zip' -DestinationPath '%INSTALL_DIR%core' -Force"
    if %errorlevel% == 0 (
        echo [✓] 依赖包安装完成
    ) else (
        echo [✗] 依赖包安装失败
        pause
        exit /b 1
    )
) else (
    echo [!] 依赖包不存在，跳过安装
)

:: 创建桌面快捷方式
echo.
echo [6/6] 创建快捷方式...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\pdf2zh 桌面版.lnk"

powershell -command "
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('%SHORTCUT%')
$Shortcut.TargetPath = '%INSTALL_DIR%pdf2zh.vbs'
$Shortcut.WorkingDirectory = '%INSTALL_DIR%'
$Shortcut.Description = 'pdf2zh 桌面版 - PDF 文档翻译工具'
$Shortcut.Save()
"

if exist "%SHORTCUT%" (
    echo [✓] 桌面快捷方式创建成功
) else (
    echo [!] 桌面快捷方式创建失败
)

:: 安装完成
echo.
echo ================================================================
echo   安装完成！
echo ================================================================
echo.
echo 安装信息:
echo   - 安装目录: %INSTALL_DIR%
echo   - 启动方式: 双击 pdf2zh.vbs 或桌面快捷方式（无控制台窗口）
echo   - 配置文件: config\app.json
echo   - 输出目录: pdf2zh_files\
echo.
echo 使用说明:
echo   1. 双击桌面快捷方式启动程序
echo   2. 选择要翻译的 PDF 文件
echo   3. 配置翻译参数（语言、服务等）
echo   4. 点击开始翻译
echo.
echo 技术支持:
echo   - 项目主页: https://github.com/your-username/pdf2zh-desktop
echo   - 问题反馈: https://github.com/your-username/pdf2zh-desktop/issues
echo.

choice /c YN /m "是否现在启动 pdf2zh 桌面版"
if %errorlevel% == 1 (
    echo 正在启动程序...
    start "" "%INSTALL_DIR%run_desktop.bat"
)

echo 感谢使用 pdf2zh 桌面版！
pause