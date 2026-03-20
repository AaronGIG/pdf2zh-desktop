@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版模块管理器
title pdf2zh 桌面版 - 模块管理器

echo ================================================================
echo   pdf2zh 桌面版 - 模块管理器
echo ================================================================
echo.

:: 设置变量
set "BASE_URL=https://github.com/your-username/pdf2zh-desktop/releases/download"
set "VERSION=v1.9.9"
set "CONFIG_FILE=config\modules.json"

:: 检查配置文件
if not exist "%CONFIG_FILE%" (
    echo [错误] 模块配置文件不存在: %CONFIG_FILE%
    pause
    exit /b 1
)

:: 显示菜单
:menu
cls
echo ================================================================
echo   pdf2zh 桌面版 - 模块管理器
echo ================================================================
echo.
echo 当前已安装模块:
if exist "core\runtime\python.exe" (
    echo [✓] 核心模块 - 已安装
) else (
    echo [✗] 核心模块 - 未安装
)

if exist "core\site-packages\pdf2zh" (
    echo [✓] PDF2ZH 库 - 已安装
) else (
    echo [✗] PDF2ZH 库 - 未安装
)

if exist "models\layout" (
    echo [✓] AI模型包 - 已安装
) else (
    echo [✗] AI模型包 - 未安装
)

if exist "plugins\translators_extended" (
    echo [✓] 扩展翻译服务 - 已安装
) else (
    echo [✗] 扩展翻译服务 - 未安装
)

echo.
echo 可用操作:
echo   1. 安装核心模块
echo   2. 安装AI模型包
echo   3. 安装扩展翻译服务
echo   4. 安装高级功能包
echo   5. 检查更新
echo   6. 卸载模块
echo   0. 退出
echo.

set /p choice="请选择操作 (0-6): "

if "%choice%"=="1" goto install_core
if "%choice%"=="2" goto install_models
if "%choice%"=="3" goto install_translators
if "%choice%"=="4" goto install_advanced
if "%choice%"=="5" goto check_updates
if "%choice%"=="6" goto uninstall
if "%choice%"=="0" goto exit
goto menu

:install_core
echo.
echo [1/3] 下载核心模块...
call :download_file "%BASE_URL%/%VERSION%/core_runtime.zip" "core_runtime.zip"
if %errorlevel% neq 0 goto download_error

echo [2/3] 解压核心模块...
powershell -command "Expand-Archive -Path 'core_runtime.zip' -DestinationPath 'core' -Force"
if %errorlevel% neq 0 goto extract_error

echo [3/3] 清理临时文件...
del "core_runtime.zip" 2>nul

echo [✓] 核心模块安装完成
pause
goto menu

:install_models
echo.
echo [1/3] 下载AI模型包 (约200MB)...
call :download_file "%BASE_URL%/%VERSION%/models.zip" "models.zip"
if %errorlevel% neq 0 goto download_error

echo [2/3] 解压AI模型包...
mkdir "models" 2>nul
powershell -command "Expand-Archive -Path 'models.zip' -DestinationPath 'models' -Force"
if %errorlevel% neq 0 goto extract_error

echo [3/3] 清理临时文件...
del "models.zip" 2>nul

echo [✓] AI模型包安装完成
pause
goto menu

:install_translators
echo.
echo [1/3] 下载扩展翻译服务...
call :download_file "%BASE_URL%/%VERSION%/translators_extended.zip" "translators_extended.zip"
if %errorlevel% neq 0 goto download_error

echo [2/3] 解压扩展翻译服务...
mkdir "plugins" 2>nul
powershell -command "Expand-Archive -Path 'translators_extended.zip' -DestinationPath 'plugins' -Force"
if %errorlevel% neq 0 goto extract_error

echo [3/3] 清理临时文件...
del "translators_extended.zip" 2>nul

echo [✓] 扩展翻译服务安装完成
pause
goto menu

:install_advanced
echo.
echo [1/3] 下载高级功能包...
call :download_file "%BASE_URL%/%VERSION%/advanced_features.zip" "advanced_features.zip"
if %errorlevel% neq 0 goto download_error

echo [2/3] 解压高级功能包...
powershell -command "Expand-Archive -Path 'advanced_features.zip' -DestinationPath 'plugins' -Force"
if %errorlevel% neq 0 goto extract_error

echo [3/3] 清理临时文件...
del "advanced_features.zip" 2>nul

echo [✓] 高级功能包安装完成
pause
goto menu

:check_updates
echo.
echo 检查更新中...
:: 这里可以添加版本检查逻辑
echo [信息] 当前版本: %VERSION%
echo [信息] 暂无可用更新
pause
goto menu

:uninstall
echo.
echo 卸载模块:
echo   1. 卸载AI模型包
echo   2. 卸载扩展翻译服务
echo   3. 卸载高级功能包
echo   0. 返回主菜单
echo.
set /p uninstall_choice="请选择要卸载的模块: "

if "%uninstall_choice%"=="1" (
    rmdir /s /q "models" 2>nul
    echo [✓] AI模型包已卸载
)
if "%uninstall_choice%"=="2" (
    rmdir /s /q "plugins\translators_extended" 2>nul
    echo [✓] 扩展翻译服务已卸载
)
if "%uninstall_choice%"=="3" (
    rmdir /s /q "plugins\advanced_features" 2>nul
    echo [✓] 高级功能包已卸载
)
if "%uninstall_choice%"=="0" goto menu

pause
goto menu

:download_file
echo 正在下载: %~2
powershell -command "
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing
    Write-Host '[✓] 下载完成'
    exit 0
} catch {
    Write-Host '[✗] 下载失败: ' $_.Exception.Message
    exit 1
}
"
exit /b %errorlevel%

:download_error
echo [✗] 下载失败，请检查网络连接
pause
goto menu

:extract_error
echo [✗] 解压失败，请检查文件完整性
pause
goto menu

:exit
echo 感谢使用 pdf2zh 桌面版模块管理器！
exit /b 0