/*
 * pdf2zh Connector for Zotero  v1.0.15
 *
 * 功能：
 *   1. HTTP 端点 /pdf2zh/attach — 接收 pdf2zh 翻译结果作为子附件（原有回写机制，一行不动）
 *   2. HTTP 端点 /pdf2zh/ping   — 健康检查（一行不动）
 *   3. NEW: 右键菜单「用 pdf2zh 翻译」— 唤起本地 pdf2zh app 翻译选中 PDF
 *
 * 兼容 Zotero 7 / 8 / 9（strict_min_version 6.999, strict_max_version 9.*）
 */

/* exported startup, shutdown, install, uninstall */

// ============ HTTP 端点（原有回写机制，不动）============

function _makeAttachEndpoint() {
    var AttachEndpoint = function () {};
    AttachEndpoint.prototype = {
        supportedMethods: ['POST'],
        supportedDataTypes: ['application/json'],
        permitBookmarklet: false,

        init: async function (options) {
            try {
                _dbgLog('=== /pdf2zh/attach POST received ===');
                var data = typeof options.data === 'string' ? JSON.parse(options.data) : options.data;
                var itemKey = data.itemKey;
                var filePath = data.filePath;
                var title = data.title;
                _dbgLog('  itemKey=' + itemKey + ' title=' + JSON.stringify(title) + ' filePath=' + JSON.stringify(filePath));

                if (!itemKey || !filePath) {
                    _dbgLog('  ✗ missing itemKey or filePath');
                    return [400, 'application/json', JSON.stringify({
                        error: 'Missing required fields: itemKey, filePath'
                    })];
                }

                var item = Zotero.Items.getByLibraryAndKey(
                    Zotero.Libraries.userLibraryID, itemKey
                );
                _dbgLog('  item lookup → ' + (item ? 'found id=' + item.id : 'NOT FOUND'));
                if (!item) {
                    return [404, 'application/json', JSON.stringify({
                        error: 'Item not found: ' + itemKey
                    })];
                }

                var parentID = item.parentItemID || item.id;
                _dbgLog('  parentID=' + parentID + ' calling importFromFile...');

                var attachment = await Zotero.Attachments.importFromFile({
                    file: filePath,
                    parentItemID: parentID,
                    title: title || 'Translated PDF',
                    contentType: 'application/pdf'
                });
                _dbgLog('  importFromFile SUCCESS: attachment.key=' + attachment.key + ' id=' + attachment.id);

                if (title) {
                    attachment.setField('title', title);
                    await attachment.saveTx();
                    _dbgLog('  title override saved');
                }

                _dbgLog('  === /pdf2zh/attach DONE ok ===');
                return [200, 'application/json', JSON.stringify({
                    key: attachment.key,
                    id: attachment.id
                })];
            } catch (e) {
                _dbgLog('  ✗ /pdf2zh/attach EXCEPTION: ' + e + ' stack=' + (e && e.stack ? e.stack : 'no-stack'));
                return [500, 'application/json', JSON.stringify({
                    error: String(e)
                })];
            }
        }
    };
    return AttachEndpoint;
}

function _makePingEndpoint() {
    var PingEndpoint = function () {};
    PingEndpoint.prototype = {
        supportedMethods: ['GET'],
        supportedDataTypes: ['application/json'],
        permitBookmarklet: false,

        init: async function (req) {
            return [200, 'application/json', JSON.stringify({
                status: 'ok',
                plugin: 'pdf2zh-desktop-connector',
                version: '1.0.15'
            })];
        }
    };
    return PingEndpoint;
}

// ============ NEW: 右键菜单唤起 pdf2zh ============

// v1.0.15: Zotero 9 (Firefox 128+) 移除了 OS 全局。用 PathUtils / nsIEnvironment 三层 fallback。
function _homeDir() {
    try { if (typeof PathUtils !== 'undefined' && PathUtils.homeDir) return PathUtils.homeDir; } catch (e) {}
    try { if (typeof OS !== 'undefined' && OS.Constants && OS.Constants.Path) return OS.Constants.Path.homeDir; } catch (e) {}
    try {
        return Components.classes["@mozilla.org/process/environment;1"]
            .getService(Components.interfaces.nsIEnvironment)
            .get(Zotero.isWin ? 'USERPROFILE' : 'HOME');
    } catch (e) {}
    return Zotero.isWin ? 'C:\\Users\\Default' : '/Users/Default';
}
function _pathJoin(a, b) {
    var sep = Zotero.isWin ? '\\' : '/';
    if (a.endsWith(sep)) return a + b;
    return a + sep + b;
}

