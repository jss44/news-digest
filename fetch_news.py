"""
Daily News Digest — fetch_news.py
Fetches top news stories per topic using Claude + web search,
then builds a static HTML page published via GitHub Pages.
"""

import anthropic
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────
# CONFIGURATION — Edit topics here
# ─────────────────────────────────────────────────────────────

TOPICS = [
    {
        "id": "vermont",
        "label": "Vermont News",
        "emoji": "🍁",
        "color": "#2F855A",
        "instructions": (
            "Search for the 5 most important Vermont state news stories from today or the past 24 hours. "
            "Cover local politics, weather, community events, economy, and Vermont-specific issues. "
            "Focus on stories that matter to Vermont residents."
        ),
    },
    {
        "id": "world",
        "label": "Top World Events",
        "emoji": "🌍",
        "color": "#2B6CB0",
        "instructions": (
            "Search for the 5 most significant international news stories from today. "
            "Focus on major geopolitical events, conflicts, diplomacy, elections, and global developments "
            "that have broad worldwide impact."
        ),
    },
    {
        "id": "us",
        "label": "Top US Events",
        "emoji": "🦅",
        "color": "#C53030",
        "instructions": (
            "Search for the 5 most important US domestic news stories from today. "
            "Cover major events, legislation, court rulings, economic news, and significant national stories. "
            "Include news about President Trump or his administration ONLY if the story is of "
            "exceptional national importance — such as a major new law, a significant Supreme Court ruling, "
            "a major foreign policy development, or an event with large direct impact on Americans. "
            "Do NOT include routine press statements, daily political commentary, minor executive actions, "
            "or social media posts."
        ),
    },
    {
        "id": "retirement",
        "label": "Personal Finance & Retirement",
        "emoji": "💰",
        "color": "#B7791F",
        "instructions": (
            "Search for 5 relevant and recent news stories about personal finance for retirees "
            "or those approaching retirement (ages 55–75). "
            "Prioritize: Social Security updates, Medicare changes, retirement account rules (IRA/401k), "
            "inflation impact on fixed incomes, interest rates, and practical financial planning advice. "
            "Avoid generic investment tips aimed at young people."
        ),
    },
    {
        "id": "ai",
        "label": "AI Technology & Usage",
        "emoji": "🤖",
        "color": "#6B46C1",
        "instructions": (
            "Search for 5 significant recent stories about artificial intelligence. "
            "Cover new AI tools and model releases, AI being used in real-world applications, "
            "AI policy and regulation news, and practical ways AI is changing everyday life or industries. "
            "Include both technical developments and human-interest angles."
        ),
    },
    {
        "id": "science",
        "label": "Advances in Science",
        "emoji": "🔬",
        "color": "#00718C",
        "instructions": (
            "Search for 5 notable recent scientific discoveries, research breakthroughs, or study findings. "
            "Cover any scientific field: physics, astronomy, climate science, chemistry, biology, "
            "archaeology, geology, or environmental science. Focus on peer-reviewed findings or "
            "significant research milestones — not speculation."
        ),
    },
    {
        "id": "healthcare",
        "label": "Advances in Health Care",
        "emoji": "🏥",
        "color": "#D53F8C",
        "instructions": (
            "Search for 5 significant recent developments in healthcare or medicine. "
            "Include new treatments or therapies, FDA approvals, clinical trial results, "
            "medical research breakthroughs, public health news, and healthcare policy changes "
            "that directly affect patients or healthcare access. "
            "Prioritize findings that have near-term real-world impact."
        ),
    },
    {
        "id": "music",
        "label": "New Music",
        "emoji": "🎵",
        "color": "#E53E3E",
        "instructions": (
            "Search for 5 interesting recent new music stories from the past 2–3 days. "
            "Cover new album or single releases, artist announcements, major tours, "
            "music awards, notable collaborations, and music industry news. "
            "Include a variety of genres — not just pop."
        ),
    },
]


# ─────────────────────────────────────────────────────────────
# NEWS FETCHING
# ─────────────────────────────────────────────────────────────

