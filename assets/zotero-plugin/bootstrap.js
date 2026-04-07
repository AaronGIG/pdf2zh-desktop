/*
 * pdf2zh Connector for Zotero
 *
 * Registers HTTP endpoints on Zotero's local server (port 23119):
 *   POST /pdf2zh/attach — add translated PDF as Zotero attachment
 *   GET  /pdf2zh/ping   — health check
 */

/* exported startup, shutdown, install, uninstall */

function startup() {
    var AttachEndpoint = function () {};
    AttachEndpoint.prototype = {
        supportedMethods: ['POST'],
        supportedDataTypes: ['application/json'],
        permitBookmarklet: false,

        init: async function (options) {
            try {
                var data = typeof options.data === 'string' ? JSON.parse(options.data) : options.data;
                var itemKey = data.itemKey;
                var filePath = data.filePath;
                var title = data.title;

                if (!itemKey || !filePath) {
                    return [400, 'application/json', JSON.stringify({
                        error: 'Missing required fields: itemKey, filePath'
                    })];
                }

                var item = Zotero.Items.getByLibraryAndKey(
                    Zotero.Libraries.userLibraryID, itemKey
                );
                if (!item) {
                    return [404, 'application/json', JSON.stringify({
                        error: 'Item not found: ' + itemKey
                    })];
                }

                var parentID = item.parentItemID || item.id;

                var attachment = await Zotero.Attachments.importFromFile({
                    file: filePath,
                    parentItemID: parentID,
                    title: title || 'Translated PDF',
                    contentType: 'application/pdf'
                });

                // 在 Zotero 自动生成的标题前面加上格式标签
                if (title) {
                    var autoTitle = attachment.getField('title');
                    attachment.setField('title', title + ' - ' + autoTitle);
                    await attachment.saveTx();
                }

                return [200, 'application/json', JSON.stringify({
                    key: attachment.key,
                    id: attachment.id
                })];
            } catch (e) {
                return [500, 'application/json', JSON.stringify({
                    error: String(e)
                })];
            }
        }
    };

    var PingEndpoint = function () {};
    PingEndpoint.prototype = {
        supportedMethods: ['GET'],
        supportedDataTypes: ['application/json'],
        permitBookmarklet: false,

        init: async function (req) {
            return [200, 'application/json', JSON.stringify({
                status: 'ok',
                plugin: 'pdf2zh-connector',
                version: '1.0.4'
            })];
        }
    };

    Zotero.Server.Endpoints['/pdf2zh/attach'] = AttachEndpoint;
    Zotero.Server.Endpoints['/pdf2zh/ping'] = PingEndpoint;
}

function shutdown() {
    delete Zotero.Server.Endpoints['/pdf2zh/attach'];
    delete Zotero.Server.Endpoints['/pdf2zh/ping'];
}

function install() {}
function uninstall() {}
