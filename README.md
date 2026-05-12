[README.md](https://github.com/user-attachments/files/27650356/README.md)
# 📰 Daily News Digest

A self-updating news page, refreshed every morning at ~6 am ET.
Hosted free on GitHub Pages. Powered by Claude AI + web search.

**Your page URL will be:** `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

---

## What it does

Every morning GitHub runs `fetch_news.py`, which asks Claude to search the web
for fresh stories across your 8 topics, then builds a clean HTML page and
publishes it automatically. You just visit the link.

---

## One-time Setup (~15 minutes)

### Step 1 — Create a GitHub account (if you don't have one)
Go to [github.com](https://github.com) and sign up. It's free.

---

### Step 2 — Create a new repository

1. Click the **+** button (top right) → **New repository**
2. Name it something like `news-digest` or `daily-news`
3. Set it to **Public** *(required for free GitHub Pages)*
4. Check **"Add a README file"**
5. Click **Create repository**

---

### Step 3 — Upload the project files

You need to add these files to your repo in exactly this structure:

```
your-repo/
├── fetch_news.py
├── index.html              ← will be auto-generated on first run
└── .github/
    └── workflows/
        └── daily_news.yml
```

**Easiest way — GitHub web upload:**

1. Open your new repository on GitHub
2. Click **Add file → Upload files**
3. Upload `fetch_news.py`
4. Click **Commit changes**

For the workflow file, you need to create the folder structure manually:
1. Click **Add file → Create new file**
2. In the filename box type: `.github/workflows/daily_news.yml`
   (GitHub will create the folders automatically as you type the `/`)
3. Paste the full contents of `daily_news.yml` into the editor
4. Click **Commit changes**

---

### Step 4 — Get an Anthropic API key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Go to **API Keys** → **Create Key**
4. Copy the key (starts with `sk-ant-...`) — you only see it once

**Cost note:** Each daily run makes ~8 API calls (one per topic).
Estimated cost: **$0.05–0.20 per day** depending on search depth.
Anthropic gives new accounts some free credits to start.

---

### Step 5 — Add your API key to GitHub Secrets

1. In your GitHub repo, click **Settings** (top tab)
2. Left sidebar → **Secrets and variables → Actions**
3. Click **New repository secret**
4. Name: `ANTHROPIC_API_KEY`
5. Value: paste your `sk-ant-...` key
6. Click **Add secret**

---

### Step 6 — Enable GitHub Pages

1. In your repo, go to **Settings → Pages** (left sidebar)
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main` / Folder: `/ (root)`
4. Click **Save**

GitHub will show you your page URL — save it!
It looks like: `https://YOUR-USERNAME.github.io/news-digest/`

---

### Step 7 — Run it for the first time

Don't wait until 6 am — trigger it now:

1. In your repo, click the **Actions** tab
2. Click **Daily News Digest** (left sidebar)
3. Click **Run workflow → Run workflow**
4. Watch it run (takes ~2–3 minutes)
5. When it's green ✅, visit your GitHub Pages URL

---

## Customizing topics

Open `fetch_news.py` in GitHub (click the file, then the pencil ✏️ icon).

The `TOPICS` list at the top of the file is where everything lives.
Each topic has:
- `label` — the section heading shown on the page
- `emoji` — the icon next to the heading
- `color` — the accent color for that section (hex code)
- `instructions` — the prompt sent to Claude (edit this to change what it finds)

After editing, click **Commit changes** and the next run will use your new settings.

---

## Timing notes

- GitHub Actions uses UTC time. The workflow is set to `0 11 * * *` (11:00 UTC).
- **Winter (EST, Nov–Mar):** runs at exactly 6:00 am
- **Summer (EDT, Apr–Oct):** runs at 7:00 am
- To flip this, change `0 11` to `0 10` in the workflow file
- GitHub sometimes delays scheduled runs by up to 15 minutes if their servers are busy

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Workflow fails with "API key" error | Double-check the secret name is exactly `ANTHROPIC_API_KEY` |
| Workflow fails with permissions error | Confirm **Settings → Actions → General → Workflow permissions** is set to "Read and write" |
| Page shows "no articles found" | The API call may have timed out — try a manual re-run |
| Page URL gives 404 | GitHub Pages can take 5–10 minutes to activate after first enabling it |
| Actions tab shows no workflows | Make sure the file is at `.github/workflows/daily_news.yml` exactly |

---

## Files in this project

| File | Purpose |
|---|---|
| `fetch_news.py` | Main script — fetches news, builds `index.html` |
| `.github/workflows/daily_news.yml` | Scheduler — runs the script at 6 am ET daily |
| `index.html` | Your news page — auto-generated, don't edit by hand |

---

*Built with [Claude AI](https://claude.ai) · [Anthropic API docs](https://docs.anthropic.com)*
