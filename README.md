<div align="center">

# Microsoft To Do — Eisenhower Matrix Desktop Wallpaper

![GitHub License](https://img.shields.io/github/license/Cfomodz/parallax-studio-pro)
![GitHub Sponsors](https://img.shields.io/github/sponsors/Cfomodz)
![Discord](https://img.shields.io/discord/425182625032962049)

</div>

#### Generate a Windows 11 desktop wallpaper from your [Microsoft To Do](https://to-do.microsoft.com/) tasks. Tasks are placed on an Eisenhower Matrix (Value vs Effort) based on which **list** they belong to, and the image is set as your desktop background — automatically.

- **Q1 — Do it now:** High value, low effort
- **Q2 — Do it next:** High value, high effort
- **Q3 — Do it if/when there is time:** Low value, low effort
- **Q4 — Don't do it:** Low value, high effort

## Features

- **Completely portable** — single PowerShell script, no Python, no installs
- **No admin privileges** required
- **No Azure app registration** — uses Microsoft's own first-party client ID
- **One-time browser sign-in** — tokens are cached, subsequent runs are silent
- **Auto-refresh** via Windows Task Scheduler

## Requirements

- Windows 10 or 11
- PowerShell 5.1 (ships with Windows — no install needed)
- A Microsoft account signed into [Microsoft To Do](https://to-do.microsoft.com/)

## Setup

### 1. Create your Eisenhower lists in Microsoft To Do

Create up to 4 lists with names that match the quadrants. The default mapping (case-insensitive):

| Quadrant | Recognized list names |
|----------|----------------------|
| **Q1** — Do it now | `Do it now`, `Do first`, `Urgent`, `Q1` |
| **Q2** — Do it next | `Do it next`, `Schedule`, `Planned`, `Q2` |
| **Q3** — If time | `Do if extra time`, `If time`, `Someday`, `Q3` |
| **Q4** — Don't do | `Don't do`, `Don't do it`, `Eliminate`, `Q4` |

You can customize the mapping by editing the `$Config.ListMapping` hashtable at the top of `eisenhower-wallpaper.ps1`.

### 2. Run

```powershell
powershell -ExecutionPolicy Bypass -File eisenhower-wallpaper.ps1
```

**First run:** a browser window opens and asks you to sign in to your Microsoft account. Enter the code shown in the terminal. After that, tokens are cached in `.token_cache.json` — future runs are fully automatic.

### 3. (Optional) Auto-refresh on a schedule

```powershell
.\install-task.ps1                     # every 30 minutes (default)
.\install-task.ps1 -IntervalMinutes 15 # every 15 minutes
```

This creates a Windows Task Scheduler entry. To remove it:

```powershell
Unregister-ScheduledTask -TaskName 'TodoEisenhowerMatrixWallpaper'
```

## Configuration

All settings are at the top of `eisenhower-wallpaper.ps1`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OutputPath` | `~/Pictures/todo_matrix_wallpaper.png` | Where the image is saved |
| `Width` / `Height` | `1920` / `1080` | Image resolution |
| `FontFamily` | `Segoe UI` | Windows system font |
| `TenantId` | `consumers` | `consumers` for personal accounts, `common` for any, or your org tenant ID |
| `MaxNotesPerQuadrant` | `6` | Max sticky notes per quadrant |
| `ListMapping` | *(see above)* | Map To Do list names → quadrants |

## How auth works

The script uses [device code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) with Microsoft's first-party Graph CLI client ID (`14d82eec-204b-4c2f-b7e8-296a70dab67e`). This means:

- **No app registration** on your part
- You sign in once via browser, then a refresh token is cached locally in `.token_cache.json`
- Only `Tasks.Read` permission is requested (read-only access to your To Do tasks)
- Revoke access anytime at [account.microsoft.com → Security → App permissions](https://account.live.com/consent/Manage)

## License

MIT — see [LICENSE](LICENSE).
