# SpaceX Launch Tracker 🚀

**100% free, runs on GitHub Actions**

Checks for new SpaceX launches every 10 minutes and posts rich Discord notifications with monthly launch counts.

---

## What you get in Discord

Every time a new SpaceX launch is added:

> 🚀 **New SpaceX Launch Detected**
> **Starlink Group 10-3**
> *5th SpaceX launch scheduled in March 2026*
>
> **Vehicle:** Falcon 9  
> **Status:** Go  
> **Monthly Count:** 5th of 8 scheduled · 3 already launched  
> **Launch Time (NET):** Mar 15, 2026 at 2:45 AM UTC  
> **Pad:** SLC-40, Cape Canaveral  
> **Mission:** Deploy 23 Starlink satellites to low Earth orbit  

---

## Setup (5 minutes)

### Step 1: Get your Discord webhook

1. Open Discord → go to the channel where you want notifications
2. Click the gear icon ⚙️ → **Integrations** → **Webhooks** → **New Webhook**
3. Name it "SpaceX Tracker"
4. Click **Copy Webhook URL**
5. Keep this URL handy for Step 3

### Step 2: Fork this repo

1. Click the **Fork** button at the top right of this page
2. This creates your own copy of the tracker in your GitHub account

### Step 3: Add your webhook URL

1. In **your forked repo**, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `DISCORD_WEBHOOK`
4. Value: paste your webhook URL from Step 1
5. Click **Add secret**

### Step 4: Enable GitHub Actions

1. Go to the **Actions** tab in your repo
2. Click **"I understand my workflows, go ahead and enable them"**
3. Done! The tracker will run automatically every 10 minutes

---

## Testing it works

**Option 1 — Wait 10 minutes**  
The tracker runs automatically on a schedule. Check the **Actions** tab to see the runs.

**Option 2 — Trigger it manually (instant)**  
1. Go to **Actions** tab → click **SpaceX Launch Tracker** workflow
2. Click **Run workflow** → **Run workflow**
3. Check your Discord channel — if there are new launches since the tracker last ran, you'll get notifications

**First run behavior:**  
On the very first run, the tracker seeds all current SpaceX launches into `seen_ids.json` **without** sending Discord notifications (to avoid spamming you with 20+ messages). From the second run onwards, it only notifies about genuinely new launches.

---

## How it works

Every 10 minutes, GitHub Actions:
1. Runs `tracker.py` which queries The Space Devs LL2 API
2. Compares current SpaceX launches against `seen_ids.json`
3. Posts to Discord for any new launches with monthly context
4. Commits updated `seen_ids.json` back to the repo

**Monthly count logic:**  
The tracker queries both upcoming and past SpaceX launches within the current UTC month, sorts them by NET (No Earlier Than) date, and assigns each an ordinal position. This count includes all scheduled launches for the month, whether they've flown or not.

---

## Free tier usage

- **GitHub Actions:** 2,000 minutes/month free
- **This tracker uses:** ~720 minutes/month (10-minute polls × 6 per hour × 24 hours × 30 days × ~10 seconds per run)
- **You're using:** 36% of the free tier ✓

**The Space Devs LL2 API:** 15 requests/hour free. The tracker makes 2 API calls per run (upcoming + monthly data) = 12 requests/hour. Stays safely within limits.

---

## Customization

Edit `.github/workflows/tracker.yml` to change the schedule:

```yaml
# Every 10 minutes (default)
- cron: '*/10 * * * *'

# Every 5 minutes (more responsive, uses more Actions minutes)
- cron: '*/5 * * * *'

# Every 15 minutes (more conservative)
- cron: '*/15 * * * *'

# Every hour
- cron: '0 * * * *'
```

---

## Troubleshooting

**No Discord messages appearing:**
- Check **Actions** tab → latest run → logs for errors
- Verify `DISCORD_WEBHOOK` secret is set correctly
- Make sure GitHub Actions is enabled (Actions tab)

**"Rate limited" in logs:**
- The tracker automatically handles this by skipping the run
- Next run (10 min later) will succeed

**Want to track a different agency:**
- Edit `tracker.py` line 13: change `lsp__name=SpaceX` to another agency name
- Example: `lsp__name=Rocket Lab` or `lsp__name=NASA`

---

## Credits

- Data: [The Space Devs Launch Library 2 API](https://thespacedevs.com/llapi)
- Runs on: [GitHub Actions](https://github.com/features/actions) (free tier)
