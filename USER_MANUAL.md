# User Manual — Installation

## Requirements

- Windows 10 or 11
- Internet connection (first-time setup only)
- Together AI API key — get one free at [together.ai](https://www.together.ai/)

## Setup

1. Copy the **libra** folder from the USB drive to your Desktop.
2. Open the folder and double-click **`setup.bat`**.
3. If Docker is not installed, the script will open the download page. Install it, restart your computer, then run `setup.bat` again.
4. When prompted, type **Y** and paste your API key.
5. Wait for the build to finish. This takes about 10–15 minutes on the first run.
6. Open your browser and go to **http://localhost**.

## Starting and Stopping

- **To start:** Open Docker Desktop, then double-click `setup.bat`.
- **To stop:** Open a terminal in the libra folder and run `docker compose down`.

## Common Issues

- **"Docker is not running"** — Open Docker Desktop and wait for it to fully load.
- **Page won't load** — The backend takes 2–3 minutes to start on first launch. Wait and refresh.
- **Wrong API key** — Delete the `.env` file in the libra folder, then run `setup.bat` again.
