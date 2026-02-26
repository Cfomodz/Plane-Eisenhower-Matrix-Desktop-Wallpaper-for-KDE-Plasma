<div align="center">

# Plane Eisenhower Matrix Desktop Wallpaper

![GitHub License](https://img.shields.io/github/license/Cfomodz/parallax-studio-pro)
![GitHub Sponsors](https://img.shields.io/github/sponsors/Cfomodz)
![Discord](https://img.shields.io/discord/425182625032962049)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

<img src="https://github.com/user-attachments/assets/36973ddd-0b1f-4013-a367-9056c4299a68" alt="matrix icon" width="300"/>

</div>

#### Generate a desktop wallpaper from your [Plane](https://plane.so) project: issues are placed on an Eisenhower matrix (Value vs Effort) by **status**, and the image is set as your desktop background.

Supports **Windows 10/11**, **macOS**, **GNOME**, and **KDE Plasma**. The script auto-detects your platform.

- **Q1 — Do it now:** High value, low effort
- **Q2 — Do it next:** High value, high effort
- **Q3 — Do it if/when there is time:** Low value, low effort
- **Q4 — Don't do it:** Low value, high effort

<div align="center">

<img width="1000" src="https://github.com/user-attachments/assets/b9e5eba9-6c8f-40e0-ba4e-d9df9fc44df8" />

</div>

Works with self-hosted Plane and Plane Cloud.

## Requirements

- Python 3.8+
- [Pillow](https://pypi.org/project/Pillow/) (PIL)
- [requests](https://pypi.org/project/requests/)
- **Windows 10/11** — wallpaper is set via the Win32 API (no extra dependencies)
- **macOS** — wallpaper is set via AppleScript (`osascript`)
- **GNOME** (Ubuntu, Fedora Workstation, etc.) — wallpaper is set via `gsettings`
- **KDE Plasma** — wallpaper is set via DBus (`qdbus`)
- On other desktops, the generated image can still be used manually.

## Install

```bash
git clone https://github.com/YOUR_USERNAME/eisenhower_matrix_desktop_background_from_plane.git
cd eisenhower_matrix_desktop_background_from_plane
pip install -r requirements.txt
```

## Configuration

1. Copy the example env file and edit it:

   ```bash
   cp .env.example .env          # Linux / macOS / Git Bash
   copy .env.example .env         # Windows Command Prompt
   ```

2. Set in `.env`:
   - **`PLANE_PROJECT_URL`** — Paste the full project URL from your browser (e.g. the issues page). The script parses base URL, workspace slug, and project ID from it.
   - **`PLANE_API_KEY`** — API token from **Profile → API Tokens** in Plane.
   - You can instead set `PLANE_BASE_URL`, `PLANE_WORKSPACE_SLUG`, and `PLANE_PROJECT_ID` separately if you prefer.

3. Optional: adjust output path, resolution, or fonts (see `.env.example`).
   - Font paths are auto-detected per platform (Segoe UI on Windows, SF/Helvetica on macOS, Noto Sans on Linux).

Quadrant mapping is driven by your **workflow state names** in Plane (e.g. "Do first", "Do it next", "Do if extra time"). You can change the mapping in `desktop_background.py` in `CONFIG["STATE_TO_QUADRANT"]`.

## Usage

```bash
python desktop_background.py
```

- Fetches issues from the configured project (with `expand=state`).
- Maps each issue to a quadrant by its status.
- Renders the matrix to the path in `PLANE_MATRIX_OUTPUT_PATH` (default: `~/Pictures/plane_matrix_wallpaper.png`).
- Auto-detects the platform and sets the desktop wallpaper:
  - **Windows** — Win32 `SystemParametersInfoW` API
  - **macOS** — AppleScript via `osascript`
  - **GNOME** — `gsettings` (sets both light and dark wallpaper)
  - **KDE Plasma** — DBus `qdbus` with cache refresh
  - **Other** — prints the image path for manual use

### Refreshing on a schedule

#### Linux (cron)

From the repo directory, run:

```bash
./install-cron.sh [interval_minutes]
```

Example: `./install-cron.sh 30` adds a cron job to run every 30 minutes. It replaces any existing `desktop_background.py` cron entry. Omit the argument to use 30 minutes.

To remove the job later: `crontab -e` and delete the line.

#### macOS (launchd)

From the repo directory, run:

```bash
./install-launchd.sh [interval_minutes]
```

Example: `./install-launchd.sh 30` creates a launch agent that runs every 30 minutes and on login. Omit the argument to use 30 minutes.

To remove the agent later:

```bash
launchctl bootout gui/$(id -u)/com.plane.eisenhower-matrix-wallpaper
rm ~/Library/LaunchAgents/com.plane.eisenhower-matrix-wallpaper.plist
```

#### Windows (Task Scheduler)

From the repo directory in PowerShell, run:

```powershell
powershell -ExecutionPolicy Bypass -File install-task.ps1 [interval_minutes]
```

Example: `.\install-task.ps1 30` creates a scheduled task that runs every 30 minutes. Omit the argument to use 30 minutes.

To remove the task later:

```powershell
Unregister-ScheduledTask -TaskName "PlaneEisenhowerMatrixWallpaper"
```

## License

MIT — see [LICENSE](LICENSE).
