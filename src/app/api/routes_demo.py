from fastapi import APIRouter
from fastapi.responses import HTMLResponse

# 创建独立的路由实例（方便后续挂载到主app）
router = APIRouter()

# 定义Demo页面的HTML内容（内联CSS+JS）
DEMO_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Chat Stream Demo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: Arial, sans-serif;
        }
        body {
            max-width: 1000px;
            margin: 20px auto;
            padding: 0 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }
        select, input[type="text"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        .btn-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
        }
        #startBtn {
            background-color: #28a745;
            color: white;
        }
        #startBtn:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        #stopBtn {
            background-color: #dc3545;
            color: white;
            display: none; /* 默认隐藏停止按钮 */
        }
        #copyTraceIdBtn, #copyCurlBtn, #clearBtn {
            background-color: #007bff;
            color: white;
        }
        .result-section {
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            display: none; /* 默认隐藏结果区 */
        }
        .section-title {
            font-weight: bold;
            margin-bottom: 8px;
            color: #444;
        }
        #metaArea {
            background-color: #f8f9fa;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        #outputArea {
            min-height: 100px;
            padding: 10px;
            border: 1px solid #eee;
            margin-bottom: 10px;
            white-space: pre-wrap;
        }
        #usageArea {
            background-color: #f8f9fa;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        #errorArea {
            color: #dc3545;
            padding: 10px;
            background-color: #f8d7da;
            border-radius: 4px;
            display: none; /* 默认隐藏错误区 */
        }
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            background-color: #ffc107;
            color: #212529;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 9999;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM 流式聊天 Demo</h1>

        <!-- 输入表单 -->
        <div class="form-group">
            <label for="providerSelect">模型引擎 (Provider)</label>
            <select id="providerSelect">
                <option value="mock">mock (测试用)</option>
                <option value="ollama">ollama (本地模型)</option>
            </select>
        </div>

        <div class="form-group">
            <label for="promptInput">输入提示 (Prompt)</label>
            <input type="text" id="promptInput" placeholder="请输入你想提问的内容，比如：hi" value="hi">
        </div>
        
        <div class="form-group">
            <label for="promptIdSelect">Prompt ID</label>
            <select id="promptIdSelect">
                <option value="chat">chat</option>
                <option value="qa_strict">qa_strict</option>
            </select>
        </div>
        
        <div class="form-group">
            <label for="promptVersionSelect">Prompt Version</label>
            <select id="promptVersionSelect">
                <option value="v1">v1</option>
            </select>
        </div>

        <div class="btn-group">
            <button id="startBtn">开始聊天 (Start)</button>
            <button id="stopBtn">停止聊天 (Stop)</button>
            <button id="copyTraceIdBtn">复制 Trace ID</button>
            <button id="copyCurlBtn">复制 Curl 命令</button>
            <button id="clearBtn">清空输出</button>
        </div>

        <!-- 结果展示区 -->
        <div class="result-section" id="resultSection">
            <div class="section-title">元信息 (Meta)</div>
            <div id="metaArea"></div>

            <div class="section-title">输出内容 (Output)</div>
            <div id="outputArea"></div>

            <div class="section-title">使用统计 (Usage)</div>
            <div id="usageArea"></div>

            <div class="section-title">错误信息 (Error)</div>
            <div id="errorArea"></div>
        </div>
    </div>

    <!-- 提示弹窗 -->
    <div class="toast" id="toast"></div>

    <script>
        // 获取DOM元素
        const providerSelect = document.getElementById('providerSelect');
        const promptInput = document.getElementById('promptInput');
        const promptIdSelect = document.getElementById('promptIdSelect');
        const promptVersionSelect = document.getElementById('promptVersionSelect');
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

        // 全局变量
        let controller = null;
        let running = false;
        let latestTraceId = '';

        // ====================== UI操作封装函数 ======================
        /**
         * 重置UI到初始状态
         */
        function resetUI() {
            // 隐藏错误区，清空所有内容
            errorArea.style.display = 'none';
            errorArea.innerHTML = '';
            metaArea.innerHTML = '';
            outputArea.innerHTML = '';
            usageArea.innerHTML = '';
            // 显示结果区
            resultSection.style.display = 'block';
        }

        /**
         * 设置运行状态（控制按钮禁用/显示）
         * @param {boolean} isRunning - 是否正在运行
         */
        function setRunning(isRunning) {
            running = isRunning;
            // 禁用/启用Start按钮
            startBtn.disabled = isRunning;
            // 显示/隐藏Stop按钮
            stopBtn.style.display = isRunning ? 'inline-block' : 'none';
            startBtn.style.display = isRunning ? 'none' : 'inline-block';
        }

        /**
         * 渲染元信息
         * @param {object} meta - 元信息对象
         */
        function renderMeta(meta) {
            latestTraceId = meta.trace_id || '未知'; // 保存最新Trace ID
            metaArea.innerHTML = `
                <div>Trace ID: ${latestTraceId}</div>
                <div>Provider: ${meta.provider || '未知'}</div>
                <div>Model: ${meta.model || '未知'}</div>
            `;
        }

        /**
         * 追加Token内容到输出区
         * @param {string} text - 要追加的文本
         */
        function appendToken(text) {
            if (!running) return; // 非运行状态不追加
            outputArea.innerHTML += text;
            // 自动滚动到底部
            outputArea.scrollTop = outputArea.scrollHeight;
        }

        /**
         * 渲染使用统计
         * @param {object} usage - 使用统计对象
         */
        function renderUsage(usage) {
            usageArea.innerHTML = `
                <div>耗时: ${usage.latency_ms || 0}ms</div>
                <div>Token事件数: ${usage.token_events || 0}</div>
            `;
        }

        /**
         * 渲染错误信息
         * @param {string|object} err - 错误信息（字符串或对象）
         */
        function renderError(err) {
            errorArea.style.display = 'block';
            if (typeof err === 'object') {
                errorArea.innerHTML = `
                    <div>Trace ID: ${err.trace_id || '未知'}</div>
                    <div>错误类型: ${err.provider || '未知'}</div>
                    <div>错误信息: ${err.error || '未知'}</div>
                `;
            } else {
                errorArea.innerHTML = err;
            }
        }

        /**
         * 渲染完成状态
         */
        function renderDone() {
            if (running) {
                outputArea.innerHTML += '<br><br>【流式响应结束】';
            }
        }

        /**
         * 显示提示弹窗
         * @param {string} message - 提示内容
         * @param {number} duration - 显示时长(ms)，默认2000
         */
        function showToast(message, duration = 2000) {
            toast.textContent = message;
            toast.style.display = 'block';
            setTimeout(() => {
                toast.style.display = 'none';
            }, duration);
        }

        // ====================== 解析工具函数 ======================
        /**
         * 解析SSE事件块
         * @param {string} chunkStr - 原始chunk字符串
         * @returns {Array} 解析后的事件数组
         */
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

        // ====================== 事件处理函数 ======================
        /**
         * 处理SSE事件
         * @param {object} event - SSE事件对象
         */
        function handleSSEEvent(event) {
            if (!running) return; // 非运行状态不处理

            const { type, data } = event;
            try {
                switch (type) {
                    case 'meta':
                        renderMeta(JSON.parse(data));
                        break;
                    case 'token':
                        appendToken(data);
                        break;
                    case 'usage':
                        renderUsage(JSON.parse(data));
                        break;
                    case 'error':
                        renderError(JSON.parse(data));
                        break;
                    case 'done':
                        renderDone();
                        break;
                    default:
                        // 忽略未知事件
                        break;
                }
            } catch (e) {
                console.error(`解析${type}事件失败:`, e, '原始数据:', data);
            }
        }
        
        /**
         * 复制Trace ID到剪贴板
         */
        function handleCopyTraceId() {
            if (!latestTraceId || latestTraceId === '未知') {
                showToast('暂无可用的Trace ID');
                return;
            }
            navigator.clipboard.writeText(latestTraceId).then(() => {
                showToast('Trace ID已复制到剪贴板');
            }).catch(err => {
                console.error('复制Trace ID失败:', err);
                showToast('复制失败，请手动复制');
            });
        }
        
        /**
         * 复制Curl命令到剪贴板
         */
        function handleCopyCurl() {
            // 构建和请求一致的payload
            const payload = {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_id: promptIdSelect.value,
                prompt_version: promptVersionSelect.value,
                prompt_vars: {}
            };

            // 拼接curl命令，处理单引号转义
            const payloadStr = JSON.stringify(payload).replace(/'/g, "'\\''");
            const curl = `curl -N -X POST http://localhost:8000/chat/stream \\\n  -H "Content-Type: application/json" \\\n  -d '${payloadStr}'`;

            // 复制到剪贴板
            navigator.clipboard.writeText(curl).then(() => {
                showToast('Curl命令已复制到剪贴板');
            }).catch(err => {
                console.error('复制Curl失败:', err);
                showToast('复制失败，请手动复制');
            });
        }

        /**
         * 清空输出并重置状态
         */
        function handleClearClick() {
            // 停止正在运行的请求
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
            resultSection.style.display = 'none'; // 隐藏结果区
            latestTraceId = ''; // 清空trace_id
            
            promptInput.focus();
    
            showToast(`已清空所有输出内容 ${stopTip}`, 2000);
        }

        // ====================== 按钮点击事件 ======================
        /**
         * 开始按钮点击事件
         */
        async function handleStartClick() {
            // 防止连续点击：如果正在运行，直接提示并返回
            if (running) {
                showToast('正在运行中，请先停止后再操作');
                return;
            }

            // 初始化状态
            resetUI();
            setRunning(true);
            controller = new AbortController();
            const signal = controller.signal;
            

            // 构建请求参数
            const payload = {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9,
                prompt_id: promptIdSelect.value,
                prompt_version: promptVersionSelect.value,
                prompt_vars: {}
            };

            try {
                // 发起POST流式请求
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload),
                    signal: signal
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误：${response.status} ${response.statusText}`);
                }

                // 读取流式响应
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (running) { // 基于running状态循环
                    const { done, value } = await reader.read();
                    if (done) break;

                    // 解码并解析SSE事件
                    buffer += decoder.decode(value, { stream: true });
                    const events = parseSSEBlocks(buffer);
                    events.forEach(handleSSEEvent);
                    // 清空已解析的缓冲区
                    buffer = buffer.split('\\n\\n').pop() || '';
                }

            } catch (error) {
                // 仅处理非AbortError的错误
                if (error.name !== 'AbortError') {
                    renderError(`请求失败：${error.message}`);
                } else {
                    // 主动停止时追加标记
                    appendToken('\\n[已停止]');
                }
            } finally {
                // 恢复运行状态和按钮
                setRunning(false);
                controller = null;
            }
        }

        /**
         * 停止按钮点击事件
         */
        function handleStopClick() {
            if (controller) {
                controller.abort(); // 终止请求
                appendToken('\\n[已停止]'); // 立即标记停止
                setRunning(false); // 重置状态
                controller = null;
            }
        }

        // 绑定按钮事件
        startBtn.addEventListener('click', handleStartClick);
        stopBtn.addEventListener('click', handleStopClick);
        copyTraceIdBtn.addEventListener('click', handleCopyTraceId);
        copyCurlBtn.addEventListener('click', handleCopyCurl);
        clearBtn.addEventListener('click', handleClearClick);
    </script>
</body>
</html>
"""


# 定义GET /demo路由，返回HTML响应
@router.get("/demo", response_class=HTMLResponse)
async def demo_path():
    return DEMO_HTML