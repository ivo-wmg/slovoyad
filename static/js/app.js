/* ========================================
   СЛОВОЯД — Frontend Application Logic
   ======================================== */

(function () {
    'use strict';

    // --- DOM References ---
    const form = document.getElementById('evaluate-form');
    const urlInput = document.getElementById('url-input');
    const submitBtn = document.getElementById('submit-btn');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorToast = document.getElementById('error-toast');
    const errorMessage = document.getElementById('error-message');
    const errorCloseBtn = document.getElementById('error-close-btn');
    const resultsSection = document.getElementById('results-section');

    const articleTitle = document.getElementById('article-title');
    const articleUrl = document.getElementById('article-url');
    const domainBadge = document.getElementById('domain-badge');
    const versionBadge = document.getElementById('version-badge');
    const classificationBadge = document.getElementById('classification-badge');
    const exportPdfBtn = document.getElementById('export-pdf-btn');

    const scoreCardsContainer = document.getElementById('score-cards');
    const overallScoreValue = document.getElementById('overall-score-value');
    const scoreRingProgress = document.getElementById('score-ring-progress');

    const strengthsList = document.getElementById('strengths-list');
    const weaknessesList = document.getElementById('weaknesses-list');

    const justificationsToggle = document.getElementById('justifications-toggle');
    const justificationsContent = document.getElementById('justifications-content');
    const justificationsList = document.getElementById('justifications-list');

    const historyToggle = document.getElementById('history-toggle');
    const historyContent = document.getElementById('history-content');
    const versionHistoryList = document.getElementById('version-history-list');
    const versionHistorySection = document.getElementById('version-history-section');

    const aiDetectionToggle = document.getElementById('ai-detection-toggle');
    const aiDetectionContent = document.getElementById('ai-detection-content');
    const aiDetectionSection = document.getElementById('ai-detection-section');
    const aiProbabilityValue = document.getElementById('ai-probability-value');
    const aiProbabilityFill = document.getElementById('ai-probability-fill');
    const aiReasoning = document.getElementById('ai-reasoning');

    const spellingToggle = document.getElementById('spelling-toggle');
    const spellingContent = document.getElementById('spelling-content');
    const spellingErrorsSection = document.getElementById('spelling-errors-section');
    const spellingErrorsList = document.getElementById('spelling-errors-list');
    const spellingNone = document.getElementById('spelling-none');

    // --- Score label mapping (Bulgarian) ---
    const SCORE_LABELS = {
        domain_specific_score: 'Ниша',
        originality: 'Оригиналност',
        trust_and_sources: 'Доверие',
        quality_and_depth: 'Качество',
        significance_locality: 'Значимост'
    };

    const SCORE_WEIGHTS = {
        domain_specific_score: '35%',
        originality: '25%',
        trust_and_sources: '20%',
        quality_and_depth: '10%',
        significance_locality: '10%'
    };

    const SCORE_ORDER = [
        'domain_specific_score',
        'originality',
        'trust_and_sources',
        'quality_and_depth',
        'significance_locality'
    ];

    const JUSTIFICATION_LABELS = {
        originality_reason: 'Оригиналност',
        significance_reason: 'Значимост и местно значение',
        domain_specific_reason: 'Специфична за нишата',
        quality_reason: 'Качество и задълбоченост',
        trust_reason: 'Доверие и източници'
    };

    // Domain accent colors for badge styling
    const DOMAIN_COLORS = {
        'news.bg': '#3b82f6',
        'money.bg': '#f59e0b',
        'infostock.bg': '#8b5cf6',
        'topsport.bg': '#22c55e',
        'lifestyle.bg': '#ec4899',
        'chr.bg': '#06b6d4',
        'webcafe.bg': '#f97316',
        'mamamia.bg': '#ef4444'
    };

    // --- Helper Functions ---

    /**
     * Returns the CSS color class for a given score (1-10).
     */
    function getScoreColor(score) {
        if (score >= 8) return 'score-green';
        if (score >= 5) return 'score-yellow';
        return 'score-red';
    }

    /**
     * Returns the hex color for a given score.
     */
    function getScoreHex(score) {
        if (score >= 8) return '#22c55e';
        if (score >= 5) return '#eab308';
        return '#ef4444';
    }

    /**
     * Returns an emoji representing score quality.
     */
    function getScoreEmoji(score) {
        if (score >= 9) return '🏆';
        if (score >= 8) return '✨';
        if (score >= 6) return '👍';
        if (score >= 4) return '⚡';
        return '⚠️';
    }

    /**
     * Formats an ISO date string to a human-friendly Bulgarian format.
     */
    function formatDate(dateStr) {
        if (!dateStr) return '—';
        const d = new Date(dateStr);
        const months = [
            'яну', 'фев', 'мар', 'апр', 'май', 'юни',
            'юли', 'авг', 'сеп', 'окт', 'ное', 'дек'
        ];
        const day = d.getDate();
        const month = months[d.getMonth()];
        const year = d.getFullYear();
        const hours = String(d.getHours()).padStart(2, '0');
        const mins = String(d.getMinutes()).padStart(2, '0');
        return `${day} ${month} ${year}, ${hours}:${mins}`;
    }

    /**
     * Creates an individual score card element.
     */
    function renderScoreCard(key, score, weight) {
        const label = SCORE_LABELS[key] || key;
        const colorClass = getScoreColor(score);
        const emoji = getScoreEmoji(score);

        const card = document.createElement('div');
        card.className = 'score-card';
        card.style.setProperty('--card-accent', getScoreHex(score));

        card.innerHTML = `
            <div class="score-card-label">${label}</div>
            <div class="score-card-value ${colorClass}">${emoji} ${score}</div>
            <div class="score-card-weight">Тежест: ${weight}</div>
        `;

        return card;
    }

    /**
     * Animates the circular progress ring for the overall score.
     */
    function animateScoreRing(score) {
        const circumference = 2 * Math.PI * 52; // r=52
        const fraction = Math.min(score / 10, 1);
        const offset = circumference * (1 - fraction);

        scoreRingProgress.style.stroke = getScoreHex(score);
        // Reset to full offset first, then animate
        scoreRingProgress.style.transition = 'none';
        scoreRingProgress.style.strokeDashoffset = circumference;

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                scoreRingProgress.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
                scoreRingProgress.style.strokeDashoffset = offset;
            });
        });
    }

    /**
     * Renders score evolution arrow comparing two scores.
     */
    function renderEvolutionArrow(currentScore, previousScore) {
        if (previousScore == null) return '';

        const diff = currentScore - previousScore;
        if (diff > 0) {
            return `<span class="score-arrow arrow-up">↑</span>`;
        } else if (diff < 0) {
            return `<span class="score-arrow arrow-down">↓</span>`;
        }
        return `<span class="score-arrow arrow-same">=</span>`;
    }

    // --- Collapsible Toggle Setup ---
    function setupCollapsible(toggleBtn, contentEl) {
        toggleBtn.addEventListener('click', () => {
            const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            toggleBtn.setAttribute('aria-expanded', !isExpanded);
            contentEl.classList.toggle('open');
        });
    }

    setupCollapsible(justificationsToggle, justificationsContent);
    setupCollapsible(historyToggle, historyContent);
    setupCollapsible(aiDetectionToggle, aiDetectionContent);
    setupCollapsible(spellingToggle, spellingContent);

    // --- Error Toast ---
    function showError(message) {
        errorMessage.textContent = message;
        errorToast.classList.remove('hidden');

        // Auto-hide after 8s
        clearTimeout(showError._timeout);
        showError._timeout = setTimeout(() => {
            errorToast.classList.add('hidden');
        }, 8000);
    }

    errorCloseBtn.addEventListener('click', () => {
        errorToast.classList.add('hidden');
    });

    // --- Loading ---
    function showLoading() {
        loadingOverlay.classList.remove('hidden');
        submitBtn.disabled = true;
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
        submitBtn.disabled = false;
    }

    // --- Render Results ---
    function renderResults(data) {
        const current = data.current;
        const evaluation = current.evaluation;

        // Article Meta
        articleTitle.textContent = evaluation.title_scraped || 'Без заглавие';

        // Article URL
        const evalUrl = current.url || '';
        articleUrl.textContent = evalUrl;
        articleUrl.href = evalUrl;
        articleUrl.title = evalUrl;

        const domainColor = DOMAIN_COLORS[evaluation.domain] || '#6366f1';
        domainBadge.textContent = evaluation.domain;
        domainBadge.style.background = `${domainColor}22`;
        domainBadge.style.color = domainColor;
        domainBadge.style.borderColor = `${domainColor}44`;

        versionBadge.textContent = `v${current.version}`;
        classificationBadge.textContent = evaluation.classification || '—';

        // Score Cards
        scoreCardsContainer.innerHTML = '';
        SCORE_ORDER.forEach(key => {
            const score = evaluation[key];
            if (score != null) {
                const card = renderScoreCard(key, score, SCORE_WEIGHTS[key]);
                scoreCardsContainer.appendChild(card);
            }
        });

        // Overall Score
        const overall = evaluation.final_overall_score;
        overallScoreValue.textContent = overall.toFixed(2);
        animateScoreRing(overall);

        // Confidence
        const confIndicator = document.getElementById('confidence-indicator');
        const confValue = document.getElementById('confidence-value');
        if (evaluation.confidence != null && confIndicator && confValue) {
            const conf = evaluation.confidence;
            confValue.textContent = conf + '%';
            confValue.style.color = conf >= 80 ? '#10b981' : conf >= 50 ? '#f59e0b' : '#ef4444';
            confIndicator.classList.remove('hidden');
        } else if (confIndicator) {
            confIndicator.classList.add('hidden');
        }

        // Strengths
        strengthsList.innerHTML = '';
        (evaluation.strengths || []).forEach(s => {
            const li = document.createElement('li');
            li.textContent = s;
            strengthsList.appendChild(li);
        });

        // Weaknesses
        weaknessesList.innerHTML = '';
        (evaluation.weaknesses || []).forEach(w => {
            const li = document.createElement('li');
            li.textContent = w;
            weaknessesList.appendChild(li);
        });

        // Justifications
        justificationsList.innerHTML = '';
        const justKeys = ['originality_reason', 'significance_reason', 'quality_reason', 'trust_reason', 'domain_specific_reason'];
        justKeys.forEach(key => {
            const text = evaluation[key];
            if (text) {
                const label = JUSTIFICATION_LABELS[key] || key;
                const item = document.createElement('div');
                item.className = 'justification-item';
                item.innerHTML = `
                    <div class="justification-label">${label}</div>
                    <div class="justification-text">${escapeHtml(text)}</div>
                `;
                justificationsList.appendChild(item);
            }
        });

        // AI Detection
        renderAiDetection(evaluation);

        // Spelling Errors
        renderSpellingErrors(evaluation);

        // Open all collapsible sections by default
        justificationsToggle.setAttribute('aria-expanded', 'true');
        justificationsContent.classList.add('open');
        historyToggle.setAttribute('aria-expanded', 'true');
        historyContent.classList.add('open');
        aiDetectionToggle.setAttribute('aria-expanded', 'true');
        aiDetectionContent.classList.add('open');
        spellingToggle.setAttribute('aria-expanded', 'true');
        spellingContent.classList.add('open');

        // Version History
        renderVersionHistory(data, evaluation);

        // Show results
        resultsSection.classList.remove('hidden');

        // Show copy link button if eval has an ID
        currentEvalId = current.id || null;
        if (currentEvalId && copyLinkBtn) {
            copyLinkBtn.style.display = '';
        }

        // Re-trigger animations
        resultsSection.querySelectorAll('.fade-in').forEach(el => {
            el.style.animation = 'none';
            el.offsetHeight; // force reflow
            el.style.animation = '';
        });
    }

    /**
     * Renders the version history section.
     */
    function renderVersionHistory(data, currentEval) {
        const previousVersions = data.previous_versions || [];

        if (previousVersions.length === 0) {
            versionHistorySection.classList.add('hidden');
            return;
        }

        versionHistorySection.classList.remove('hidden');
        versionHistoryList.innerHTML = '';

        // Build all versions list: previous + current, sorted by version desc
        const allVersions = [...previousVersions].sort((a, b) => b.version - a.version);

        allVersions.forEach((ver, index) => {
            const verEval = ver.evaluation || {};
            const overallScore = verEval.final_overall_score;

            // Determine the next newer version for comparison
            let newerOverall = null;
            if (index === 0) {
                // Compare the most recent previous version with the current evaluation
                newerOverall = currentEval.final_overall_score;
            } else {
                const newerVer = allVersions[index - 1];
                newerOverall = newerVer.evaluation?.final_overall_score ?? null;
            }

            const card = document.createElement('div');
            card.className = 'version-card';
            card.style.animationDelay = `${index * 0.08}s`;

            // Build score items
            let scoresHtml = '';
            SCORE_ORDER.forEach(key => {
                const score = verEval[key];
                if (score != null) {
                    const label = SCORE_LABELS[key] || key;
                    scoresHtml += `
                        <span class="version-score-item">
                            <span>${label}: </span>
                            <strong class="${getScoreColor(score)}">${score}</strong>
                        </span>
                    `;
                }
            });

            const arrowHtml = newerOverall != null
                ? renderEvolutionArrow(newerOverall, overallScore)
                : '';

            card.innerHTML = `
                <div class="version-card-header">
                    <span class="version-number">Версия ${ver.version}</span>
                    <span class="version-date">${formatDate(ver.evaluated_at)}</span>
                </div>
                <div class="version-scores">
                    ${scoresHtml}
                    <span class="version-overall ${getScoreColor(overallScore)}">
                        ${overallScore != null ? overallScore.toFixed(2) : '—'}
                        ${arrowHtml}
                    </span>
                </div>
            `;

            versionHistoryList.appendChild(card);
        });
    }

    /**
     * Escapes HTML entities to prevent XSS.
     */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // --- Form Submission ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = urlInput.value.trim();
        if (!url) return;

        showLoading();
        resultsSection.classList.add('hidden');
        errorToast.classList.add('hidden');

        try {
            const response = await fetch('/api/evaluate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!response.ok) {
                let errorText = 'Възникна грешка при анализа на статията.';
                try {
                    const errData = await response.json();
                    errorText = errData.detail || errData.error || errData.message || errorText;
                } catch (_) {
                    // Use default error text
                }
                throw new Error(errorText);
            }

            const data = await response.json();
            renderResults(data);

            // Update URL to root so user doesn't share a stale permalink
            if (window.location.pathname !== '/') {
                window.history.pushState(null, '', '/');
            }

        } catch (err) {
            const friendlyMessages = {
                'Failed to fetch': 'Няма връзка със сървъра. Моля, проверете дали сървърът работи.',
                'NetworkError': 'Мрежова грешка. Проверете интернет връзката си.',
            };

            let msg = err.message;
            Object.keys(friendlyMessages).forEach(key => {
                if (msg.includes(key)) {
                    msg = friendlyMessages[key];
                }
            });

            showError(msg);
        } finally {
            hideLoading();
        }
    });

    // --- PDF Export (server-side) ---
    exportPdfBtn.addEventListener('click', async () => {
        const urlEl = document.getElementById('article-url');
        const articleUrl = urlEl ? urlEl.href : '';
        if (!articleUrl || articleUrl === '#') return;

        exportPdfBtn.disabled = true;
        exportPdfBtn.textContent = '⏳';

        try {
            const resp = await fetch(`/api/pdf?url=${encodeURIComponent(articleUrl)}`);
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || 'PDF generation failed');
            }
            const blob = await resp.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            const disposition = resp.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?(.+?)"?$/);
            link.download = match ? match[1] : 'slovoyad_report.pdf';
            link.click();
            URL.revokeObjectURL(link.href);
        } catch (err) {
            showError('PDF грешка: ' + err.message);
        } finally {
            exportPdfBtn.disabled = false;
            exportPdfBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg> PDF';
        }
    });

    // --- AI Detection ---
    function renderAiDetection(evaluation) {
        const prob = evaluation.ai_probability;
        const reasoning = evaluation.ai_reasoning;

        if (prob == null && !reasoning) {
            aiDetectionSection.classList.add('hidden');
            return;
        }

        aiDetectionSection.classList.remove('hidden');

        if (prob != null) {
            const pct = prob;
            aiProbabilityValue.textContent = `${pct}%`;
            // Color the value based on probability
            if (pct >= 70) {
                aiProbabilityValue.style.color = 'var(--red)';
            } else if (pct >= 40) {
                aiProbabilityValue.style.color = 'var(--yellow)';
            } else {
                aiProbabilityValue.style.color = 'var(--green)';
            }
            // Animate fill bar
            requestAnimationFrame(() => {
                aiProbabilityFill.style.width = `${pct}%`;
            });
        } else {
            aiProbabilityValue.textContent = '—';
            aiProbabilityFill.style.width = '0%';
        }

        aiReasoning.textContent = reasoning || '';
    }

    // --- Spelling Errors ---
    function renderSpellingErrors(evaluation) {
        const errors = evaluation.spelling_errors;

        if (!errors || errors.length === 0) {
            spellingErrorsList.innerHTML = '';
            spellingNone.classList.remove('hidden');
            spellingErrorsSection.classList.remove('hidden');
            return;
        }

        spellingNone.classList.add('hidden');
        spellingErrorsSection.classList.remove('hidden');
        spellingErrorsList.innerHTML = '';

        errors.forEach(err => {
            const item = document.createElement('div');
            item.className = 'spelling-error-item';

            if (typeof err === 'string') {
                item.innerHTML = `<span class="spelling-error-word">${escapeHtml(err)}</span>`;
            } else {
                const word = err.word || err.original || '';
                const suggestion = err.suggestion || err.correct || '';
                const context = err.context || '';

                let html = `<span class="spelling-error-word">${escapeHtml(word)}</span>`;
                if (suggestion) {
                    html += ` <span class="spelling-error-suggestion">→ ${escapeHtml(suggestion)}</span>`;
                }
                if (context) {
                    html += `<span class="spelling-error-context"> — ${escapeHtml(context)}</span>`;
                }
                item.innerHTML = html;
            }

            spellingErrorsList.appendChild(item);
        });
    }
    // --- Copy Link ---
    let currentEvalId = null;
    const copyLinkBtn = document.getElementById('copy-link-btn');

    copyLinkBtn.addEventListener('click', () => {
        if (!currentEvalId) return;
        const url = `${window.location.origin}/evaluations/${currentEvalId}`;
        navigator.clipboard.writeText(url).then(() => {
            const orig = copyLinkBtn.innerHTML;
            copyLinkBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Копиран!';
            setTimeout(() => { copyLinkBtn.innerHTML = orig; }, 2000);
        });
    });

    // --- Permalink: auto-load saved evaluation ---
    const pathMatch = window.location.pathname.match(/^\/evaluations\/(\d+)$/);
    if (pathMatch) {
        const evalId = pathMatch[1];
        (async () => {
            showLoading();
            try {
                const ev = await fetch(`/api/evaluations/${evalId}`).then(r => {
                    if (!r.ok) throw new Error('Evaluation not found');
                    return r.json();
                });

                // Parse JSON strings from DB
                if (typeof ev.justifications === 'string') {
                    try { ev.justifications = JSON.parse(ev.justifications); } catch(e) {}
                }
                if (typeof ev.strengths === 'string') {
                    try { ev.strengths = JSON.parse(ev.strengths); } catch(e) {}
                }
                if (typeof ev.weaknesses === 'string') {
                    try { ev.weaknesses = JSON.parse(ev.weaknesses); } catch(e) {}
                }
                if (typeof ev.spelling_errors === 'string') {
                    try { ev.spelling_errors = JSON.parse(ev.spelling_errors); } catch(e) {}
                }

                // Flatten justifications into evaluation
                const justs = ev.justifications || {};
                Object.assign(ev, justs);

                // Build data structure that renderResults expects
                const data = {
                    current: {
                        url: ev.url,
                        version: ev.version || 1,
                        id: ev.id,
                        evaluation: ev,
                        evaluated_at: ev.evaluated_at,
                    },
                    versions: [{ version: ev.version || 1, evaluated_at: ev.evaluated_at }]
                };

                renderResults(data);
            } catch (err) {
                showError(err.message);
            } finally {
                hideLoading();
            }
        })();
    }

})();
