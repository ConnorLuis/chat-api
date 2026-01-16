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
        #stopBtn {
            background-color: #dc3545;
            color: white;
            display: none; /* 默认隐藏停止按钮 */
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
        
        <div class="btn-group">
            <button id="startBtn">开始聊天 (Start)</button>
            <button id="stopBtn">停止聊天 (Stop)</button>
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

    <script>
        // 获取DOM元素
        const providerSelect = document.getElementById('providerSelect');
        const promptInput = document.getElementById('promptInput');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const resultSection = document.getElementById('resultSection');
        const metaArea = document.getElementById('metaArea');
        const outputArea = document.getElementById('outputArea');
        const usageArea = document.getElementById('usageArea');
        const errorArea = document.getElementById('errorArea');

        // 全局变量：控制流式请求的AbortController
        let abortController = null;

        // 解析SSE事件块的工具函数
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

        // 开始聊天按钮点击事件
        startBtn.addEventListener('click', async () => {
            // 重置UI状态
            resultSection.style.display = 'block';
            metaArea.innerHTML = '';
            outputArea.innerHTML = '';
            usageArea.innerHTML = '';
            errorArea.style.display = 'none';
            errorArea.innerHTML = '';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'inline-block';

            // 创建AbortController（用于停止请求）
            abortController = new AbortController();
            const signal = abortController.signal;

            // 构建请求参数
            const payload = {
                provider: providerSelect.value,
                messages: [{ role: 'user', content: promptInput.value.trim() }],
                max_tokens: 128,
                temperature: 0.7,
                top_p: 0.9
            };

            try {
                // 发起POST流式请求（核心：读取ReadableStream）
                const response = await fetch('/chat/stream', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload),
                    signal: signal // 关联AbortController
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误：${response.status} ${response.statusText}`);
                }

                // 读取流式响应
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    // 解码chunk并拼接缓冲区
                    buffer += decoder.decode(value, { stream: true });
                    // 解析SSE事件块
                    const events = parseSSEBlocks(buffer);
                    // 处理解析后的事件
                    events.forEach(event => {
                        handleSSEEvent(event);
                    });
                    // 清空已解析的缓冲区（保留未完成的最后一块）
                    buffer = buffer.split('\\n\\n').pop() || '';
                }

            } catch (error) {
                // 处理错误（排除主动停止的情况）
                if (error.name !== 'AbortError') {
                    errorArea.style.display = 'block';
                    errorArea.innerHTML = `请求失败：${error.message}`;
                }
            } finally {
                // 恢复按钮状态
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
                abortController = null;
            }
        });

        // 停止聊天按钮点击事件
        stopBtn.addEventListener('click', () => {
            if (abortController) {
                abortController.abort(); // 终止流式请求
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
            }
        });

        // 处理SSE事件的核心函数
        function handleSSEEvent(event) {
            const { type, data } = event;
            try {
                switch (type) {
                    case 'meta':
                        // 处理元信息事件（JSON解析）
                        const meta = JSON.parse(data);
                        metaArea.innerHTML = `
                            <div>Trace ID: ${meta.trace_id || '未知'}</div>
                            <div>Provider: ${meta.provider || '未知'}</div>
                            <div>Model: ${meta.model || '未知'}</div>
                        `;
                        break;
                    case 'token':
                        // 处理token事件（追加内容）
                        outputArea.innerHTML += data;
                        // 自动滚动到底部
                        outputArea.scrollTop = outputArea.scrollHeight;
                        break;
                    case 'usage':
                        // 处理使用统计事件（JSON解析）
                        const usage = JSON.parse(data);
                        usageArea.innerHTML = `
                            <div>输入Token数: ${usage.prompt_tokens || 0}</div>
                            <div>输出Token数: ${usage.completion_tokens || 0}</div>
                            <div>总Token数: ${usage.total_tokens || 0}</div>
                            <div>耗时: ${usage.latency_ms || 0}ms</div>
                        `;
                        break;
                    case 'error':
                        // 处理错误事件（JSON解析）
                        const error = JSON.parse(data);
                        errorArea.style.display = 'block';
                        errorArea.innerHTML = `
                            <div>Trace ID: ${error.trace_id || '未知'}</div>
                            <div>错误类型: ${error.provider || '未知'}</div>
                            <div>错误信息: ${error.error || '未知'}</div>
                        `;
                        break;
                    case 'done':
                        // 处理结束事件
                        outputArea.innerHTML += '<br><br>【流式响应结束】';
                        break;
                    default:
                        // 忽略未知事件
                        break;
                }
            } catch (e) {
                console.error(`解析${type}事件失败:`, e, '原始数据:', data);
            }
        }
    </script>
</body>
</html>
"""

# 定义GET /demo路由，返回HTML响应
@router.get("/demo", response_class=HTMLResponse)
async def demo_path():
    return DEMO_HTML