def fetch_articles_for_topic(client: anthropic.Anthropic, topic: dict) -> list[dict]:
    """
    Calls the Anthropic API with the web_search tool to find
    recent news articles for a given topic. Returns a list of
    article dicts with title, url, source, and summary.

    web_search_20250305 is a server-side tool: Anthropic executes
    the searches automatically between turns. We loop until we get
    an end_turn with a text block containing JSON.
    """

    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = f"""Today is {today}.

{topic['instructions']}

Search the web now and return ONLY a raw JSON array — absolutely no markdown, no code fences, no explanation before or after.

Each element in the array must have exactly these four fields:
  "title"   — the article's actual headline (not paraphrased)
  "url"     — the full, direct URL to the article (must start with https://)
  "source"  — the publication or website name (e.g. "BBC News", "Vermont Digger")
  "summary" — one clear sentence explaining why this story is noteworthy today

Return between 4 and 6 items. Do not duplicate stories."""

    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    for attempt in range(15):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2500,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            print(f"    ✗ API error (attempt {attempt + 1}): {e}")
            break

        stop = response.stop_reason
        block_types = [getattr(b, "type", "?") for b in response.content]
        print(f"    turn {attempt + 1}: stop_reason={stop!r}  blocks={block_types}")

        # Always record the assistant turn so the conversation stays valid
        messages.append({"role": "assistant", "content": response.content})

        if stop == "end_turn":
            # Look for a text block containing our JSON
            for block in response.content:
                text = getattr(block, "text", "").strip()
                if text:
                    print(f"    text snippet: {text[:120]!r}")
                    return parse_articles(text, topic["label"])
            print(f"    ✗ end_turn but no text block found")
            break

        elif stop == "tool_use":
            # The model wants to search — send back empty tool_results so it
            # can continue.  Anthropic fills in the real search results
            # server-side before the next turn begins.
            tool_results = []
            for block in response.content:
                if getattr(block, "type", "") == "tool_use":
                    query = getattr(block, "input", {})
                    print(f"    web_search call: {query}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "",   # server fills this in
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                print(f"    ✗ tool_use stop but no tool_use blocks found")
                break

        elif stop == "max_tokens":
            # Ran out of tokens — try to salvage any text block present
            print(f"    ⚠ max_tokens reached, attempting to parse partial response")
            for block in response.content:
                text = getattr(block, "text", "").strip()
                if text:
                    return parse_articles(text, topic["label"])
            break

        else:
            print(f"    ✗ Unexpected stop_reason={stop!r}")
            break

    print(f"    ✗ No articles retrieved for '{topic['label']}'")
    return []


def parse_articles(text: str, topic_label: str) -> list[dict]:
    """
    Parses a JSON array from the model's response text.
    Strips markdown fences if present and validates structure.
    """
    clean = text.strip()

    # Strip any markdown code fences
    for fence in ["```json", "```JSON", "```"]:
        if clean.startswith(fence):
            clean = clean[len(fence):]
            break
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    # Find the outermost JSON array
    start = clean.find("[")
    end = clean.rfind("]")
    if start == -1 or end == -1:
        print(f"    Parse error: no JSON array found in response for '{topic_label}'")
        return []

    clean = clean[start : end + 1]

    try:
        articles = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"    JSON parse error for '{topic_label}': {e}")
        print(f"    Raw snippet: {clean[:200]}")
        return []

    validated = []
    for a in articles:
        if not isinstance(a, dict):
            continue
        title = str(a.get("title", "")).strip()
        url = str(a.get("url", "")).strip()
        if not title or not url:
            continue
        validated.append({
            "title": title,
            "url": url if url.startswith("http") else f"https://{url}",
            "source": str(a.get("source", "Unknown Source")).strip(),
            "summary": str(a.get("summary", "")).strip(),
        })

    return validated


# ─────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────

