<div align="center">

# Microsoft To Do Eisenhower Matrix Desktop Wallpaper for Windows 11

![GitHub License](https://img.shields.io/github/license/Cfomodz/parallax-studio-pro)
![GitHub Sponsors](https://img.shields.io/github/sponsors/Cfomodz)
![Discord](https://img.shields.io/discord/425182625032962049)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

</div>

#### Generate a Windows 11 desktop wallpaper from your [Microsoft To Do](https://to-do.microsoft.com/) tasks: tasks are placed on an Eisenhower matrix (Value vs Effort) by **list name**, and the image is set as your desktop background.

- **Q1 — Do it now:** High value, low effort
- **Q2 — Do it next:** High value, high effort
- **Q3 — Do it if/when there is time:** Low value, low effort
- **Q4 — Don't do it:** Low value, high effort

Create lists in Microsoft To Do named after each quadrant (e.g. "Do it now", "Do it next", "Do if extra time", "Don't do"), and incomplete tasks in those lists appear as sticky notes on your wallpaper.

## Requirements

- Windows 11 (or 10)
- Python 3.8+
- [Pillow](https://pypi.org/project/Pillow/) (PIL)
- [requests](https://pypi.org/project/requests/)
- [msal](https://pypi.org/project/msal/) (Microsoft Authentication Library)

## Install

```powershell
git clone https://github.com/Cfomodz/Plane-Eisenhower-Matrix-Desktop-Wallpaper-for-KDE-Plasma.git
cd Plane-Eisenhower-Matrix-Desktop-Wallpaper-for-KDE-Plasma
pip install -r requirements.txt
```

## Azure App Registration

Microsoft To Do uses the Microsoft Graph API, which requires an app registration:

1. Go to the [Azure Portal — App registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade).
2. Click **New registration**.
3. Name it anything (e.g. "Eisenhower Wallpaper").
4. Under **Supported account types**, select **Personal Microsoft accounts only** (or whichever fits your use case).
5. Set **Redirect URI** to **Public client/native (mobile & desktop)** with value `http://localhost`.
6. Click **Register**.
7. Copy the **Application (client) ID** — this is your `MS_CLIENT_ID`.
8. Under **API permissions**, click **Add a permission** → **Microsoft Graph** → **Delegated permissions** → search for `Tasks.Read` → **Add**.
9. No client secret is needed (this uses the device code flow for public clients).

## Configuration

1. Copy the example env file and edit it:

   ```powershell
   copy .env.example .env
   ```

2. Set in `.env`:
   - **`MS_CLIENT_ID`** — The Application (client) ID from your Azure app registration.
   - **`MS_TENANT_ID`** — `consumers` for personal Microsoft accounts (default), `common` for any account type, or your specific tenant ID.

3. Optional: adjust output path, resolution, or fonts (see `.env.example`).

### List-to-Quadrant Mapping

Tasks are assigned to quadrants based on which **Microsoft To Do list** they belong to. The default mapping recognizes these list names (case-insensitive):

| Quadrant | List names recognized |
|----------|----------------------|
| Q1 (Do it now) | "Do it now", "Do first", "Urgent", "Q1" |
| Q2 (Do it next) | "Do it next", "Schedule", "Planned", "Q2" |
| Q3 (If time) | "Do if extra time", "If time", "Someday", "Q3" |
| Q4 (Don't do) | "Don't do", "Don't do it", "Eliminate", "Q4" |

You can customize the mapping in `desktop_background.py` in `CONFIG["LIST_TO_QUADRANT"]`. Lists not in the mapping are ignored.

## Usage

```powershell
python desktop_background.py
```

On first run, you'll be prompted to log in via a device code flow (visit a URL and enter a code). After that, tokens are cached in `.ms_token_cache.bin` so subsequent runs are automatic.

- Fetches your To Do lists and incomplete tasks.
- Maps each task to a quadrant by its list name.
- Renders the matrix to `TODO_MATRIX_OUTPUT_PATH` (default: `~/Pictures/todo_matrix_wallpaper.png`).
- Sets the image as the Windows desktop wallpaper.

### Refreshing on a schedule (Task Scheduler)

From the repo directory in PowerShell:

```powershell
.\install-task.ps1                     # every 30 minutes (default)
.\install-task.ps1 -IntervalMinutes 15 # every 15 minutes
```

This creates a Windows Task Scheduler entry that runs automatically. To remove it:

```powershell
Unregister-ScheduledTask -TaskName "TodoEisenhowerMatrixWallpaper"
```

## License

MIT — see [LICENSE](LICENSE).