// v1.0.15: 用户手动配置的路径 (Zotero pref)。找不到时可让用户设置 extensions.pdf2zh.exePath
function _getSavedExePath() {
    try {
        var p = Zotero.Prefs.get('extensions.pdf2zh.exePath', true);
        if (p && Zotero.File.pathToFile(p).exists()) return p;
    } catch (e) {}
    return null;
}

function _fileExists(path) {
    try {
        var f = Zotero.File.pathToFile(path);
        return f && f.exists() ? path : null;
    } catch (e) { return null; }
}

// 在某目录下浅层扫描 pdf2zh.exe: 直接子文件 + 一层子目录(处理带版本号外层)
function _scanDirForExe(dir, exeName) {
    try {
        var d = Zotero.File.pathToFile(dir);
        if (!d || !d.exists() || !d.isDirectory()) return null;
        var direct = _fileExists(_pathJoin(dir, exeName));
        if (direct) return direct;
        var entries = d.directoryEntries;
        while (entries.hasMoreElements()) {
            var sub = entries.getNext().QueryInterface(Components.interfaces.nsIFile);
            if (sub.isDirectory()) {
                var name = sub.leafName || '';
                // 只进 pdf2zh 相关子目录, 避免全盘扫描
                if (name.toLowerCase().indexOf('pdf2zh') === -1) continue;
                var hit = _fileExists(_pathJoin(sub.path, exeName));
                if (hit) return hit;
                // 再深一层: <base>\pdf2zh-desktop-win-v2.3.3\pdf2zh-desktop-win\pdf2zh.exe
                var hit2 = _fileExists(_pathJoin(sub.path, 'pdf2zh-desktop-win\\' + exeName));
                if (hit2) return hit2;
            }
        }
    } catch (e) {}
    return null;
}

// 找 pdf2zh 可执行文件（跨平台）— v1.0.15 大幅增强搜索
function _findPdf2zhExecutable() {
    var home = _homeDir();

    // 0) 用户手动配置优先
    var saved = _getSavedExePath();
    if (saved) return saved;

    if (Zotero.isMac) {
        var macs = ['/Applications/pdf2zh.app', _pathJoin(home, 'Applications/pdf2zh.app')];
        for (var i = 0; i < macs.length; i++) { if (_fileExists(macs[i])) return macs[i]; }
        return null;
    }

    if (!Zotero.isWin) {
        var lins = ['/usr/local/bin/pdf2zh', _pathJoin(home, 'pdf2zh-desktop-win/pdf2zh')];
        for (var j = 0; j < lins.length; j++) { if (_fileExists(lins[j])) return lins[j]; }
        return null;
    }

    // ===== Windows =====
    var exe = 'pdf2zh.exe';
    var folderNames = ['pdf2zh-desktop-win', 'pdf2zh-desktop-win-v2.3.3', 'pdf2zh-desktop-win-v2.3.2',
                       'pdf2zh-desktop-win-v2.3.1', 'pdf2zh'];
    // 1) 固定候选: <base>\<folderName>\pdf2zh.exe  和  <base>\pdf2zh.exe
    var bases = [
        'C:\\', 'C:\\Program Files', 'C:\\Program Files (x86)',
        _pathJoin(home, 'Downloads'), _pathJoin(home, 'Desktop'),
        _pathJoin(home, 'Documents'), home,
        'D:\\', 'D:\\Program Files', 'E:\\', 'F:\\'
    ];
    for (var b = 0; b < bases.length; b++) {
        for (var fn = 0; fn < folderNames.length; fn++) {
            var p = _fileExists(_pathJoin(_pathJoin(bases[b], folderNames[fn]), exe));
            if (p) return p;
            // 嵌套一层: <base>\<folderName>\pdf2zh-desktop-win\pdf2zh.exe
            var p2 = _fileExists(_pathJoin(_pathJoin(_pathJoin(bases[b], folderNames[fn]), 'pdf2zh-desktop-win'), exe));
            if (p2) return p2;
        }
        var direct = _fileExists(_pathJoin(bases[b], exe));
        if (direct) return direct;
    }
    // 2) 浅递归扫描常见下载/解压位置 (处理任意版本号外层文件夹名)
    var scanDirs = [_pathJoin(home, 'Downloads'), _pathJoin(home, 'Desktop'),
                    _pathJoin(home, 'Documents'), 'C:\\', 'D:\\', 'E:\\'];
    for (var s = 0; s < scanDirs.length; s++) {
        var hit = _scanDirForExe(scanDirs[s], exe);
        if (hit) return hit;
    }
    return null;
}

