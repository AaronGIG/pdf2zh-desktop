@echo off
setlocal enabledelayedexpansion

:: pdf2zh 桌面版配置管理器
title pdf2zh 桌面版 - 配置管理器

echo ================================================================
echo   pdf2zh 桌面版 - 配置管理器
echo ================================================================
echo.

set "CONFIG_DIR=config"
set "APP_CONFIG=%CONFIG_DIR%\app.json"
set "USER_CONFIG=%CONFIG_DIR%\user.json"
set "MODULES_CONFIG=%CONFIG_DIR%\modules.json"

:menu
cls
echo ================================================================
echo   pdf2zh 桌面版 - 配置管理器
echo ================================================================
echo.
echo 当前配置状态:
if exist "%APP_CONFIG%" (
    echo [✓] 应用配置 - 已存在
) else (
    echo [✗] 应用配置 - 不存在
)

if exist "%USER_CONFIG%" (
    echo [✓] 用户配置 - 已存在
) else (
    echo [✗] 用户配置 - 不存在
)

if exist "%MODULES_CONFIG%" (
    echo [✓] 模块配置 - 已存在
) else (
    echo [✗] 模块配置 - 不存在
)

echo.
echo 可用操作:
echo   1. 创建默认配置
echo   2. 重置用户配置
echo   3. 备份配置文件
echo   4. 恢复配置文件
echo   5. 编辑配置文件
echo   6. 验证配置文件
echo   7. 导入/导出配置
echo   0. 退出
echo.

set /p choice="请选择操作 (0-7): "

if "%choice%"=="1" goto create_default
if "%choice%"=="2" goto reset_user
if "%choice%"=="3" goto backup_config
if "%choice%"=="4" goto restore_config
if "%choice%"=="5" goto edit_config
if "%choice%"=="6" goto validate_config
if "%choice%"=="7" goto import_export
if "%choice%"=="0" goto exit
goto menu

:create_default
echo.
echo 创建默认配置文件...
mkdir "%CONFIG_DIR%" 2>nul

:: 创建应用配置
echo 创建应用配置文件...
(
echo {
echo   "app": {
echo     "name": "pdf2zh 桌面版",
echo     "version": "1.9.9",
echo     "build": "slim",
echo     "author": "pdf2zh Desktop Contributors"
echo   },
echo   "runtime": {
echo     "python_version": "3.12",
echo     "architecture": "x64",
echo     "embedded": true
echo   },
echo   "features": {
echo     "core_translation": true,
echo     "pdf_preview": true,
echo     "batch_processing": true,
echo     "cache_system": true,
echo     "auto_update": true
echo   },
echo   "paths": {
echo     "core": "./core",
echo     "config": "./config",
echo     "plugins": "./plugins",
echo     "cache": "./cache",
echo     "assets": "./assets",
echo     "output": "./pdf2zh_files"
echo   },
echo   "optimization": {
echo     "lazy_loading": true,
echo     "memory_limit": "512MB",
echo     "cache_size": "100MB",
echo     "preload_models": false
echo   }
echo }
) > "%APP_CONFIG%"

:: 创建用户配置
echo 创建用户配置文件...
(
echo {
echo   "ui": {
echo     "language": "zh-CN",
echo     "theme": "light",
echo     "window_size": [1200, 800],
echo     "window_position": "center",
echo     "remember_settings": true
echo   },
echo   "translation": {
echo     "default_service": "Google",
echo     "source_language": "auto",
echo     "target_language": "zh-CN",
echo     "output_format": "dual",
echo     "batch_size": 5
echo   },
echo   "advanced": {
echo     "thread_count": 4,
echo     "skip_font_subset": false,
echo     "ignore_cache": false,
echo     "formula_font_regex": "",
echo     "auto_save": true
echo   },
echo   "api_keys": {
echo     "openai": "",
echo     "deepl": "",
echo     "azure": "",
echo     "google": ""
echo   }
echo }
) > "%USER_CONFIG%"

echo [✓] 默认配置文件创建完成
pause
goto menu

:reset_user
echo.
echo [警告] 此操作将重置所有用户配置
choice /c YN /m "确定要重置用户配置吗"
if %errorlevel% == 2 goto menu

