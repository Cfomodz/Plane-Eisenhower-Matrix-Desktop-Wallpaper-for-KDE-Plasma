import requests
import json
import subprocess
import os
import re
import sys
import time
import platform
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFont
import textwrap
import math

# Load .env if present (optional dependency: pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# CONFIGURATION (env: .env or environment variables)
# ==========================================
def _env(key, default=None):
    return os.environ.get(key, default)

def _resolution():
    r = _env("PLANE_MATRIX_RESOLUTION", "1920x1080")
    try:
        w, h = r.strip().lower().split("x")
        return (int(w), int(h))
    except Exception:
        return (1920, 1080)


def _parse_project_url(url):
    """
    Parse a full Plane project URL into base URL, workspace slug, and project ID.
    e.g. http://localhost:8080/radnom/projects/cf6bdea1-24bb-4ff3-9719-10b803fae577/issues/
    -> (http://localhost:8080, radnom, cf6bdea1-24bb-4ff3-9719-10b803fae577)
    """
    url = (url or "").strip()
    if not url:
        return None, None, None
    parsed = urlparse(url)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc}".rstrip("/")
    path = (parsed.path or "").strip("/")
    parts = [p for p in path.split("/") if p]
    try:
        i = parts.index("projects")
        workspace_slug = parts[i - 1] if i > 0 else None
        project_id = parts[i + 1] if i + 1 < len(parts) else None
        # project_id should look like a UUID
        if project_id and not re.match(r"^[0-9a-fA-F-]{36}$", project_id):
            project_id = None
        return base, workspace_slug, project_id
    except ValueError:
        return base, None, None


def _plane_config_from_env():
    """Build (base_url, api_key, workspace_slug, project_id) from env, preferring PLANE_PROJECT_URL."""
    project_url = _env("PLANE_PROJECT_URL", "").strip()
    if project_url:
        base, workspace, project_id = _parse_project_url(project_url)
        return (
            base or _env("PLANE_BASE_URL", "http://localhost:8080").rstrip("/"),
            _env("PLANE_API_KEY", ""),
            workspace or _env("PLANE_WORKSPACE_SLUG", ""),
            project_id or _env("PLANE_PROJECT_ID", ""),
        )
    return (
        _env("PLANE_BASE_URL", "http://localhost:8080").rstrip("/"),
        _env("PLANE_API_KEY", ""),
        _env("PLANE_WORKSPACE_SLUG", ""),
        _env("PLANE_PROJECT_ID", ""),
    )


_plane_base, _plane_key, _plane_workspace, _plane_project = _plane_config_from_env()

def _default_font_path(bold=False):
    """Return a sensible default font path for the current platform."""
    if platform.system() == "Windows":
        base = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        return os.path.join(base, "segoeui" + ("b" if bold else "") + ".ttf")
    return "/usr/share/fonts/noto/NotoSans-" + ("Bold" if bold else "Regular") + ".ttf"

CONFIG = {
    # PLANE API (from .env: PLANE_PROJECT_URL + PLANE_API_KEY, or separate vars)
    "PLANE_BASE_URL": _plane_base,
    "API_KEY": _plane_key,
    "WORKSPACE_SLUG": _plane_workspace,
    "PROJECT_ID": _plane_project,

    # OUTPUT & DISPLAY
    "OUTPUT_PATH": _env("PLANE_MATRIX_OUTPUT_PATH") or os.path.expanduser("~/Pictures/plane_matrix_wallpaper.png"),
    "RESOLUTION": _resolution(),
    "FONT_PATH": _env("PLANE_MATRIX_FONT_PATH", _default_font_path(bold=False)),
    "FONT_BOLD_PATH": _env("PLANE_MATRIX_FONT_BOLD_PATH", _default_font_path(bold=True)),

    # VISUAL SETTINGS
    "NOTE_SIZE": (200, 200),
    "NOTE_PADDING": 20, # Space between notes
    "MAX_NOTES_PER_QUADRANT": 6,  # Max notes shown per quadrant

    # STATE → QUADRANT (status name → matrix quadrant; case-insensitive)
    # Customize in code or extend via env if you add support.
    "STATE_TO_QUADRANT": {
        "do first": "q1",
        "do it now": "q1",
        "in progress": "q1",
        "started": "q1",
        "do it next": "q2",
        "next": "q2",
        "planned": "q2",
        "schedule": "q2",
        "do if extra time": "q3",
        "if time": "q3",
        "backlog": "q3",
        "unstarted": "q3",
        "don't do": "q4",
        "don't do it": "q4",
        "won't do": "q4",
        "cancelled": "q4",
    },
}

