/**
 * StudyRAG V2.2 — Modern Local Academic Assistant with Visual Learning Engine
 */

document.addEventListener("DOMContentLoaded", () => {
    // App State
    const state = {
        currentConvId: null,
        conversations: [],
        activeModel: "qwen3:1.7b",
        topK: 4,
        minSimilarity: 0.25,
        debugMode: false,
        diagramMode: false,
        theme: localStorage.getItem("studyrag_theme") || "dark",
        isGenerating: false,
        abortController: null,
        modalZoomLevel: 1.0,
        activeModalSvg: "",
        activeModalTitle: "Diagram",
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
        diagramModeBtn: document.getElementById("diagram-mode-btn"),
        inputModeIndicator: document.getElementById("input-mode-indicator"),

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
        statusVisualPill: document.getElementById("status-visual-pill"),
        statusMongoPill: document.getElementById("status-mongo-pill"),
        statusVectorsCount: document.getElementById("status-vectors-count"),

        // Diagram Modal Lightbox
        diagramModal: document.getElementById("diagram-modal"),
        diagramModalTitle: document.getElementById("diagram-modal-title"),
        diagramModalContent: document.getElementById("diagram-modal-content"),
        diagramModalZoomIn: document.getElementById("diagram-modal-zoom-in"),
        diagramModalZoomOut: document.getElementById("diagram-modal-zoom-out"),
        diagramModalReset: document.getElementById("diagram-modal-reset"),
        diagramModalDownloadSvg: document.getElementById("diagram-modal-download-svg"),
        diagramModalDownloadPng: document.getElementById("diagram-modal-download-png"),
        diagramModalClose: document.getElementById("diagram-modal-close"),
    };

    // Configure Marked.js renderer
    if (window.marked) {
        marked.setOptions({
            breaks: true,
            gfm: true,
            highlight: function (code, lang) {
                if (lang === "mermaid") return code; // Let Mermaid render it
                if (window.hljs && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {}
                }
                return window.hljs ? hljs.highlightAuto(code).value : code;
            },
        });
    }

    // Initialize Mermaid.js with strict security mode
    function initMermaid() {
        if (window.mermaid) {
            try {
                mermaid.initialize({
                    startOnLoad: false,
                    theme: state.theme === "dark" ? "dark" : "default",
                    securityLevel: "strict",
                    fontFamily: "Plus Jakarta Sans, sans-serif",
                    flowchart: { htmlLabels: false, curve: "basis" },
                    sequence: { showSequenceNumbers: false },
                    state: { defaultRenderer: "dagre-d3" },
                });
            } catch (e) {
                console.warn("Mermaid init:", e);
            }
        }
    }

    // Initialize Application
    async function initApp() {
        initMermaid();
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

        // Diagram Mode Toggle
        elements.diagramModeBtn?.addEventListener("click", () => {
            state.diagramMode = !state.diagramMode;
            elements.diagramModeBtn.classList.toggle("active", state.diagramMode);
            if (elements.inputModeIndicator) {
                elements.inputModeIndicator.textContent = state.diagramMode
                    ? "📊 Diagram Generation Mode Active: prompts will generate structured architectural diagrams."
                    : "100% Offline AI · Grounded in study materials · Local Mermaid diagrams";
            }
            elements.chatTextarea.placeholder = state.diagramMode
                ? "Describe the diagram you want to generate (e.g. 'TCP Handshake', 'OS Process States')..."
                : "Ask anything about your study materials or request diagrams...";
            elements.chatTextarea.focus();
        });

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

        // Diagram Modal Lightbox Controls
        elements.diagramModalClose?.addEventListener("click", () => {
            elements.diagramModal.classList.add("hidden");
        });
        elements.diagramModalZoomIn?.addEventListener("click", () => {
            state.modalZoomLevel = Math.min(state.modalZoomLevel + 0.25, 3.0);
            updateModalZoom();
        });
        elements.diagramModalZoomOut?.addEventListener("click", () => {
            state.modalZoomLevel = Math.max(state.modalZoomLevel - 0.25, 0.5);
            updateModalZoom();
        });
        elements.diagramModalReset?.addEventListener("click", () => {
            state.modalZoomLevel = 1.0;
            updateModalZoom();
        });
        elements.diagramModalDownloadSvg?.addEventListener("click", () => {
            downloadSvgDirect(state.activeModalSvg, `${state.activeModalTitle.replace(/\s+/g, '_')}.svg`);
        });
        elements.diagramModalDownloadPng?.addEventListener("click", () => {
            downloadPngDirect(state.activeModalSvg, `${state.activeModalTitle.replace(/\s+/g, '_')}.png`);
        });

        // Backdrop click close
        [elements.docsModal, elements.settingsModal, elements.diagramModal].forEach((modal) => {
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

    function updateModalZoom() {
        const svgEl = elements.diagramModalContent?.querySelector("svg");
        if (svgEl) {
            svgEl.style.transform = `scale(${state.modalZoomLevel})`;
        }
    }

    // Fetch System Health & Config
    async function fetchSystemStatus() {
        try {
            const res = await fetch("/api/status");
            if (!res.ok) throw new Error("Status check failed");
            const data = await res.json();

            state.activeModel = data.ollama_model || "qwen3:1.7b";
            state.topK = data.top_k || 4;
            state.minSimilarity = data.min_similarity || 0.25;

            // Update UI indicators
            if (elements.activeModelName) elements.activeModelName.textContent = state.activeModel;
            if (elements.docCounter) elements.docCounter.textContent = Object.keys(data.indexed_documents || {}).length;
            if (elements.modalDocCount) elements.modalDocCount.textContent = Object.keys(data.indexed_documents || {}).length;
            if (elements.statusVectorsCount) elements.statusVectorsCount.textContent = `${data.total_vectors || 0} Vectors`;

            const ollamaOk = data.ollama_available;
            const mongoOk = data.mongodb_available !== false;
            const visualOk = data.visual_learning_enabled !== false;

            if (elements.statusOllamaPill) {
                elements.statusOllamaPill.textContent = ollamaOk ? "Online" : "Offline";
                elements.statusOllamaPill.className = `status-pill ${ollamaOk ? "online" : "offline"}`;
            }

            if (elements.statusVisualPill) {
                elements.statusVisualPill.textContent = visualOk ? "Ready (Local Mermaid)" : "Disabled";
                elements.statusVisualPill.className = `status-pill ${visualOk ? "online" : "offline"}`;
            }

            if (elements.statusMongoPill) {
                elements.statusMongoPill.textContent = mongoOk ? "Connected" : "Disconnected (Volatile)";
                elements.statusMongoPill.className = `status-pill ${mongoOk ? "online" : "offline"}`;
            }

            if (elements.globalStatusDot && elements.globalStatusLabel) {
                if (ollamaOk && visualOk) {
                    elements.globalStatusDot.className = "status-dot online";
                    elements.globalStatusLabel.textContent = "Ollama & Visual Ready";
                } else if (ollamaOk) {
                    elements.globalStatusDot.className = "status-dot online";
                    elements.globalStatusLabel.textContent = "Ollama Online";
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

                item.addEventListener("click", (e) => {
                    if (e.target.closest(".delete-conv")) return;
                    openConversation(conv.conversation_id);
                });

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
                for (const msg of messages) {
                    await renderMessage(msg.role, msg.content, msg.sources, msg.metadata, false);
                }
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

    // Helper: Determine if query is requesting a diagram
    function isDiagramQuery(query) {
        if (state.diagramMode) return true;
        const q = query.trim().toLowerCase();
        const diagramKeywords = [
            "diagram", "draw", "flowchart", "state diagram", "sequence diagram",
            "architecture diagram", "class diagram", "er diagram", "visualize", "illustrate",
            "show diagram", "create a diagram", "generate diagram", "state transition",
            "handshake diagram", "scheduling diagram"
        ];
        return diagramKeywords.some((kw) => q.includes(kw));
    }

    // Helper: Normalize Mermaid diagram code (strip fences, unescape newlines)
    function normalizeMermaidCode(code) {
        if (!code || typeof code !== "string") return "";
        let clean = code.trim();
        // Remove markdown code fences if present
        clean = clean.replace(/^```(?:mermaid|json|text)?\s*\n?/i, "");
        clean = clean.replace(/\n?```\s*$/i, "");
        // If the code has literal \\n instead of real newlines, unescape them
        if (clean.includes("\\n") && (!clean.includes("\n") || clean.split("\\n").length > clean.split("\n").length)) {
            try {
                clean = clean.replace(/\\n/g, "\n").replace(/\\t/g, "\t").replace(/\\"/g, '"');
            } catch (e) {}
        }
        return clean.trim();
    }

    // Helper: Sanitize explanation text to never expose raw JSON strings to users
    function sanitizeDiagramExplanation(text) {
        if (!text || typeof text !== "string") return "";
        const trimmed = text.trim();
        if (trimmed.startsWith("{") && (trimmed.includes('"mermaid"') || trimmed.includes('"title"') || trimmed.includes('"explanation"'))) {
            try {
                const parsed = JSON.parse(trimmed);
                return parsed.explanation || "";
            } catch (e) {
                const match = trimmed.match(/"explanation"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"/);
                if (match) {
                    try {
                        return JSON.parse(`"${match[1]}"`);
                    } catch (err) {
                        return match[1].replace(/\\n/g, "\n").replace(/\\"/g, '"');
                    }
                }
                return "";
            }
        }
        return text;
    }

    // Render Mermaid Diagram block inside an element
    async function renderMermaidInElement(container, mermaidCode, uniqueId) {
        if (!container) return null;

        if (!window.mermaid) {
            container.innerHTML = `
                <div style="color:var(--accent-warning);font-size:12px;padding:12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-card);">
                    ⚠️ Mermaid library is not available. Ensure offline vendor scripts are loaded.
                </div>
            `;
            return null;
        }

        const cleanCode = normalizeMermaidCode(mermaidCode);
        if (!cleanCode) {
            container.innerHTML = `
                <div style="color:var(--accent-warning);font-size:12px;padding:12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-card);">
                    ⚠️ Diagram definition is empty or could not be generated.
                </div>
            `;
            return null;
        }

        try {
            const safePrefix = (uniqueId || Math.random().toString(36).substring(2, 9)).replace(/[^a-zA-Z0-9_]/g, "_");
            const renderId = `mermaid_${safePrefix}_${Math.random().toString(36).substring(2, 7)}`;
            const { svg } = await mermaid.render(renderId, cleanCode);
            container.innerHTML = svg;
            return svg;
        } catch (err) {
            console.warn("Mermaid rendering error:", err);
            // Clean up any stray error SVG elements that Mermaid may have appended to document body
            try {
                document.querySelectorAll(`[id^="dmermaid_"]`).forEach((el) => el.remove());
            } catch (e) {}

            container.innerHTML = `
                <div style="color:var(--accent-warning);font-size:12px;padding:12px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-card);">
                    <div style="font-weight:600;margin-bottom:4px;">⚠️ Diagram syntax could not be rendered visually:</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">${escapeHtml(err.message || "Syntax error detected in generated Mermaid definition.")}</div>
                    <details style="margin-top:6px;">
                        <summary style="cursor:pointer;font-size:11px;color:var(--accent-primary);outline:none;">View Diagram Source</summary>
                        <pre style="margin-top:6px;background:var(--bg-app);padding:8px;border-radius:4px;font-size:11px;overflow-x:auto;white-space:pre-wrap;">${escapeHtml(cleanCode)}</pre>
                    </details>
                </div>
            `;
            return null;
        }
    }

    // Render Diagram Card component
    async function renderDiagramCard(artifact, parentEl) {
        const uniqueId = `diag_${artifact.artifact_id || Math.random().toString(36).substring(2, 9)}`;
        const card = document.createElement("div");
        card.className = "diagram-card";

        const isGrounded = artifact.grounding_status === "grounded";
        const groundingLabel = isGrounded ? "📄 Grounded in Study Material" : "🌐 General Academic Knowledge";
        const groundingClass = isGrounded ? "grounded" : "general_knowledge";
        const rawMermaid = artifact.mermaid_code || artifact.mermaid || "";
        const cleanExplanation = sanitizeDiagramExplanation(artifact.explanation || "");

        card.innerHTML = `
            <div class="diagram-header">
                <div class="diagram-title-group">
                    <span class="diagram-title">${escapeHtml(artifact.title || "Educational Diagram")}</span>
                    <span class="diagram-type-tag">${escapeHtml(artifact.diagram_type || "flowchart")}</span>
                </div>
                <div class="diagram-badges-group">
                    <span class="grounding-badge ${groundingClass}">${groundingLabel}</span>
                </div>
            </div>
            <div class="diagram-viewport" id="${uniqueId}_viewport">
                <div class="history-skeleton">Rendering diagram...</div>
            </div>
            <div class="diagram-actions-bar">
                <div class="diagram-btn-group">
                    <button class="btn-diagram-action export-svg-btn" title="Download SVG Vector Graphic">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg> SVG
                    </button>
                    <button class="btn-diagram-action export-png-btn" title="Download PNG Image">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg> PNG
                    </button>
                    <button class="btn-diagram-action copy-mermaid-btn" title="Copy Mermaid Definition">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy Code
                    </button>
                </div>
                <div class="diagram-btn-group">
                    <button class="btn-diagram-action fullscreen-btn" title="View in Fullscreen Lightbox">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg> Fullscreen
                    </button>
                </div>
            </div>
            ${cleanExplanation ? `<div class="diagram-explanation">${formatMarkdown(cleanExplanation)}</div>` : ""}
            ${renderSourcesHtml(artifact.source_references)}
        `;

        parentEl.appendChild(card);

        // Render Mermaid SVG
        const viewport = card.querySelector(`#${uniqueId}_viewport`);
        const renderedSvg = await renderMermaidInElement(viewport, rawMermaid, uniqueId);

        // Action Buttons Logic
        const svgBtn = card.querySelector(".export-svg-btn");
        const pngBtn = card.querySelector(".export-png-btn");
        const copyBtn = card.querySelector(".copy-mermaid-btn");
        const fullBtn = card.querySelector(".fullscreen-btn");

        svgBtn?.addEventListener("click", () => {
            const svgContent = viewport.querySelector("svg")?.outerHTML || renderedSvg;
            if (svgContent) {
                // Save to server for export tracking
                if (artifact.artifact_id) {
                    fetch("/api/visualize/export/svg", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ artifact_id: artifact.artifact_id, svg: svgContent }),
                    }).catch(() => {});
                }

                downloadSvgDirect(svgContent, `${(artifact.title || "diagram").replace(/\s+/g, "_")}.svg`);
            }
        });

        pngBtn?.addEventListener("click", () => {
            const svgContent = viewport.querySelector("svg")?.outerHTML || renderedSvg;
            if (svgContent) {
                downloadPngDirect(svgContent, `${(artifact.title || "diagram").replace(/\s+/g, "_")}.png`);
            }
        });

        copyBtn?.addEventListener("click", () => {
            const codeToCopy = normalizeMermaidCode(rawMermaid);
            navigator.clipboard.writeText(codeToCopy).then(() => {
                copyBtn.textContent = "Copied!";
                setTimeout(() => (copyBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy Code'), 2000);
            });
        });

        fullBtn?.addEventListener("click", () => {
            const svgContent = viewport.querySelector("svg")?.outerHTML || renderedSvg;
            if (svgContent) {
                state.activeModalSvg = svgContent;
                state.activeModalTitle = artifact.title || "Educational Diagram";
                state.modalZoomLevel = 1.0;
                elements.diagramModalTitle.textContent = state.activeModalTitle;
                elements.diagramModalContent.innerHTML = svgContent;
                updateModalZoom();
                openModal(elements.diagramModal);
            }
        });

        return card;
    }

    // Direct SVG & PNG Client-side downloads
    function downloadSvgDirect(svgContent, filename) {
        if (!svgContent) return;
        let formattedSvg = svgContent;
        if (!formattedSvg.includes('xmlns="http://www.w3.org/2000/svg"')) {
            formattedSvg = formattedSvg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
        }
        const blob = new Blob([formattedSvg], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "studyrag_diagram.svg";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function downloadPngDirect(svgContent, filename) {
        if (!svgContent) return;
        let formattedSvg = svgContent;
        if (!formattedSvg.includes('xmlns="http://www.w3.org/2000/svg"')) {
            formattedSvg = formattedSvg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
        }
        const img = new Image();
        const svgBlob = new Blob([formattedSvg], { type: "image/svg+xml;charset=utf-8" });
        const url = URL.createObjectURL(svgBlob);

        img.onload = () => {
            try {
                const canvas = document.createElement("canvas");
                const scale = 2; // 2x high-DPI scaling
                canvas.width = (img.naturalWidth || img.width || 800) * scale;
                canvas.height = (img.naturalHeight || img.height || 600) * scale;
                const ctx = canvas.getContext("2d");
                ctx.fillStyle = state.theme === "dark" ? "#181b24" : "#ffffff";
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

                canvas.toBlob((blob) => {
                    if (!blob) return;
                    const pngUrl = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = pngUrl;
                    a.download = filename || "studyrag_diagram.png";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(pngUrl);
                }, "image/png");
            } catch (err) {
                console.error("PNG export error:", err);
            } finally {
                URL.revokeObjectURL(url);
            }
        };

        img.onerror = (err) => {
            console.error("Failed to load SVG for PNG conversion:", err);
            URL.revokeObjectURL(url);
        };

        img.src = url;
    }

    // Message Rendering & Sending
    async function renderMessage(role, content, sources = [], metadata = {}, animate = true) {
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
            elements.messagesList.appendChild(wrapper);

            // If message contains mermaid code blocks, render them
            const mermaidBlocks = wrapper.querySelectorAll("code.language-mermaid");
            for (const codeEl of mermaidBlocks) {
                const pre = codeEl.closest("pre");
                if (pre) {
                    const mermaidCode = codeEl.textContent;
                    const container = document.createElement("div");
                    container.className = "diagram-viewport";
                    pre.replaceWith(container);
                    await renderMermaidInElement(container, mermaidCode);
                }
            }
        } else {
            wrapper.innerHTML = `
                <div class="message-body">
                    ${escapeHtml(content)}
                </div>
            `;
            elements.messagesList.appendChild(wrapper);
        }

        // Attach copy button handlers for standard code blocks
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

        // Preserve SVG blocks
        const svgBlocks = [];
        let sanitizedText = text.replace(/<svg[\s\S]*?<\/svg>/gi, (match) => {
            const placeholder = `%%SVG_BLOCK_${svgBlocks.length}%%`;
            svgBlocks.push(match);
            return placeholder;
        });

        if (window.marked) {
            let html = marked.parse(sanitizedText);

            html = html.replace(/<pre><code class="language-([^"]+)">([\s\S]*?)<\/code><\/pre>/g, (match, lang, code) => {
                if (lang === "mermaid") return match;
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

        // Check if diagram workflow is triggered
        if (isDiagramQuery(query)) {
            await handleDiagramGeneration(query);
            return;
        }

        // Standard text streaming workflow
        await handleStreamingChat(query);
    }

    // Handle dedicated visual diagram generation
    async function handleDiagramGeneration(query) {
        setGeneratingState(true);
        const assistantWrapper = document.createElement("div");
        assistantWrapper.className = "message-wrapper assistant";
        assistantWrapper.innerHTML = `
            <div class="message-avatar">📊</div>
            <div class="message-body">
                <div class="history-skeleton">Searching study materials & generating technical diagram...</div>
            </div>
        `;
        elements.messagesList.appendChild(assistantWrapper);
        scrollToBottom();

        try {
            const res = await fetch("/api/visualize", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    question: query,
                    conversation_id: state.currentConvId,
                    top_k: state.topK,
                    min_similarity: state.minSimilarity,
                    model: state.activeModel,
                }),
            });

            const data = await res.json();
            const messageBody = assistantWrapper.querySelector(".message-body");
            messageBody.innerHTML = "";

            if (!res.ok || data.error) {
                messageBody.innerHTML = `<span style="color:var(--accent-error);">⚠️ Diagram generation error: ${escapeHtml(data.error || "Failed to generate diagram")}</span>`;
            } else {
                await renderDiagramCard(data, messageBody);
            }

            await loadConversations();
        } catch (e) {
            console.error("Visual generation error:", e);
            const messageBody = assistantWrapper.querySelector(".message-body");
            messageBody.innerHTML = `<span style="color:var(--accent-error);">⚠️ Error communicating with visual learning engine: ${escapeHtml(e.message)}</span>`;
        } finally {
            setGeneratingState(false);
            scrollToBottom();
        }
    }

    // Handle standard text chat stream
    async function handleStreamingChat(query) {
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
                partialBuffer = lines.pop();

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

                            // Append sources and debug
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

                            // Render any embedded Mermaid diagrams
                            const mermaidBlocks = bodyEl.querySelectorAll("code.language-mermaid");
                            for (const codeEl of mermaidBlocks) {
                                const pre = codeEl.closest("pre");
                                if (pre) {
                                    const mCode = codeEl.textContent;
                                    const container = document.createElement("div");
                                    container.className = "diagram-viewport";
                                    pre.replaceWith(container);
                                    await renderMermaidInElement(container, mCode);
                                }
                            }
                        }
                    } catch (err) {
                        console.debug("SSE json chunk parse:", err);
                    }
                }
            }

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

        // Apply theme and re-init Mermaid theme
        document.documentElement.setAttribute("data-theme", state.theme);
        localStorage.setItem("studyrag_theme", state.theme);
        initMermaid();

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