if exist "%USER_CONFIG%" (
    copy "%USER_CONFIG%" "%USER_CONFIG%.backup" >nul
    echo [✓] 已备份原配置为: %USER_CONFIG%.backup
)

goto create_default

:backup_config
echo.
echo 备份配置文件...
set "BACKUP_DIR=config_backup_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "BACKUP_DIR=%BACKUP_DIR: =0%"
mkdir "%BACKUP_DIR%" 2>nul

if exist "%CONFIG_DIR%" (
    xcopy "%CONFIG_DIR%\*" "%BACKUP_DIR%\" /y >nul
    echo [✓] 配置文件已备份到: %BACKUP_DIR%
) else (
    echo [!] 配置目录不存在
)
pause
goto menu

:restore_config
echo.
echo 可用的备份:
for /d %%d in (config_backup_*) do echo   - %%d
echo.
set /p backup_name="请输入要恢复的备份目录名: "

if exist "%backup_name%" (
    echo [警告] 此操作将覆盖当前配置
    choice /c YN /m "确定要恢复配置吗"
    if !errorlevel! == 1 (
        xcopy "%backup_name%\*" "%CONFIG_DIR%\" /y >nul
        echo [✓] 配置已从 %backup_name% 恢复
    )
) else (
    echo [!] 备份目录不存在: %backup_name%
)
pause
goto menu

:edit_config
echo.
echo 选择要编辑的配置文件:
echo   1. 应用配置 (%APP_CONFIG%)
echo   2. 用户配置 (%USER_CONFIG%)
echo   3. 模块配置 (%MODULES_CONFIG%)
echo   0. 返回
echo.
set /p edit_choice="请选择: "

if "%edit_choice%"=="1" (
    if exist "%APP_CONFIG%" (
        notepad "%APP_CONFIG%"
    ) else (
        echo [!] 文件不存在: %APP_CONFIG%
    )
)
if "%edit_choice%"=="2" (
    if exist "%USER_CONFIG%" (
        notepad "%USER_CONFIG%"
    ) else (
        echo [!] 文件不存在: %USER_CONFIG%
    )
)
if "%edit_choice%"=="3" (
    if exist "%MODULES_CONFIG%" (
        notepad "%MODULES_CONFIG%"
    ) else (
        echo [!] 文件不存在: %MODULES_CONFIG%
    )
)
if "%edit_choice%"=="0" goto menu

pause
goto menu

:validate_config
echo.
echo 验证配置文件...

:: 验证JSON格式
for %%f in ("%APP_CONFIG%" "%USER_CONFIG%" "%MODULES_CONFIG%") do (
    if exist "%%f" (
        echo 验证: %%f
        powershell -command "
        try {
            $json = Get-Content '%%f' -Raw | ConvertFrom-Json
            Write-Host '[✓] JSON格式正确'
        } catch {
            Write-Host '[✗] JSON格式错误: ' $_.Exception.Message
        }
        "
    ) else (
        echo [!] 文件不存在: %%f
    )
)

pause
goto menu

:import_export
echo.
echo 配置导入/导出:
echo   1. 导出配置包
echo   2. 导入配置包
echo   0. 返回
echo.
set /p ie_choice="请选择: "

if "%ie_choice%"=="1" (
    set "EXPORT_FILE=pdf2zh_config_%date:~0,4%%date:~5,2%%date:~8,2%.zip"
    echo 正在导出配置包...
    powershell -command "Compress-Archive -Path '%CONFIG_DIR%\*' -DestinationPath '%EXPORT_FILE%' -Force"
    if exist "%EXPORT_FILE%" (
        echo [✓] 配置包已导出: %EXPORT_FILE%
    ) else (
        echo [✗] 导出失败
    )
)

if "%ie_choice%"=="2" (
    set /p import_file="请输入配置包文件名: "
    if exist "!import_file!" (
        echo [警告] 此操作将覆盖当前配置
        choice /c YN /m "确定要导入配置吗"
        if !errorlevel! == 1 (
            powershell -command "Expand-Archive -Path '!import_file!' -DestinationPath '%CONFIG_DIR%' -Force"
            echo [✓] 配置包已导入
        )
    ) else (
        echo [!] 文件不存在: !import_file!
    )
)

pause
goto menu

:exit
echo 感谢使用 pdf2zh 桌面版配置管理器！
exit /b 0