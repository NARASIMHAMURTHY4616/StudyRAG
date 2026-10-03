/**
 * StudyRAG V2 — Modern ChatGPT-Style Local Academic Assistant Controller
 */

document.addEventListener("DOMContentLoaded", () => {
    // App State
    const state = {
        currentConvId: null,
        conversations: [],
        activeModel: "qwen3:1.7b",
        topK: 10,
        minSimilarity: 0.25,
        debugMode: false,
        theme: localStorage.getItem("studyrag_theme") || "dark",
        isGenerating: false,
        abortController: null,
    };

    // Apply saved theme
    document.documentElement.setAttribute("data-theme", state.theme);

    // DOM Elements
    const elements = {
        sidebar: document.getElementById("sidebar"),
        sidebarToggle: document.getElementById("sidebar-toggle"),
        newChatBtn: document.getElementById("new-chat-btn"),
        historySearch: document.getElementById("history-search"),
        historyList: document.getElementById("history-list"),
        openDocsBtn: document.getElementById("open-docs-btn"),
        openSettingsBtn: document.getElementById("open-settings-btn"),
        docCounter: document.getElementById("doc-counter"),
        globalStatusDot: document.getElementById("global-status-dot"),
        globalStatusLabel: document.getElementById("global-status-label"),

        currentChatTitle: document.getElementById("current-chat-title"),
        activeModelName: document.getElementById("active-model-name"),
        clearChatBtn: document.getElementById("clear-chat-btn"),

        chatMessagesContainer: document.getElementById("chat-messages"),
        welcomeScreen: document.getElementById("welcome-screen"),
        messagesList: document.getElementById("messages-list"),

        chatTextarea: document.getElementById("chat-textarea"),
        sendMessageBtn: document.getElementById("send-message-btn"),
        stopGenerationBtn: document.getElementById("stop-generation-btn"),
        attachShortcutBtn: document.getElementById("attach-shortcut-btn"),

        // Docs Modal
        docsModal: document.getElementById("docs-modal"),
        closeDocsModal: document.getElementById("close-docs-modal"),
        modalDropzone: document.getElementById("modal-dropzone"),
        modalFileInput: document.getElementById("modal-file-input"),
        browseFilesBtn: document.getElementById("browse-files-btn"),
        uploadProgressContainer: document.getElementById("upload-progress-container"),
        uploadProgressBar: document.getElementById("upload-progress-bar"),
        uploadProgressText: document.getElementById("upload-progress-text"),
        modalDocCount: document.getElementById("modal-doc-count"),
        modalDocsList: document.getElementById("modal-docs-list"),

        // Settings Modal
        settingsModal: document.getElementById("settings-modal"),
        closeSettingsModal: document.getElementById("close-settings-modal"),
        settingsForm: document.getElementById("settings-form"),
        settingModel: document.getElementById("setting-model"),
        settingTopK: document.getElementById("setting-top-k"),
        valTopK: document.getElementById("val-top-k"),
        settingMinSim: document.getElementById("setting-min-sim"),
        valMinSim: document.getElementById("val-min-sim"),
        settingTheme: document.getElementById("setting-theme"),
        settingDebug: document.getElementById("setting-debug"),
        statusOllamaPill: document.getElementById("status-ollama-pill"),
        statusMongoPill: document.getElementById("status-mongo-pill"),
        statusVectorsCount: document.getElementById("status-vectors-count"),
        statusEmbedderName: document.getElementById("status-embedder-name"),
    };

    // Configure Marked.js renderer
    if (window.marked) {
        marked.setOptions({
            breaks: true,
            gfm: true,
            highlight: function (code, lang) {
                if (window.hljs && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {}
                }
                return window.hljs ? hljs.highlightAuto(code).value : code;
            },
        });
    }

    // Initialize Application
    async function initApp() {
        bindEvents();
        await fetchSystemStatus();
        await loadConversations();
        await loadDocumentsList();
    }

    // Event Bindings
    function bindEvents() {
        // Sidebar toggle
        elements.sidebarToggle?.addEventListener("click", () => {
            elements.sidebar.classList.toggle("open");
        });

        // New Chat
        elements.newChatBtn?.addEventListener("click", () => startNewChat());

        // Clear Chat
        elements.clearChatBtn?.addEventListener("click", () => startNewChat());

        // Textarea auto-resize & keypress
        elements.chatTextarea?.addEventListener("input", () => {
            autoResizeTextarea();
            toggleSendButton();
        });

        elements.chatTextarea?.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!state.isGenerating && elements.chatTextarea.value.trim()) {
                    sendMessage();
                }
            }
        });

        // Send & Stop Buttons
        elements.sendMessageBtn?.addEventListener("click", () => sendMessage());
        elements.stopGenerationBtn?.addEventListener("click", () => stopGeneration());

        // History search
        elements.historySearch?.addEventListener("input", (e) => {
            filterHistoryList(e.target.value);
        });

        // Suggestion prompts
        document.querySelectorAll(".suggestion-card").forEach((card) => {
            card.addEventListener("click", () => {
                const prompt = card.getAttribute("data-prompt");
                if (prompt) {
                    elements.chatTextarea.value = prompt;
                    autoResizeTextarea();
                    toggleSendButton();
                    sendMessage();
                }
            });
        });

        // Documents Modal Open/Close
        elements.openDocsBtn?.addEventListener("click", () => openModal(elements.docsModal));
        elements.attachShortcutBtn?.addEventListener("click", () => openModal(elements.docsModal));
        elements.closeDocsModal?.addEventListener("click", () => closeModal(elements.docsModal));

        // Settings Modal Open/Close
        elements.openSettingsBtn?.addEventListener("click", () => {
            openSettings();
            openModal(elements.settingsModal);
        });
        elements.closeSettingsModal?.addEventListener("click", () => closeModal(elements.settingsModal));

        // Settings inputs
        elements.settingTopK?.addEventListener("input", (e) => {
            elements.valTopK.textContent = e.target.value;
        });
        elements.settingMinSim?.addEventListener("input", (e) => {
            elements.valMinSim.textContent = e.target.value;
        });
        elements.settingsForm?.addEventListener("submit", (e) => {
            e.preventDefault();
            saveSettings();
        });

        // Modal file upload triggers
        elements.browseFilesBtn?.addEventListener("click", () => elements.modalFileInput.click());
        elements.modalFileInput?.addEventListener("change", (e) => handleFileUpload(e.target.files));

        // Drag & Drop
        elements.modalDropzone?.addEventListener("dragover", (e) => {
            e.preventDefault();
            elements.modalDropzone.classList.add("dragover");
        });
        elements.modalDropzone?.addEventListener("dragleave", () => {
            elements.modalDropzone.classList.remove("dragover");
        });
        elements.modalDropzone?.addEventListener("drop", (e) => {
            e.preventDefault();
            elements.modalDropzone.classList.remove("dragover");
            if (e.dataTransfer.files?.length) {
                handleFileUpload(e.dataTransfer.files);
            }
        });

        // Modal backdrop click
        [elements.docsModal, elements.settingsModal].forEach((modal) => {
            modal?.addEventListener("click", (e) => {
                if (e.target === modal) closeModal(modal);
            });
        });
    }

    // Textarea helpers
    function autoResizeTextarea() {
        const ta = elements.chatTextarea;
        ta.style.height = "auto";
        ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    }

    function toggleSendButton() {
        const hasText = elements.chatTextarea.value.trim().length > 0;
        elements.sendMessageBtn.disabled = !hasText || state.isGenerating;
    }

    function openModal(modal) {
        modal?.classList.remove("hidden");
    }

    function closeModal(modal) {
        modal?.classList.add("hidden");
    }

    // Fetch System Health & Config
    async function fetchSystemStatus() {
        try {
            const res = await fetch("/api/status");
            if (!res.ok) throw new Error("Status check failed");
            const data = await res.json();

            state.activeModel = data.ollama_model || "qwen3:1.7b";
            state.topK = data.top_k || 10;
            state.minSimilarity = data.min_similarity || 0.25;

            // Update UI indicators
            if (elements.activeModelName) elements.activeModelName.textContent = state.activeModel;
            if (elements.docCounter) elements.docCounter.textContent = Object.keys(data.indexed_documents || {}).length;
            if (elements.modalDocCount) elements.modalDocCount.textContent = Object.keys(data.indexed_documents || {}).length;
            if (elements.statusVectorsCount) elements.statusVectorsCount.textContent = `${data.total_vectors || 0} Vectors`;
            if (elements.statusEmbedderName) elements.statusEmbedderName.textContent = data.embedding_model || "all-MiniLM-L6-v2";

            const ollamaOk = data.ollama_available;
            const mongoOk = data.mongodb_available !== false;

            if (elements.statusOllamaPill) {
                elements.statusOllamaPill.textContent = ollamaOk ? "Online" : "Offline";
                elements.statusOllamaPill.className = `status-pill ${ollamaOk ? "online" : "offline"}`;
            }

            if (elements.statusMongoPill) {
                elements.statusMongoPill.textContent = mongoOk ? "Connected" : "Disconnected (Volatile)";
                elements.statusMongoPill.className = `status-pill ${mongoOk ? "online" : "offline"}`;
            }

            if (elements.globalStatusDot && elements.globalStatusLabel) {
                if (ollamaOk && mongoOk) {
                    elements.globalStatusDot.className = "status-dot online";
                    elements.globalStatusLabel.textContent = "Ollama & Mongo Ready";
                } else if (ollamaOk && !mongoOk) {
                    elements.globalStatusDot.className = "status-dot online";
                    elements.globalStatusLabel.textContent = "Ollama Online (Memory DB)";
                } else {
                    elements.globalStatusDot.className = "status-dot";
                    elements.globalStatusLabel.textContent = "Ollama Offline";
                }
            }

            // Populate model dropdown
            if (elements.settingModel && data.available_models) {
                elements.settingModel.innerHTML = "";
                data.available_models.forEach((m) => {
                    const opt = document.createElement("option");
                    opt.value = m;
                    opt.textContent = m;
                    if (m === state.activeModel) opt.selected = true;
                    elements.settingModel.appendChild(opt);
                });
            }
        } catch (e) {
            console.warn("Could not fetch system status:", e);
        }
    }

    // Conversations Management
    async function loadConversations() {
        try {
            const res = await fetch("/api/conversations");
            if (!res.ok) return;
            const convs = await res.json();
            state.conversations = convs;
            renderHistoryList(convs);
        } catch (e) {
            console.error("Error loading conversations:", e);
        }
    }

    function groupConversationsByDate(convList) {
        const groups = {
            Today: [],
            Yesterday: [],
            "Previous 7 Days": [],
            Older: [],
        };

        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const startOfYesterday = new Date(startOfToday.getTime() - 24 * 60 * 60 * 1000);
        const startOf7Days = new Date(startOfToday.getTime() - 7 * 24 * 60 * 60 * 1000);

        convList.forEach((conv) => {
            const date = new Date(conv.updated_at || conv.created_at || Date.now());
            if (date >= startOfToday) {
                groups["Today"].push(conv);
            } else if (date >= startOfYesterday) {
                groups["Yesterday"].push(conv);
            } else if (date >= startOf7Days) {
                groups["Previous 7 Days"].push(conv);
            } else {
                groups["Older"].push(conv);
            }
        });

        return groups;
    }

    function renderHistoryList(convList) {
        if (!elements.historyList) return;
        elements.historyList.innerHTML = "";

        if (convList.length === 0) {
            elements.historyList.innerHTML = '<div class="history-skeleton" style="padding:10px 14px;">No chats yet</div>';
            return;
        }

        const grouped = groupConversationsByDate(convList);

        for (const [groupName, items] of Object.entries(grouped)) {
            if (items.length === 0) continue;

            const groupTitle = document.createElement("div");
            groupTitle.className = "history-group-title";
            groupTitle.textContent = groupName;
            elements.historyList.appendChild(groupTitle);

            items.forEach((conv) => {
                const item = document.createElement("div");
                item.className = `history-item ${conv.conversation_id === state.currentConvId ? "active" : ""}`;
                item.dataset.id = conv.conversation_id;

                item.innerHTML = `
                    <span class="history-item-title" title="${escapeHtml(conv.title || 'Untitled Chat')}">
                        ${escapeHtml(conv.title || "Untitled Chat")}
                    </span>
                    <div class="history-item-actions">
                        <button class="history-action-btn delete-conv" title="Delete conversation">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                `;

                // Select chat click
                item.addEventListener("click", (e) => {
                    if (e.target.closest(".delete-conv")) return;
                    openConversation(conv.conversation_id);
                });

                // Delete chat click
                item.querySelector(".delete-conv")?.addEventListener("click", (e) => {
                    e.stopPropagation();
                    deleteConversation(conv.conversation_id);
                });

                elements.historyList.appendChild(item);
            });
        }
    }

    function filterHistoryList(query) {
        if (!query.trim()) {
            renderHistoryList(state.conversations);
            return;
        }
        const filtered = state.conversations.filter((c) =>
            (c.title || "").toLowerCase().includes(query.toLowerCase())
        );
        renderHistoryList(filtered);
    }

    function startNewChat() {
        state.currentConvId = null;
        if (elements.currentChatTitle) elements.currentChatTitle.textContent = "New Chat";
        if (elements.messagesList) elements.messagesList.innerHTML = "";
        if (elements.welcomeScreen) elements.welcomeScreen.classList.remove("hidden");
        document.querySelectorAll(".history-item").forEach((el) => el.classList.remove("active"));
        elements.chatTextarea.value = "";
        autoResizeTextarea();
        toggleSendButton();
        if (window.innerWidth <= 768) elements.sidebar.classList.remove("open");
    }

    async function openConversation(convId) {
        if (state.currentConvId === convId) return;

        state.currentConvId = convId;
        document.querySelectorAll(".history-item").forEach((el) => {
            el.classList.toggle("active", el.dataset.id === convId);
        });

        if (elements.welcomeScreen) elements.welcomeScreen.classList.add("hidden");
        if (elements.messagesList) elements.messagesList.innerHTML = "<div class='history-skeleton' style='text-align:center;'>Loading messages...</div>";

        try {
            const res = await fetch(`/api/conversations/${convId}`);
            if (!res.ok) throw new Error("Failed to load conversation");
            const data = await res.json();

            if (elements.currentChatTitle) elements.currentChatTitle.textContent = data.title || "Study Session";
            if (elements.messagesList) elements.messagesList.innerHTML = "";

            const messages = data.messages || [];
            if (messages.length === 0) {
                if (elements.welcomeScreen) elements.welcomeScreen.classList.remove("hidden");
            } else {
                messages.forEach((msg) => {
                    renderMessage(msg.role, msg.content, msg.sources, msg.metadata, false);
                });
                scrollToBottom();
            }

            if (window.innerWidth <= 768) elements.sidebar.classList.remove("open");
        } catch (e) {
            console.error("Error loading conversation:", e);
            if (elements.messagesList) elements.messagesList.innerHTML = "<div style='color:var(--accent-error);text-align:center;'>Error loading conversation messages.</div>";
        }
    }

    async function deleteConversation(convId) {
        if (!confirm("Are you sure you want to delete this conversation?")) return;
        try {
            const res = await fetch(`/api/conversations/${convId}`, { method: "DELETE" });
            if (res.ok) {
                state.conversations = state.conversations.filter((c) => c.conversation_id !== convId);
                renderHistoryList(state.conversations);
                if (state.currentConvId === convId) {
                    startNewChat();
                }
            }
        } catch (e) {
            console.error("Error deleting conversation:", e);
        }
    }

    // Message Rendering & Sending
    function renderMessage(role, content, sources = [], metadata = {}, animate = true) {
        if (elements.welcomeScreen) elements.welcomeScreen.classList.add("hidden");

        const wrapper = document.createElement("div");
        wrapper.className = `message-wrapper ${role}`;

        if (role === "assistant") {
            wrapper.innerHTML = `
                <div class="message-avatar">📚</div>
                <div class="message-body">
                    <div class="markdown-content">${formatMarkdown(content)}</div>
                    ${renderSourcesHtml(sources)}
                    ${renderDebugHtml(metadata?.retrieved_chunks_data)}
                </div>
            `;
        } else {
            wrapper.innerHTML = `
                <div class="message-body">
                    ${escapeHtml(content)}
                </div>
            `;
        }

        // Attach copy button handlers
        wrapper.querySelectorAll(".code-copy-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const pre = btn.closest("pre");
                const code = pre?.querySelector("code")?.innerText || "";
                navigator.clipboard.writeText(code).then(() => {
                    btn.textContent = "Copied!";
                    setTimeout(() => (btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy'), 2000);
                });
            });
        });

        elements.messagesList.appendChild(wrapper);
        return wrapper;
    }

    function renderSourcesHtml(sources) {
        if (!sources || sources.length === 0) return "";
        const pills = sources
            .map((src) => {
                const doc = escapeHtml(src.document || src.source || "Document");
                const page = src.page || src.page_number || "?";
                const score = src.score ? `<span class="source-score-badge">${Math.round(src.score * 100)}%</span>` : "";
                return `
                    <div class="source-pill" title="${doc} (Page ${page})">
                        📄 <strong>${doc}</strong> · p.${page} ${score}
                    </div>
                `;
            })
            .join("");

        return `
            <div class="sources-container">
                <div class="sources-header">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                    Sources & Verified Citations
                </div>
                <div class="sources-pills">${pills}</div>
            </div>
        `;
    }

    function renderDebugHtml(chunks) {
        if (!state.debugMode || !chunks || chunks.length === 0) return "";
        const chunkCards = chunks
            .map((c, idx) => {
                const doc = escapeHtml(c.document_name || c.source || "Doc");
                const p = c.page_number || c.page || "?";
                const score = c.score ? (c.score * 100).toFixed(1) + "%" : "";
                const text = escapeHtml((c.chunk_text || c.text || "").substring(0, 160));
                return `
                    <div class="debug-chunk-card">
                        <div class="debug-chunk-meta">
                            <span>[#${idx + 1}] ${doc} (Page ${p})</span>
                            <span>Score: ${score}</span>
                        </div>
                        <div class="debug-chunk-text">${text}...</div>
                    </div>
                `;
            })
            .join("");

        return `
            <details class="debug-accordion">
                <summary>Inspect Retrieved Context Chunks (${chunks.length})</summary>
                <div class="debug-chunks-list">${chunkCards}</div>
            </details>
        `;
    }

    function formatMarkdown(text) {
        if (!text) return "";

        // Check if there are SVG diagram blocks to preserve
        const svgBlocks = [];
        let sanitizedText = text.replace(/<svg[\s\S]*?<\/svg>/gi, (match) => {
            const placeholder = `%%SVG_BLOCK_${svgBlocks.length}%%`;
            svgBlocks.push(match);
            return placeholder;
        });

        if (window.marked) {
            let html = marked.parse(sanitizedText);

            // Add custom code headers with copy button
            html = html.replace(/<pre><code class="language-([^"]+)">([\s\S]*?)<\/code><\/pre>/g, (match, lang, code) => {
                return `
                    <pre>
                        <div class="code-header">
                            <span>${lang}</span>
                            <button class="code-copy-btn" type="button">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                                Copy
                            </button>
                        </div>
                        <code class="hljs language-${lang}">${code}</code>
                    </pre>
                `;
            });

            // Restore SVG diagram blocks
            svgBlocks.forEach((svg, idx) => {
                const placeholder = `%%SVG_BLOCK_${idx}%%`;
                html = html.replace(placeholder, `<div class="svg-diagram-container">${svg}</div>`);
            });

            return html;
        }

        return escapeHtml(text).replace(/\n/g, "<br>");
    }


    async function sendMessage() {
        const query = elements.chatTextarea.value.trim();
        if (!query || state.isGenerating) return;

        // Render user message
        renderMessage("user", query);
        elements.chatTextarea.value = "";
        autoResizeTextarea();
        toggleSendButton();
        scrollToBottom();

        // Assistant skeleton message
        setGeneratingState(true);
        const assistantWrapper = renderMessage("assistant", "", [], {}, true);
        const markdownBody = assistantWrapper.querySelector(".markdown-content");
        markdownBody.innerHTML = '<span class="history-skeleton">Searching study materials and thinking...</span>';

        state.abortController = new AbortController();
        let streamTokens = "";
        let retrievedChunks = [];
        let sources = [];

        try {
            const response = await fetch("/api/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: query,
                    conversation_id: state.currentConvId,
                    top_k: state.topK,
                    min_similarity: state.minSimilarity,
                    model: state.activeModel,
                }),
                signal: state.abortController.signal,
            });

            if (!response.ok) throw new Error(`HTTP error ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let partialBuffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                partialBuffer += decoder.decode(value, { stream: true });
                const lines = partialBuffer.split("\n");
                partialBuffer = lines.pop(); // keep trailing partial line

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const jsonStr = line.slice(6).trim();
                    if (!jsonStr) continue;

                    try {
                        const event = JSON.parse(jsonStr);

                        if (event.event === "conversation_id") {
                            state.currentConvId = event.conversation_id;
                            if (event.title && elements.currentChatTitle) {
                                elements.currentChatTitle.textContent = event.title;
                            }
                        } else if (event.event === "retrieval") {
                            retrievedChunks = event.retrieved_chunks || [];
                            sources = event.sources || [];
                        } else if (event.event === "token") {
                            streamTokens += event.token;
                            markdownBody.innerHTML = formatMarkdown(streamTokens);
                            scrollToBottom();
                        } else if (event.event === "done") {
                            sources = event.sources || sources;
                            streamTokens = event.answer || streamTokens;
                            markdownBody.innerHTML = formatMarkdown(streamTokens);

                            // Append sources and debug elements
                            const bodyEl = assistantWrapper.querySelector(".message-body");
                            if (sources.length > 0) {
                                const sourcesDiv = document.createElement("div");
                                sourcesDiv.innerHTML = renderSourcesHtml(sources);
                                bodyEl.appendChild(sourcesDiv);
                            }
                            if (state.debugMode && retrievedChunks.length > 0) {
                                const debugDiv = document.createElement("div");
                                debugDiv.innerHTML = renderDebugHtml(retrievedChunks);
                                bodyEl.appendChild(debugDiv);
                            }
                        }
                    } catch (err) {
                        console.debug("JSON SSE parse chunk:", err);
                    }
                }
            }

            // Refresh conversations list to show updated titles
            await loadConversations();
        } catch (e) {
            if (e.name === "AbortError") {
                markdownBody.innerHTML += '<br><em style="color:var(--text-muted);">[Generation stopped by user]</em>';
            } else {
                markdownBody.innerHTML = `<span style="color:var(--accent-error);">⚠️ Error: ${e.message || "Failed to communicate with local assistant"}</span>`;
            }
        } finally {
            setGeneratingState(false);
            scrollToBottom();
        }
    }

    function setGeneratingState(isGen) {
        state.isGenerating = isGen;
        if (isGen) {
            elements.sendMessageBtn?.classList.add("hidden");
            elements.stopGenerationBtn?.classList.remove("hidden");
        } else {
            elements.sendMessageBtn?.classList.remove("hidden");
            elements.stopGenerationBtn?.classList.add("hidden");
        }
        toggleSendButton();
    }

    function stopGeneration() {
        if (state.abortController) {
            state.abortController.abort();
            setGeneratingState(false);
        }
    }

    function scrollToBottom() {
        elements.chatMessagesContainer.scrollTop = elements.chatMessagesContainer.scrollHeight;
    }

    // Documents Management Modal Logic
    async function loadDocumentsList() {
        try {
            const res = await fetch("/api/documents");
            if (!res.ok) return;
            const data = await res.json();
            renderDocumentsModalList(data.documents || []);
            if (elements.docCounter) elements.docCounter.textContent = (data.documents || []).length;
            if (elements.modalDocCount) elements.modalDocCount.textContent = (data.documents || []).length;
        } catch (e) {
            console.error("Error loading documents:", e);
        }
    }

    function renderDocumentsModalList(docs) {
        if (!elements.modalDocsList) return;
        elements.modalDocsList.innerHTML = "";

        if (docs.length === 0) {
            elements.modalDocsList.innerHTML = '<div class="docs-empty-state">No study documents indexed yet. Upload a PDF above.</div>';
            return;
        }

        docs.forEach((doc) => {
            const item = document.createElement("div");
            item.className = "modal-doc-item";
            item.innerHTML = `
                <div class="modal-doc-info">
                    <strong>📄 ${escapeHtml(doc.filename)}</strong>
                    <span>${doc.pages_count || 0} pages · ${doc.chunks_count || 0} chunks · Added: ${escapeHtml(doc.indexed_at || "Recent")}</span>
                </div>
                <button class="modal-doc-delete-btn" title="Delete document">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
            `;

            item.querySelector(".modal-doc-delete-btn")?.addEventListener("click", () => {
                deleteDocument(doc.filename);
            });

            elements.modalDocsList.appendChild(item);
        });
    }

    async function handleFileUpload(files) {
        if (!files || files.length === 0) return;

        elements.uploadProgressContainer?.classList.remove("hidden");
        elements.uploadProgressBar.style.width = "20%";
        elements.uploadProgressText.textContent = "Uploading study materials...";

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (!file.name.toLowerCase().endsWith(".pdf")) {
                alert(`File '${file.name}' is not a PDF.`);
                continue;
            }

            const formData = new FormData();
            formData.append("file", file);

            try {
                elements.uploadProgressBar.style.width = "50%";
                elements.uploadProgressText.textContent = `Extracting & chunking '${file.name}' (~3 chunks/page)...`;

                const res = await fetch("/upload", {
                    method: "POST",
                    body: formData,
                });

                elements.uploadProgressBar.style.width = "90%";
                const data = await res.json();

                if (!res.ok) {
                    alert(`Error processing ${file.name}: ${data.error || 'Ingestion failed'}`);
                }
            } catch (e) {
                alert(`Network error uploading ${file.name}: ${e.message}`);
            }
        }

        elements.uploadProgressBar.style.width = "100%";
        elements.uploadProgressText.textContent = "All documents successfully processed and indexed!";
        setTimeout(() => {
            elements.uploadProgressContainer?.classList.add("hidden");
            elements.uploadProgressBar.style.width = "0%";
        }, 2000);

        await loadDocumentsList();
        await fetchSystemStatus();
    }

    async function deleteDocument(filename) {
        if (!confirm(`Remove '${filename}' and its chunk vectors from index?`)) return;
        try {
            const res = await fetch(`/api/documents/${encodeURIComponent(filename)}`, {
                method: "DELETE",
            });
            if (res.ok) {
                await loadDocumentsList();
                await fetchSystemStatus();
            }
        } catch (e) {
            console.error("Error deleting document:", e);
        }
    }

    // Settings Modal
    function openSettings() {
        if (elements.settingTopK) elements.settingTopK.value = state.topK;
        if (elements.valTopK) elements.valTopK.textContent = state.topK;
        if (elements.settingMinSim) elements.settingMinSim.value = state.minSimilarity;
        if (elements.valMinSim) elements.valMinSim.textContent = state.minSimilarity;
        if (elements.settingTheme) elements.settingTheme.value = state.theme;
        if (elements.settingDebug) elements.settingDebug.checked = state.debugMode;
        fetchSystemStatus();
    }

    async function saveSettings() {
        state.topK = parseInt(elements.settingTopK.value, 10);
        state.minSimilarity = parseFloat(elements.settingMinSim.value);
        state.theme = elements.settingTheme.value;
        state.debugMode = elements.settingDebug.checked;
        state.activeModel = elements.settingModel.value;

        // Apply theme
        document.documentElement.setAttribute("data-theme", state.theme);
        localStorage.setItem("studyrag_theme", state.theme);

        try {
            await fetch("/api/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    top_k: state.topK,
                    min_similarity: state.minSimilarity,
                    model: state.activeModel,
                }),
            });
        } catch (e) {
            console.warn("Could not persist runtime settings to server:", e);
        }

        closeModal(elements.settingsModal);
    }

    // Utility: HTML Escape
    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Launch App
    initApp();
});
