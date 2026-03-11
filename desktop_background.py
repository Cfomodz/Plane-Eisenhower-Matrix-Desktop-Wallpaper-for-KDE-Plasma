import requests
import json
import subprocess
import os
import sys
import time
import ctypes
from PIL import Image, ImageDraw, ImageFont
import textwrap

# Load .env if present (optional dependency: pip install python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# MSAL for Microsoft Graph OAuth2
try:
    import msal
except ImportError:
    msal = None

# ==========================================
# CONFIGURATION (env: .env or environment variables)
# ==========================================
def _env(key, default=None):
    return os.environ.get(key, default)

def _resolution():
    r = _env("TODO_MATRIX_RESOLUTION", "1920x1080")
    try:
        w, h = r.strip().lower().split("x")
        return (int(w), int(h))
    except Exception:
        return (1920, 1080)


# Microsoft Graph endpoint for To Do
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["Tasks.Read"]

# Azure AD app registration defaults (users must register their own app)
MS_CLIENT_ID = _env("MS_CLIENT_ID", "")
MS_TENANT_ID = _env("MS_TENANT_ID", "consumers")  # "consumers" for personal MS accounts

# Token cache file for persistent auth
TOKEN_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ms_token_cache.bin")

CONFIG = {
    # OUTPUT & DISPLAY
    "OUTPUT_PATH": _env("TODO_MATRIX_OUTPUT_PATH") or os.path.join(os.path.expanduser("~"), "Pictures", "todo_matrix_wallpaper.png"),
    "RESOLUTION": _resolution(),
    "FONT_PATH": _env("TODO_MATRIX_FONT_PATH", "C:\\Windows\\Fonts\\segoeui.ttf"),
    "FONT_BOLD_PATH": _env("TODO_MATRIX_FONT_BOLD_PATH", "C:\\Windows\\Fonts\\segoeuib.ttf"),

    # VISUAL SETTINGS
    "NOTE_SIZE": (200, 200),
    "NOTE_PADDING": 20,
    "MAX_NOTES_PER_QUADRANT": 6,

    # LIST → QUADRANT mapping (To Do list name → matrix quadrant; case-insensitive)
    # Users should create 4 lists in Microsoft To Do named to match these keys,
    # or change this mapping to match their existing list names.
    "LIST_TO_QUADRANT": {
        "do it now": "q1",
        "do first": "q1",
        "urgent": "q1",
        "q1": "q1",
        "do it next": "q2",
        "schedule": "q2",
        "planned": "q2",
        "q2": "q2",
        "do if extra time": "q3",
        "if time": "q3",
        "someday": "q3",
        "q3": "q3",
        "don't do": "q4",
        "don't do it": "q4",
        "eliminate": "q4",
        "q4": "q4",
    },
}

# Colors
COLORS = {
    "background": "#FFFFFF",
    "axis": "#333333",
    "text_main": "#000000",
    "q1_note": "#89C4F4",  # Blue (Do it now) - High Value, Low Effort
    "q2_note": "#F4B37D",  # Orange (Do it next) - High Value, High Effort
    "q3_note": "#FCE373",  # Yellow (If time) - Low Value, Low Effort
    "q4_note": "#9CA3AF",  # Grey (Don't do)
}

# ==========================================
# MICROSOFT GRAPH AUTH (Device Code Flow)
# ==========================================
def _build_msal_app():
    """Build an MSAL PublicClientApplication with persistent token cache."""
    if msal is None:
        print("ERROR: msal package not installed. Run: pip install msal")
        sys.exit(1)
    if not MS_CLIENT_ID:
        print("ERROR: MS_CLIENT_ID not set. Register an app in Azure and set MS_CLIENT_ID in .env.")
        print("See README for setup instructions.")
        sys.exit(1)

    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, "r") as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        MS_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{MS_TENANT_ID}",
        token_cache=cache,
    )
    return app, cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_CACHE_PATH, "w") as f:
            f.write(cache.serialize())


def get_graph_token():
    """Acquire a Microsoft Graph access token, using cache or device code flow."""
    app, cache = _build_msal_app()

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0])

    if not result:
        print("No cached token. Starting device code login...")
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPES)
        if "user_code" not in flow:
            print(f"Device flow error: {json.dumps(flow, indent=2)}")
            sys.exit(1)
        print(flow["message"])  # Tells user to visit a URL and enter a code
        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache)

    if "access_token" in result:
        return result["access_token"]
    else:
        print(f"Auth error: {result.get('error')}: {result.get('error_description')}")
        sys.exit(1)