// v1.0.15: 日志到 /tmp/pdf2zh-xpi-debug.log 便于用户复制粘贴排查
function _dbgLog(msg) {
    try {
        var line = '[' + (new Date()).toISOString() + '] ' + msg + '\n';
        Zotero.debug('pdf2zh-xpi: ' + msg);
        // 走 IOUtils（Zotero 9+）→ OS.File（老版本）
        try {
            IOUtils.write('/tmp/pdf2zh-xpi-debug.log',
                new TextEncoder().encode(line),
                { mode: 'appendOrCreate' });
        } catch (e1) { /* IOUtils 不可用则算了，Zotero.debug 已经写了 */ }
    } catch (e) { /* never throw */ }
}

// 加载 Subprocess API（Zotero 9 / Firefox 128+ 用 .sys.mjs，Zotero 7/8 用 .jsm）
function _loadSubprocess() {
    try {
        return ChromeUtils.importESModule("resource://gre/modules/Subprocess.sys.mjs").Subprocess;
    } catch (e1) {
        try {
            return ChromeUtils.import("resource://gre/modules/Subprocess.jsm").Subprocess;
        } catch (e2) {
            return null;
        }
    }
}

// 唤起 pdf2zh app + 传参
async function _launchPdf2zh(filePath, format, auto) {
    var exe = _findPdf2zhExecutable();
    if (!exe) {
        // v1.0.15: 找不到时让用户手动指定 pdf2zh.exe / pdf2zh.app 路径, 存进 pref 永久生效
        var picked = null;
        try {
            var win = Zotero.getMainWindow();
            var yes = Services.prompt.confirm(win, 'pdf2zh-desktop Connector',
                '没有自动找到 pdf2zh-desktop 应用。\n\n' +
                'Windows: 请确认已把 pdf2zh-desktop-win 文件夹解压出来(里面有 pdf2zh.exe)。\n' +
                'Mac: 确认 pdf2zh.app 在“应用程序”里。\n\n' +
                '点“确定”手动选择 ' + (Zotero.isWin ? 'pdf2zh.exe' : 'pdf2zh.app') + ' 的位置(只需选一次)；\n' +
                '点“取消”去下载：github.com/AaronGIG/pdf2zh-desktop/releases');
            if (yes) {
                var fp = Components.classes['@mozilla.org/filepicker;1'].createInstance(Components.interfaces.nsIFilePicker);
                fp.init(win, '选择 pdf2zh 程序', fp.modeOpen);
                if (Zotero.isWin) { fp.appendFilter('pdf2zh.exe', 'pdf2zh.exe'); fp.appendFilters(fp.filterApps); }
                var rv = fp.show ? fp.show() : fp.open;
                if (rv === fp.returnOK && fp.file) {
                    picked = fp.file.path;
                    try { Zotero.Prefs.set('extensions.pdf2zh.exePath', picked, true); } catch (e) {}
                }
            }
        } catch (e) { /* 老版本 Zotero 无 filepicker 时降级 */ }
        if (picked) {
            exe = picked;
        } else {
            Zotero.alert(null, 'pdf2zh-desktop Connector',
                '未找到 pdf2zh-desktop 应用。\n' +
                'Windows: 把下载的 zip 解压, 确认有 pdf2zh-desktop-win\\pdf2zh.exe；建议解压到“下载”或“桌面”。\n' +
                'Mac: 把 pdf2zh.app 放进“应用程序”。\n\n' +
                '下载：https://github.com/AaronGIG/pdf2zh-desktop/releases');
            return;
        }
    }

    var args = [];
    if (format) args.push('--format=' + format);
    if (auto) args.push('--auto');
    args.push(filePath);

    var command, allArgs;
    if (Zotero.isMac) {
        command = '/usr/bin/open';
        allArgs = ['-a', exe, '--args'].concat(args);
    } else {
        command = exe;
        allArgs = args;
    }

    _dbgLog('launch command=' + command + ' args=' + JSON.stringify(allArgs));

    // 首选: Subprocess API（Zotero 9 / Firefox 128+ 之后 nsIProcess 在部分场景已失效）
    var Subprocess = _loadSubprocess();
    _dbgLog('Subprocess module: ' + (Subprocess ? 'available' : 'NOT available'));
    if (Subprocess) {
        try {
            _dbgLog('calling Subprocess.call...');
            await Subprocess.call({ command: command, arguments: allArgs });
            _dbgLog('Subprocess.call SUCCESS');
            return;
        } catch (subErr) {
            _dbgLog('Subprocess.call FAILED: ' + subErr + ' stack=' + (subErr && subErr.stack ? subErr.stack : 'no-stack'));
        }
    }

    // 兜底: 老式 nsIProcess
    try {
        _dbgLog('trying nsIProcess...');
        var proc = Components.classes["@mozilla.org/process/util;1"]
            .createInstance(Components.interfaces.nsIProcess);
        proc.init(Zotero.File.pathToFile(command));
        proc.run(false, allArgs, allArgs.length);
        _dbgLog('nsIProcess.run SUCCESS');
    } catch (e) {
        _dbgLog('nsIProcess FAILED: ' + e);
        Zotero.alert(null, 'pdf2zh-desktop Connector',
            '唤起 pdf2zh-desktop 失败：\n' + String(e) + '\n\n' +
            '临时办法：手动打开 pdf2zh-desktop 应用，把 PDF 拖进去。\n' +
            '日志已写到 /tmp/pdf2zh-xpi-debug.log');
    }
}

