@echo off
chcp 65001>nul 2>&1
setlocal enabledelayedexpansion

:: pdf2zh 桌面版一键安装脚本
title pdf2zh 桌面版 - 安装程序

echo ================================================================
echo   pdf2zh 桌面版 v1.0.0 - 一键安装程序
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
    echo [√] Windows 10/11 64位系统
) else (
    echo [×] 不支持的操作系统版本
    echo 需要 Windows 10/11 64位系统
    pause
    exit /b 1
)

:: 检查 VC++ Redistributable
echo.
echo [2/6] 检查 Visual C++ 运行库...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %errorlevel% == 0 (
    echo [√] Visual C++ Redistributable 已安装
) else (
    echo [!] 需要安装 Visual C++ Redistributable
    if exist "%INSTALL_DIR%VC_redist.x64.exe" (
        echo 正在安装 VC++ 运行库...
        "%INSTALL_DIR%VC_redist.x64.exe" /quiet /norestart
        if %errorlevel% == 0 (
            echo [√] VC++ 运行库安装成功
        ) else (
            echo [×] VC++ 运行库安装失败
            pause
            exit /b 1
        )
    ) else (
        echo [×] 找不到 VC_redist.x64.exe 安装包
        echo 请从 https://aka.ms/vs/17/release/vc_redist.x64.exe 下载
        pause
        exit /b 1
    )
)

:: 创建目录结构
echo.
echo [3/6] 创建目录结构...
mkdir "%INSTALL_DIR%pdf2zh_files" 2>nul
mkdir "%INSTALL_DIR%logs" 2>nul
echo [√] 目录结构创建完成

:: 检查核心文件
echo.
echo [4/6] 检查核心模块...
if exist "%INSTALL_DIR%core\runtime\pythonw.exe" (
    echo [√] Python 运行时已就绪
) else (
    echo [×] Python 运行时缺失，请重新下载完整的发行包
    pause
    exit /b 1
)

:: 检查依赖包
echo.
echo [5/6] 检查依赖包...
if exist "%INSTALL_DIR%core\site-packages\pdf2zh\gui_pyqt5.py" (
    echo [√] 依赖包已就绪
) else (
    echo [×] 依赖包缺失，请重新下载完整的发行包
    pause
    exit /b 1
)

:: 创建桌面快捷方式
echo.
echo [6/6] 创建快捷方式...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\pdf2zh 桌面版.lnk"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%pdf2zh.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'pdf2zh 桌面版 - PDF 文档翻译工具'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [√] 桌面快捷方式创建成功
) else (
    echo [!] 桌面快捷方式创建失败（不影响使用，可手动双击 pdf2zh.bat 启动）
)

:: 安装完成
echo.
echo ================================================================
echo   安装完成！
echo ================================================================
echo.
echo 安装信息:
echo   - 安装目录: %INSTALL_DIR%
echo   - 启动方式: 双击 pdf2zh.bat 或桌面快捷方式
echo   - 输出目录: pdf2zh_files\
echo.
echo 使用说明:
echo   1. 双击桌面快捷方式或 pdf2zh.bat 启动程序
echo   2. 选择要翻译的 PDF 文件
echo   3. 配置翻译参数（语言、服务等）
echo   4. 点击「开始翻译」
echo.
echo 技术支持:
echo   - 项目主页: https://github.com/AaronGIG/pdf2zh-desktop
echo   - 问题反馈: https://github.com/AaronGIG/pdf2zh-desktop/issues
echo.

choice /c YN /m "是否现在启动 pdf2zh 桌面版"
if %errorlevel% == 1 (
    echo 正在启动程序...
    start "" "%INSTALL_DIR%pdf2zh.bat"
)

echo 感谢使用 pdf2zh 桌面版！
pause
