from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

DEMO_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Chat Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
        body { max-width: 1000px; margin: 20px auto; padding: 0 20px; background-color: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 18px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; color: #333; }
        select, input[type="text"], input[type="number"] {
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 16px;
        }
        .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .hint { color: #666; font-size: 13px; margin-top: 6px; }
        .btn-group { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        button { padding: 10px 20px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }
        #startBtn { background-color: #28a745; color: white; }
        #startBtn:disabled { background-color: #6c757d; cursor: not-allowed; }
        #stopBtn { background-color: #dc3545; color: white; display: none; }
        #copyTraceIdBtn, #copyCurlBtn, #clearBtn { background-color: #007bff; color: white; }

        .result-section { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; display: none; }
        .section-title { font-weight: bold; margin-bottom: 8px; color: #444; }
        #metaArea { background-color: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        #outputArea {
            min-height: 100px; padding: 10px; border: 1px solid #eee; margin-bottom: 10px; white-space: pre-wrap;
        }
        #usageArea { background-color: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; }
        #citationsArea { background-color: #f8f9fa; padding: 10px; margin-bottom: 10px; border-radius: 4px; display: none; }
        #errorArea { color: #dc3545; padding: 10px; background-color: #f8d7da; border-radius: 4px; display: none; }

        /* Compare 专用样式 */
        .compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .compare-card { border: 1px solid #eee; border-radius: 6px; padding: 10px; background: #fff; }
        .compare-card h3 { font-size: 14px; margin-bottom: 6px; color: #333; }
        .compare-meta { font-size: 13px; color: #555; margin-bottom: 6px; }
        .compare-answer { white-space: pre-wrap; border: 1px solid #f0f0f0; padding: 8px; border-radius: 4px; min-height: 80px; }
        .toast {
            position: fixed; top: 20px; right: 20px; padding: 10px 20px;
            background-color: #ffc107; color: #212529; border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 9999; display: none;
        }
        .hidden { display: none !important; }

        /* RAG controls */
        .checkbox-row { display: flex; align-items: center; gap: 8px; height: 44px; padding: 0 10px; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
        .checkbox-row input { width: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM Chat Demo（Stream / Chat / Compare）</h1>

        <div class="form-group">
            <label for="modeSelect">模式 (Mode)</label>
            <select id="modeSelect">
                <option value="stream">Stream Chat（SSE, /chat/stream）</option>
                <option value="chat">Sync Chat（/chat, 支持 citations 展示）</option>
                <option value="compare">Prompt Compare（A/B, /prompt/compare）</option>
            </select>
            <div class="hint">Stream：调用 /chat/stream；Chat：调用 /chat（同步，便于展示 citations）；Compare：调用 /prompt/compare。</div>
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

        <!-- RAG controls -->
        <div class="form-group row-2">
            <div>
                <label>RAG（使用知识库）</label>
                <div class="checkbox-row">
                    <input type="checkbox" id="useKbCheck">
                    <span>Use KB (RAG)</span>
                </div>
                <div class="hint">开启后会把 use_kb/kb_top_k 传给后端。同步 /chat 会展示 citations；流式 citations 在 usage 事件中展示。</div>
            </div>
            <div>
                <label for="kbTopKInput">KB top_k</label>
                <input type="number" id="kbTopKInput" value="3" min="1" max="20">
                <div class="hint">建议 3~8。过大可能导致 prompt 过长。</div>
            </div>
        </div>

        <!-- Stream/Chat 模式：单套 prompt -->
        <div id="streamPromptBox">
            <div class="form-group row-2">
                <div>
                    <label for="promptIdSelect">Prompt ID</label>
                    <select id="promptIdSelect">
                        <option value="chat">chat</option>
                        <option value="qa_strict">qa_strict</option>
                    </select>
                </div>
                <div>
                    <label for="promptVersionSelect">Prompt Version</label>
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
            <button id="startBtn">开始 (Start)</button>
            <button id="stopBtn">停止 (Stop)</button>
            <button id="copyTraceIdBtn">复制 Trace/Group ID</button>
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

            <div class="section-title">引用 (Citations)</div>
            <div id="citationsArea"></div>

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

        const useKbCheck = document.getElementById('useKbCheck');
        const kbTopKInput = document.getElementById('kbTopKInput');

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
        const citationsArea = document.getElementById('citationsArea');
        const errorArea = document.getElementById('errorArea');
        const toast = document.getElementById('toast');

        // State
        let controller = null;
        let running = false;

        // 这两个用于“复制”
        let latestTraceOrGroupId = '';
        let lastStreamPayload = null;
        let lastChatPayload = null;
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
            citationsArea.style.display = 'none';
            citationsArea.innerHTML = '';
            resultSection.style.display = 'block';
        }

        function setRunning(isRunning) {
            running = isRunning;
            startBtn.disabled = isRunning;
        }

        function setModeUI() {
            const mode = modeSelect.value;

            if (mode === 'compare') {
                comparePromptBox.classList.remove('hidden');
                streamPromptBox.classList.add('hidden');
                stopBtn.style.display = 'none';
                startBtn.style.display = 'inline-block';
                startBtn.textContent = '开始对比 (Compare)';
                copyTraceIdBtn.textContent = '复制 Group ID';
                return;
            }

            // stream / chat 都使用单套 prompt
            comparePromptBox.classList.add('hidden');
            streamPromptBox.classList.remove('hidden');

            if (mode === 'stream') {
                startBtn.textContent = '开始聊天 (Stream)';
                copyTraceIdBtn.textContent = '复制 Trace ID';
                stopBtn.style.display = running ? 'inline-block' : 'none';
                startBtn.style.display = running ? 'none' : 'inline-block';
            } else {
                startBtn.textContent = '发送 (Chat)';
                copyTraceIdBtn.textContent = '复制 Trace ID';
                stopBtn.style.display = 'none';
                startBtn.style.display = 'inline-block';
            }
        }

        // ===== SSE utils =====
        function parseSSEBlocks(chunkStr) {
          // 1) 统一换行（兼容 \r\n）
          chunkStr = chunkStr.replace(/\r\n/g, "\n");
        
          const blocks = chunkStr.split("\n\n");
          const events = [];
        
          for (const block of blocks) {
            if (!block.trim()) continue;
        
            const lines = block.split("\n");
            let eventType = null;
            const dataLines = [];
        
            for (const line of lines) {
              const t = line.trim();
        
              // event: meta  或  event:meta 都兼容
              if (t.startsWith("event:")) {
                eventType = t.slice("event:".length).trim();
                continue;
              }
        
              // data: xxx 或 data:xxx 都兼容；允许空串
              if (t.startsWith("data:")) {
                const v = t.slice("data:".length);
                dataLines.push(v.startsWith(" ") ? v.slice(1) : v);
              }
            }
        
            if (eventType !== null && dataLines.length > 0) {
              events.push({ type: eventType, data: dataLines.join("\n") });
            }
          }
        
          return events;
        }

        // ✅ 修复：meta 使用后端 meta.rag 展示 hits/context_chars
        function renderStreamMeta(meta) {
            latestTraceOrGroupId = meta.trace_id || '未知';
            const rag = meta.rag || null;

            const ragLine = rag
              ? `RAG: ${rag.enabled ? 'on' : 'off'} | top_k=${rag.top_k} | hits=${rag.hits} | context_chars=${rag.context_chars}`
              : `RAG: ${useKbCheck.checked ? 'on' : 'off'} | top_k=${kbTopKInput.value || '3'}`;

            metaArea.innerHTML = `
                <div>Trace ID: ${latestTraceOrGroupId}</div>
                <div>Provider: ${meta.provider || '未知'}</div>
                <div>Model: ${meta.model || '未知'}</div>
                <div>Prompt: ${(meta.prompt_id || 'none')}@${(meta.prompt_version || 'none')}</div>
                <div>${ragLine}</div>
            `;
        }

        function appendToken(text) {
            if (!running) return;
            outputArea.innerHTML += text;
            outputArea.scrollTop = outputArea.scrollHeight;
        }

        // ✅ 修复：context_chars 来自 usage.rag.context_chars
        function renderStreamUsage(usage) {
            const rag = usage.rag || null;
            const extra = [];
            if (rag && rag.context_chars !== undefined) extra.push(`<div>context_chars: ${rag.context_chars}</div>`);
            if (rag && rag.hits !== undefined) extra.push(`<div>rag_hits: ${rag.hits}</div>`);
            if (rag && Array.isArray(rag.citations)) extra.push(`<div>citations_count: ${rag.citations.length}</div>`);

            usageArea.innerHTML = `
                <div>耗时: ${usage.latency_ms || 0}ms</div>
                <div>Token事件数: ${usage.token_events || 0}</div>
                ${extra.join('')}
            `;
        }

        function renderCitations(citations) {
            if (!citations || citations.length === 0) {
                citationsArea.style.display = 'none';
                citationsArea.innerHTML = '';
                return;
            }
            citationsArea.style.display = 'block';
            const items = citations.map((c, idx) => {
                const title = (c.title === null || c.title === undefined) ? '' : ` | title=${c.title}`;
                return `<div>[${idx+1}] doc_id=${c.doc_id} | chunk_id=${c.chunk_id} | source=${c.source}${title}</div>`;
            });
            citationsArea.innerHTML = items.join('');
        }

        function renderError(err) {
            errorArea.style.display = 'block';
            if (typeof err === 'object') {
                // 如果 error 事件里带 rag 摘要，也展示出来（可选）
                const rag = err.rag || null;
                const ragInfo = rag ? `<div>RAG: ${rag.enabled ? 'on' : 'off'} | top_k=${rag.top_k} | hits=${rag.hits} | context_chars=${rag.context_chars} | citations_count=${rag.citations_count || 0}</div>` : '';
                errorArea.innerHTML = `
                    <div>Trace/Group: ${err.trace_id || err.compare_group_id || '未知'}</div>
                    <div>Provider: ${err.provider || '未知'}</div>
                    ${ragInfo}
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
                    case 'meta': {
                        const meta = JSON.parse(data);
                        renderStreamMeta(meta);
                        break;
                    }
                    case 'token': appendToken(data); break;
                    case 'usage': {
                        const usage = JSON.parse(data);
                        renderStreamUsage(usage);

                        if (usage.rag && Array.isArray(usage.rag.citations)) {
                            renderCitations(usage.rag.citations);
                        } else {
                            renderCitations([]);
                        }

                        if (usage.rag && usage.rag.error) {
                            renderError({ error: usage.rag.error, trace_id: usage.trace_id, provider: usage.provider });
                        }
                        break;
                    }
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
        function buildBasePayload() {
            const useKb = !!useKbCheck.checked;
            const topK = parseInt(kbTopKInput.value || '3', 10);
            return {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_id: promptIdSelect.value,
                prompt_version: promptVersionSelect.value,
                prompt_vars: {},
                use_kb: useKb,
                kb_top_k: useKb ? topK : null
            };
        }

        function buildStreamPayload() { return buildBasePayload(); }
        function buildChatPayload() { return buildBasePayload(); }

        function buildComparePayload() {
            return {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_a: { prompt_id: promptAIdSelect.value, prompt_version: promptAVersionSelect.value, prompt_vars: {} },
                prompt_b: { prompt_id: promptBIdSelect.value, prompt_version: promptBVersionSelect.value, prompt_vars: {} }
            };
        }

        // ===== Actions =====
        async function startChat() {
            if (running) { showToast('正在运行中，请稍后再试'); return; }
            resetUI();
            setRunning(true);
            setModeUI();

            const payload = buildChatPayload();
            lastChatPayload = payload;

            try {
                const resp = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!resp.ok) {
                    const text = await resp.text();
                    throw new Error(`HTTP错误：${resp.status} ${resp.statusText} ${text}`);
                }

                const data = await resp.json();
                latestTraceOrGroupId = data.trace_id || '未知';

                const md = data.metadata || {};
                const rag = md.rag || null;

                metaArea.innerHTML = `
                    <div>Trace ID: ${latestTraceOrGroupId}</div>
                    <div>Provider: ${md.provider || payload.provider || '未知'}</div>
                    <div>Model: ${md.model || '未知'}</div>
                    <div>Prompt: ${(md.prompt_id || payload.prompt_id || 'none')}@${(md.prompt_version || payload.prompt_version || 'none')}</div>
                    <div>RAG: ${payload.use_kb ? 'on' : 'off'} | top_k=${payload.kb_top_k || 'n/a'} | hits=${(rag && rag.hits !== undefined) ? rag.hits : 'n/a'}</div>
                `;

                outputArea.innerHTML = (data.answer || '').replace(/</g,'&lt;').replace(/>/g,'&gt;');

                usageArea.innerHTML = `
                    <div>耗时: ${md.latency_ms || 0}ms</div>
                    <div>context_chars: ${md.context_chars || 0}</div>
                `;

                if (rag && Array.isArray(rag.citations)) {
                    renderCitations(rag.citations);
                } else {
                    renderCitations([]);
                }

            } catch (err) {
                renderError(`Chat 失败：${err.message || err}`);
            } finally {
                setRunning(false);
                setModeUI();
            }
        }

        async function startStream() {
            if (running) { showToast('正在运行中，请先停止后再操作'); return; }
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
                    buffer = buffer.replace(/\r\n/g, "\n");
                    
                    // 只处理完整事件块：找到最后一个 \n\n
                    const lastSep = buffer.lastIndexOf("\n\n");
                    if (lastSep === -1) {
                      continue; // 还不够一个完整块
                    }
                    
                    const ready = buffer.slice(0, lastSep + 2);  // +2 保留分隔符
                    buffer = buffer.slice(lastSep + 2);          // 剩余半包留到下次
                    
                    const events = parseSSEBlocks(ready);
                    events.forEach(handleSSEEvent);
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
            citationsArea.style.display = 'none';
            citationsArea.innerHTML = '';
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
            const mode = modeSelect.value;
            let curl = '';

            if (mode === 'compare') {
                const payload = lastComparePayload || buildComparePayload();
                const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
                curl = `curl -X POST http://localhost:8000/prompt/compare \n  -H "Content-Type: application/json" \n  -d '${payloadStr}'`;
            } else if (mode === 'chat') {
                const payload = lastChatPayload || buildChatPayload();
                const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
                curl = `curl -X POST http://localhost:8000/chat \n  -H "Content-Type: application/json" \n  -d '${payloadStr}'`;
            } else {
                const payload = lastStreamPayload || buildStreamPayload();
                const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
                curl = `curl -N -X POST http://localhost:8000/chat/stream \n  -H "Content-Type: application/json" \n  -d '${payloadStr}'`;
            }

            navigator.clipboard.writeText(curl).then(() => {
                showToast('Curl命令已复制到剪贴板');
            }).catch(err => {
                console.error('复制Curl失败:', err);
                showToast('复制失败，请手动复制');
            });
        }

        async function handleStartClick() {
            const mode = modeSelect.value;
            if (mode === 'compare') await startCompare();
            else if (mode === 'chat') await startChat();
            else await startStream();
        }

        // init
        modeSelect.addEventListener('change', () => {
            setModeUI();
            resultSection.style.display = 'none';
            latestTraceOrGroupId = '';
        });

        useKbCheck.addEventListener('change', () => {
            if (!useKbCheck.checked) {
                kbTopKInput.value = '3';
            }
        });

        startBtn.addEventListener('click', handleStartClick);
        stopBtn.addEventListener('click', handleStopClick);
        copyTraceIdBtn.addEventListener('click', handleCopyTraceOrGroupId);
        copyCurlBtn.addEventListener('click', handleCopyCurl);
        clearBtn.addEventListener('click', handleClearClick);

        setModeUI();
    </script>
</body>
</html>
"""

@router.get("/demo", response_class=HTMLResponse)
async def demo_path():
    return DEMO_HTML