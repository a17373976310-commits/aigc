document.addEventListener('DOMContentLoaded', () => {
    const promptInput = document.getElementById('promptInput');
    const generateBtn = document.getElementById('generateBtn');
    const imageContainer = document.getElementById('imageContainer');
    const generatedImage = document.getElementById('generatedImage');
    const emptyContent = document.querySelector('.empty-content');
    const modelSelect = document.getElementById('modelSelect');
    const refImageInput = document.getElementById('refImageInput');
    const uploadBox = document.getElementById('uploadBox');

    // State
    let currentRatio = '1:1';
    let selectedFiles = [];
    let currentScenario = 'free'; // Track current scenario

    // --- Settings / API Key Logic ---
    const settingsModal = document.getElementById('settingsModal');
    const apiKeyInput = document.getElementById('apiKeyInput');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const settingsBtn = document.querySelector('.header-controls button:nth-child(2)'); // Assuming it's the second button

    // Load API Key
    const savedKey = localStorage.getItem('gemini_api_key');
    if (savedKey) {
        apiKeyInput.value = savedKey;
    }

    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            settingsModal.classList.remove('hidden');
        });
    }

    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('hidden');
        });
    }

    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', () => {
            const key = apiKeyInput.value.trim();
            if (key) {
                localStorage.setItem('gemini_api_key', key);
                alert('API Key saved!');
                settingsModal.classList.add('hidden');
            } else {
                localStorage.removeItem('gemini_api_key');
                alert('API Key removed.');
            }
        });
    }

    function getApiKey() {
        return localStorage.getItem('gemini_api_key') || '';
    }

    function getHeaders(contentType = null) {
        const headers = {};
        const key = getApiKey();
        if (key) headers['X-API-Key'] = key;
        if (contentType) headers['Content-Type'] = contentType;
        return headers;
    }

    // Scenario selector
    const scenarioSelect = document.getElementById('scenarioSelect');
    const taobaoCopyInput = document.getElementById('taobaoCopyInput');

    // Update scenario when changed
    if (scenarioSelect) {
        scenarioSelect.addEventListener('change', (e) => {
            currentScenario = e.target.value;
            console.log('[Scenario Changed]', currentScenario);

            // Show/hide Taobao copy input
            const taobaoCopyGroup = document.getElementById('taobaoCopyGroup');
            if (taobaoCopyGroup) {
                if (currentScenario === 'taobao') {
                    taobaoCopyGroup.classList.remove('hidden');
                } else {
                    taobaoCopyGroup.classList.add('hidden');
                }
            }
        });
    }

    // Magic Wand Optimization
    const magicBtn = document.getElementById('magicBtn');
    const optimizedPromptGroup = document.getElementById('optimizedPromptGroup');
    const optimizedPromptInput = document.getElementById('optimizedPromptInput');
    const clearOptimizedBtn = document.getElementById('clearOptimizedBtn');

    if (magicBtn) {
        magicBtn.addEventListener('click', async () => {
            const prompt = promptInput.value.trim();

            if (!prompt && selectedFiles.length === 0) {
                alert('Please enter a prompt or upload an image to optimize.');
                return;
            }

            const originalText = magicBtn.textContent;
            magicBtn.textContent = '✨';
            magicBtn.disabled = true;
            promptInput.disabled = true;

            try {
                let response;

                if (selectedFiles.length > 0) {
                    const formData = new FormData();
                    formData.append('prompt', prompt);
                    formData.append('scenario', (currentScenario === 'commerce') ? 'commerce' : 'free');
                    selectedFiles.forEach(file => {
                        formData.append('image', file);
                    });

                    response = await fetch('/api/optimize-prompt', {
                        method: 'POST',
                        headers: getHeaders(),
                        body: formData
                    });
                } else {
                    response = await fetch('/api/optimize-prompt', {
                        method: 'POST',
                        headers: getHeaders('application/json'),
                        body: JSON.stringify({ prompt, scenario: (currentScenario === 'commerce') ? 'commerce' : 'free' }),
                    });
                }

                const data = await (async () => {
                    const ct = response.headers.get('content-type') || '';
                    if (ct.includes('application/json')) {
                        return response.json();
                    }
                    const text = await response.text();
                    try { return JSON.parse(text); } catch { return { error: text }; }
                })();

                if (!response.ok) {
                    throw new Error(data.error || data.message || 'Failed to optimize prompt');
                }

                if (data.optimized_prompt) {
                    if (optimizedPromptGroup && optimizedPromptInput) {
                        optimizedPromptGroup.classList.remove('hidden');
                        optimizedPromptInput.value = data.optimized_prompt;
                        optimizedPromptInput.style.height = 'auto';
                        optimizedPromptInput.style.height = optimizedPromptInput.scrollHeight + 'px';
                    } else {
                        promptInput.value = data.optimized_prompt;
                    }
                }

            } catch (error) {
                console.error('Optimization Error:', error);
                alert(`Failed to optimize prompt: ${error.message}`);
            } finally {
                magicBtn.textContent = originalText;
                magicBtn.disabled = false;
                promptInput.disabled = false;
            }
        });
    }

    if (clearOptimizedBtn) {
        clearOptimizedBtn.addEventListener('click', () => {
            optimizedPromptInput.value = '';
            optimizedPromptGroup.classList.add('hidden');
        });
    }

    // Auto-clear optimized prompt when user edits the main prompt
    promptInput.addEventListener('input', () => {
        if (optimizedPromptGroup && !optimizedPromptGroup.classList.contains('hidden')) {
            optimizedPromptGroup.classList.add('hidden');
            optimizedPromptInput.value = '';
        }
    });

    uploadBox.addEventListener('click', (e) => {
        if (e.target.tagName !== 'IMG' && !e.target.classList.contains('delete-preview-btn')) {
            refImageInput.click();
        }
    });

    refImageInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            const newFiles = Array.from(e.target.files);
            selectedFiles = [...selectedFiles, ...newFiles];

            const placeholders = uploadBox.querySelectorAll('.upload-content');
            placeholders.forEach(el => el.remove());

            renderImagePreviews();
        }
    });

    function renderImagePreviews() {
        const existingPreviews = uploadBox.querySelectorAll('.preview-thumb-wrapper');
        existingPreviews.forEach(el => el.remove());

        selectedFiles.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const wrapper = document.createElement('div');
                wrapper.className = 'preview-thumb-wrapper';
                wrapper.dataset.index = index;

                const img = document.createElement('img');
                img.src = e.target.result;
                img.className = 'preview-thumb';

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-preview-btn';
                deleteBtn.textContent = '×';
                deleteBtn.onclick = (e) => {
                    e.stopPropagation();
                    removeImage(index);
                };

                wrapper.appendChild(img);
                wrapper.appendChild(deleteBtn);
                uploadBox.appendChild(wrapper);
            }
            reader.readAsDataURL(file);
        });

        if (selectedFiles.length === 0) {
            const placeholder = document.createElement('div');
            placeholder.className = 'upload-content';
            placeholder.innerHTML = `
                <span class="plus-icon">+</span>
                <span>Add Reference Image</span>
            `;
            uploadBox.appendChild(placeholder);
        }
    }

    function removeImage(index) {
        selectedFiles.splice(index, 1);
        renderImagePreviews();
    }

    document.querySelectorAll('.ratio-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.ratio-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentRatio = btn.dataset.ratio;
        });
    });

    // Generate Action
    generateBtn.addEventListener('click', async () => {
        let prompt = promptInput.value.trim();
        if (optimizedPromptInput && !optimizedPromptGroup.classList.contains('hidden') && optimizedPromptInput.value.trim()) {
            prompt = optimizedPromptInput.value.trim();
        }

        const model = modelSelect.value;

        if (!prompt) {
            alert('Please enter a prompt first.');
            return;
        }

        console.log('[Generate] Scenario:', currentScenario, 'Prompt:', prompt);

        setLoading(true);

        try {
            // Route: only free and commerce
            if (currentScenario === 'commerce') {
                await handleCommerceGeneration(prompt, model);
            } else {
                await handleFreeGeneration(prompt, model);
            }

        } catch (error) {
            console.error('[Generate Error]', error);
            alert(`Error: ${error.message}`);
            setLoading(false);
        }
    });

    // Free Mode Generation (standard)
    async function handleFreeGeneration(prompt, model) {
        console.log('[Free Mode] Generating...');

        let response;

        const formData = new FormData();
        formData.append('prompt', prompt);
        formData.append('model', model);
        formData.append('ratio', currentRatio);

        if (selectedFiles.length > 0) {
            selectedFiles.forEach(file => {
                formData.append('image', file);
            });
        }

        response = await fetch('/api/generate', {
            method: 'POST',
            headers: getHeaders(),
            body: formData
        });

        const data = await (async () => {
            const ct = response.headers.get('content-type') || '';
            if (ct.includes('application/json')) {
                return response.json();
            }
            const text = await response.text();
            try { return JSON.parse(text); } catch { return { error: text }; }
        })();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate image');
        }

        displayGeneratedImage(data.image_path || data.image_url, data.image_url);
    }

    // Taobao Mode - A-V-A Workflow
    async function handleCommerceGeneration(prompt, model) {
        console.log('[Commerce] Optimizing...');
        let optimizedPrompt = prompt;

        try {
            let optResponse;
            if (selectedFiles.length > 0) {
                const optForm = new FormData();
                optForm.append('prompt', prompt);
                optForm.append('scenario', 'commerce');
                selectedFiles.forEach(file => optForm.append('image', file));
                optResponse = await fetch('/api/optimize-prompt', { method: 'POST', headers: getHeaders(), body: optForm });
            } else {
                optResponse = await fetch('/api/optimize-prompt', {
                    method: 'POST',
                    headers: getHeaders('application/json'),
                    body: JSON.stringify({ prompt, scenario: 'commerce' })
                });
            }

            const optData = await (async () => {
                const ct = optResponse.headers.get('content-type') || '';
                if (ct.includes('application/json')) return optResponse.json();
                const text = await optResponse.text();
                try { return JSON.parse(text); } catch { return { error: text }; }
            })();

            if (!optResponse.ok) {
                console.warn('[Commerce] Optimize failed:', optData && (optData.error || optData.message));
                alert('优化提示词失败：' + (optData && (optData.error || optData.message || '未知错误')));
            }

            if (optData && optData.optimized_prompt) {
                optimizedPrompt = optData.optimized_prompt;
                if (optimizedPromptGroup && optimizedPromptInput) {
                    optimizedPromptGroup.classList.remove('hidden');
                    optimizedPromptInput.value = optimizedPrompt;
                    optimizedPromptInput.style.height = 'auto';
                    optimizedPromptInput.style.height = optimizedPromptInput.scrollHeight + 'px';
                }
            }
        } catch (e) {
            console.error('[Commerce] Optimize exception', e);
        }

        console.log('[Commerce] Generating...');
        const genForm = new FormData();
        genForm.append('scenario', 'commerce');
        genForm.append('prompt', optimizedPrompt);
        genForm.append('optimized_prompt', optimizedPrompt);
        genForm.append('model', model);
        genForm.append('ratio', currentRatio);
        if (selectedFiles.length > 0) {
            selectedFiles.forEach(file => genForm.append('image', file));
        }
        const response = await fetch('/api/generate-ecommerce', { method: 'POST', headers: getHeaders(), body: genForm });
        const data = await (async () => {
            const ct = response.headers.get('content-type') || '';
            if (ct.includes('application/json')) return response.json();
            const text = await response.text();
            try { return JSON.parse(text); } catch { return { error: text }; }
        })();
        if (!response.ok) throw new Error(data.error || 'Failed to generate commerce image');
        if (data.style_id) applyTheme(data.style_id);
        if (data.layout) renderTextOverlay(data.layout);
        displayGeneratedImage(data.image_path || data.image_url, data.image_url);
        setLoading(false);
    }

    function applyTheme(styleId) {
        console.log('[Theme] Applying style:', styleId);
        const themeClass = `theme-${styleId}`;

        // Remove existing theme classes
        document.body.classList.forEach(cls => {
            if (cls.startsWith('theme-')) {
                document.body.classList.remove(cls);
            }
        });

        // Add new theme class
        document.body.classList.add(themeClass);
    }

    // Amazon Mode - White Background
    // legacy handlers removed (taobao/amazon/detail)

    // Detail Page Mode - Batch Generation
    async function handleDetailPageGeneration(prompt, model) {
        console.log('[Detail Page Mode] Batch generation not yet implemented');
        alert('Detail Page mode coming soon!');
        setLoading(false);
    }

    let lastImageSources = [];
    // Display generated image
    let currentGenerationId = 0;

    function setLoading(isLoading) {
        if (isLoading) {
            generateBtn.classList.add('loading');
            generateBtn.disabled = true;
        } else {
            generateBtn.classList.remove('loading');
            generateBtn.disabled = false;
        }
    }

    // ... (history code) ...

    // Display generated image
    function displayGeneratedImage(imageUrl, fallbackUrl) {
        // Capture the generation ID at the start of this function call? 
        // No, this function is called WHEN generation finishes.
        // We need to check if the generation that just finished is still relevant?
        // Actually, the issue is that history view clears the loading state.

        lastImageSources = [imageUrl, fallbackUrl].filter(Boolean);

        // We don't rely on onload to clear loading state anymore for the main generation flow
        // to avoid race conditions with history view.
        // But we DO need to wait for image to load to show it?
        // Let's just set src and clear loading immediately, but keep the spinner on the image itself if needed.
        // Or better: ensure setLoading(false) is called explicitly by the generation function, NOT by the image onload.

        generatedImage.onload = null; // Clear any history handlers
        generatedImage.onerror = null;

        generatedImage.src = imageUrl;

        const canvasContainer = document.getElementById('canvasContainer');
        if (canvasContainer) {
            canvasContainer.classList.remove('hidden');
        } else {
            generatedImage.classList.remove('hidden');
        }
        emptyContent.classList.add('hidden');
        imageContainer.classList.remove('empty-state');

        loadHistory();
    }

    // Render text overlay for Taobao mode
    function renderTextOverlay(layoutData) {
        const textOverlay = document.getElementById('textOverlay');
        if (!textOverlay) return;

        textOverlay.innerHTML = '';

        const layoutClass = layoutData.selected_layout || 'layout-classic-left';
        const styleClass = layoutData.style || 'text-style-a';
        const titleText = layoutData.title || '';
        const subtitleText = layoutData.subtitle || '';
        const badges = layoutData.badges || [];

        console.log(`[Text Overlay]Layout: ${layoutClass}, Style: ${styleClass} `);

        // Main Container with Layout Class
        const containerDiv = document.createElement('div');
        containerDiv.className = layoutClass;

        // Title
        if (titleText) {
            const titleDiv = document.createElement('div');
            titleDiv.className = `text-layer ${styleClass}`;
            titleDiv.textContent = titleText;
            titleDiv.style.fontSize = 'clamp(24px, 5vw, 48px)';
            titleDiv.style.marginBottom = '20px'; // Increased from 8px
            titleDiv.style.position = 'relative'; // For z-index

            // Style C Banner
            if (styleClass === 'text-style-c') {
                const banner = document.createElement('div');
                banner.className = 'style-c-banner';
                banner.style.width = '120%'; // Wider than text
                banner.style.height = '100%';
                banner.style.position = 'absolute';
                banner.style.top = '0';
                banner.style.left = '-10%';
                banner.style.zIndex = '-1';
                titleDiv.appendChild(banner);
            }
            containerDiv.appendChild(titleDiv);
        }

        // Subtitle
        if (subtitleText) {
            const subtitleDiv = document.createElement('div');
            subtitleDiv.textContent = subtitleText;
            subtitleDiv.style.fontSize = 'clamp(14px, 3vw, 24px)';
            subtitleDiv.style.color = 'white';
            subtitleDiv.style.textShadow = '0 2px 4px rgba(0,0,0,0.5)';
            subtitleDiv.style.marginBottom = '20px'; // Increased from 12px
            subtitleDiv.style.fontWeight = '500';
            containerDiv.appendChild(subtitleDiv);
        }

        // Badges
        if (badges.length > 0) {
            const badgeContainer = document.createElement('div');
            badgeContainer.className = 'badge-container';

            badges.forEach(badgeText => {
                const badge = document.createElement('div');
                badge.className = 'badge-pill';
                badge.textContent = badgeText;
                badgeContainer.appendChild(badge);
            });
            containerDiv.appendChild(badgeContainer);
        }

        textOverlay.appendChild(containerDiv);
    }

    function setLoading(isLoading) {
        if (isLoading) {
            generateBtn.classList.add('loading');
            generateBtn.disabled = true;
        } else {
            generateBtn.classList.remove('loading');
            generateBtn.disabled = false;
        }
    }

    const historyBtn = document.getElementById('historyBtn');
    const closeHistoryBtn = document.getElementById('closeHistoryBtn');
    const historySidebar = document.getElementById('historySidebar');
    const historyList = document.getElementById('historyList');
    const migrateHistoryBtn = document.getElementById('migrateHistoryBtn');

    function toggleHistory() {
        historySidebar.classList.toggle('hidden');
        if (!historySidebar.classList.contains('hidden')) {
            loadHistory();
        }
    }

    if (historyBtn) historyBtn.addEventListener('click', toggleHistory);
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', toggleHistory);
    if (migrateHistoryBtn) migrateHistoryBtn.addEventListener('click', async () => {
        try {
            migrateHistoryBtn.disabled = true;
            const res = await fetch('/api/history/migrate', { method: 'POST' });
            await loadHistory();
        } catch (e) {
            console.error('History migrate failed', e);
        } finally {
            migrateHistoryBtn.disabled = false;
        }
    });

    async function loadHistory() {
        try {
            const response = await fetch('/api/history');
            const history = await response.json();

            historyList.innerHTML = '';

            history.forEach(item => {
                const div = document.createElement('div');
                div.className = 'history-item';

                const normalize = (p) => (p && !p.startsWith('/') ? `/${p}` : p);
                const thumbWrap = document.createElement('div');
                thumbWrap.className = 'history-thumb-wrap';
                const img = document.createElement('img');
                img.className = 'history-thumb';
                img.loading = 'lazy';
                img.src = normalize(item.composite_path) || normalize(item.image_path) || normalize(item.image_url);
                img.onerror = () => {
                    if (item.image_path && img.src !== normalize(item.image_path)) {
                        img.src = normalize(item.image_path);
                    } else if (item.image_url && img.src !== normalize(item.image_url)) {
                        img.src = normalize(item.image_url);
                    }
                };

                const info = document.createElement('div');
                info.className = 'history-info';
                const optimized = item.optimized_prompt || '';
                const original = item.original_prompt || '';
                const escapeHTML = (s) => String(s || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', '\'': '&#39;' }[c]));
                const toHTML = (s) => escapeHTML(s).replace(/\n/g, '<br/>');
                info.innerHTML = `
                    <div class="history-prompt">${toHTML(item.prompt || '')}</div>
                    ${optimized ? `<div class="history-prompt-optimized">${toHTML(optimized)}</div>` : ''}
                    ${original ? `<div class="history-prompt-original">${toHTML(original)}</div>` : ''}
                    <div class="history-meta">
                        <span>${item.ratio || ''}</span>
                        <span>${new Date(item.timestamp).toLocaleTimeString()}</span>
                    </div>
                `;

                thumbWrap.appendChild(img);
                div.appendChild(thumbWrap);
                div.appendChild(info);
                div.addEventListener('click', () => {
                    const sources = [normalize(item.composite_path), normalize(item.image_path), normalize(item.image_url)].filter(Boolean);
                    const src = sources[0];
                    if (src) {
                        // Clear previous handlers to prevent state corruption
                        generatedImage.onload = null;
                        generatedImage.onerror = null;

                        // Update main preview image
                        generatedImage.src = src;
                        // Ensure preview container is visible
                        const canvasContainer = document.getElementById('canvasContainer');
                        if (canvasContainer) {
                            canvasContainer.classList.remove('hidden');
                        }
                        emptyContent.classList.add('hidden');
                        imageContainer.classList.remove('empty-state');
                        // Reset main image zoom
                        genScale = 1;
                        generatedImage.style.transform = 'scale(1)';
                        // Also open modal for large preview
                        const promptText = (optimized && original) ? `优化后：${optimized}\n原文：${original}` : (item.prompt || item.marketing_copy || '');
                        openModal([src], promptText);
                    }
                });
                historyList.appendChild(div);
            });
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }

    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalPrompt = document.getElementById('modalPrompt');
    const closeModalBtn = document.getElementById('closeModalBtn');

    let currentScale = 1;
    let isDragging = false;
    let startX, startY, translateX = 0, translateY = 0;

    function openModal(imageSrc, promptText) {
        const normalize = (p) => {
            if (!p) return null;
            if (/^https?:\/\//.test(p)) return p;
            return p.startsWith('/') ? p : '/' + p;
        };
        const srcs = (Array.isArray(imageSrc) ? imageSrc : [imageSrc]).map(normalize).filter(Boolean);
        modal.classList.remove('hidden');
        modalPrompt.textContent = String(promptText || '');

        let idx = 0;
        const tryLoad = () => {
            const s = srcs[idx];
            if (!s) return;
            modalImage.onerror = () => {
                idx += 1;
                tryLoad();
            };
            modalImage.onload = () => {
                currentScale = 1;
                translateX = 0;
                translateY = 0;
                updateImageTransform();
            };
            modalImage.src = s;
        };

        tryLoad();
    }

    function closeModal() {
        modal.classList.add('hidden');
    }

    function updateImageTransform() {
        modalImage.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;
    }

    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);

    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    generatedImage.addEventListener('click', () => {
        if (lastImageSources.length) {
            openModal(lastImageSources, promptInput.value || "Generated Image");
        } else if (generatedImage.src) {
            openModal([generatedImage.src], promptInput.value || "Generated Image");
        }
    });

    generatedImage.style.cursor = 'pointer';

    // Initial load of history on page ready
    loadHistory();

    // Wheel zoom for generated image
    let genScale = 1;
    if (generatedImage) {
        generatedImage.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY * -0.001;
            const newScale = Math.min(Math.max(0.5, genScale + delta), 5);
            genScale = newScale;
            generatedImage.style.transform = `scale(${genScale})`;
        }, { passive: false });
    }

    // Wheel zoom for modal preview
    const mic = document.querySelector('.modal-image-container');
    if (modalImage) modalImage.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY * -0.001;
        const newScale = Math.min(Math.max(0.5, currentScale + delta), 5);
        currentScale = newScale;
        updateImageTransform();
    }, { passive: false });

    if (mic) mic.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY * -0.001;
        const newScale = Math.min(Math.max(0.5, currentScale + delta), 5);
        currentScale = newScale;
        updateImageTransform();
    }, { passive: false });

    // Download Composite Image Logic
    const downloadCompositeBtn = document.getElementById('downloadCompositeBtn');
    if (downloadCompositeBtn) {
        downloadCompositeBtn.addEventListener('click', async () => {
            if (!modalImage.src) return;

            const originalText = downloadCompositeBtn.textContent;
            downloadCompositeBtn.textContent = '⏳ Processing...';
            downloadCompositeBtn.disabled = true;

            try {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                const img = new Image();

                img.crossOrigin = "anonymous"; // Important for CORS if images are from external URLs
                img.src = modalImage.src;

                await new Promise((resolve, reject) => {
                    img.onload = resolve;
                    img.onerror = reject;
                });

                // Set canvas size to match image
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;

                // Draw base image
                ctx.drawImage(img, 0, 0);

                // Draw Text Overlay
                // We need to replicate the CSS styles in Canvas
                // This is a simplified implementation based on the current layout logic

                const textOverlay = document.getElementById('textOverlay');
                const layoutDiv = textOverlay.querySelector('div'); // The container with layout class

                if (layoutDiv) {
                    const layoutClass = layoutDiv.className; // e.g., "layout-classic-left"
                    const titleEl = layoutDiv.querySelector('.text-layer');
                    const subtitleEl = layoutDiv.querySelector('div:not(.text-layer):not(.badge-container)'); // Rough selector for subtitle
                    const badges = layoutDiv.querySelectorAll('.badge-pill');

                    // Helper to parse color (simplified)
                    const getComputedStyleProp = (el, prop) => window.getComputedStyle(el).getPropertyValue(prop);

                    // --- Layout Logic (Mapping CSS positions to Canvas coordinates) ---
                    // Note: Canvas coordinates are absolute pixels. CSS uses %, so we calculate based on canvas width/height.

                    let titleX, titleY, subtitleX, subtitleY, align;

                    if (layoutClass.includes('layout-classic-left')) {
                        align = 'left';
                        titleX = canvas.width * 0.08;
                        titleY = canvas.height * 0.15;
                    } else if (layoutClass.includes('layout-clean-right')) {
                        align = 'right';
                        titleX = canvas.width * 0.92;
                        titleY = canvas.height * 0.15;
                    } else if (layoutClass.includes('layout-modern-bottom')) {
                        align = 'center';
                        titleX = canvas.width * 0.5;
                        titleY = canvas.height * 0.85;
                    } else {
                        // Default
                        align = 'left';
                        titleX = 50;
                        titleY = 100;
                    }

                    // --- Draw Title ---
                    if (titleEl) {
                        const fontSize = Math.max(24, canvas.width * 0.06); // Scale font size
                        ctx.font = `900 ${fontSize}px "Microsoft YaHei", sans-serif`;
                        ctx.textAlign = align;
                        ctx.textBaseline = 'top';

                        // Shadow
                        ctx.shadowColor = "rgba(0, 0, 0, 0.8)";
                        ctx.shadowBlur = 4;
                        ctx.shadowOffsetX = 2;
                        ctx.shadowOffsetY = 2;

                        // Gradient Text (Style A simulation)
                        if (titleEl.classList.contains('text-style-a')) {
                            const gradient = ctx.createLinearGradient(0, titleY, 0, titleY + fontSize);
                            gradient.addColorStop(0, "#ffd700");
                            gradient.addColorStop(1, "#ffaa00");
                            ctx.fillStyle = gradient;
                        } else {
                            ctx.fillStyle = "white";
                        }

                        // Handle multi-line text (if any)
                        const text = titleEl.textContent;
                        ctx.fillText(text, titleX, titleY);

                        // Update Y for subtitle
                        if (layoutClass.includes('layout-modern-bottom')) {
                            // For bottom layout, title is above subtitle, so we move UP for title or down for subtitle
                            // Actually let's just offset subtitle below title
                            subtitleY = titleY + fontSize + 20;
                            subtitleX = titleX;
                        } else {
                            subtitleY = titleY + fontSize + 20;
                            subtitleX = titleX;
                        }
                    }

                    // --- Draw Subtitle ---
                    if (subtitleEl) {
                        const subFontSize = Math.max(14, canvas.width * 0.03);
                        ctx.font = `500 ${subFontSize}px "Microsoft YaHei", sans-serif`;
                        ctx.textAlign = align;
                        ctx.fillStyle = "white";
                        ctx.shadowColor = "rgba(0, 0, 0, 0.5)";
                        ctx.shadowBlur = 4;

                        ctx.fillText(subtitleEl.textContent, subtitleX, subtitleY);
                    }

                    // --- Draw Badges (Simplified: Just drawing text pills) ---
                    if (badges.length > 0) {
                        let badgeX = titleX;
                        let badgeY = subtitleY + (canvas.width * 0.03) + 20;

                        if (align === 'right') {
                            // Adjust starting X for right alignment to flow leftwards or stack?
                            // Simple stacking for now
                        }

                        ctx.font = `bold ${Math.max(12, canvas.width * 0.025)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.shadowColor = 'transparent';

                        badges.forEach((badge, index) => {
                            const text = badge.textContent;
                            const metrics = ctx.measureText(text);
                            const padding = 20;
                            const badgeWidth = metrics.width + padding * 2;
                            const badgeHeight = Math.max(24, canvas.width * 0.04);

                            // Draw Pill Background
                            const gradient = ctx.createLinearGradient(badgeX, badgeY, badgeX + badgeWidth, badgeY + badgeHeight);
                            gradient.addColorStop(0, "#ff4d4d");
                            gradient.addColorStop(1, "#f44336");
                            ctx.fillStyle = gradient;

                            // Round rect (manual)
                            ctx.beginPath();
                            ctx.roundRect(align === 'center' ? badgeX - badgeWidth / 2 : (align === 'right' ? badgeX - badgeWidth : badgeX), badgeY, badgeWidth, badgeHeight, 20);
                            ctx.fill();

                            // Draw Text
                            ctx.fillStyle = "white";
                            ctx.fillText(text, align === 'center' ? badgeX : (align === 'right' ? badgeX - badgeWidth / 2 : badgeX + badgeWidth / 2), badgeY + badgeHeight / 2);

                            // Offset for next badge
                            if (align === 'center') {
                                badgeX += badgeWidth + 10; // This will break centering if multiple badges, but good enough for v1
                            } else if (align === 'right') {
                                badgeY += badgeHeight + 10; // Stack vertically for right layout
                            } else {
                                badgeX += badgeWidth + 10;
                            }
                        });
                    }
                }

                // Trigger Download
                const link = document.createElement('a');
                link.download = `taobao-gen-${Date.now()}.png`;
                link.href = canvas.toDataURL('image/png');
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

            } catch (error) {
                console.error('Download Error:', error);
                alert('Failed to generate download image. See console for details.');
            } finally {
                downloadCompositeBtn.textContent = originalText;
                downloadCompositeBtn.disabled = false;
            }
        });
    }
});
function normalizeLayout(raw) {
    if (!raw) return {};
    const sys = raw.Taobao_Master_Layout_System || raw;
    const fx = sys.background_fx || {};
    return {
        selected_layout: sys.layout_template || sys.selected_layout || 'layout-classic-left',
        style: fx.style || sys.style || 'text-style-a',
        title: sys.title || '',
        subtitle: sys.subtitle || '',
        badges: sys.badges || []
    };
}
