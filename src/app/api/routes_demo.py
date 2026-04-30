from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

DEMO_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Chat Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body {
            max-width: 1000px; margin: 20px auto; padding: 0 20px; background-color: #f5f5f5;
        }
        .container {
            background: white; padding: 30px; border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .form-group { margin-bottom: 18px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; color: #333; }
        select, input[type="text"] {
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px;
        }
        .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .hint { color: #666; font-size: 13px; margin-top: 6px; }
        .btn-group { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        button {
            padding: 10px 20px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer;
        }
        #startBtn { background-color: #28a745; color: white; }
        #startBtn:disabled { background-color: #6c757d; cursor: not-allowed; }
        #stopBtn { background-color: #dc3545; color: white; display: none; }
        #copyTraceIdBtn, #copyCurlBtn, #clearBtn { background-color: #007bff; color: white; }

        .result-section {
            margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; display: none;
        }
        .section-title { font-weight: bold; margin-bottom: 8px; color: #444; }
        #metaArea { background-color: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        #outputArea {
            min-height: 100px; padding: 10px; border: 1px solid #eee; margin-bottom: 10px; white-space: pre-wrap;
        }
        #usageArea { background-color: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        #errorArea {
            color: #dc3545; padding: 10px; background-color: #f8d7da; border-radius: 4px; display: none;
        }

        /* Compare 专用样式 */
        .compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .compare-card {
            border: 1px solid #eee; border-radius: 6px; padding: 10px; background: #fff;
        }
        .compare-card h3 { font-size: 14px; margin-bottom: 6px; color: #333; }
        .compare-meta { font-size: 13px; color: #555; margin-bottom: 6px; }
        .compare-answer { white-space: pre-wrap; border: 1px solid #f0f0f0; padding: 8px; border-radius: 4px; min-height: 80px; }
        .toast {
            position: fixed; top: 20px; right: 20px; padding: 10px 20px;
            background-color: #ffc107; color: #212529; border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 9999; display: none;
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM Chat Demo（Stream / Compare）</h1>

        <div class="form-group">
            <label for="modeSelect">模式 (Mode)</label>
            <select id="modeSelect">
                <option value="stream">Stream Chat（SSE）</option>
                <option value="compare">Prompt Compare（A/B）</option>
            </select>
            <div class="hint">Stream：调用 /chat/stream；Compare：调用 /prompt/compare（同步对比）。</div>
        </div>

        <div class="form-group">
            <label for="providerSelect">模型引擎 (Provider)</label>
            <select id="providerSelect">
                <option value="mock">mock (测试用)</option>
                <option value="ollama">ollama (本地模型)</option>
            </select>
        </div>

        <div class="form-group">
            <label for="promptInput">输入问题 (User Prompt)</label>
            <input type="text" id="promptInput" placeholder="请输入你想提问的内容，比如：hi" value="hi">
        </div>

        <!-- Stream 模式：单套 prompt -->
        <div id="streamPromptBox">
            <div class="form-group row-2">
                <div>
                    <label for="promptIdSelect">Prompt ID（Stream）</label>
                    <select id="promptIdSelect">
                        <option value="chat">chat</option>
                        <option value="qa_strict">qa_strict</option>
                    </select>
                </div>
                <div>
                    <label for="promptVersionSelect">Prompt Version（Stream）</label>
                    <select id="promptVersionSelect">
                        <option value="v1">v1</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Compare 模式：A/B 两套 prompt -->
        <div id="comparePromptBox" class="hidden">
            <div class="form-group row-2">
                <div>
                    <label for="promptAIdSelect">Prompt A ID</label>
                    <select id="promptAIdSelect">
                        <option value="chat">chat</option>
                        <option value="qa_strict">qa_strict</option>
                    </select>
                </div>
                <div>
                    <label for="promptAVersionSelect">Prompt A Version</label>
                    <select id="promptAVersionSelect">
                        <option value="v1">v1</option>
                    </select>
                </div>
            </div>

            <div class="form-group row-2">
                <div>
                    <label for="promptBIdSelect">Prompt B ID</label>
                    <select id="promptBIdSelect">
                        <option value="qa_strict" selected>qa_strict</option>
                        <option value="chat">chat</option>
                    </select>
                </div>
                <div>
                    <label for="promptBVersionSelect">Prompt B Version</label>
                    <select id="promptBVersionSelect">
                        <option value="v1">v1</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="btn-group">
            <button id="startBtn">开始聊天 (Start)</button>
            <button id="stopBtn">停止聊天 (Stop)</button>
            <button id="copyTraceIdBtn">复制 Trace ID</button>
            <button id="copyCurlBtn">复制 Curl 命令</button>
            <button id="clearBtn">清空输出</button>
        </div>

        <div class="result-section" id="resultSection">
            <div class="section-title">元信息 (Meta)</div>
            <div id="metaArea"></div>

            <div class="section-title">输出内容 (Output)</div>
            <div id="outputArea"></div>

            <div class="section-title">使用统计 (Usage / Metrics)</div>
            <div id="usageArea"></div>

            <div class="section-title">错误信息 (Error)</div>
            <div id="errorArea"></div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        // DOM
        const modeSelect = document.getElementById('modeSelect');
        const providerSelect = document.getElementById('providerSelect');
        const promptInput = document.getElementById('promptInput');

        const streamPromptBox = document.getElementById('streamPromptBox');
        const promptIdSelect = document.getElementById('promptIdSelect');
        const promptVersionSelect = document.getElementById('promptVersionSelect');

        const comparePromptBox = document.getElementById('comparePromptBox');
        const promptAIdSelect = document.getElementById('promptAIdSelect');
        const promptAVersionSelect = document.getElementById('promptAVersionSelect');
        const promptBIdSelect = document.getElementById('promptBIdSelect');
        const promptBVersionSelect = document.getElementById('promptBVersionSelect');

        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const copyTraceIdBtn = document.getElementById('copyTraceIdBtn');
        const copyCurlBtn = document.getElementById('copyCurlBtn');
        const clearBtn = document.getElementById('clearBtn');

        const resultSection = document.getElementById('resultSection');
        const metaArea = document.getElementById('metaArea');
        const outputArea = document.getElementById('outputArea');
        const usageArea = document.getElementById('usageArea');
        const errorArea = document.getElementById('errorArea');
        const toast = document.getElementById('toast');

        // State
        let controller = null;
        let running = false;

        // 这两个用于“复制”
        let latestTraceOrGroupId = '';
        let lastAction = 'stream'; // 'stream' | 'compare'
        let lastStreamPayload = null;
        let lastComparePayload = null;

        function showToast(message, duration = 2000) {
            toast.textContent = message;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, duration);
        }

        function resetUI() {
            errorArea.style.display = 'none';
            errorArea.innerHTML = '';
            metaArea.innerHTML = '';
            outputArea.innerHTML = '';
            usageArea.innerHTML = '';
            resultSection.style.display = 'block';
        }

        function setRunning(isRunning) {
            running = isRunning;
            startBtn.disabled = isRunning;
            // stopBtn 是否显示由 mode 决定
        }

        function setModeUI() {
            const mode = modeSelect.value;
            if (mode === 'stream') {
                streamPromptBox.classList.remove('hidden');
                comparePromptBox.classList.add('hidden');
                startBtn.textContent = '开始聊天 (Start)';
                copyTraceIdBtn.textContent = '复制 Trace ID';
                stopBtn.style.display = running ? 'inline-block' : 'none';
                startBtn.style.display = running ? 'none' : 'inline-block';
            } else {
                streamPromptBox.classList.add('hidden');
                comparePromptBox.classList.remove('hidden');
                startBtn.textContent = '开始对比 (Compare)';
                copyTraceIdBtn.textContent = '复制 Group ID';
                // compare 是同步请求，不需要 stop
                stopBtn.style.display = 'none';
                startBtn.style.display = 'inline-block';
            }
        }

        // ===== SSE utils =====
        function parseSSEBlocks(chunkStr) {
            const blocks = chunkStr.split('\\n\\n');
            const events = [];
            for (const block of blocks) {
                if (!block.trim()) continue;
                const lines = block.split('\\n');
                let eventType = null;
                let dataLines = [];
                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('event: ')) {
                        eventType = trimmedLine.replace('event: ', '');
                    } else if (trimmedLine.startsWith('data: ')) {
                        dataLines.push(trimmedLine.replace('data: ', ''));
                    }
                }
                if (eventType && dataLines.length > 0) {
                    const dataStr = dataLines.join('\\n');
                    events.push({ type: eventType, data: dataStr });
                }
            }
            return events;
        }

        function renderStreamMeta(meta) {
            latestTraceOrGroupId = meta.trace_id || '未知';
            metaArea.innerHTML = `
                <div>Trace ID: ${latestTraceOrGroupId}</div>
                <div>Provider: ${meta.provider || '未知'}</div>
                <div>Model: ${meta.model || '未知'}</div>
                <div>Prompt: ${(meta.prompt_id || 'none')}@${(meta.prompt_version || 'none')}</div>
            `;
        }

        function appendToken(text) {
            if (!running) return;
            outputArea.innerHTML += text;
            outputArea.scrollTop = outputArea.scrollHeight;
        }

        function renderStreamUsage(usage) {
            usageArea.innerHTML = `
                <div>耗时: ${usage.latency_ms || 0}ms</div>
                <div>Token事件数: ${usage.token_events || 0}</div>
            `;
        }

        function renderError(err) {
            errorArea.style.display = 'block';
            if (typeof err === 'object') {
                errorArea.innerHTML = `
                    <div>Trace/Group: ${err.trace_id || err.compare_group_id || '未知'}</div>
                    <div>Provider: ${err.provider || '未知'}</div>
                    <div>错误信息: ${err.error || '未知'}</div>
                `;
            } else {
                errorArea.innerHTML = err;
            }
        }

        function handleSSEEvent(event) {
            if (!running) return;
            const { type, data } = event;
            try {
                switch (type) {
                    case 'meta': renderStreamMeta(JSON.parse(data)); break;
                    case 'token': appendToken(data); break;
                    case 'usage': renderStreamUsage(JSON.parse(data)); break;
                    case 'error': renderError(JSON.parse(data)); break;
                    case 'done':
                        appendToken('\\n\\n【流式响应结束】');
                        break;
                    default: break;
                }
            } catch (e) {
                console.error(`解析${type}事件失败:`, e, '原始数据:', data);
            }
        }

        // ===== Payload builders =====
        function buildStreamPayload() {
            return {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_id: promptIdSelect.value,
                prompt_version: promptVersionSelect.value,
                prompt_vars: {}
            };
        }

        function buildComparePayload() {
            return {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_a: {
                    prompt_id: promptAIdSelect.value,
                    prompt_version: promptAVersionSelect.value,
                    prompt_vars: {}
                },
                prompt_b: {
                    prompt_id: promptBIdSelect.value,
                    prompt_version: promptBVersionSelect.value,
                    prompt_vars: {}
                }
            };
        }

        // ===== Actions =====
        async function startStream() {
            if (running) { showToast('正在运行中，请先停止后再操作'); return; }
            lastAction = 'stream';
            resetUI();
            setRunning(true);
            setModeUI();

            controller = new AbortController();
            const signal = controller.signal;

            const payload = buildStreamPayload();
            lastStreamPayload = payload;

            try {
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误：${response.status} ${response.statusText}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (running) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const events = parseSSEBlocks(buffer);
                    events.forEach(handleSSEEvent);
                    buffer = buffer.split('\\n\\n').pop() || '';
                }

            } catch (error) {
                if (error.name !== 'AbortError') {
                    renderError(`请求失败：${error.message}`);
                } else {
                    appendToken('\\n[已停止]');
                }
            } finally {
                running = false;
                setRunning(false);
                controller = null;
                setModeUI();
            }
        }

        async function startCompare() {
            if (running) { showToast('正在运行中，请稍后再试'); return; }
            lastAction = 'compare';
            resetUI();
            setRunning(true);
            setModeUI();

            const payload = buildComparePayload();
            lastComparePayload = payload;

            try {
                const resp = await fetch('/prompt/compare', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!resp.ok) {
                    const text = await resp.text();
                    throw new Error(`HTTP错误：${resp.status} ${resp.statusText} ${text}`);
                }

                const data = await resp.json();

                // meta：显示 group + A/B trace
                latestTraceOrGroupId = data.compare_group_id || '未知';
                const a = data.a || {};
                const b = data.b || {};
                const ma = (a.metadata || {});
                const mb = (b.metadata || {});

                metaArea.innerHTML = `
                    <div><b>Compare Group ID</b>: ${latestTraceOrGroupId}</div>
                    <div>A Trace: ${a.trace_id || '未知'} | Prompt: ${(ma.prompt_id || 'none')}@${(ma.prompt_version || 'none')}</div>
                    <div>B Trace: ${b.trace_id || '未知'} | Prompt: ${(mb.prompt_id || 'none')}@${(mb.prompt_version || 'none')}</div>
                    <div>Provider: ${(ma.provider || mb.provider || '未知')} | Model: ${(ma.model || mb.model || '未知')}</div>
                `;

                // output：左右并列
                outputArea.innerHTML = `
                    <div class="compare-grid">
                        <div class="compare-card">
                            <h3>A 输出</h3>
                            <div class="compare-meta">trace_id: ${a.trace_id || '未知'}</div>
                            <div class="compare-answer">${(a.answer || '').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
                        </div>
                        <div class="compare-card">
                            <h3>B 输出</h3>
                            <div class="compare-meta">trace_id: ${b.trace_id || '未知'}</div>
                            <div class="compare-answer">${(b.answer || '').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
                        </div>
                    </div>
                `;

                // metrics
                const m = data.metrics || {};
                usageArea.innerHTML = `
                    <div><b>latency_ms</b>: A=${m.latency_ms_a || 0} | B=${m.latency_ms_b || 0} | diff=${m.diff_latency_ms || 0}</div>
                    <div><b>output_chars</b>: A=${m.output_chars_a || 0} | B=${m.output_chars_b || 0} | diff=${m.output_chars_diff || 0}</div>
                `;

            } catch (err) {
                renderError(`Compare 失败：${err.message || err}`);
            } finally {
                setRunning(false);
                setModeUI();
            }
        }

        function handleStopClick() {
            if (controller) {
                controller.abort();
                controller = null;
                running = false;
                setRunning(false);
                setModeUI();
            }
        }

        function handleClearClick() {
            let stopTip = '';
            if (controller) {
                controller.abort();
                controller = null;
                stopTip = '（已终止正在运行的请求）';
            }
            errorArea.style.display = 'none';
            errorArea.innerHTML = '';
            metaArea.innerHTML = '';
            outputArea.innerHTML = '';
            usageArea.innerHTML = '';
            resultSection.style.display = 'none';
            latestTraceOrGroupId = '';
            showToast(`已清空所有输出内容 ${stopTip}`, 2000);
        }

        function handleCopyTraceOrGroupId() {
            if (!latestTraceOrGroupId || latestTraceOrGroupId === '未知') {
                showToast('暂无可用的 Trace/Group ID');
                return;
            }
            navigator.clipboard.writeText(latestTraceOrGroupId).then(() => {
                showToast(modeSelect.value === 'compare' ? 'Group ID已复制' : 'Trace ID已复制');
            }).catch(err => {
                console.error('复制失败:', err);
                showToast('复制失败，请手动复制');
            });
        }

        function handleCopyCurl() {
            let curl = '';
            if (modeSelect.value === 'compare') {
                const payload = lastComparePayload || buildComparePayload();
                const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
                curl = `curl -X POST http://localhost:8000/prompt/compare \\\\n  -H "Content-Type: application/json" \\\\n  -d '${payloadStr}'`;
            } else {
                const payload = lastStreamPayload || buildStreamPayload();
                const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
                curl = `curl -N -X POST http://localhost:8000/chat/stream \\\\n  -H "Content-Type: application/json" \\\\n  -d '${payloadStr}'`;
            }

            navigator.clipboard.writeText(curl).then(() => {
                showToast('Curl命令已复制到剪贴板');
            }).catch(err => {
                console.error('复制Curl失败:', err);
                showToast('复制失败，请手动复制');
            });
        }

        async function handleStartClick() {
            if (modeSelect.value === 'compare') {
                await startCompare();
            } else {
                await startStream();
            }
        }

        // init
        modeSelect.addEventListener('change', () => {
            setModeUI();
            // 切换模式时把结果区隐藏，避免误解
            resultSection.style.display = 'none';
            latestTraceOrGroupId = '';
        });

        startBtn.addEventListener('click', handleStartClick);
        stopBtn.addEventListener('click', handleStopClick);
        copyTraceIdBtn.addEventListener('click', handleCopyTraceOrGroupId);
        copyCurlBtn.addEventListener('click', handleCopyCurl);
        clearBtn.addEventListener('click', handleClearClick);

        // 默认初始化
        setModeUI();
    </script>
</body>
</html>
"""

@router.get("/demo", response_class=HTMLResponse)
async def demo_path():
    return DEMO_HTML