# Colors based on your image
COLORS = {
    "background": "#FFFFFF",
    "axis": "#333333",
    "text_main": "#000000",
    "q1_note": "#89C4F4", # Blue (Do it now) - High Value, Low Effort
    "q2_note": "#F4B37D", # Orange (Do it next) - High Value, High Effort
    "q3_note": "#FCE373", # Yellow (If time) - Low Value, Low Effort
    "q4_note": "#9CA3AF",  # Grey (Don't do)
}

# ==========================================
# PLANE API HANDLER
# ==========================================
def get_plane_issues():
    """Fetches issues from Plane."""
    url = f"{CONFIG['PLANE_BASE_URL']}/api/v1/workspaces/{CONFIG['WORKSPACE_SLUG']}/projects/{CONFIG['PROJECT_ID']}/issues/"
    headers = {
        "x-api-key": CONFIG["API_KEY"],
        "Content-Type": "application/json"
    }
    
    # Request state details so we can categorize by status name
    try:
        response = requests.get(url, headers=headers, params={"expand": "state"})
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"Error fetching from Plane: {e}")
        return []

def categorize_issue(issue):
    """
    Determines which quadrant an issue belongs to using its status (state name).
    Configure STATE_TO_QUADRANT in CONFIG to match your Plane workflow states.

    Returns: 'q1', 'q2', 'q3', 'q4' or None (to skip)
    """
    state = issue.get("state")
    if not state or not isinstance(state, dict):
        return "q3"  # default when state not expanded or missing

    state_name = (state.get("name") or "").strip().lower()
    mapping = CONFIG.get("STATE_TO_QUADRANT") or {}

    quadrant = mapping.get(state_name)
    if quadrant:
        return quadrant

    # Fallback: map by state group if name didn't match
    group = (state.get("group") or "").strip().lower()
    group_to_q = {"started": "q1", "unstarted": "q2", "backlog": "q3", "cancelled": "q4", "completed": None}
    return group_to_q.get(group, "q3")  # skip completed, default others to q3

# ==========================================
# IMAGE GENERATION
# ==========================================
def create_rounded_rectangle(size, radius, color):
    """Creates a rounded rectangle image for the sticky notes."""
    # Create a larger image for antialiasing
    factor = 4
    w, h = size
    w *= factor
    h *= factor
    radius *= factor
    
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=color)
    
    # Resize back down
    return im.resize(size, Image.Resampling.LANCZOS)

def draw_text_centered(draw, x_center, y_center, text, font, fill="black", line_spacing=None):
    """Draw text centered at (x_center, y_center). Text can be multiline (use \\n)."""
    lines = text.split("\n")
    if line_spacing is None:
        bbox = draw.textbbox((0, 0), "Ay", font=font)
        line_spacing = bbox[3] - bbox[1]
    total_h = len(lines) * line_spacing
    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
    total_w = max(widths) if widths else 0
    x = x_center - total_w / 2
    y = y_center - total_h / 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text((x_center - line_w / 2, y + i * line_spacing), line, font=font, fill=fill)


def draw_text_on_note(note_img, text, font_path):
    """Wraps and draws text onto a note image."""
    draw = ImageDraw.Draw(note_img)
    w, h = note_img.size
    
    # Font setup (slightly larger for readability)
    font_size = 21
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
        
    # Text Wrapping
    lines = textwrap.wrap(text, width=14)
    line_height = 26
    total_text_height = len(lines) * line_height
    current_y = (h - total_text_height) // 2
    
    for line in lines:
        # Get text width using getbbox (left, top, right, bottom)
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        current_x = (w - text_w) // 2
        draw.text((current_x, current_y), line, font=font, fill="black")
        current_y += line_height
        
    return note_img

