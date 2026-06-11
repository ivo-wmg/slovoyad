"""
Slovoyad — PDF генератор за оценки.
Използва WeasyPrint за сървър-сайд PDF рендериране с vector текст.
"""

from weasyprint import HTML


def _score_color(score: int) -> str:
    if score >= 8:
        return "#22c55e"
    if score >= 5:
        return "#eab308"
    return "#ef4444"


def _ai_color(prob: int) -> str:
    if prob <= 30:
        return "#22c55e"
    if prob <= 60:
        return "#eab308"
    return "#ef4444"


def generate_evaluation_pdf(eval_data: dict, url: str, version: int,
                             evaluated_at: str) -> bytes:
    """Generate a PDF report for an article evaluation.

    Returns PDF as bytes.
    """
    e = eval_data

    # Score cards
    scores = [
        ("Ниша", e.get("domain_specific_score", 0), "35%"),
        ("Оригиналност", e.get("originality", 0), "25%"),
        ("Доверие", e.get("trust_and_sources", 0), "20%"),
        ("Качество", e.get("quality_and_depth", 0), "10%"),
        ("Значимост", e.get("significance_locality", 0), "10%"),
    ]
    score_cards_html = ""
    for label, score, weight in scores:
        color = _score_color(score)
        score_cards_html += f"""
        <div class="score-card">
            <div class="sc-label">{label}</div>
            <div class="sc-value" style="color:{color};">{score}</div>
            <div class="sc-weight">Тежест: {weight}</div>
        </div>
        """

    overall = e.get("final_overall_score", 0)
    overall_color = _score_color(int(overall))

    # Strengths & weaknesses
    strengths = e.get("strengths", [])
    strengths_html = "".join(f"<li>{s}</li>" for s in strengths)

    weaknesses = e.get("weaknesses", [])
    weaknesses_html = "".join(f"<li>{w}</li>" for w in weaknesses)

    # Justifications
    just_map = {
        "originality_reason": "Оригиналност",
        "significance_reason": "Значимост и местно значение",
        "domain_specific_reason": "Специфична за нишата",
    }
    justifications_html = ""
    for key, label in just_map.items():
        text = e.get(key, "")
        if text:
            justifications_html += f"""
            <div class="just-card">
                <div class="just-label">{label}</div>
                <div class="just-text">{text}</div>
            </div>
            """

    # AI Detection
    ai_prob = e.get("ai_probability")
    ai_html = ""
    if ai_prob is not None:
        ai_color = _ai_color(ai_prob)
        ai_reason = e.get("ai_reasoning", "")
        ai_html = f"""
        <div class="section-card">
            <div class="section-header">
                <span>🤖 AI вероятност</span>
                <span style="color:{ai_color}; font-weight:700;">{ai_prob}%</span>
            </div>
            <div class="ai-track">
                <div class="ai-fill" style="width:{ai_prob}%; background:{ai_color};"></div>
            </div>
            <div class="ai-reason">{ai_reason}</div>
        </div>
        """

    # Spelling errors
    spelling = e.get("spelling_errors", [])
    spelling_html = ""
    if spelling:
        items = "".join(f"<li>{err}</li>" for err in spelling)
        spelling_html = f"""
        <div class="section-card">
            <div class="section-header">✏️ Правописни грешки</div>
            <ul class="spell-list">{items}</ul>
        </div>
        """

    title = e.get("title_scraped", "Без заглавие")
    domain = e.get("domain", "")
    classification = e.get("classification", "")

    html = f"""
    <!DOCTYPE html>
    <html lang="bg">
    <head>
        <meta charset="utf-8">
        <style>
            @page {{
                size: A4;
                margin: 1.8cm 1.5cm;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
                font-family: sans-serif;
                background: #0a0a0f;
                color: #e5e7eb;
                font-size: 11px;
                line-height: 1.55;
            }}

            .header {{
                text-align: center;
                margin-bottom: 18px;
                padding-bottom: 10px;
                border-bottom: 1px solid #2d2d44;
            }}
            .logo {{
                font-size: 26px;
                font-weight: 900;
                color: #818cf8;
                letter-spacing: 4px;
            }}
            .subtitle {{
                font-size: 9px;
                color: #6b7280;
                margin-top: 2px;
            }}

            .article-title {{
                font-size: 15px;
                font-weight: 700;
                color: #f0f0f5;
                margin-bottom: 3px;
            }}
            .article-url {{
                font-size: 8px;
                color: #6b7280;
                word-break: break-all;
            }}

            .badges {{
                margin: 8px 0 14px;
            }}
            .badge {{
                display: inline-block;
                padding: 2px 10px;
                font-size: 9px;
                font-weight: 600;
                border-radius: 20px;
                margin-right: 5px;
            }}
            .badge-domain {{
                background: rgba(99,102,241,0.15);
                color: #818cf8;
                border: 1px solid rgba(99,102,241,0.3);
            }}
            .badge-ver {{
                background: rgba(255,255,255,0.06);
                color: #9ca3af;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .badge-class {{
                background: rgba(139,92,246,0.15);
                color: #a78bfa;
                border: 1px solid rgba(139,92,246,0.3);
            }}

            .scores-row {{
                display: flex;
                gap: 6px;
                margin-bottom: 14px;
            }}
            .score-card {{
                flex: 1;
                text-align: center;
                padding: 10px 4px;
                background: #1a1a2e;
                border: 1px solid #2d2d44;
                border-radius: 8px;
            }}
            .sc-label {{
                font-size: 9px;
                color: #9ca3af;
                text-transform: uppercase;
                letter-spacing: 0.4px;
                margin-bottom: 4px;
            }}
            .sc-value {{
                font-size: 24px;
                font-weight: 800;
            }}
            .sc-weight {{
                font-size: 8px;
                color: #6b7280;
                margin-top: 3px;
            }}

            .overall {{
                text-align: center;
                padding: 16px;
                background: #1a1a2e;
                border: 1px solid #2d2d44;
                border-radius: 10px;
                margin-bottom: 14px;
            }}
            .overall-label {{
                font-size: 9px;
                color: #9ca3af;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
            }}
            .overall-value {{
                font-size: 32px;
                font-weight: 900;
            }}

            .sw-row {{
                display: flex;
                gap: 10px;
                margin-bottom: 14px;
            }}
            .sw-card {{
                flex: 1;
                background: #1a1a2e;
                border: 1px solid #2d2d44;
                border-radius: 10px;
                padding: 12px;
            }}
            .sw-title {{
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 6px;
            }}
            .sw-card ul {{
                list-style: none;
                padding: 0;
            }}
            .sw-card li {{
                margin-bottom: 3px;
                font-size: 10.5px;
                color: #d1d5db;
                padding-left: 8px;
            }}
            .sw-card li::before {{
                content: "•";
                margin-right: 5px;
            }}

            .section-title {{
                font-size: 12px;
                font-weight: 700;
                color: #f0f0f5;
                margin: 12px 0 8px;
            }}

            .just-card {{
                padding: 8px 10px;
                background: #12121a;
                border-left: 3px solid #6366f1;
                border-radius: 4px;
                margin-bottom: 6px;
            }}
            .just-label {{
                font-size: 9px;
                font-weight: 700;
                color: #818cf8;
                text-transform: uppercase;
                letter-spacing: 0.4px;
                margin-bottom: 3px;
            }}
            .just-text {{
                font-size: 10.5px;
                color: #9ca3af;
                line-height: 1.55;
            }}

            .section-card {{
                background: #1a1a2e;
                border: 1px solid #2d2d44;
                border-radius: 10px;
                padding: 12px;
                margin-bottom: 10px;
            }}
            .section-header {{
                font-size: 12px;
                font-weight: 700;
                color: #f0f0f5;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
            }}
            .ai-track {{
                background: #0a0a0f;
                border-radius: 20px;
                height: 7px;
                overflow: hidden;
                margin-bottom: 8px;
            }}
            .ai-fill {{
                height: 100%;
                border-radius: 20px;
            }}
            .ai-reason {{
                font-size: 10px;
                color: #9ca3af;
                line-height: 1.5;
            }}
            .spell-list {{
                list-style: none;
                padding: 0;
            }}
            .spell-list li {{
                font-size: 10.5px;
                color: #eab308;
                margin-bottom: 2px;
                padding-left: 8px;
            }}
            .spell-list li::before {{
                content: "•";
                margin-right: 5px;
            }}

            .footer {{
                text-align: center;
                margin-top: 16px;
                padding-top: 8px;
                border-top: 1px solid #2d2d44;
                font-size: 8px;
                color: #6b7280;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">СЛОВОЯД</div>
            <div class="subtitle">Анализатор на медийно съдържание</div>
        </div>

        <div class="article-title">{title}</div>
        <div class="article-url">{url}</div>

        <div class="badges">
            <span class="badge badge-domain">{domain}</span>
            <span class="badge badge-ver">v{version}</span>
            <span class="badge badge-class">{classification}</span>
        </div>

        <div class="scores-row">
            {score_cards_html}
        </div>

        <div class="overall">
            <div class="overall-label">Обща оценка</div>
            <div class="overall-value" style="color:{overall_color};">{overall:.2f}</div>
        </div>

        <div class="sw-row">
            <div class="sw-card">
                <div class="sw-title" style="color:#22c55e;">✅ Силни страни</div>
                <ul>{strengths_html}</ul>
            </div>
            <div class="sw-card">
                <div class="sw-title" style="color:#ef4444;">✗ Слаби страни</div>
                <ul>{weaknesses_html}</ul>
            </div>
        </div>

        <div class="section-title">📋 Обосновки</div>
        {justifications_html}

        {ai_html}
        {spelling_html}

        <div class="footer">
            Генерирано от СЛОВОЯД • {evaluated_at}
        </div>
    </body>
    </html>
    """

    return HTML(string=html).write_pdf()
