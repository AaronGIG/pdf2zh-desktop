/*
 * pdf2zh 桌面版启动器
 * 编译：windres pdf2zh.rc -o pdf2zh_res.o && gcc -mwindows pdf2zh.c pdf2zh_res.o -o pdf2zh.exe
 * 功能：调用同目录下的 core\runtime\pythonw.exe _launcher.py
 */
#include <windows.h>
#include <stdio.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    wchar_t appDir[MAX_PATH];
    wchar_t pythonw[MAX_PATH];
    wchar_t script[MAX_PATH];
    wchar_t cmdLine[MAX_PATH * 3];

    // 获取 exe 所在目录
    GetModuleFileNameW(NULL, appDir, MAX_PATH);
    wchar_t *lastSlash = wcsrchr(appDir, L'\\');
    if (lastSlash) *lastSlash = L'\0';

    // 构建路径
    swprintf(pythonw, MAX_PATH, L"%s\\core\\runtime\\pythonw.exe", appDir);
    swprintf(script, MAX_PATH, L"%s\\_launcher.py", appDir);

    // 检查 pythonw.exe 是否存在
    if (GetFileAttributesW(pythonw) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
            L"找不到 Python 运行时：core\\runtime\\pythonw.exe\n\n"
            L"请确保完整解压了 pdf2zh-desktop-win 压缩包。",
            L"pdf2zh 桌面版", MB_ICONERROR);
        return 1;
    }

    // 设置环境变量
    SetEnvironmentVariableW(L"PYTHONHOME", NULL);
    SetEnvironmentVariableW(L"PYTHONPATH", NULL);
    SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE", L"1");
    SetEnvironmentVariableW(L"PYTHONIOENCODING", L"utf-8");

    // 构建命令行
    swprintf(cmdLine, MAX_PATH * 3, L"\"%s\" \"%s\"", pythonw, script);

    // 启动进程
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;

    if (!CreateProcessW(NULL, cmdLine, NULL, NULL, FALSE, 0, NULL, appDir, &si, &pi)) {
        MessageBoxW(NULL,
            L"启动失败，请尝试直接运行 pdf2zh.bat",
            L"pdf2zh 桌面版", MB_ICONERROR);
        return 1;
    }

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return 0;
}
