# Manual Installation Guide

This guide walks you through setting up Libra manually, without using the setup script.

## Requirements

- Windows 10 or 11
- Internet connection (first-time setup only)

## Step 1: Install Docker Desktop

1. Go to [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).
2. Download and install Docker Desktop.
3. Restart your computer.
4. Open Docker Desktop and wait until it says **"Docker Desktop is running"**.

## Step 2: Get a Together AI API Key

1. Go to [together.ai](https://www.together.ai/) and create a free account.
2. Go to **Settings → API Keys**.
3. Click **Create API Key** and copy it.

## Step 3: Copy the Project Files

1. Copy the **libra-1** folder from the USB drive to your Desktop.

## Step 4: Set Up the Environment File

1. Open the **libra-1** folder.
2. Find the file called `.env.example`.
3. Make a copy of it and rename the copy to `.env`.
4. Open `.env` with Notepad.
5. Replace `your_together_api_key_here` with the API key you copied earlier.
6. Save and close the file.

## Step 5: Build and Start Libra

1. Open **Command Prompt** or **PowerShell**.
2. Navigate to the libra-1 folder:
   ```
   cd %USERPROFILE%\Desktop\libra-1
   ```
3. Build and start the application:
   ```
   docker compose up --build -d
   ```
4. Wait for the build to finish. This takes about 10–15 minutes the first time.

## Step 6: Open Libra

1. Open your browser.
2. Go to **http://localhost**.
3. If the page does not load, wait 2–3 minutes and try again. The backend needs time to initialize on first launch.

## Stopping Libra

Open a terminal in the libra-1 folder and run:
```
docker compose down
```

## Starting Libra Again

Open Docker Desktop, then open a terminal in the libra-1 folder and run:
```
docker compose up -d
```
No rebuild is needed after the first time.