def build_html(all_results: list[dict]) -> str:
    today_long = datetime.now().strftime("%A, %B %d, %Y")
    today_short = datetime.now().strftime("%Y-%m-%d")

    # ── Sidebar navigation ──
    nav_items = "".join(
        f'<a href="#{r["id"]}" class="nav-link" style="--accent:{r["color"]}">'
        f'{r["emoji"]}&nbsp; {r["label"]}</a>\n'
        for r in all_results
    )

    # ── Article sections ──
    sections = ""
    for r in all_results:
        articles_html = ""
        if r["articles"]:
            for art in r["articles"]:
                escaped_title = art["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                escaped_summary = art["summary"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                escaped_source = art["source"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                articles_html += f"""
          <div class="article-card">
            <a class="article-title" href="{art['url']}" target="_blank" rel="noopener noreferrer">
              {escaped_title}
            </a>
            <span class="article-source">{escaped_source}</span>
            <p class="article-summary">{escaped_summary}</p>
          </div>"""
        else:
            articles_html = '<p class="empty">No articles found for this topic today.</p>'

        sections += f"""
      <section id="{r['id']}" class="topic-section">
        <h2 class="section-heading" style="border-color:{r['color']}">
          <span class="section-emoji">{r['emoji']}</span>
          {r['label']}
        </h2>
        {articles_html}
        <a class="back-top" href="#page-top">↑ top</a>
      </section>"""

    total_articles = sum(len(r["articles"]) for r in all_results)

    return f"""<!DOCTYPE html>
<html lang="en" id="page-top">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily News Digest · {today_short}</title>
  <style>
    /* ── Reset & tokens ── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg:        #f0f2f5;
      --surface:   #ffffff;
      --border:    #e2e8f0;
      --text:      #1a202c;
      --muted:     #718096;
      --link:      #2b6cb0;
      --header-bg: #1a202c;
      --nav-bg:    #2d3748;
      --nav-text:  #e2e8f0;
      --nav-hover: #4a5568;
      --shadow:    0 1px 6px rgba(0,0,0,.08);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg:      #111827;
        --surface: #1f2937;
        --border:  #374151;
        --text:    #f3f4f6;
        --muted:   #9ca3af;
        --link:    #60a5fa;
        --nav-bg:  #111827;
        --nav-hover: #1f2937;
      }}
    }}

    /* ── Layout ── */
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
             background: var(--bg); color: var(--text); line-height: 1.65; }}

    header {{
      position: sticky; top: 0; z-index: 200;
      background: var(--header-bg); color: #fff;
      padding: 14px 28px;
      display: flex; align-items: center; justify-content: space-between;
      box-shadow: 0 2px 10px rgba(0,0,0,.35);
    }}
    header h1 {{ font-size: 1.2rem; font-weight: 700; letter-spacing: -.01em; }}
    header .meta {{ font-size: .8rem; opacity: .65; }}

    .layout {{ display: flex; min-height: calc(100vh - 58px); }}

    /* ── Sidebar ── */
    nav {{
      width: 230px; min-width: 230px;
      background: var(--nav-bg);
      position: sticky; top: 58px;
      height: calc(100vh - 58px);
      overflow-y: auto;
      padding: 18px 0;
    }}
    nav .nav-label {{
      font-size: .68rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .1em; color: #718096;
      padding: 0 18px 10px;
    }}
    .nav-link {{
      display: block; color: var(--nav-text);
      text-decoration: none; font-size: .87rem;
      padding: 9px 18px;
      border-left: 3px solid transparent;
      transition: background .15s, border-color .15s;
    }}
    .nav-link:hover {{
      background: var(--nav-hover);
      border-left-color: var(--accent);
    }}

    /* ── Main content ── */
    main {{ flex: 1; padding: 28px 32px; max-width: 900px; }}

    .topic-section {{
      background: var(--surface);
      border-radius: 12px;
      padding: 24px 28px 16px;
      margin-bottom: 26px;
      box-shadow: var(--shadow);
    }}
    .section-heading {{
      font-size: 1.15rem; font-weight: 700;
      border-left: 5px solid #ccc;
      padding-left: 12px;
      margin-bottom: 18px;
      display: flex; align-items: center; gap: 8px;
    }}
    .section-emoji {{ font-size: 1.2rem; }}

    .article-card {{
      padding: 14px 0;
      border-bottom: 1px solid var(--border);
    }}
    .article-card:last-of-type {{ border-bottom: none; }}

    .article-title {{
      display: block;
      font-size: .97rem; font-weight: 600;
      color: var(--link); text-decoration: none;
      margin-bottom: 3px; line-height: 1.4;
    }}
    .article-title:hover {{ text-decoration: underline; }}

    .article-source {{
      display: inline-block;
      font-size: .72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: .06em;
      color: var(--muted); margin-bottom: 5px;
    }}
    .article-summary {{
      font-size: .88rem; color: var(--muted); line-height: 1.55;
    }}

    .back-top {{
      display: inline-block; margin-top: 14px;
      font-size: .78rem; color: var(--muted); text-decoration: none;
    }}
    .back-top:hover {{ color: var(--text); }}

    .empty {{ font-style: italic; color: var(--muted); font-size: .9rem; }}

    footer {{
      text-align: center; padding: 22px;
      font-size: .78rem; color: var(--muted);
      border-top: 1px solid var(--border);
    }}

    /* ── Mobile ── */
    @media (max-width: 680px) {{
      nav {{ display: none; }}
      main {{ padding: 16px; }}
      .topic-section {{ padding: 18px 16px 12px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>📰 Daily News Digest</h1>
    <span class="meta">{today_long} · {total_articles} stories across {len(all_results)} topics</span>
  </header>

  <div class="layout">
    <nav>
      <div class="nav-label">Jump to</div>
      {nav_items}
    </nav>
    <main>
      {sections}
    </main>
  </div>

  <footer>
    Built with Claude AI + web search &nbsp;·&nbsp; Refreshed daily at ~6 am ET &nbsp;·&nbsp; {today_long}
  </footer>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n📰  Daily News Digest — {run_time}")
    print("=" * 55)

    all_results = []
    for topic in TOPICS:
        print(f"\n{topic['emoji']}  {topic['label']}...")
        articles = fetch_articles_for_topic(client, topic)
        print(f"    ✓ {len(articles)} articles retrieved")
        all_results.append({**topic, "articles": articles})

    print("\n🏗   Building HTML page...")
    html = build_html(all_results)

    out_path = Path("index.html")
    out_path.write_text(html, encoding="utf-8")

    total = sum(len(r["articles"]) for r in all_results)
    print(f"✅  Saved → {out_path.resolve()}")
    print(f"    {total} total articles across {len(TOPICS)} topics\n")


if __name__ == "__main__":
    main()