// 从选中的 items 里拿 PDF 附件路径
async function _getSelectedPdfPaths() {
    var win = Zotero.getMainWindow();
    if (!win || !win.ZoteroPane) return [];
    var items = win.ZoteroPane.getSelectedItems();
    var paths = [];
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        // 如果是 attachment 直接拿
        if (item.isAttachment && item.isAttachment()
            && item.attachmentContentType === 'application/pdf') {
            var p = await item.getFilePathAsync();
            if (p) paths.push(p);
            continue;
        }
        // 如果是 regular item，取它的 PDF 附件
        if (item.isRegularItem && item.isRegularItem()) {
            var attIds = item.getAttachments();
            for (var j = 0; j < attIds.length; j++) {
                var att = Zotero.Items.get(attIds[j]);
                if (att && att.attachmentContentType === 'application/pdf') {
                    var p = await att.getFilePathAsync();
                    if (p) paths.push(p);
                }
            }
        }
    }
    return paths;
}

// 右键菜单入口 — 触发翻译
async function _triggerTranslate(format, auto) {
    _dbgLog('=== _triggerTranslate called format=' + format + ' auto=' + auto + ' ===');
    try {
        var paths = await _getSelectedPdfPaths();
        _dbgLog('selected pdf paths count=' + paths.length + ' paths=' + JSON.stringify(paths));
        if (paths.length === 0) {
            Zotero.alert(null, 'pdf2zh-desktop Connector', '请先选中一个 PDF 附件或含 PDF 的文献条目\n(pdf2zh-desktop Connector)');
            return;
        }
        for (var i = 0; i < paths.length; i++) {
            await _launchPdf2zh(paths[i], format, auto);
        }
        _dbgLog('=== _triggerTranslate DONE ===');
    } catch (e) {
        _dbgLog('_triggerTranslate EXCEPTION: ' + e + ' stack=' + (e && e.stack ? e.stack : 'no-stack'));
        Zotero.alert(null, 'pdf2zh-desktop Connector',
            '右键翻译失败：\n' + String(e) + '\n\n日志已写到 /tmp/pdf2zh-xpi-debug.log');
    }
}

