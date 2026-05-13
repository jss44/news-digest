"""
Daily News Digest — fetch_news.py
Fetches top news stories per topic using Claude + web search,
then builds a static HTML page published via GitHub Pages.
"""

import anthropic
import time
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
            "exceptional national importance such as a major new law, a significant Supreme Court ruling, "
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
            "or those approaching retirement ages 55 to 75. "
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
            "significant research milestones, not speculation."
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
            "Search for 5 interesting recent new music stories from the past 2 to 3 days. "
            "Cover new album or single releases, artist announcements, major tours, "
            "music awards, notable collaborations, and music industry news. "
            "Include a variety of genres, not just pop."
        ),
    },
]


# ─────────────────────────────────────────────────────────────
# NEWS FETCHING
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a JSON-only news aggregator API. "
    "Your responses must always be a single raw JSON array and nothing else. "
    "Do not include any explanatory text, greetings, markdown, or code fences. "
    "Do not narrate what you are doing. "
    "Start every response with [ and end with ]."
)


def fetch_articles_for_topic(client, topic):
    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = (
        "Today is " + today + ".\n\n"
        + topic["instructions"] + "\n\n"
        + "Search the web and return a JSON array of 4 to 6 articles. "
        + "Each item must have exactly these four fields:\n"
        + "  title   : exact article headline\n"
        + "  url     : full URL beginning with https://\n"
        + "  source  : publication name such as BBC News or VTDigger\n"
        + "  summary : one sentence explaining why this story matters today\n"
        + "No duplicates. Output only the JSON array."
    )

    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]

    # Rate-limit retry loop
    response = None
    for attempt in range(4):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2500,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.RateLimitError:
            if attempt < 3:
                print("    rate limited, waiting 65s...")
                time.sleep(65)
            else:
                print("    rate limit persists, skipping topic")
                return []
        except anthropic.APIError as e:
            print("    API error: " + str(e))
            return []

    if response is None:
        return []

    block_types = [getattr(b, "type", "?") for b in response.content]
    print("    stop=" + repr(response.stop_reason) + " blocks=" + str(block_types))

    # Collect all non-empty text blocks, try last-to-first (JSON is usually last)
    text_blocks = [
        getattr(b, "text", "").strip()
        for b in response.content
        if getattr(b, "type", "") == "text" and getattr(b, "text", "").strip()
    ]

    if not text_blocks:
        print("    no text blocks found")
        return []

    for text in reversed(text_blocks):
        print("    snippet: " + repr(text[:120]))
        articles = parse_articles(text, topic["label"])
        if articles:
            return articles

    # One correction retry if no JSON was found
    print("    no JSON found, sending correction...")
    try:
        retry = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": (
                    "Your response did not contain a valid JSON array. "
                    "Reply with only the JSON array starting with [ and ending with ]."
                )},
            ],
        )
        for text in reversed([
            getattr(b, "text", "").strip()
            for b in retry.content
            if getattr(b, "type", "") == "text" and getattr(b, "text", "").strip()
        ]):
            print("    retry snippet: " + repr(text[:120]))
            articles = parse_articles(text, topic["label"])
            if articles:
                return articles
    except anthropic.APIError as e:
        print("    retry error: " + str(e))

    print("    giving up on: " + topic["label"])
    return []


def parse_articles(text, topic_label):
    clean = text.strip()

    for fence in ["```json", "```JSON", "```"]:
        if clean.startswith(fence):
            clean = clean[len(fence):]
            break
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    start = clean.find("[")
    end = clean.rfind("]")
    if start == -1 or end == -1:
        print("    no JSON array found for: " + topic_label)
        return []

    try:
        articles = json.loads(clean[start: end + 1])
    except json.JSONDecodeError as e:
        print("    JSON error for " + topic_label + ": " + str(e))
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
            "url": url if url.startswith("http") else "https://" + url,
            "source": str(a.get("source", "Unknown")).strip(),
            "summary": str(a.get("summary", "")).strip(),
        })

    return validated


# ─────────────────────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────────────────────

