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
    const domainBadge = document.getElementById('domain-badge');
    const versionBadge = document.getElementById('version-badge');
    const classificationBadge = document.getElementById('classification-badge');

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
        const justKeys = ['originality_reason', 'significance_reason', 'domain_specific_reason'];
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

        // Reset collapsible states
        justificationsToggle.setAttribute('aria-expanded', 'false');
        justificationsContent.classList.remove('open');
        historyToggle.setAttribute('aria-expanded', 'false');
        historyContent.classList.remove('open');

        // Version History
        renderVersionHistory(data, evaluation);

        // Show results
        resultsSection.classList.remove('hidden');

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

})();