# ==========================================
# MICROSOFT TO DO API HANDLER
# ==========================================
def get_todo_tasks():
    """Fetches tasks from Microsoft To Do via Graph API, grouped by list."""
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch all task lists
    lists_url = f"{GRAPH_BASE}/me/todo/lists"
    try:
        resp = requests.get(lists_url, headers=headers)
        resp.raise_for_status()
        lists_data = resp.json().get("value", [])
    except Exception as e:
        print(f"Error fetching To Do lists: {e}")
        return []

    mapping = CONFIG.get("LIST_TO_QUADRANT") or {}
    issues = []

    for task_list in lists_data:
        list_name = task_list.get("displayName", "")
        list_id = task_list.get("id", "")
        quadrant = mapping.get(list_name.strip().lower())
        if not quadrant:
            continue  # Skip lists not mapped to a quadrant

        # Fetch tasks in this list (only incomplete tasks)
        tasks_url = f"{GRAPH_BASE}/me/todo/lists/{list_id}/tasks"
        try:
            resp = requests.get(tasks_url, headers=headers, params={"$filter": "status ne 'completed'"})
            resp.raise_for_status()
            tasks = resp.json().get("value", [])
        except Exception as e:
            print(f"Error fetching tasks from list '{list_name}': {e}")
            continue

        for task in tasks:
            issues.append({
                "name": task.get("title", "Untitled"),
                "quadrant": quadrant,
            })

    return issues


def categorize_issue(issue):
    """Returns the quadrant for an issue (already mapped during fetch)."""
    return issue.get("quadrant", "q3")


# ==========================================
# IMAGE GENERATION
# ==========================================
def create_rounded_rectangle(size, radius, color):
    """Creates a rounded rectangle image for the sticky notes."""
    factor = 4
    w, h = size
    w *= factor
    h *= factor
    radius *= factor

    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=color)

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

    font_size = 21
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    lines = textwrap.wrap(text, width=14)
    line_height = 26
    total_text_height = len(lines) * line_height
    current_y = (h - total_text_height) // 2

    for line in lines:
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
    except Exception:
        font_axis = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_header = ImageFont.load_default()

    # --- Draw Axes ---
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

    draw.line([(h_left + arrow_len, cy), (h_right - arrow_len, cy)], fill=axis_color, width=3)
    draw.line([(cx, v_top + arrow_len), (cx, v_bottom - arrow_len)], fill=axis_color, width=3)

    # Arrowheads
    draw.polygon([(cx, v_top), (cx - arrow_half, v_top + arrow_len), (cx + arrow_half, v_top + arrow_len)], fill=axis_color)
    draw.polygon([(cx, v_bottom), (cx - arrow_half, v_bottom - arrow_len), (cx + arrow_half, v_bottom - arrow_len)], fill=axis_color)
    draw.polygon([(h_left, cy), (h_left + arrow_len, cy - arrow_half), (h_left + arrow_len, cy + arrow_half)], fill=axis_color)
    draw.polygon([(h_right, cy), (h_right - arrow_len, cy - arrow_half), (h_right - arrow_len, cy + arrow_half)], fill=axis_color)

    # --- Axis Labels ---
    axis_label_top_y = 30
    axis_label_bottom_y = height - 35
    draw_text_centered(draw, cx, axis_label_top_y, "High Value", font_axis, fill="black")
    draw_text_centered(draw, cx, axis_label_bottom_y, "Low Value", font_axis, fill="black")
    draw_text_centered(draw, axis_label_left_x, cy, "Low\nEffort", font_axis, fill="black")
    draw_text_centered(draw, axis_label_right_x, cy, "High\nEffort", font_axis, fill="black")

    # --- Quadrant Headers ---
    q_headers = {
        'q1': "Do it now",
        'q2': "Do it next",
        'q3': "Do it if/when there is time",
        'q4': "Don't do it"
    }
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
            buckets[bucket].append(issue['name'])

    # --- Draw Notes ---
    note_w, note_h = CONFIG['NOTE_SIZE']
    padding = CONFIG['NOTE_PADDING']
    max_notes = CONFIG['MAX_NOTES_PER_QUADRANT']

    margin = 50
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
    os.makedirs(os.path.dirname(CONFIG['OUTPUT_PATH']), exist_ok=True)
    image.save(CONFIG['OUTPUT_PATH'])
    print(f"Wallpaper generated at: {CONFIG['OUTPUT_PATH']}")

# ==========================================
# WINDOWS 11 WALLPAPER INTEGRATION
# ==========================================
def set_windows_wallpaper(image_path):
    """Sets the desktop wallpaper on Windows using the SystemParametersInfo API."""
    abs_path = os.path.abspath(image_path)

    if sys.platform != "win32":
        print(f"Not on Windows. Wallpaper saved to: {abs_path}")
        print("Set it manually as your desktop background.")
        return

    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        abs_path,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    )
    if result:
        print("Wallpaper updated successfully.")
    else:
        print("Failed to set wallpaper. Try running as administrator.")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    if not MS_CLIENT_ID:
        print("Missing Microsoft app config. Set MS_CLIENT_ID in .env.")
        print("See README for Azure app registration instructions.")

    print("Fetching tasks from Microsoft To Do...")
    issues = get_todo_tasks()

    if not issues:
        print("No tasks found or API error. Generating demo matrix...")
        issues = [
            {'name': 'Test High Value/Low Effort', 'quadrant': 'q1'},
            {'name': 'Test High Value/High Effort', 'quadrant': 'q2'},
            {'name': 'Test Low Value/Low Effort', 'quadrant': 'q3'},
            {'name': 'Test Don\'t Do It', 'quadrant': 'q4'},
        ]

    print(f"Processing {len(issues)} tasks...")
    generate_wallpaper(issues)
    set_windows_wallpaper(CONFIG['OUTPUT_PATH'])
