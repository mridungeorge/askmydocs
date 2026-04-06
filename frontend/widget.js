(function() {
    const API_URL = "https://askmydocs-production-a2bf.up.railway.app";

    function initWidget() {
        const container = document.getElementById('askmydocs-widget');
        if (!container) return;

        const sourceAttr = container.getAttribute('data-source');
        if (!sourceAttr) {
            console.error('AskMyDocs: data-source attribute required');
            return;
        }

        // Create styles
        const styles = `
            .askmydocs-widget {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                width: 100%;
                max-width: 500px;
                height: 600px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                display: flex;
                flex-direction: column;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .askmydocs-header {
                padding: 16px;
                background: #f5f5f5;
                border-bottom: 1px solid #e0e0e0;
                font-weight: 600;
                font-size: 14px;
            }
            .askmydocs-messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .askmydocs-message {
                display: flex;
                gap: 8px;
                font-size: 13px;
                line-height: 1.5;
            }
            .askmydocs-message.user {
                justify-content: flex-end;
            }
            .askmydocs-message.assistant {
                justify-content: flex-start;
            }
            .askmydocs-bubble {
                max-width: 80%;
                padding: 10px 12px;
                border-radius: 6px;
                word-wrap: break-word;
            }
            .askmydocs-message.user .askmydocs-bubble {
                background: #007AFF;
                color: white;
            }
            .askmydocs-message.assistant .askmydocs-bubble {
                background: #f0f0f0;
                color: #333;
            }
            .askmydocs-sources {
                font-size: 12px;
                color: #666;
                margin-top: 8px;
                max-width: 80%;
                padding: 8px;
                background: #fafafa;
                border-radius: 4px;
                border-left: 2px solid #ddd;
            }
            .askmydocs-input-area {
                display: flex;
                gap: 8px;
                padding: 12px;
                border-top: 1px solid #e0e0e0;
            }
            .askmydocs-input {
                flex: 1;
                padding: 10px 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 13px;
                font-family: inherit;
            }
            .askmydocs-input:focus {
                outline: none;
                border-color: #007AFF;
                box-shadow: 0 0 0 2px rgba(0,122,255,0.1);
            }
            .askmydocs-button {
                padding: 10px 16px;
                background: #007AFF;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
            }
            .askmydocs-button:hover {
                background: #0051D5;
            }
            .askmydocs-button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            .askmydocs-loading {
                text-align: center;
                color: #999;
                font-size: 12px;
            }
            .askmydocs-error {
                background: #fee;
                color: #c00;
                padding: 10px;
                border-radius: 4px;
                font-size: 12px;
            }
        `;

        const styleSheet = document.createElement('style');
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);

        // Create widget HTML
        const widget = document.createElement('div');
        widget.className = 'askmydocs-widget';
        widget.innerHTML = `
            <div class="askmydocs-header">
                📄 Ask My Docs
            </div>
            <div class="askmydocs-messages" id="askmydocs-messages"></div>
            <div class="askmydocs-input-area">
                <input 
                    type="text" 
                    class="askmydocs-input" 
                    id="askmydocs-input"
                    placeholder="Ask a question..."
                />
                <button class="askmydocs-button" id="askmydocs-send">Send</button>
            </div>
        `;

        container.appendChild(widget);

        // Wire up event handlers
        const messagesDiv = document.getElementById('askmydocs-messages');
        const inputField = document.getElementById('askmydocs-input');
        const sendButton = document.getElementById('askmydocs-send');

        const sendMessage = async () => {
            const query = inputField.value.trim();
            if (!query) return;

            // Show user message
            addMessage(query, 'user');
            inputField.value = '';
            sendButton.disabled = true;

            // Show loading
            const loadingId = addMessage('Thinking...', 'assistant', true);

            try {
                const response = await fetch(`${API_URL}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, source_name: sourceAttr }),
                });

                if (!response.ok) {
                    throw new Error(`API error: ${response.statusText}`);
                }

                const data = await response.json();
                
                // Remove loading message
                messagesDiv.removeChild(document.getElementById(loadingId));

                // Show answer
                const answerEl = document.createElement('div');
                answerEl.className = 'askmydocs-message assistant';
                answerEl.innerHTML = `
                    <div>
                        <div class="askmydocs-bubble">${escapeHtml(data.answer)}</div>
                        ${data.sources && data.sources.length > 0 ? `
                            <div class="askmydocs-sources">
                                <strong>Sources:</strong><br/>
                                ${data.sources.map((s, i) => `
                                    <div>[${i+1}] <strong>${escapeHtml(s.name)}</strong>${s.score ? ` (${s.score}% match)` : ''}<br/>
                                    <em>${escapeHtml(s.snippet ?? '')}</em></div>
                                `).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
                messagesDiv.appendChild(answerEl);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;

            } catch (error) {
                messagesDiv.removeChild(document.getElementById(loadingId));
                const errorEl = document.createElement('div');
                errorEl.className = 'askmydocs-message assistant';
                errorEl.innerHTML = `<div class="askmydocs-error">Error: ${escapeHtml(error.message)}</div>`;
                messagesDiv.appendChild(errorEl);
            }

            sendButton.disabled = false;
            inputField.focus();
        };

        function addMessage(text, role, isLoading = false) {
            const msgEl = document.createElement('div');
            msgEl.className = `askmydocs-message ${role}`;
            const msgId = `msg-${Date.now()}`;
            msgEl.id = msgId;
            msgEl.innerHTML = `<div class="askmydocs-bubble${isLoading ? ' askmydocs-loading' : ''}">${escapeHtml(text)}</div>`;
            messagesDiv.appendChild(msgEl);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            return msgId;
        }

        function escapeHtml(text) {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
            return (text || '').replace(/[&<>"']/g, m => map[m]);
        }

        sendButton.addEventListener('click', sendMessage);
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        inputField.focus();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initWidget);
    } else {
        initWidget();
    }
})();
