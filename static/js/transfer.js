/* 文件传输中心：分片上传（暂停/续传/取消/重试）+ Range 下载（流式落盘/内存/原生三档）
 * 并发策略（内存上限 8GB 设计）：
 * - 上传任务最多 MAX_CONCURRENT 个并行，任务内分片严格串行；
 * - 单分片 5MB，服务端 2MB 以上落临时文件，浏览器侧单片常驻约数 MB；
 * - 下载优先 File System Access 边下边写（不占内存），否则小文件走内存 blob，
 *   超限大文件走原生下载（无页内进度）。
 */
(function () {
    'use strict';

    var root = document.getElementById('transfer-root');
    if (!root) return;
    var D = root.dataset;
    var URL_INIT = D.initUrl, URL_CHUNK = D.chunkUrl, URL_COMPLETE = D.completeUrl,
        URL_CANCEL = D.cancelUrl, URL_QUOTA = D.quotaUrl, URL_META = D.filemetaUrl,
        URL_DL_TPL = D.downloadUrlTpl, CHUNK_SIZE = parseInt(D.chunkSize, 10) || 5242880,
        BLOB_CAP = parseInt(D.blobCap, 10) || 536870912,
        MAX_CONCURRENT = parseInt(D.maxConcurrent, 10) || 2,
        SEG_SIZE = 8 * 1024 * 1024;
    var CSRF = (document.querySelector('#transfer-root input[name=csrfmiddlewaretoken]') || {}).value || '';

    function $(sel, el) { return (el || document).querySelector(sel); }
    function fmtBytes(n) {
        n = Number(n) || 0;
        if (n < 1024) return n + ' B';
        if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
        if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
        return (n / 1073741824).toFixed(2) + ' GB';
    }
    function fmtSpeed(bps) { return fmtBytes(bps) + '/s'; }
    function fmtETA(sec) {
        if (!isFinite(sec) || sec < 0) return '--';
        sec = Math.round(sec);
        if (sec < 60) return sec + 's';
        if (sec < 3600) return Math.floor(sec / 60) + 'm' + (sec % 60) + 's';
        return Math.floor(sec / 3600) + 'h' + Math.floor((sec % 3600) / 60) + 'm';
    }
    function postJSON(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
            body: JSON.stringify(data || {})
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (j) {
                if (!r.ok) throw new Error((j && j.error) || ('请求失败 ' + r.status));
                return j;
            });
        });
    }
    function postForm(url, fd) {
        return new Promise(function (resolve, reject) {
            var xhr = new XMLHttpRequest();
            var task = this;
            xhr.open('POST', url);
            xhr.setRequestHeader('X-CSRFToken', CSRF);
            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable && task && task.onChunkProgress) task.onChunkProgress(e.loaded);
            };
            xhr.onload = function () {
                var j = {};
                try { j = JSON.parse(xhr.responseText); } catch (e) { /* noop */ }
                if (xhr.status >= 200 && xhr.status < 300) resolve({ xhr: xhr, json: j });
                else reject(new Error((j && j.error) || ('上传失败 ' + xhr.status)));
            };
            xhr.onerror = function () { reject(new Error('网络错误')); };
            xhr.onabort = function () { reject(new Error('__aborted__')); };
            if (task) task._xhr = xhr;
            xhr.send(fd);
        });
    }

    /* ---------------- 上传 ---------------- */
    var upSeq = 0;
    var UploadManager = {
        tasks: [], activeCount: 0,
        add: function (file, folderId) {
            var t = new UploadTask(file, folderId);
            this.tasks.unshift(t);
            renderUploads();
            this.pump();
            return t;
        },
        pump: function () {
            var self = this;
            while (self.activeCount < MAX_CONCURRENT) {
                var next = null;
                for (var i = 0; i < self.tasks.length; i++) {
                    if (self.tasks[i].state === 'queued') { next = self.tasks[i]; break; }
                }
                if (!next) break;
                self.activeCount++;
                next.start().finally(function () { self.activeCount--; self.pump(); renderUploads(); });
            }
            renderOverall();
        }
    };

    function UploadTask(file, folderId) {
        this.id = 'u' + (++upSeq);
        this.file = file;
        this.folderId = folderId || '';
        this.state = 'queued'; // queued|uploading|paused|merging|done|error|cancelled
        this.sessionId = null;
        this.totalChunks = 0;
        this.received = {};
        this.nextIndex = 0;
        this.doneBytes = 0;
        this.speed = 0;
        this._lastT = 0; this._lastB = 0;
        this.error = '';
        this.retries = 0;
        this._xhr = null;
        this._stopFlag = false;
    }
    UploadTask.prototype.baseBytes = function () {
        var n = 0;
        for (var k in this.received) n++;
        return Math.min(n * CHUNK_SIZE, this.file.size);
    };
    UploadTask.prototype.tick = function (loaded) {
        var now = Date.now();
        var cur = this.baseBytes() + loaded;
        if (this._lastT) {
            var dt = (now - this._lastT) / 1000;
            if (dt > 0.2) {
                var inst = (cur - this._lastB) / dt;
                this.speed = this.speed ? this.speed * 0.7 + inst * 0.3 : inst;
                this._lastT = now; this._lastB = cur;
            }
        } else { this._lastT = now; this._lastB = cur; }
        this.doneBytes = cur;
        paintTask(this);
        renderOverall();
    };
    UploadTask.prototype.start = function () {
        var self = this;
        self.state = 'uploading';
        self._stopFlag = false;
        renderUploads();
        return postJSON(URL_INIT, {
            filename: self.file.name, total_size: self.file.size, folder_id: self.folderId || null
        }).then(function (j) {
            if (self._stopFlag) return; // 暂停/取消发生在 init 请求期间
            self.sessionId = j.session_id;
            self.totalChunks = j.total_chunks;
            self.received = {};
            (j.received || []).forEach(function (i) { self.received[i] = true; });
            self.nextIndex = 0;
            while (self.received[self.nextIndex]) self.nextIndex++;
            self.doneBytes = self.baseBytes();
            self._lastT = 0;
            return self.loop();
        }).then(function () {
            if (self._stopFlag) return;
            self.state = 'merging';
            renderUploads();
            return postJSON(URL_COMPLETE, { session_id: self.sessionId }).then(function () {
                refreshQuota();
                finishUpload(self, 'done', '');
            });
        }).catch(function (err) {
            if (err && err.message === '__aborted__') return; // pause/cancel 主动中断
            if (self._stopFlag) return;
            finishUpload(self, 'error', (err && err.message) || '未知错误');
        });
    };
    UploadTask.prototype.loop = function () {
        var self = this;
        function step() {
            if (self._stopFlag) return Promise.resolve();
            while (self.received[self.nextIndex]) self.nextIndex++;
            if (self.nextIndex >= self.totalChunks) return Promise.resolve();
            var idx = self.nextIndex;
            var start = idx * CHUNK_SIZE;
            var blob = self.file.slice(start, Math.min(start + CHUNK_SIZE, self.file.size));
            var fd = new FormData();
            fd.append('session_id', self.sessionId);
            fd.append('index', String(idx));
            fd.append('chunk', blob, 'chunk');
            self.retries = 0;
            return self.sendChunk(fd, idx).then(step);
        }
        return step();
    };
    UploadTask.prototype.sendChunk = function (fd, idx) {
        var self = this;
        function attempt(n) {
            if (self._stopFlag) return Promise.reject(new Error('__aborted__'));
            return postForm.call(self, URL_CHUNK, fd).then(function (res) {
                self.received = {};
                (res.json.received || []).forEach(function (i) { self.received[i] = true; });
                self.nextIndex = idx + 1;
                self.doneBytes = self.baseBytes();
                self._lastT = 0;
                paintTask(self); renderOverall();
            }).catch(function (err) {
                if ((err && err.message === '__aborted__') || self._stopFlag) {
                    return Promise.reject(err);
                }
                if (n < 3) {
                    return new Promise(function (r) { setTimeout(r, 1000 * n); }).then(function () { return attempt(n + 1); });
                }
                return Promise.reject(err);
            });
        }
        self.onChunkProgress = function (loaded) { self.tick(loaded); };
        return attempt(1);
    };
    UploadTask.prototype.pause = function () {
        if (this.state !== 'uploading') return;
        this._stopFlag = true;
        if (this._xhr) { try { this._xhr.abort(); } catch (e) { /* noop */ } }
        this.state = 'paused';
        renderUploads(); renderOverall();
    };
    UploadTask.prototype.resume = function () {
        if (this.state !== 'paused') return;
        this.state = 'queued';
        this.error = '';
        renderUploads();
        UploadManager.pump();
    };
    UploadTask.prototype.cancel = function () {
        this._stopFlag = true;
        if (this._xhr) { try { this._xhr.abort(); } catch (e) { /* noop */ } }
        var sid = this.sessionId;
        this.sessionId = null;
        finishUpload(this, 'cancelled', '');
        if (sid) postJSON(URL_CANCEL, { session_id: sid }).catch(function () { /* noop */ });
    };

    /* ---------------- 下载 ---------------- */
    var dlSeq = 0;
    var DownloadManager = {
        tasks: [],
        add: function (fileId, name, size) {
            var t = new DownloadTask(fileId, name, size);
            this.tasks.unshift(t);
            renderDownloads();
            t.prepare();
            return t;
        },
        addError: function (fileId, msg) {
            var t = new DownloadTask(fileId, '文件 #' + fileId, 0);
            t.state = 'error';
            t.error = msg;
            this.tasks.unshift(t);
            renderDownloads();
            return t;
        }
    };
    var FS_OK = !!(window.showSaveFilePicker && window.WritableStream);

    function DownloadTask(fileId, name, size) {
        this.id = 'd' + (++dlSeq);
        this.fileId = fileId;
        this.name = name;
        this.size = Number(size) || 0;
        this.url = URL_DL_TPL.replace('/0/', '/' + fileId + '/');
        this.state = 'preparing'; // preparing|awaiting|downloading|paused|done|error
        this.offset = 0;
        this.speed = 0;
        this._lastT = 0; this._lastB = 0;
        this._abort = null;
        this._stopFlag = false;
        this.mode = '';
        this.error = '';
    }
    DownloadTask.prototype.tick = function () {
        var now = Date.now();
        if (this._lastT) {
            var dt = (now - this._lastT) / 1000;
            if (dt > 0.2) {
                var inst = (this.offset - this._lastB) / dt;
                this.speed = this.speed ? this.speed * 0.7 + inst * 0.3 : inst;
                this._lastT = now; this._lastB = this.offset;
            }
        } else { this._lastT = now; this._lastB = this.offset; }
        paintDlTask(this);
    };
    DownloadTask.prototype.prepare = function () {
        // 自动触发无用户手势时，FS  picker 会被拦截 → 先查大小再定策略
        if (FS_OK && this.size > BLOB_CAP) {
            this.state = 'awaiting';
            this.mode = 'fs';
        } else if (this.size > BLOB_CAP) {
            this.native();
            return;
        } else {
            this.mode = 'blob';
            this.run();
            return;
        }
        renderDownloads();
    };
    // 用户手势内调用：选择落盘位置后开始流式下载
    DownloadTask.prototype.pickAndRun = function () {
        var self = this;
        return window.showSaveFilePicker({ suggestedName: self.name }).then(function (handle) {
            return handle.createWritable().then(function (w) {
                self._writer = w;
                self.mode = 'fs';
                self.run();
            });
        }).catch(function () { self.native(); });
    };
    DownloadTask.prototype.native = function () {
        this.mode = 'native';
        var a = document.createElement('a');
        a.href = this.url;
        a.download = this.name;
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { a.remove(); }, 1000);
        finishDownload(this, '已转浏览器下载', '');
    };
    DownloadTask.prototype.run = function () {
        var self = this;
        self.state = 'downloading';
        self._stopFlag = false;
        self._lastT = 0;
        renderDownloads();
        if (self.mode === 'fs') self.fsLoop();
        else self.blobRun();
    };
    DownloadTask.prototype.fsLoop = function () {
        var self = this;
        if (self._stopFlag || self.offset >= self.size && self.size) { self.fsFinish(); return; }
        var end = Math.min(self.offset + SEG_SIZE - 1, (self.size || self.offset + SEG_SIZE) - 1);
        var ctrl = new AbortController();
        self._abort = ctrl;
        fetch(self.url, { headers: { Range: 'bytes=' + self.offset + '-' + end }, signal: ctrl.signal }).then(function (res) {
            if (res.status !== 206 && res.status !== 200) throw new Error('下载失败 ' + res.status);
            if (!self.size) {
                var cr = res.headers.get('Content-Range') || '';
                var m = cr.match(/\/(\d+)$/);
                if (m) self.size = parseInt(m[1], 10);
            }
            var reader = res.body.getReader();
            function pump() {
                return reader.read().then(function (r) {
                    if (r.done) {
                        if (self.size && self.offset >= self.size) self.fsFinish();
                        else if (!self.size) self.fsFinish();
                        else self.fsLoop();
                        return;
                    }
                    return self._writer.write(r.value).then(function () {
                        self.offset += r.value.length;
                        self.tick();
                        if (self._stopFlag) { try { reader.cancel(); } catch (e) { /* noop */ } return; }
                        return pump();
                    });
                });
            }
            return pump();
        }).catch(function (err) {
            if (self._stopFlag) return;
            finishDownload(self, '失败', (err && err.message) || '下载失败');
        });
    };
    DownloadTask.prototype.fsFinish = function () {
        var w = this._writer;
        this._writer = null;
        if (w) w.close().catch(function () { /* noop */ });
        finishDownload(this, '已完成', '');
    };
    DownloadTask.prototype.blobRun = function () {
        var self = this;
        var ctrl = new AbortController();
        self._abort = ctrl;
        fetch(self.url, { signal: ctrl.signal }).then(function (res) {
            if (!res.ok) throw new Error('下载失败 ' + res.status);
            if (!self.size) {
                var len = res.headers.get('Content-Length');
                if (len) self.size = parseInt(len, 10);
            }
            var reader = res.body.getReader();
            var parts = [];
            function pump() {
                return reader.read().then(function (r) {
                    if (r.done) {
                        var blob = new Blob(parts, { type: 'application/octet-stream' });
                        parts = [];
                        var objUrl = URL.createObjectURL(blob);
                        var a = document.createElement('a');
                        a.href = objUrl;
                        a.download = self.name;
                        document.body.appendChild(a);
                        a.click();
                        setTimeout(function () { a.remove(); URL.revokeObjectURL(objUrl); }, 5000);
                        finishDownload(self, '已完成', '');
                        return;
                    }
                    parts.push(r.value);
                    self.offset += r.value.length;
                    self.tick();
                    if (self._stopFlag) { try { reader.cancel(); } catch (e) { /* noop */ } return; }
                    return pump();
                });
            }
            return pump();
        }).catch(function (err) {
            if (self._stopFlag) return;
            finishDownload(self, '失败', (err && err.message) || '下载失败');
        });
    };
    DownloadTask.prototype.pause = function () {
        if (this.state !== 'downloading') return;
        this._stopFlag = true;
        if (this._abort) { try { this._abort.abort(); } catch (e) { /* noop */ } }
        this.state = 'paused';
        renderDownloads();
    };
    DownloadTask.prototype.resume = function () {
        if (this.state !== 'paused') return;
        if (this.mode === 'fs' && !this._writer) { this.state = 'awaiting'; renderDownloads(); return; }
        this.error = '';
        this.run();
    };
    DownloadTask.prototype.cancel = function () {
        this._stopFlag = true;
        if (this._abort) { try { this._abort.abort(); } catch (e) { /* noop */ } }
        var w = this._writer;
        this._writer = null;
        if (w) w.abort().catch(function () { /* noop */ });
        finishDownload(this, '已取消', '');
    };

    /* ---------------- 终态归档 + 历史记录（localStorage，不入库） ---------------- */
    var HIST_KEY = 'transfer_history_v1';
    var HIST_MAX = 100;
    function loadHistory() {
        try { var h = JSON.parse(localStorage.getItem(HIST_KEY)); return Array.isArray(h) ? h : []; }
        catch (e) { return []; }
    }
    function saveHistory(h) {
        try { localStorage.setItem(HIST_KEY, JSON.stringify((h || []).slice(0, HIST_MAX))); } catch (e) { /* noop */ }
    }
    function pushHistory(rec) {
        var h = loadHistory();
        h.unshift({ kind: rec.kind, name: rec.name, size: rec.size || 0, status: rec.status, detail: rec.detail || '', time: Date.now() });
        saveHistory(h);
        renderHistory();
    }
    function fmtTime(ts) {
        var d = new Date(ts);
        function p(n) { return (n < 10 ? '0' : '') + n; }
        return (d.getMonth() + 1) + '-' + d.getDate() + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
    }
    // 任务终态移出活动列表并记入历史（防重复归档）
    function finishUpload(t, status, detail) {
        if (t._finished) return;
        t._finished = true;
        t.state = status;
        if (status === 'error') t.error = detail || '未知错误';
        if (status === 'done') t.doneBytes = t.file.size;
        pushHistory({
            kind: 'upload', name: t.file.name, size: t.file.size,
            status: status === 'done' ? '已完成' : (status === 'error' ? '失败' : '已取消'),
            detail: status === 'error' ? (detail || '') : ''
        });
        var i = UploadManager.tasks.indexOf(t);
        if (i >= 0) UploadManager.tasks.splice(i, 1);
        renderUploads(); renderOverall();
    }
    function finishDownload(t, statusText, detail) {
        if (t._finished) return;
        t._finished = true;
        t.state = statusText === '已取消' ? 'cancelled' : (statusText === '失败' ? 'error' : 'done');
        if (statusText === '失败') t.error = detail || '';
        pushHistory({ kind: 'download', name: t.name, size: t.size, status: statusText, detail: detail });
        var i = DownloadManager.tasks.indexOf(t);
        if (i >= 0) DownloadManager.tasks.splice(i, 1);
        renderDownloads();
    }
    function renderHistory() {
        var box = document.getElementById('history-list');
        if (!box) return;
        var h = loadHistory();
        if (!h.length) {
            box.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:16px;">暂无历史记录，完成 / 失败 / 取消的上传下载会记在这里（仅保存在本浏览器）</div>';
            return;
        }
        box.innerHTML = h.map(function (r) {
            var icon = r.kind === 'upload' ? 'fa-upload' : 'fa-download';
            var color = (r.status === '已完成' || r.status === '已转浏览器下载') ? 'var(--success)' : (r.status === '失败' ? 'var(--danger)' : 'var(--text-muted)');
            var sub = fmtBytes(r.size) + ' · ' + fmtTime(r.time) + (r.detail ? ' · ' + escapeHtml(r.detail) : '');
            return '<div class="transfer-task"><div style="display:flex;gap:10px;align-items:center;">' +
                '<i class="fas ' + icon + '" style="color:' + color + ';width:16px;text-align:center;"></i>' +
                '<div style="flex:1;min-width:0;"><div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(r.name) + '</div>' +
                '<div style="font-size:0.75rem;color:var(--text-muted);">' + sub + '</div></div>' +
                '<span class="badge" style="background:var(--bg-secondary);color:' + color + ';flex-shrink:0;">' + r.status + '</span>' +
                '</div></div>';
        }).join('');
    }

    /* ---------------- 渲染 ---------------- */
    function taskStateText(t) {
        return { queued: '排队中', uploading: '上传中', paused: '已暂停', merging: '合并处理中', done: '已完成', error: '失败', cancelled: '已取消' }[t.state] || t.state;
    }
    function taskRow(t) {
        var pct = t.file.size ? Math.min(100, (t.doneBytes / t.file.size) * 100) : 0;
        var btns = '';
        if (t.state === 'uploading') btns = '<button class="btn btn-outline btn-sm" data-act="pause">暂停</button>';
        else if (t.state === 'paused') btns = '<button class="btn btn-primary btn-sm" data-act="resume">继续</button>';
        if (t.state === 'uploading' || t.state === 'queued' || t.state === 'paused') btns += '<button class="btn btn-danger btn-sm" data-act="cancel">取消</button>';
        var sub = t.state === 'done' ? '上传完成' :
            t.state === 'error' ? ('<span style="color:var(--danger);">' + t.error + '</span>') :
            fmtBytes(t.doneBytes) + ' / ' + fmtBytes(t.file.size) + ' · ' + fmtSpeed(t.speed) + ' · 剩余 ' + fmtETA((t.file.size - t.doneBytes) / (t.speed || 1));
        return '<div class="transfer-task" id="up-' + t.id + '" data-id="' + t.id + '">' +
            '<div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">' +
            '<div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(t.file.name) + '</div>' +
            '<div style="display:flex;gap:6px;flex-shrink:0;">' + btns + '</div></div>' +
            '<div class="transfer-bar"><div class="transfer-fill" style="width:' + pct.toFixed(1) + '%;"></div></div>' +
            '<div style="font-size:0.75rem;color:var(--text-muted);display:flex;justify-content:space-between;"><span>' + sub + '</span><span>' + taskStateText(t) + ' ' + pct.toFixed(1) + '%</span></div></div>';
    }
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }
    function renderUploads() {
        var box = document.getElementById('upload-list');
        if (!box) return;
        box.innerHTML = UploadManager.tasks.length ?
            UploadManager.tasks.map(taskRow).join('') :
            '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:16px;">暂无上传任务，把文件拖到上方区域即可开始</div>';
        bindTaskButtons(box, true);
    }
    function paintTask(t) {
        var box = document.getElementById('up-' + t.id);
        if (!box) return;
        var tmp = document.createElement('div');
        tmp.innerHTML = taskRow(t);
        box.replaceWith(tmp.firstChild);
        bindTaskButtons(document.getElementById('upload-list'), true);
    }
    function renderOverall() {
        var bar = document.getElementById('overall-fill');
        var txt = document.getElementById('overall-text');
        if (!bar || !txt) return;
        var total = 0, done = 0, active = 0;
        UploadManager.tasks.forEach(function (t) {
            if (t.state === 'cancelled') return;
            total += t.file.size; done += Math.min(t.doneBytes, t.file.size);
            if (t.state === 'uploading' || t.state === 'queued' || t.state === 'merging') active++;
        });
        var pct = total ? (done / total) * 100 : 0;
        bar.style.width = pct.toFixed(1) + '%';
        txt.textContent = active ? ('总进度 ' + pct.toFixed(1) + '% · ' + fmtBytes(done) + ' / ' + fmtBytes(total)) : (total ? '总进度 ' + pct.toFixed(1) + '%' : '暂无任务');
    }
    function dlStateText(t) {
        return { preparing: '准备中', awaiting: '待确认保存位置', downloading: '下载中', paused: '已暂停', done: t.mode === 'native' ? '已转浏览器下载' : '已完成', error: '失败' }[t.state] || t.state;
    }
    function renderDownloads() {
        var box = document.getElementById('download-list');
        if (!box) return;
        if (!DownloadManager.tasks.length) {
            box.innerHTML = '<div style="color:var(--text-muted);font-size:0.85rem;text-align:center;padding:16px;">暂无下载任务，在下方文件表点“下载”即可加入</div>';
            return;
        }
        box.innerHTML = DownloadManager.tasks.map(function (t) {
            var pct = t.size ? Math.min(100, (t.offset / t.size) * 100) : 0;
            var btns = '';
            if (t.state === 'awaiting') btns = '<button class="btn btn-primary btn-sm" data-act="pick">选择保存位置并下载</button>';
            else if (t.state === 'downloading') btns = '<button class="btn btn-outline btn-sm" data-act="pause">暂停</button>';
            else if (t.state === 'paused') btns = '<button class="btn btn-primary btn-sm" data-act="resume">继续</button>';
            if (t.state !== 'done') btns += '<button class="btn btn-danger btn-sm" data-act="cancel">取消</button>';
            var sub = t.state === 'done' ? (t.mode === 'native' ? '已交由浏览器下载' : '下载完成') :
                t.state === 'error' ? ('<span style="color:var(--danger);">' + escapeHtml(t.error) + '</span>') :
                t.state === 'awaiting' ? '大文件将边下边写盘，不占内存' :
                fmtBytes(t.offset) + (t.size ? ' / ' + fmtBytes(t.size) : '') + ' · ' + fmtSpeed(t.speed) + (t.size ? ' · 剩余 ' + fmtETA((t.size - t.offset) / (t.speed || 1)) : '');
            return '<div class="transfer-task" id="dl-' + t.id + '" data-id="' + t.id + '">' +
                '<div style="display:flex;justify-content:space-between;gap:8px;align-items:center;">' +
                '<div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + escapeHtml(t.name) + '</div>' +
                '<div style="display:flex;gap:6px;flex-shrink:0;">' + btns + '</div></div>' +
                '<div class="transfer-bar"><div class="transfer-fill dl" style="width:' + pct.toFixed(1) + '%;"></div></div>' +
                '<div style="font-size:0.75rem;color:var(--text-muted);display:flex;justify-content:space-between;"><span>' + sub + '</span><span>' + dlStateText(t) + ' ' + pct.toFixed(1) + '%</span></div></div>';
        }).join('');
        bindTaskButtons(box, false);
    }
    function paintDlTask(t) {
        var box = document.getElementById('dl-' + t.id);
        if (!box) { renderDownloads(); return; }
        var pct = t.size ? Math.min(100, (t.offset / t.size) * 100) : 0;
        var fill = box.querySelector('.transfer-fill');
        if (fill) fill.style.width = pct.toFixed(1) + '%';
        var spans = box.querySelectorAll('div[style*="justify-content:space-between"] span');
        if (spans.length >= 2) {
            spans[0].textContent = fmtBytes(t.offset) + (t.size ? ' / ' + fmtBytes(t.size) : '') + ' · ' + fmtSpeed(t.speed);
            spans[1].textContent = dlStateText(t) + ' ' + pct.toFixed(1) + '%';
        }
    }
    function bindTaskButtons(box, isUpload) {
        box.querySelectorAll('.transfer-task [data-act]').forEach(function (btn) {
            btn.onclick = function () {
                var id = btn.closest('.transfer-task').dataset.id;
                var list = isUpload ? UploadManager.tasks : DownloadManager.tasks;
                var t = list.find(function (x) { return x.id === id; });
                if (!t) return;
                var act = btn.dataset.act;
                if (act === 'pause') t.pause();
                else if (act === 'resume') t.resume();
                else if (act === 'cancel') t.cancel();
                else if (act === 'pick') t.pickAndRun();
            };
        });
    }
    function refreshQuota() {
        fetch(URL_QUOTA).then(function (r) { return r.json(); }).then(function (j) {
            var el = document.getElementById('quota-text');
            if (el) el.textContent = '已用 ' + j.usage_display + ' / ' + j.quota_display;
        }).catch(function () { /* noop */ });
    }

    /* ---------------- 页面装配 ---------------- */
    function folderId() {
        var s = document.getElementById('dest-folder');
        return s ? s.value : '';
    }
    var dz = document.getElementById('transfer-drop');
    var fi = document.getElementById('transfer-files');
    if (dz && fi) {
        ['dragenter', 'dragover'].forEach(function (ev) {
            dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('drag-over'); });
        });
        ['dragleave', 'drop'].forEach(function (ev) {
            dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('drag-over'); });
        });
        dz.addEventListener('drop', function (e) {
            var files = e.dataTransfer.files;
            for (var i = 0; i < files.length; i++) UploadManager.add(files[i], folderId());
        });
        dz.addEventListener('click', function () { fi.click(); });
        fi.addEventListener('change', function () {
            for (var i = 0; i < fi.files.length; i++) UploadManager.add(fi.files[i], folderId());
            fi.value = '';
        });
    }
    var clearHistBtn = document.getElementById('clear-history');
    if (clearHistBtn) clearHistBtn.addEventListener('click', function () {
        if (!confirm('确定删除全部传输历史记录吗？（仅清本浏览器缓存）')) return;
        saveHistory([]);
        renderHistory();
    });
    window.switchTab = switchTab;
    function switchTab(name) {
        document.querySelectorAll('.transfer-tab').forEach(function (t) {
            t.classList.toggle('active', t.dataset.tab === name);
        });
        document.querySelectorAll('.transfer-pane').forEach(function (p) {
            p.style.display = p.dataset.pane === name ? 'block' : 'none';
        });
        // 一键删除按钮只在历史记录 Tab 显示
        var ch = document.getElementById('clear-history');
        if (ch) ch.style.display = (name === 'history') ? '' : 'none';
    }
    document.querySelectorAll('.transfer-tab').forEach(function (t) {
        t.addEventListener('click', function () { switchTab(t.dataset.tab); });
    });

    // 从文件列表 ?download=ID 跳转：先取元信息再加入，失效 ID 显式报错；
    // 立刻清掉地址栏参数，刷新不再重复加入
    if (D.autoDownload) {
        try {
            var _u = new URL(location.href);
            _u.searchParams.delete('download');
            history.replaceState(null, '', _u.pathname + _u.search + _u.hash);
        } catch (e) { /* noop */ }
        switchTab('download');
        fetch(URL_META + '?id=' + encodeURIComponent(D.autoDownload)).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (j) {
                if (!r.ok) throw new Error((j && j.error) || ('请求失败 ' + r.status));
                return j;
            });
        }).then(function (j) {
            DownloadManager.add(j.id, j.name, j.size);
        }).catch(function (err) {
            DownloadManager.addError(D.autoDownload, (err && err.message) || '加入下载失败');
        });
    }
    renderUploads(); renderDownloads(); renderHistory(); renderOverall();
})();