def build_html(all_results):
    today_long = datetime.now().strftime("%A, %B %d, %Y")
    today_short = datetime.now().strftime("%Y-%m-%d")
    total_articles = sum(len(r["articles"]) for r in all_results)

    nav_items = ""
    for r in all_results:
        nav_items += (
            '<a href="#' + r["id"] + '" class="nav-link" style="--accent:' + r["color"] + '">'
            + r["emoji"] + "&nbsp; " + r["label"] + "</a>\n"
        )

    sections = ""
    for r in all_results:
        if r["articles"]:
            cards = ""
            for art in r["articles"]:
                t = art["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                s = art["summary"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                src = art["source"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                cards += (
                    '<div class="article-card">'
                    '<a class="article-title" href="' + art["url"] + '" target="_blank" rel="noopener noreferrer">' + t + "</a>"
                    '<span class="article-source">' + src + "</span>"
                    '<p class="article-summary">' + s + "</p>"
                    "</div>\n"
                )
        else:
            cards = '<p class="empty">No articles found for this topic today.</p>'

        sections += (
            '<section id="' + r["id"] + '" class="topic-section">'
            '<h2 class="section-heading" style="border-color:' + r["color"] + '">'
            '<span class="section-emoji">' + r["emoji"] + "</span>"
            + r["label"] + "</h2>"
            + cards
            + '<a class="back-top" href="#page-top">top</a>'
            "</section>\n"
        )

    page = """<!DOCTYPE html>
<html lang="en" id="page-top">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily News Digest</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f0f2f5; --surface: #ffffff; --border: #e2e8f0;
      --text: #1a202c; --muted: #718096; --link: #2b6cb0;
      --header-bg: #1a202c; --nav-bg: #2d3748; --nav-text: #e2e8f0;
      --nav-hover: #4a5568; --shadow: 0 1px 6px rgba(0,0,0,.08);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #111827; --surface: #1f2937; --border: #374151;
        --text: #f3f4f6; --muted: #9ca3af; --link: #60a5fa;
        --nav-bg: #111827; --nav-hover: #1f2937;
      }
    }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
           background: var(--bg); color: var(--text); line-height: 1.65; }
    header {
      position: sticky; top: 0; z-index: 200; background: var(--header-bg); color: #fff;
      padding: 14px 28px; display: flex; align-items: center; justify-content: space-between;
      box-shadow: 0 2px 10px rgba(0,0,0,.35);
    }
    header h1 { font-size: 1.2rem; font-weight: 700; }
    header .meta { font-size: .8rem; opacity: .65; }
    .layout { display: flex; min-height: calc(100vh - 58px); }
    nav {
      width: 230px; min-width: 230px; background: var(--nav-bg);
      position: sticky; top: 58px; height: calc(100vh - 58px);
      overflow-y: auto; padding: 18px 0;
    }
    nav .nav-label {
      font-size: .68rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: .1em; color: #718096; padding: 0 18px 10px;
    }
    .nav-link {
      display: block; color: var(--nav-text); text-decoration: none;
      font-size: .87rem; padding: 9px 18px; border-left: 3px solid transparent;
      transition: background .15s, border-color .15s;
    }
    .nav-link:hover { background: var(--nav-hover); border-left-color: var(--accent); }
    main { flex: 1; padding: 28px 32px; max-width: 900px; }
    .topic-section {
      background: var(--surface); border-radius: 12px;
      padding: 24px 28px 16px; margin-bottom: 26px; box-shadow: var(--shadow);
    }
    .section-heading {
      font-size: 1.15rem; font-weight: 700; border-left: 5px solid #ccc;
      padding-left: 12px; margin-bottom: 18px; display: flex; align-items: center; gap: 8px;
    }
    .section-emoji { font-size: 1.2rem; }
    .article-card { padding: 14px 0; border-bottom: 1px solid var(--border); }
    .article-card:last-of-type { border-bottom: none; }
    .article-title {
      display: block; font-size: .97rem; font-weight: 600; color: var(--link);
      text-decoration: none; margin-bottom: 3px; line-height: 1.4;
    }
    .article-title:hover { text-decoration: underline; }
    .article-source {
      display: block; font-size: .72rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: 5px;
    }
    .article-summary { font-size: .88rem; color: var(--muted); line-height: 1.55; }
    .back-top { display: inline-block; margin-top: 14px; font-size: .78rem; color: var(--muted); text-decoration: none; }
    .back-top:hover { color: var(--text); }
    .empty { font-style: italic; color: var(--muted); font-size: .9rem; }
    footer { text-align: center; padding: 22px; font-size: .78rem; color: var(--muted); border-top: 1px solid var(--border); }
    @media (max-width: 680px) { nav { display: none; } main { padding: 16px; } }
  </style>
</head>
<body>
  <header>
    <h1>Daily News Digest</h1>
    <span class="meta">DATE &middot; COUNT stories across NTOPICS topics</span>
  </header>
  <div class="layout">
    <nav><div class="nav-label">Jump to</div>NAV</nav>
    <main>SECTIONS</main>
  </div>
  <footer>Built with Claude AI + web search &middot; Refreshed daily at ~6 am ET &middot; DATE</footer>
</body>
</html>"""

    page = page.replace("DATE", today_long)
    page = page.replace("COUNT", str(total_articles))
    page = page.replace("NTOPICS", str(len(all_results)))
    page = page.replace("NAV", nav_items)
    page = page.replace("SECTIONS", sections)

    return page


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    print("\nDaily News Digest — " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 55)

    all_results = []
    for i, topic in enumerate(TOPICS):
        print("\n" + topic["emoji"] + "  " + topic["label"] + "...")
        articles = fetch_articles_for_topic(client, topic)
        print("    " + str(len(articles)) + " articles retrieved")
        all_results.append({**topic, "articles": articles})
        if i < len(TOPICS) - 1:
            time.sleep(5)

    print("\nBuilding HTML page...")
    html = build_html(all_results)
    Path("index.html").write_text(html, encoding="utf-8")

    total = sum(len(r["articles"]) for r in all_results)
    print("Done. " + str(total) + " total articles across " + str(len(TOPICS)) + " topics.\n")


if __name__ == "__main__":
    main()
