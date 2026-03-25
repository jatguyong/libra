# Libra — Installation Guide

## What You Need

- **Windows 10/11** (64-bit)
- **Together AI API Key** (free) — [Sign up here](https://www.together.ai/)

> **That's it.** The setup script will handle Docker and everything else.

---

## Installation Steps

### Step 1: Copy from USB

Copy the `libra-1` folder from the USB drive to your computer (e.g., your Desktop).

### Step 2: Run Setup

1. Open the `libra-1` folder.
2. **Double-click `setup.bat`**.
3. The script will:
   - Install Docker Desktop if needed (opens the download page)
   - Ask you to paste your Together AI API key
   - Build and start Libra automatically

> **First-time setup takes 10–15 minutes** while it downloads dependencies. Subsequent starts are instant.

### Step 3: Open Libra

Once setup completes, open your browser and go to:

```
http://localhost
```

---

## Daily Use

| Action | How |
|--------|-----|
| **Start Libra** | Open Docker Desktop, then double-click `setup.bat` |
| **Stop Libra** | Run `docker compose down` in the folder, or stop containers in Docker Desktop |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `setup.bat` opens a Docker download page | Install Docker Desktop, restart your PC, then run `setup.bat` again |
| Build fails with network errors | Check your internet connection — first build needs to download packages |
| Page doesn't load at `http://localhost` | Wait 2–3 minutes — the backend initializes the knowledge base on first run |
| "API key" errors | Delete the `.env` file and run `setup.bat` again to re-enter your key |