// 注入右键菜单（Zotero 7/8/9 通用做法：MutationObserver 监听 popup）
function _installContextMenu(window) {
    if (!window || !window.document) return;
    var doc = window.document;
    var menupopup = doc.getElementById('zotero-itemmenu');
    if (!menupopup) return;

    // 避免重复安装
    if (doc.getElementById('pdf2zh-translate-menu')) return;

    // 主菜单项
    var menu = doc.createXULElement ? doc.createXULElement('menu') : doc.createElement('menu');
    menu.id = 'pdf2zh-translate-menu';
    menu.setAttribute('label', '📖 用 pdf2zh-desktop 翻译');

    var subpopup = doc.createXULElement ? doc.createXULElement('menupopup') : doc.createElement('menupopup');

    var items = [
        { label: '一键翻译（默认 · 中外并排）', format: 'side_by_side', auto: true },
        { label: '─────────', separator: true },
        { label: '只出「中外并排」（side by side）', format: 'side_by_side', auto: false },
        { label: '只出「上下双语」（dual）', format: 'dual', auto: false },
        { label: '只出「纯中文」（mono）', format: 'mono', auto: false },
        { label: '出全部 3 种格式', format: 'all', auto: false },
        { label: '─────────', separator: true },
        { label: '⚙️ 打开 pdf2zh-desktop 手动配置', format: null, auto: false }
    ];

    items.forEach(function (item) {
        if (item.separator) {
            var sep = doc.createXULElement ? doc.createXULElement('menuseparator') : doc.createElement('menuseparator');
            subpopup.appendChild(sep);
            return;
        }
        var mi = doc.createXULElement ? doc.createXULElement('menuitem') : doc.createElement('menuitem');
        mi.setAttribute('label', item.label);
        mi.addEventListener('command', function () {
            _triggerTranslate(item.format, item.auto);
        });
        subpopup.appendChild(mi);
    });

    menu.appendChild(subpopup);
    menupopup.appendChild(menu);
}

function _removeContextMenu(window) {
    if (!window || !window.document) return;
    var m = window.document.getElementById('pdf2zh-translate-menu');
    if (m && m.parentNode) m.parentNode.removeChild(m);
}

// 监听 Zotero 主窗口 ready
var _windowListener = null;

function _registerWindowListener() {
    var wm = Components.classes["@mozilla.org/appshell/window-mediator;1"]
        .getService(Components.interfaces.nsIWindowMediator);

    // 已打开的窗口
    var enumerator = wm.getEnumerator('navigator:browser');
    while (enumerator.hasMoreElements()) {
        var win = enumerator.getNext();
        try { _installContextMenu(win); } catch (e) { Zotero.debug('install menu: ' + e); }
    }

    // 新窗口
    _windowListener = {
        onOpenWindow: function (aWindow) {
            var domWindow = aWindow.QueryInterface(Components.interfaces.nsIInterfaceRequestor)
                .getInterface(Components.interfaces.nsIDOMWindow);
            domWindow.addEventListener('load', function onLoad() {
                domWindow.removeEventListener('load', onLoad, false);
                try { _installContextMenu(domWindow); } catch (e) { Zotero.debug('install menu on new win: ' + e); }
            }, false);
        },
        onCloseWindow: function () {},
        onWindowTitleChange: function () {}
    };
    wm.addListener(_windowListener);
}

function _unregisterWindowListener() {
    if (!_windowListener) return;
    var wm = Components.classes["@mozilla.org/appshell/window-mediator;1"]
        .getService(Components.interfaces.nsIWindowMediator);
    wm.removeListener(_windowListener);
    _windowListener = null;

    // 移除所有窗口上的菜单
    var enumerator = wm.getEnumerator('navigator:browser');
    while (enumerator.hasMoreElements()) {
        var win = enumerator.getNext();
        try { _removeContextMenu(win); } catch (e) { /* ignore */ }
    }
}

// ============ 生命周期 ============

function startup() {
    // 1. 注册 HTTP 端点（回写机制 — 一行不动）
    Zotero.Server.Endpoints['/pdf2zh/attach'] = _makeAttachEndpoint();
    Zotero.Server.Endpoints['/pdf2zh/ping'] = _makePingEndpoint();

    // 2. NEW: 注册右键菜单（新功能，独立 try 避免影响回写）
    try {
        _registerWindowListener();
    } catch (e) {
        Zotero.debug('pdf2zh: 右键菜单注册失败（HTTP 端点仍工作）: ' + e);
    }
}

function shutdown() {
    delete Zotero.Server.Endpoints['/pdf2zh/attach'];
    delete Zotero.Server.Endpoints['/pdf2zh/ping'];
    try { _unregisterWindowListener(); } catch (e) { /* ignore */ }
}

function install() {}
function uninstall() {}