def generate_wallpaper(issues):
    width, height = CONFIG['RESOLUTION']
    image = Image.new('RGB', (width, height), COLORS['background'])
    draw = ImageDraw.Draw(image)
    
    try:
        font_axis = ImageFont.truetype(CONFIG['FONT_BOLD_PATH'], 24)
        font_label = ImageFont.truetype(CONFIG['FONT_PATH'], 20)
        font_header = ImageFont.truetype(CONFIG['FONT_PATH'], 28)
    except:
        font_axis = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_header = ImageFont.load_default()

    # --- Draw Axes (shorter at each end for arrowheads) ---
    cx, cy = width // 2, height // 2
    axis_color = COLORS['axis']
    arrow_len = 12
    arrow_half = 8

    effort_label_margin = 75
    axis_label_left_x = effort_label_margin
    axis_label_right_x = width - effort_label_margin
    h_left = effort_label_margin + 55
    h_right = width - effort_label_margin - 55
    v_top = 55
    v_bottom = height - 50

    # Horizontal line (Effort) — shortened at both ends for arrowheads
    draw.line([(h_left + arrow_len, cy), (h_right - arrow_len, cy)], fill=axis_color, width=3)
    # Vertical line (Value) — shortened at both ends for arrowheads
    draw.line([(cx, v_top + arrow_len), (cx, v_bottom - arrow_len)], fill=axis_color, width=3)

    # Arrowheads (filled triangles) at all 4 ends
    # Up
    draw.polygon([(cx, v_top), (cx - arrow_half, v_top + arrow_len), (cx + arrow_half, v_top + arrow_len)], fill=axis_color)
    # Down
    draw.polygon([(cx, v_bottom), (cx - arrow_half, v_bottom - arrow_len), (cx + arrow_half, v_bottom - arrow_len)], fill=axis_color)
    # Left
    draw.polygon([(h_left, cy), (h_left + arrow_len, cy - arrow_half), (h_left + arrow_len, cy + arrow_half)], fill=axis_color)
    # Right
    draw.polygon([(h_right, cy), (h_right - arrow_len, cy - arrow_half), (h_right - arrow_len, cy + arrow_half)], fill=axis_color)
    
    # --- Draw Axis Labels (centered: text in box, box at edges for Effort) ---
    axis_label_top_y = 30
    axis_label_bottom_y = height - 35
    draw_text_centered(draw, cx, axis_label_top_y, "High Value", font_axis, fill="black")
    draw_text_centered(draw, cx, axis_label_bottom_y, "Low Value", font_axis, fill="black")
    draw_text_centered(draw, axis_label_left_x, cy, "Low\nEffort", font_axis, fill="black")
    draw_text_centered(draw, axis_label_right_x, cy, "High\nEffort", font_axis, fill="black")

    # --- Draw Quadrant Headers (centered in each quadrant) ---
    q_headers = {
        'q1': "Do it now",
        'q2': "Do it next",
        'q3': "Do it if/when there is time",
        'q4': "Don't do it"
    }
    # Top headers near top of top quads; bottom headers same distance below axis as top content is below top headers
    header_top_y = 60
    header_bottom_y = cy + 30
    q_header_centers = {
        'q1': (cx // 2, header_top_y),
        'q2': (cx + (width - cx) // 2, header_top_y),
        'q3': (cx // 2, header_bottom_y),
        'q4': (cx + (width - cx) // 2, header_bottom_y),
    }
    for q_key, header_text in q_headers.items():
        draw_text_centered(draw, q_header_centers[q_key][0], q_header_centers[q_key][1], header_text, font_header, fill="black")

    # --- Sort Data ---
    buckets = {'q1': [], 'q2': [], 'q3': [], 'q4': []}
    for issue in issues:
        bucket = categorize_issue(issue)
        if bucket:
            buckets[bucket].append(issue['name']) # Using 'name' or 'title' depending on API

    # --- Draw Notes (max 6 per quadrant, centered in each quadrant) ---
    note_w, note_h = CONFIG['NOTE_SIZE']
    padding = CONFIG['NOTE_PADDING']
    max_notes = CONFIG['MAX_NOTES_PER_QUADRANT']

    # Content rectangle for each quadrant (left, top, right, bottom) — notes drawn inside
    margin = 50
    # Top quadrants: notes start below "Do it now" / "Do it next"
    header_bottom = 110
    q_content = {
        'q1': (margin, header_bottom, cx - margin, cy - margin),
        'q2': (cx + margin, header_bottom, width - margin, cy - margin),
        'q3': (margin, cy + margin, cx - margin, height - margin),
        'q4': (cx + margin, cy + margin, width - margin, height - margin),
    }

    for q_key, titles in buckets.items():
        titles = titles[:max_notes]
        if not titles:
            continue

        left, top, right, bottom = q_content[q_key]
        q_width = right - left
        q_height = bottom - top

        cols = min(3, max(1, q_width // (note_w + padding)))
        rows = (len(titles) + cols - 1) // cols
        block_w = cols * note_w + (cols - 1) * padding
        block_h = rows * note_h + (rows - 1) * padding
        start_x = left + (q_width - block_w) // 2
        start_y = top + (q_height - block_h) // 2

        for i, title in enumerate(titles):
            row = i // cols
            col = i % cols
            x = int(start_x + col * (note_w + padding))
            y = int(start_y + row * (note_h + padding))

            color = COLORS[f"{q_key}_note"]
            shadow = create_rounded_rectangle((note_w, note_h), 5, "#DDDDDD")
            image.paste(shadow, (x + 5, y + 5), shadow)
            note = create_rounded_rectangle((note_w, note_h), 5, color)
            note = draw_text_on_note(note, title, CONFIG['FONT_PATH'])
            image.paste(note, (x, y), note)

    # Save
    image.save(CONFIG['OUTPUT_PATH'])
    print(f"Wallpaper generated at: {CONFIG['OUTPUT_PATH']}")

# ==========================================
# WALLPAPER INTEGRATION (cross-platform)
# ==========================================
def set_windows_wallpaper(image_path):
    """
    Sets the desktop wallpaper on Windows 10/11 using the Win32 API.
    The image must be a BMP for the legacy API, but SystemParametersInfoW
    with SPI_SETDESKWALLPAPER handles JPG/PNG natively on modern Windows.
    """
    abs_path = os.path.abspath(image_path)
    try:
        import ctypes
        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDWININICHANGE = 0x02
        result = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, abs_path,
            SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
        )
        if result:
            print("Wallpaper updated successfully.")
        else:
            print("SystemParametersInfoW returned failure. Check the image path and format.")
    except Exception as e:
        print(f"Failed to set wallpaper on Windows: {e}")


def set_plasma_wallpaper(image_path):
    """
    Sets the wallpaper on KDE Plasma (5/6) using DBus.
    Clears the image first so Plasma reloads from disk (avoids showing cached old image).
    """
    abs_path = os.path.abspath(image_path)
    uri = "file://" + abs_path

    jscript_clear = """
    var allDesktops = desktops();
    for (i=0; i<allDesktops.length; i++) {
        d = allDesktops[i];
        d.wallpaperPlugin = "org.kde.image";
        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
        d.writeConfig("Image", "");
    }
    """
    jscript_set = f"""
    var allDesktops = desktops();
    for (i=0; i<allDesktops.length; i++) {{
        d = allDesktops[i];
        d.wallpaperPlugin = "org.kde.image";
        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
        d.writeConfig("Image", "{uri}");
    }}
    """

    def run_script(script):
        for qdbus in ("qdbus", "qdbus-qt5"):
            try:
                subprocess.run(
                    [qdbus, "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script],
                    check=True, capture_output=True
                )
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        return False

    if run_script(jscript_clear):
        time.sleep(0.15)
    if run_script(jscript_set):
        print("Wallpaper updated successfully.")
    else:
        print("Failed to set wallpaper. Ensure KDE Plasma is running and qdbus is installed.")


def set_wallpaper(image_path):
    """Auto-detect platform and set the wallpaper accordingly."""
    if platform.system() == "Windows":
        set_windows_wallpaper(image_path)
    else:
        set_plasma_wallpaper(image_path)

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    if not CONFIG["API_KEY"] or not CONFIG["WORKSPACE_SLUG"] or not CONFIG["PROJECT_ID"]:
        print("Missing Plane config. Set PLANE_PROJECT_URL (and PLANE_API_KEY) in .env, or use PLANE_BASE_URL, PLANE_WORKSPACE_SLUG, PLANE_PROJECT_ID. See .env.example.")
    print("Fetching issues from Plane...")
    issues = get_plane_issues()

    if not issues:
        print("No issues found or API error. Generating demo matrix...")
        # Demo data if API fails, so you can test the graphics immediately
        issues = [
            {'name': 'Test High Value/Low Effort', 'priority': 'urgent', 'estimate_point': 1},
            {'name': 'Test High Value/High Effort', 'priority': 'high', 'estimate_point': 8},
            {'name': 'Test Low Value/Low Effort', 'priority': 'low', 'estimate_point': 1},
            {'name': 'Test Don\'t Do It', 'priority': 'low', 'estimate_point': 8},
        ]

    print(f"Processing {len(issues)} issues...")
    generate_wallpaper(issues)
    set_wallpaper(CONFIG['OUTPUT_PATH'])