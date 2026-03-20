@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版卸载程序
title pdf2zh 桌面版 - 卸载程序

echo ================================================================
echo   pdf2zh 桌面版 - 卸载程序
echo ================================================================
echo.

:: 警告提示
echo [警告] 此操作将完全移除 pdf2zh 桌面版及其所有数据
echo.
echo 将要删除的内容:
echo   - 程序文件和运行时
echo   - 配置文件和用户设置
echo   - 缓存文件和临时数据
echo   - 桌面快捷方式
echo   - 翻译历史记录
echo.
echo [注意] 翻译输出的PDF文件(pdf2zh_files目录)将被保留
echo.

choice /c YN /m "确定要卸载 pdf2zh 桌面版吗"
if %errorlevel% == 2 (
    echo 取消卸载
    pause
    exit /b 0
)

echo.
echo 开始卸载...

:: 关闭可能运行的程序
echo [1/6] 关闭运行中的程序...
taskkill /f /im python.exe 2>nul
taskkill /f /im pdf2zh.exe 2>nul
timeout /t 2 /nobreak >nul

:: 删除桌面快捷方式
echo [2/6] 删除桌面快捷方式...
set "DESKTOP=%USERPROFILE%\Desktop"
del "%DESKTOP%\pdf2zh 桌面版.lnk" 2>nul
if exist "%DESKTOP%\pdf2zh 桌面版.lnk" (
    echo [!] 无法删除桌面快捷方式
) else (
    echo [✓] 桌面快捷方式已删除
)

:: 删除开始菜单快捷方式
echo [3/6] 删除开始菜单快捷方式...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"
del "%STARTMENU%\pdf2zh 桌面版.lnk" 2>nul

:: 备份用户数据
echo [4/6] 备份用户数据...
set "BACKUP_DIR=%USERPROFILE%\pdf2zh_backup_%date:~0,4%%date:~5,2%%date:~8,2%"
mkdir "%BACKUP_DIR%" 2>nul

if exist "pdf2zh_files" (
    echo 正在备份翻译文件到: %BACKUP_DIR%
    xcopy "pdf2zh_files" "%BACKUP_DIR%\pdf2zh_files" /e /i /q 2>nul
)

if exist "config\user_config.json" (
    copy "config\user_config.json" "%BACKUP_DIR%\" 2>nul
)

if exist "%USERPROFILE%\pdf2zh_history.json" (
    copy "%USERPROFILE%\pdf2zh_history.json" "%BACKUP_DIR%\" 2>nul
)

echo [✓] 用户数据已备份到: %BACKUP_DIR%

:: 删除程序文件
echo [5/6] 删除程序文件...
cd /d "%~dp0"
set "INSTALL_DIR=%~dp0"

:: 删除核心文件
rmdir /s /q "core" 2>nul
rmdir /s /q "models" 2>nul
rmdir /s /q "plugins" 2>nul
rmdir /s /q "cache" 2>nul
rmdir /s /q "assets" 2>nul
del "config\*.json" 2>nul
rmdir /s /q "config" 2>nul

:: 删除脚本文件
del "run_desktop.bat" 2>nul
del "install.bat" 2>nul
del "module_manager.bat" 2>nul
del "README.md" 2>nul
del "LICENSE" 2>nul
del "requirements.txt" 2>nul
del ".gitignore" 2>nul
del "pyproject.toml" 2>nul

:: 清理注册表和用户配置
echo [6/6] 清理用户配置...
del "%USERPROFILE%\pdf2zh_gui_config.json" 2>nul
del "%USERPROFILE%\pdf2zh_history.json" 2>nul
rmdir /s /q "%USERPROFILE%\.config\PDFMathTranslate" 2>nul

:: 卸载完成
echo.
echo ================================================================
echo   卸载完成！
echo ================================================================
echo.
echo 卸载信息:
echo   - 程序文件: 已删除
echo   - 配置文件: 已删除
echo   - 缓存文件: 已删除
echo   - 快捷方式: 已删除
echo.
echo 保留内容:
echo   - 翻译文件备份: %BACKUP_DIR%
echo   - 原始pdf2zh_files目录: 已保留
echo.
echo 如需完全清理，请手动删除:
echo   - %BACKUP_DIR%
echo   - %INSTALL_DIR%pdf2zh_files
echo.

:: 询问是否删除安装目录
choice /c YN /m "是否删除整个安装目录"
if %errorlevel% == 1 (
    echo 正在删除安装目录...
    cd /d "%TEMP%"
    rmdir /s /q "%INSTALL_DIR%" 2>nul
    echo [✓] 安装目录已删除
) else (
    echo 安装目录已保留: %INSTALL_DIR%
)

echo.
echo 感谢使用 pdf2zh 桌面版！
echo 如有问题或建议，欢迎访问项目主页反馈
pause

:: 删除卸载脚本自身
del "%~f0" 2>nul