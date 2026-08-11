from __future__ import annotations

# BUILD: 2026-08-11-1620 — source-sheet sweat-test values, report role filtering, report notes

import html
import hmac
import io
import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import gspread
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.oauth2.service_account import Credentials
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas as pdf_canvas


# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
DEFAULT_SHEET_ID = "1CF2n3fAt8jALZK6HIC80Un20ITScfSMZd4kXM4ZPMSo"
DEFAULT_JUMP_TAB = "Jump Data"
DEFAULT_VELO_TAB = "FB Velo"
DEFAULT_PERFORMANCE_TAB = "PP_Sprint"
DEFAULT_ROSTER_TAB = "Master Roster"
DEFAULT_HYDRATION_SHEET_ID = "15SQ2MBobXTP5kgR40l1E1e43C1pviT0Wd_3zIuG0Deg"
DEFAULT_DSL_HYDRATION_TAB = "DSL"
HYDRATION_TAB_TEAM_MAP = {
    "AAA": "Rochester",
    "AA": "Harrisburg",
    "A+": "Wilmington",
    "A": "Fredericksburg",
    "FCL+Rehab": None,
}
LOCAL_SERVICE_ACCOUNT_FILE = Path.home() / "Desktop" / "service_account.json"
MAX_FLAG_AGE_DAYS = 30

KNOWN_TEAM_ALIASES = {
    "DSL": "DSL",
    "FCL": "FCL",
    "FREDERICKSBURG": "Fredericksburg",
    "WILMINGTON": "Wilmington",
    "HARRISBURG": "Harrisburg",
    "ROCHESTER": "Rochester",
    "WASHINGTON": "Washington",
    "REHAB": "REHAB",
    "REHABILITATION": "REHAB",
    "WESTPALMBEACH": "FCL",
    "PALMBEACH": "FCL",
    "DRAFT": "Draft",
}
TEAM_ORDER = [
    "Washington",
    "Rochester",
    "Harrisburg",
    "Wilmington",
    "Fredericksburg",
    "FCL",
    "DSL",
    "REHAB",
    "Draft",
]

# Design system
BG = "#F6F8FC"
CARD_BG = "#FFFFFF"
NAVY = "#0A1F44"
NAVY_MID = "#183B6D"
ACCENT_RED = "#C8102E"
BLUE = "#1E5AA8"
GREEN = "#14805E"
AMBER = "#B7791F"
TEAL = "#0D7E8A"
TEXT = "#162033"
SUBTEXT = "#667085"
BORDER = "#DDE4EE"
GRID = "#E8EDF3"
LIGHT_RED = "#FFF1F3"
LIGHT_AMBER = "#FFF8E8"
LIGHT_GREEN = "#ECFDF5"

st.set_page_config(
    page_title="Nutrition Early Warning",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
<style>
    :root {{
      --app-bg: {BG}; --app-card: {CARD_BG}; --app-navy: {NAVY};
      --app-red: {ACCENT_RED}; --app-blue: {BLUE}; --app-text: {TEXT};
      --app-sub: {SUBTEXT}; --app-border: {BORDER};
    }}
    .stApp {{ background: var(--app-bg); color: var(--app-text); }}
    .block-container {{ max-width: 1580px; padding-top: 1.7rem; padding-bottom: 3rem; }}
    h1, h2, h3 {{ letter-spacing: -0.025em; }}

    [data-testid="stSidebar"] {{
      background: linear-gradient(180deg, #081B3A 0%, #0A1F44 100%);
      border-right: 1px solid rgba(255,255,255,.08);
    }}
    [data-testid="stSidebar"] > div:first-child {{ padding-top: 1.35rem; }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown span {{ color: #DCE7F5 !important; }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
      font-weight: 700; font-size: .84rem;
    }}

    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-baseweb="input"] > div,
    [data-testid="stSidebar"] .stDateInput > div > div,
    [data-testid="stSidebar"] .stNumberInput > div > div {{
      background: #FFFFFF !important;
      border: 1px solid #DDE4EE !important;
      border-radius: 12px !important;
      color: #162033 !important;
      box-shadow: none !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="select"] *,
    [data-testid="stSidebar"] div[data-baseweb="input"] *,
    [data-testid="stSidebar"] input {{
      color: #162033 !important;
      -webkit-text-fill-color: #162033 !important;
      opacity: 1 !important;
    }}
    div[data-baseweb="popover"], div[role="listbox"] {{ background: #FFFFFF !important; }}
    div[data-baseweb="popover"] *, div[role="listbox"] *,
    div[role="option"], div[role="option"] * {{
      color: #162033 !important; -webkit-text-fill-color: #162033 !important;
    }}
    [data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.13); }}
    [data-testid="stSidebar"] .stButton button {{
      background: {ACCENT_RED}; color: #FFFFFF; border: none; border-radius: 10px;
      font-weight: 800; min-height: 2.5rem;
    }}

    .metric-card {{
      position: relative; overflow: hidden; background: var(--app-card);
      border: 1px solid var(--app-border); border-radius: 16px; padding: 17px 19px;
      min-height: 116px; box-shadow: 0 7px 24px rgba(15,35,64,.055);
    }}
    .metric-accent {{ width: 36px; height: 4px; border-radius: 999px; margin-bottom: 14px; }}
    .metric-label {{ color: var(--app-sub); font-size: 10px; letter-spacing: .1em;
                     font-weight: 800; text-transform: uppercase; margin-bottom: 7px; }}
    .metric-value {{ color: var(--app-navy); font-size: 29px; line-height: 1.05;
                     font-weight: 800; margin: 0; letter-spacing: -0.03em; }}
    .metric-note {{ color: var(--app-sub); font-size: 12px; margin-top: 7px; }}

    .status-pill {{ display:inline-block; padding:5px 9px; border-radius:999px;
                   font-size:11px; font-weight:800; letter-spacing:.02em; }}
    .status-review {{ background:{LIGHT_RED}; color:{ACCENT_RED}; border:1px solid #F7C7D0; }}
    .status-monitor {{ background:{LIGHT_AMBER}; color:{AMBER}; border:1px solid #F1D59B; }}
    .status-stable {{ background:{LIGHT_GREEN}; color:{GREEN}; border:1px solid #B9E6D2; }}
    .status-nodata {{ background:#F2F4F7; color:{SUBTEXT}; border:1px solid #E1E5EA; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
      background: #FFFFFF; border: 1px solid var(--app-border) !important;
      border-radius: 16px !important; box-shadow: 0 7px 24px rgba(15,35,64,.05);
      padding: 6px 8px 10px 8px;
    }}
    [data-testid="stDataFrame"] {{ border: 1px solid var(--app-border); border-radius: 12px; overflow: hidden; }}
    .stPlotlyChart {{ border-radius: 12px; overflow: hidden; }}
    .small-note {{ color:{SUBTEXT}; font-size:12px; }}
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    lookup = {str(col).strip().lower(): col for col in columns}
    for candidate in candidates:
        found = lookup.get(candidate.strip().lower())
        if found is not None:
            return found
    return None


def parse_sheet_dates(series: pd.Series) -> pd.Series:
    raw = series.copy()
    parsed = pd.to_datetime(raw, errors="coerce")
    missing = parsed.isna()
    if missing.any():
        numeric = pd.to_numeric(raw[missing], errors="coerce")
        serial_mask = numeric.between(30000, 60000)
        if serial_mask.any():
            parsed.loc[numeric[serial_mask].index] = (
                pd.Timestamp("1899-12-30") + pd.to_timedelta(numeric[serial_mask], unit="D")
            )
    return parsed.dt.normalize()


def canonical_name(value) -> str:
    if pd.isna(value):
        return ""
    name = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    name = name.lower().strip()
    if "," in name:
        pieces = [piece.strip() for piece in name.split(",") if piece.strip()]
        if len(pieces) >= 2:
            name = " ".join(pieces[1:] + [pieces[0]])
    tokens = re.findall(r"[a-z0-9]+", name)
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    tokens = [token for token in tokens if token not in suffixes]
    return " ".join(sorted(tokens))


def normalize_team(value) -> str | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return None
    key = re.sub(r"[^A-Z0-9]", "", raw.upper())
    return KNOWN_TEAM_ALIASES.get(key)


def is_pitcher_position(value) -> bool:
    """Return True for roster positions that represent pitchers."""
    if value is None or pd.isna(value):
        return False
    raw = str(value).strip().upper()
    if not raw or raw in {"NA", "N/A", "NONE", "NAN"}:
        return False
    if "PITCH" in raw:
        return True
    tokens = set(re.findall(r"[A-Z0-9]+", raw))
    return bool(tokens & {"P", "RHP", "LHP", "SP", "RP"})


def is_position_player_position(value) -> bool:
    """Return True for hitter/position-player roster positions."""
    if value is None or pd.isna(value) or is_pitcher_position(value):
        return False
    raw = str(value).strip().upper()
    if not raw or raw in {"NA", "N/A", "NONE", "NAN"}:
        return False
    if "POSITION PLAYER" in raw:
        return True
    tokens = set(re.findall(r"[A-Z0-9]+", raw))
    position_tokens = {
        "C", "INF", "IF", "OF", "1B", "2B", "3B", "SS",
        "LF", "CF", "RF", "DH", "UT", "UTIL", "UTILITY",
    }
    return bool(tokens & position_tokens)


def clean_hydration_player_name(value) -> str:
    """Normalize display names from hydration sheets without changing ordinary names."""
    if pd.isna(value):
        return ""
    name = str(value).strip()
    # DR sheet can contain labels such as "2027- Hendrick Barrios".
    name = re.sub(r"^\s*20\d{2}\s*[-–—:]\s*", "", name)
    return name.strip()


def hydration_classification(value) -> str:
    text = str(value or "").strip().lower().replace("-", " ")
    if not text:
        return ""
    if "very high" in text:
        return "Very High"
    if ("moderate/high" in text) or ("moderate high" in text):
        return "Moderate/High"
    if "high" in text:
        return "High"
    if "moderate" in text:
        return "Moderate"
    if "low" in text:
        return "Low"
    return ""


def parse_hydration_values(
    values: list[list[str]],
    source_tab: str,
    source_team: str | None,
    source_book: str,
) -> pd.DataFrame:
    """Parse the Player / Sodium Loss(or Results) / Recommendation sheet layout."""
    columns = [
        "name_key", "athlete", "source_team", "source_tab", "source_book",
        "sodium_loss_mg_l", "classification", "result_raw", "recommendation",
    ]
    if not values:
        return pd.DataFrame(columns=columns)

    # The supplied workbooks have a blank first row, so find the real header row.
    header_idx = None
    for idx, row in enumerate(values[:15]):
        first = str(row[0]).strip().lower() if row else ""
        if first in {"player", "athlete", "name"}:
            header_idx = idx
            break
    if header_idx is None:
        return pd.DataFrame(columns=columns)

    headers = [str(x).strip() for x in values[header_idx]]
    name_idx = next((i for i, h in enumerate(headers) if h.lower() in {"player", "athlete", "name"}), 0)
    result_idx = next(
        (i for i, h in enumerate(headers) if h.lower() in {"sodium loss", "results", "result"}),
        1 if len(headers) > 1 else None,
    )
    recommendation_idx = next(
        (i for i, h in enumerate(headers) if h.lower() == "recommendation"),
        2 if len(headers) > 2 else None,
    )
    if result_idx is None:
        return pd.DataFrame(columns=columns)

    rows = []
    for row in values[header_idx + 1:]:
        if not row:
            continue
        athlete = clean_hydration_player_name(row[name_idx] if name_idx < len(row) else "")
        if not athlete:
            continue
        result_raw = str(row[result_idx]).strip() if result_idx < len(row) else ""
        recommendation = (
            str(row[recommendation_idx]).strip()
            if recommendation_idx is not None and recommendation_idx < len(row)
            else ""
        )
        match = re.search(r"(?i)(\d{2,4}(?:\.\d+)?)\s*mg\s*/\s*l", result_raw)
        sodium_loss = float(match.group(1)) if match else np.nan
        rows.append({
            "athlete": athlete,
            "name_key": canonical_name(athlete),
            "source_team": source_team,
            "source_tab": source_tab,
            "source_book": source_book,
            "sodium_loss_mg_l": sodium_loss,
            "classification": hydration_classification(result_raw),
            "result_raw": result_raw,
            "recommendation": recommendation,
        })

    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out
    out = out[(out["athlete"] != "") & (out["name_key"] != "")].copy()
    # Prefer rows with an actual numeric test result if duplicate names exist.
    out["_has_result"] = out["sodium_loss_mg_l"].notna().astype(int)
    out = (
        out.sort_values(["name_key", "_has_result"], kind="stable")
        .drop_duplicates(["name_key", "source_tab"], keep="last")
        .drop(columns=["_has_result"])
        .reset_index(drop=True)
    )
    return out


def fmt(value, digits=1, suffix="") -> str:
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return "—"
    return f"{float(value):,.{digits}f}{suffix}"


def fmt_signed(value, digits=1, suffix="") -> str:
    if value is None or pd.isna(value) or not np.isfinite(float(value)):
        return "—"
    return f"{float(value):+,.{digits}f}{suffix}"


def fmt_date(value) -> str:
    if value is None or pd.isna(value):
        return "—"
    value = pd.Timestamp(value)
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def metric_card(title: str, value: str, accent: str, note: str = "") -> str:
    note_html = f'<div class="metric-note">{html.escape(note)}</div>' if note else ""
    return f"""
    <div class="metric-card">
      <div class="metric-accent" style="background:{accent};"></div>
      <div class="metric-label">{html.escape(title)}</div>
      <div class="metric-value">{html.escape(value)}</div>
      {note_html}
    </div>
    """


def base_figure_layout(fig: go.Figure, height: int = 430) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        font={"family": "Inter, Avenir Next, Arial, sans-serif", "color": TEXT},
        hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": BORDER, "font": {"color": TEXT, "size": 13}},
        margin={"l": 62, "r": 28, "t": 28, "b": 54},
        height=height,
        showlegend=False,
    )
    return fig


def csv_download_button(df: pd.DataFrame, label: str, filename: str, key: str) -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def secret_or_default(key: str, default: str) -> str:
    try:
        value = st.secrets.get(key)
    except Exception:
        value = None
    return str(value) if value else default


# -----------------------------------------------------------------------------
# GOOGLE SHEETS
# -----------------------------------------------------------------------------
def get_credentials() -> Credentials:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    try:
        service_account_info = st.secrets.get("gcp_service_account")
    except Exception:
        service_account_info = None

    if service_account_info:
        return Credentials.from_service_account_info(dict(service_account_info), scopes=scopes)

    local_file = Path(os.environ.get("SERVICE_ACCOUNT_FILE", str(LOCAL_SERVICE_ACCOUNT_FILE))).expanduser()
    if local_file.exists():
        return Credentials.from_service_account_file(str(local_file), scopes=scopes)

    raise FileNotFoundError(
        "No Google credentials were found. Put service_account.json on your Desktop for local use, "
        "or add [gcp_service_account] to Streamlit Secrets."
    )


def read_tab(client: gspread.Client, sheet_id: str, tab_name: str) -> pd.DataFrame:
    worksheet = client.open_by_key(sheet_id).worksheet(tab_name)
    return pd.DataFrame(worksheet.get_all_records())


def read_tab_optional(client: gspread.Client, sheet_id: str, tab_name: str) -> pd.DataFrame:
    try:
        return read_tab(client, sheet_id, tab_name)
    except Exception:
        return pd.DataFrame()


def read_tab_values_optional(
    client: gspread.Client,
    sheet_id: str,
    tab_name: str,
) -> tuple[list[list[str]], str | None]:
    """Read raw cell values so hydration sheets can have a blank row above their headers."""
    try:
        worksheet = client.open_by_key(sheet_id).worksheet(tab_name)
        return worksheet.get_all_values(), None
    except Exception as exc:
        return [], f"{tab_name}: {exc}"


@dataclass
class SourceBundle:
    jump: pd.DataFrame
    velo: pd.DataFrame
    monthly: pd.DataFrame
    roster: pd.DataFrame
    hydration: pd.DataFrame
    hydration_status: str
    status: str
    bw_source_col: str


@st.cache_data(ttl=300, show_spinner="Loading organization data…")
def load_source_data() -> SourceBundle:
    sheet_id = secret_or_default("SHEET_ID", DEFAULT_SHEET_ID)
    jump_tab = secret_or_default("JUMP_TAB", DEFAULT_JUMP_TAB)
    velo_tab = secret_or_default("VELO_TAB", DEFAULT_VELO_TAB)
    # Backward-compatible with the existing app's BAT_TAB secret.
    performance_tab = secret_or_default(
        "PERFORMANCE_TAB",
        secret_or_default("BAT_TAB", DEFAULT_PERFORMANCE_TAB),
    )
    roster_tab = secret_or_default("ROSTER_TAB", DEFAULT_ROSTER_TAB)
    hydration_sheet_id = secret_or_default(
        "HYDRATION_SHEET_ID", DEFAULT_HYDRATION_SHEET_ID
    )
    dsl_hydration_tab = secret_or_default(
        "DSL_HYDRATION_TAB", DEFAULT_DSL_HYDRATION_TAB
    )

    creds = get_credentials()
    client = gspread.authorize(creds)
    jump_raw = read_tab(client, sheet_id, jump_tab)
    velo_raw = read_tab(client, sheet_id, velo_tab)
    performance_raw = read_tab(client, sheet_id, performance_tab)
    roster_raw = read_tab_optional(client, sheet_id, roster_tab)

    if jump_raw.empty:
        raise ValueError(f"The '{jump_tab}' tab did not return any rows.")
    if velo_raw.empty:
        raise ValueError(f"The '{velo_tab}' tab did not return any rows.")
    if performance_raw.empty:
        raise ValueError(f"The '{performance_tab}' tab did not return any rows.")

    # ----- Jump Data: bodyweight + CI -----
    jump_raw.columns = jump_raw.columns.astype(str).str.strip()
    jump_name_col = first_existing(
        jump_raw.columns.tolist(),
        ["Athlete", "athlete", "Player", "player", "Name", "name"],
    )
    jump_date_col = first_existing(
        jump_raw.columns.tolist(), ["Date", "date", "Test Date", "test_date"]
    )
    jump_team_col = first_existing(
        jump_raw.columns.tolist(), ["Team", "team", "Level", "level"]
    )
    jump_ci_col = first_existing(
        jump_raw.columns.tolist(),
        ["Concentric Impulse [N s]", "Concentric Impulse", "CI", "ci"],
    )
    jump_bw_col = first_existing(
        jump_raw.columns.tolist(),
        [
            "BW kg", "BW (kg)", "BW [kg]", "Bodyweight kg", "Body Weight kg",
            "Bodyweight [kg]", "Body Mass [kg]", "Body Mass kg", "Bodyweight",
            "Body Weight", "BW", "Weight kg", "Weight (kg)", "BW (lbs)",
            "BW lbs", "Bodyweight lbs", "Body Weight (lbs)", "Weight (lbs)",
        ],
    )
    missing_jump = [
        label
        for label, col in {
            "athlete name": jump_name_col,
            "date": jump_date_col,
            "bodyweight": jump_bw_col,
            "concentric impulse": jump_ci_col,
        }.items()
        if col is None
    ]
    if missing_jump:
        raise ValueError(
            "Jump Data is missing required column(s): " + ", ".join(missing_jump) + ". "
            "Bodyweight candidates include BW kg, Bodyweight, Body Weight, BW, and BW (lbs)."
        )

    bw_numeric = pd.to_numeric(jump_raw[jump_bw_col], errors="coerce")
    bw_col_lower = str(jump_bw_col).lower()
    source_is_lbs = ("lb" in bw_col_lower) or ("pound" in bw_col_lower)
    bw_kg = bw_numeric / 2.2046226218 if source_is_lbs else bw_numeric

    jump = pd.DataFrame({
        "athlete": jump_raw[jump_name_col].astype(str).str.strip(),
        "date": parse_sheet_dates(jump_raw[jump_date_col]),
        "team_raw": jump_raw[jump_team_col].astype(str).str.strip() if jump_team_col else "",
        "bodyweight_kg": bw_kg,
        "ci": pd.to_numeric(jump_raw[jump_ci_col], errors="coerce"),
    })
    jump["bodyweight_lb"] = jump["bodyweight_kg"] * 2.2046226218
    jump["team"] = jump["team_raw"].map(normalize_team)
    jump["name_key"] = jump["athlete"].map(canonical_name)
    jump = jump[
        (jump["athlete"] != "") & (jump["name_key"] != "") & jump["date"].notna()
    ].copy()
    # Remove physically impossible values without being overly restrictive for pro baseball.
    jump.loc[~jump["bodyweight_kg"].between(35, 180), ["bodyweight_kg", "bodyweight_lb"]] = np.nan
    jump.loc[~jump["ci"].between(50, 600), "ci"] = np.nan
    jump = jump.sort_values(["name_key", "date"], kind="stable").reset_index(drop=True)

    # ----- FB Velo -----
    velo_raw.columns = velo_raw.columns.astype(str).str.strip()
    velo_name_col = first_existing(
        velo_raw.columns.tolist(),
        ["pitcher", "Pitcher", "athlete", "Athlete", "player", "Player", "Name", "name"],
    )
    velo_date_col = first_existing(
        velo_raw.columns.tolist(), ["game_date", "Game_Date", "Game Date", "date", "Date"]
    )
    velo_fb_col = first_existing(
        velo_raw.columns.tolist(),
        [
            "fb_velo", "FB_Velo", "FB Velo", "fb velo",
            "fastball_velo", "Fastball Velo", "Fastball Velocity",
        ],
    )
    velo_ytd_col = first_existing(
        velo_raw.columns.tolist(),
        [
            "ytd_fb_velo", "YTD_FB_Velo", "YTD FB Velo", "YTD Fastball Velo",
            "ytd fastball velo", "ytd_fastball_velo",
        ],
    )
    if any(col is None for col in [velo_name_col, velo_date_col, velo_fb_col, velo_ytd_col]):
        raise ValueError(
            "FB Velo requires pitcher/name, game date, fb_velo, and ytd_fb_velo columns."
        )

    velo = pd.DataFrame({
        "athlete": velo_raw[velo_name_col].astype(str).str.strip(),
        "date": parse_sheet_dates(velo_raw[velo_date_col]),
        "fb_velo": pd.to_numeric(velo_raw[velo_fb_col], errors="coerce"),
        "ytd_fb_velo": pd.to_numeric(velo_raw[velo_ytd_col], errors="coerce"),
    })
    velo["name_key"] = velo["athlete"].map(canonical_name)
    velo = velo[
        (velo["athlete"] != "") & (velo["name_key"] != "")
    ].dropna(subset=["date", "fb_velo", "ytd_fb_velo"])
    velo = velo[
        velo["fb_velo"].between(50, 110)
        & velo["ytd_fb_velo"].between(50, 110)
    ].copy()
    velo = velo.sort_values(["name_key", "date"], kind="stable").reset_index(drop=True)

    # ----- PP_Sprint monthly bat/sprint speed -----
    performance_raw.columns = performance_raw.columns.astype(str).str.strip()
    perf_name_col = first_existing(
        performance_raw.columns.tolist(),
        [
            "batter", "Batter", "hitter", "Hitter", "athlete", "Athlete",
            "player", "Player", "Name", "name",
        ],
    )
    perf_date_col = first_existing(
        performance_raw.columns.tolist(), ["game_date", "Game Date", "date", "Date"]
    )
    perf_team_col = first_existing(
        performance_raw.columns.tolist(), ["Team", "team", "Level", "level"]
    )
    bat_col = first_existing(
        performance_raw.columns.tolist(),
        [
            "monthly_avg_bat_speed", "Monthly Avg Bat Speed", "monthly avg bat speed",
            "monthly_average_bat_speed", "Monthly Average Bat Speed",
        ],
    )
    sprint_col = first_existing(
        performance_raw.columns.tolist(),
        [
            "monthly_max_sprint_speed", "Monthly Max Sprint Speed",
            "monthly max sprint speed", "monthly_max_speed", "Monthly Maximum Sprint Speed",
        ],
    )
    if any(col is None for col in [perf_name_col, perf_date_col, bat_col, sprint_col]):
        raise ValueError(
            "PP_Sprint requires player/batter, game_date, monthly_avg_bat_speed, "
            "and monthly_max_sprint_speed."
        )

    perf = pd.DataFrame({
        "athlete": performance_raw[perf_name_col].astype(str).str.strip(),
        "date": parse_sheet_dates(performance_raw[perf_date_col]),
        "team_raw": performance_raw[perf_team_col].astype(str).str.strip() if perf_team_col else "",
        "monthly_avg_bat_speed": pd.to_numeric(performance_raw[bat_col], errors="coerce"),
        "monthly_max_sprint_speed": pd.to_numeric(performance_raw[sprint_col], errors="coerce"),
    })
    perf["team"] = perf["team_raw"].map(normalize_team)
    perf["name_key"] = perf["athlete"].map(canonical_name)
    perf = perf[
        (perf["athlete"] != "") & (perf["name_key"] != "") & perf["date"].notna()
    ].copy()
    perf["month"] = perf["date"].dt.to_period("M").dt.to_timestamp()
    perf.loc[~perf["monthly_avg_bat_speed"].between(20, 100), "monthly_avg_bat_speed"] = np.nan
    perf.loc[~perf["monthly_max_sprint_speed"].between(5, 40), "monthly_max_sprint_speed"] = np.nan

    coverage = (
        perf.groupby(["name_key", "month"], as_index=False)
        .agg(data_dates=("date", "nunique"))
    )
    monthly = (
        perf.sort_values(["name_key", "month", "date"], kind="stable")
        .groupby(["name_key", "month"], as_index=False)
        .tail(1)[[
            "name_key", "athlete", "team", "month", "date",
            "monthly_avg_bat_speed", "monthly_max_sprint_speed",
        ]]
        .merge(coverage, on=["name_key", "month"], how="left")
        .rename(columns={"date": "as_of_date"})
        .sort_values(["name_key", "month"], kind="stable")
        .reset_index(drop=True)
    )

    # ----- Optional Master Roster -----
    roster = pd.DataFrame(columns=["name_key", "athlete", "team", "position"])
    if not roster_raw.empty:
        roster_raw.columns = roster_raw.columns.astype(str).str.strip()
        roster_name_col = first_existing(
            roster_raw.columns.tolist(),
            ["Athlete", "athlete", "Player", "player", "Name", "name"],
        )
        roster_team_col = first_existing(
            roster_raw.columns.tolist(), ["Team", "team", "Level", "level"]
        )
        roster_position_col = first_existing(
            roster_raw.columns.tolist(), ["Position", "position", "Pos", "pos"]
        )
        if roster_name_col:
            roster = pd.DataFrame({
                "athlete": roster_raw[roster_name_col].astype(str).str.strip(),
                "team": roster_raw[roster_team_col].map(normalize_team) if roster_team_col else None,
                "position": roster_raw[roster_position_col].astype(str).str.strip() if roster_position_col else "",
            })
            roster["name_key"] = roster["athlete"].map(canonical_name)
            roster = roster[(roster["athlete"] != "") & (roster["name_key"] != "")]
            roster = roster.drop_duplicates("name_key", keep="last")[["name_key", "athlete", "team", "position"]]

    # ----- Hydration / sweat sodium -----
    # External Hydration spreadsheet contains AAA, AA, A+, A, and FCL+Rehab.
    # The primary reporting spreadsheet contains the DR results on the DSL tab.
    hydration_frames = []
    hydration_errors = []
    for hydration_tab_name, hydration_team in HYDRATION_TAB_TEAM_MAP.items():
        values, error = read_tab_values_optional(
            client, hydration_sheet_id, hydration_tab_name
        )
        if error:
            hydration_errors.append(error)
            continue
        parsed = parse_hydration_values(
            values,
            source_tab=hydration_tab_name,
            source_team=hydration_team,
            source_book="Hydration",
        )
        if not parsed.empty:
            hydration_frames.append(parsed)

    dsl_values, dsl_error = read_tab_values_optional(
        client, sheet_id, dsl_hydration_tab
    )
    if dsl_error:
        hydration_errors.append(f"Primary {dsl_error}")
    else:
        dsl_parsed = parse_hydration_values(
            dsl_values,
            source_tab=dsl_hydration_tab,
            source_team="DSL",
            source_book="Primary reports",
        )
        if not dsl_parsed.empty:
            hydration_frames.append(dsl_parsed)

    hydration_columns = [
        "name_key", "athlete", "source_team", "source_tab", "source_book",
        "sodium_loss_mg_l", "classification", "result_raw", "recommendation",
    ]
    hydration = (
        pd.concat(hydration_frames, ignore_index=True)
        if hydration_frames
        else pd.DataFrame(columns=hydration_columns)
    )
    if not hydration.empty:
        # One result per player is expected in the supplied structure. Prefer a numeric result
        # while retaining the source tab and full recommendation.
        hydration["_has_result"] = hydration["sodium_loss_mg_l"].notna().astype(int)
        hydration = (
            hydration.sort_values(["name_key", "_has_result"], kind="stable")
            .drop_duplicates("name_key", keep="last")
            .drop(columns=["_has_result"])
            .reset_index(drop=True)
        )

    if hydration_errors:
        hydration_status = (
            f"Loaded {len(hydration):,} hydration rows; some tabs were unavailable: "
            + " | ".join(hydration_errors[:3])
        )
    else:
        hydration_status = f"Loaded {len(hydration):,} hydration rows"

    status = (
        f"Loaded {len(jump):,} Jump Data rows, {len(velo):,} FB Velo rows, "
        f"{len(monthly):,} player-month PP_Sprint rows"
        + (f", {len(roster):,} roster rows" if not roster.empty else "")
        + f", {len(hydration):,} hydration rows"
        + f" · {datetime.now().strftime('%I:%M %p').lstrip('0')}"
    )
    return SourceBundle(
        jump=jump,
        velo=velo,
        monthly=monthly,
        roster=roster,
        hydration=hydration,
        hydration_status=hydration_status,
        status=status,
        bw_source_col=str(jump_bw_col),
    )


# -----------------------------------------------------------------------------
# TEAM / PLAYER LOOKUPS
# -----------------------------------------------------------------------------
def build_player_directory(bundle: SourceBundle, as_of_date) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).normalize()
    frames = []

    jump_pre = bundle.jump[bundle.jump["date"] <= as_of].copy()
    if not jump_pre.empty:
        j = (
            jump_pre.sort_values(["name_key", "date"], kind="stable")
            .groupby("name_key", as_index=False)
            .tail(1)[["name_key", "athlete", "team", "date"]]
            .rename(columns={"date": "team_date"})
        )
        j["source_priority"] = 2
        frames.append(j)

    monthly_pre = bundle.monthly[bundle.monthly["as_of_date"] <= as_of].copy()
    if not monthly_pre.empty:
        m = (
            monthly_pre.sort_values(["name_key", "as_of_date"], kind="stable")
            .groupby("name_key", as_index=False)
            .tail(1)[["name_key", "athlete", "team", "as_of_date"]]
            .rename(columns={"as_of_date": "team_date"})
        )
        m["source_priority"] = 1
        frames.append(m)

    if frames:
        directory = pd.concat(frames, ignore_index=True)
        directory["team_date"] = pd.to_datetime(directory["team_date"])
        directory = (
            directory.sort_values(["name_key", "team_date", "source_priority"], kind="stable")
            .groupby("name_key", as_index=False)
            .tail(1)[["name_key", "athlete", "team"]]
        )
    else:
        directory = pd.DataFrame(columns=["name_key", "athlete", "team"])

    # Roster is preferred for current display name/team when available.
    if not bundle.roster.empty:
        roster = bundle.roster.copy().rename(
            columns={"athlete": "roster_athlete", "team": "roster_team"}
        )
        directory = directory.merge(roster, on="name_key", how="outer")
        directory["athlete"] = directory["roster_athlete"].combine_first(directory["athlete"])
        directory["team"] = directory["roster_team"].combine_first(directory["team"])
        directory["position"] = directory.get("position", "")
        directory = directory.drop(columns=[c for c in ["roster_athlete", "roster_team"] if c in directory.columns])
    else:
        directory["position"] = ""

    # Add anyone who only exists in velo.
    velo_pre = bundle.velo[bundle.velo["date"] <= as_of]
    if not velo_pre.empty:
        v = (
            velo_pre.sort_values(["name_key", "date"], kind="stable")
            .groupby("name_key", as_index=False)
            .tail(1)[["name_key", "athlete"]]
        )
        directory = directory.merge(v.rename(columns={"athlete": "velo_athlete"}), on="name_key", how="outer")
        directory["athlete"] = directory["athlete"].combine_first(directory["velo_athlete"])
        directory = directory.drop(columns=["velo_athlete"])

    directory["athlete"] = directory["athlete"].fillna(directory["name_key"])
    directory["position"] = directory.get("position", "").fillna("")
    directory = directory[directory["team"].isin(TEAM_ORDER)].copy()
    return directory.drop_duplicates("name_key", keep="last").reset_index(drop=True)


def build_hydration_view(
    bundle: SourceBundle,
    directory: pd.DataFrame,
    team_filter: str = "Full Organization",
) -> pd.DataFrame:
    """Resolve hydration records to the player's current dashboard team when possible."""
    columns = [
        "name_key", "athlete", "team", "position", "sodium_loss_mg_l",
        "classification", "result_raw", "recommendation", "source_tab", "source_book",
    ]
    if bundle.hydration.empty:
        return pd.DataFrame(columns=columns)

    hydration = bundle.hydration.copy()
    current = directory[["name_key", "athlete", "team", "position"]].drop_duplicates("name_key")
    view = hydration.merge(
        current,
        on="name_key",
        how="left",
        suffixes=("_hydration", ""),
    )
    view["athlete"] = view["athlete"].combine_first(view["athlete_hydration"])
    view["team"] = view["team"].combine_first(view["source_team"])
    view["position"] = view["position"].fillna("")
    view = view.drop(
        columns=[c for c in ["athlete_hydration", "source_team"] if c in view.columns]
    )

    if team_filter != "Full Organization":
        view = view[view["team"] == team_filter].copy()

    keep = [c for c in columns if c in view.columns]
    return view[keep].sort_values(["team", "athlete"], kind="stable").reset_index(drop=True)


def get_player_hydration(
    bundle: SourceBundle,
    name_key: str,
    current_team: str | None = None,
) -> pd.Series | None:
    """Return the best hydration row for one player, preferring the current-team source."""
    if bundle.hydration.empty:
        return None
    rows = bundle.hydration[bundle.hydration["name_key"] == name_key].copy()
    if rows.empty:
        return None
    if current_team:
        same_team = rows[rows["source_team"] == current_team]
        if not same_team.empty:
            rows = same_team
    with_numeric = rows[rows["sodium_loss_mg_l"].notna()]
    if not with_numeric.empty:
        rows = with_numeric
    return rows.iloc[-1]


# -----------------------------------------------------------------------------
# CHANGE SNAPSHOTS
# -----------------------------------------------------------------------------
def bodyweight_snapshot(
    jump: pd.DataFrame,
    as_of_date,
    recent_days: int,
    baseline_days: int,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).normalize()
    recent_start = as_of - pd.Timedelta(days=max(1, recent_days) - 1)
    baseline_end = recent_start - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=max(1, baseline_days) - 1)

    work = jump.dropna(subset=["bodyweight_lb"]).copy()
    current_window = work[(work["date"] >= recent_start) & (work["date"] <= as_of)].copy()
    baseline_window = work[(work["date"] >= baseline_start) & (work["date"] <= baseline_end)].copy()

    current = (
        current_window.sort_values(["name_key", "date"], kind="stable")
        .groupby("name_key", as_index=False)
        .tail(1)[["name_key", "bodyweight_lb", "date"]]
        .rename(columns={"bodyweight_lb": "bw_current_lb", "date": "bw_current_date"})
    )
    baseline = (
        baseline_window.groupby("name_key", as_index=False)
        .agg(
            bw_baseline_lb=("bodyweight_lb", "median"),
            bw_baseline_n=("bodyweight_lb", "count"),
            bw_baseline_first=("date", "min"),
            bw_baseline_last=("date", "max"),
        )
    )
    out = current.merge(baseline, on="name_key", how="outer")
    out["bw_change_lb"] = out["bw_current_lb"] - out["bw_baseline_lb"]
    out["bw_change_pct"] = np.where(
        out["bw_baseline_lb"].abs() > 1e-9,
        out["bw_change_lb"] / out["bw_baseline_lb"] * 100.0,
        np.nan,
    )
    return out


def ci_snapshot(
    jump: pd.DataFrame,
    as_of_date,
    recent_days: int,
    baseline_days: int,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).normalize()
    recent_start = as_of - pd.Timedelta(days=max(1, recent_days) - 1)
    baseline_end = recent_start - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=max(1, baseline_days) - 1)

    work = jump.dropna(subset=["ci"]).copy()
    recent = work[(work["date"] >= recent_start) & (work["date"] <= as_of)].copy()
    baseline = work[(work["date"] >= baseline_start) & (work["date"] <= baseline_end)].copy()

    recent_s = (
        recent.groupby("name_key", as_index=False)
        .agg(
            ci_current=("ci", "mean"),
            ci_recent_n=("ci", "count"),
            ci_current_date=("date", "max"),
        )
    )
    base_s = (
        baseline.groupby("name_key", as_index=False)
        .agg(
            ci_baseline=("ci", "mean"),
            ci_baseline_n=("ci", "count"),
            ci_baseline_first=("date", "min"),
            ci_baseline_last=("date", "max"),
        )
    )
    out = recent_s.merge(base_s, on="name_key", how="outer")
    out["ci_change"] = out["ci_current"] - out["ci_baseline"]
    out["ci_change_pct"] = np.where(
        out["ci_baseline"].abs() > 1e-9,
        out["ci_change"] / out["ci_baseline"] * 100.0,
        np.nan,
    )
    return out


def velo_snapshot(
    velo: pd.DataFrame,
    as_of_date,
) -> pd.DataFrame:
    """Compare the latest row's fb_velo with that same row's ytd_fb_velo."""
    as_of = pd.Timestamp(as_of_date).normalize()
    rows = []
    work = velo[
        (velo["date"] <= as_of)
        & velo["fb_velo"].notna()
        & velo["ytd_fb_velo"].notna()
    ].copy()

    for name_key, group in work.groupby("name_key", sort=False):
        current_row = group.sort_values("date").iloc[-1]
        rows.append({
            "name_key": name_key,
            "velo_current": float(current_row["fb_velo"]),
            "velo_current_date": current_row["date"],
            "velo_baseline": float(current_row["ytd_fb_velo"]),
            "velo_baseline_date": current_row["date"],
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=[
            "name_key", "velo_current", "velo_current_date", "velo_baseline",
            "velo_baseline_date", "velo_change", "velo_change_pct",
        ])

    # Negative values mean current FB velocity is below the player's YTD FB velocity.
    out["velo_change"] = out["velo_current"] - out["velo_baseline"]
    out["velo_change_pct"] = out["velo_change"] / out["velo_baseline"] * 100.0
    return out


def monthly_metric_snapshot(
    monthly: pd.DataFrame,
    metric_col: str,
    as_of_date,
    min_data_dates: int,
    prefix: str,
) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of_date).normalize()
    work = monthly[
        (monthly["as_of_date"] <= as_of)
        & monthly[metric_col].notna()
        & (monthly["data_dates"] >= max(1, int(min_data_dates)))
    ].copy()
    rows = []
    for name_key, group in work.groupby("name_key", sort=False):
        group = group.sort_values("month")
        if len(group) < 2:
            continue
        current = group.iloc[-1]
        previous = group.iloc[-2]
        rows.append({
            "name_key": name_key,
            f"{prefix}_current": float(current[metric_col]),
            f"{prefix}_current_month": current["month"],
            f"{prefix}_current_date": current["as_of_date"],
            f"{prefix}_current_days": int(current["data_dates"]),
            f"{prefix}_baseline": float(previous[metric_col]),
            f"{prefix}_baseline_month": previous["month"],
            f"{prefix}_baseline_date": previous["as_of_date"],
            f"{prefix}_baseline_days": int(previous["data_dates"]),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=[
            "name_key", f"{prefix}_current", f"{prefix}_current_month",
            f"{prefix}_current_date", f"{prefix}_current_days",
            f"{prefix}_baseline", f"{prefix}_baseline_month",
            f"{prefix}_baseline_date", f"{prefix}_baseline_days",
            f"{prefix}_change", f"{prefix}_change_pct",
        ])
    out[f"{prefix}_change"] = out[f"{prefix}_current"] - out[f"{prefix}_baseline"]
    out[f"{prefix}_change_pct"] = (
        out[f"{prefix}_change"] / out[f"{prefix}_baseline"] * 100.0
    )
    return out


@dataclass
class Thresholds:
    bw_monitor_pct: float
    bw_review_pct: float
    bw_direction: str
    ci_monitor_pct: float
    ci_review_pct: float
    velo_monitor_mph: float
    velo_review_mph: float
    bat_monitor_mph: float
    bat_review_mph: float
    sprint_monitor: float
    sprint_review: float
    escalate_multi: bool


def level_label(level: int) -> str:
    return {2: "Review", 1: "Monitor", 0: "Stable"}.get(int(level), "Stable")


def bw_flag_level(change_pct, thresholds: Thresholds) -> int:
    if pd.isna(change_pct):
        return 0
    value = float(change_pct)
    magnitude = abs(value) if thresholds.bw_direction == "Gain or loss" else max(0.0, -value)
    if magnitude >= thresholds.bw_review_pct:
        return 2
    if magnitude >= thresholds.bw_monitor_pct:
        return 1
    return 0


def decline_flag_level(change, monitor_threshold: float, review_threshold: float) -> int:
    if pd.isna(change):
        return 0
    decline = -float(change)
    if decline >= review_threshold:
        return 2
    if decline >= monitor_threshold:
        return 1
    return 0


def build_alert_table(
    bundle: SourceBundle,
    directory: pd.DataFrame,
    as_of_date,
    recent_days: int,
    baseline_days: int,
    bat_min_days: int,
    sprint_min_days: int,
    thresholds: Thresholds,
) -> pd.DataFrame:
    bw = bodyweight_snapshot(bundle.jump, as_of_date, recent_days, baseline_days)
    ci = ci_snapshot(bundle.jump, as_of_date, recent_days, baseline_days)
    velo = velo_snapshot(bundle.velo, as_of_date)
    bat = monthly_metric_snapshot(
        bundle.monthly, "monthly_avg_bat_speed", as_of_date, bat_min_days, "bat"
    )
    sprint = monthly_metric_snapshot(
        bundle.monthly, "monthly_max_sprint_speed", as_of_date, sprint_min_days, "sprint"
    )

    out = directory.copy()
    for frame in [bw, ci, velo, bat, sprint]:
        out = out.merge(frame, on="name_key", how="left")

    out["bw_level"] = out["bw_change_pct"].map(lambda x: bw_flag_level(x, thresholds))
    out["ci_level"] = out["ci_change_pct"].map(
        lambda x: decline_flag_level(x, thresholds.ci_monitor_pct, thresholds.ci_review_pct)
    )
    out["velo_level"] = out["velo_change"].map(
        lambda x: decline_flag_level(x, thresholds.velo_monitor_mph, thresholds.velo_review_mph)
    )
    out["bat_level"] = out["bat_change"].map(
        lambda x: decline_flag_level(x, thresholds.bat_monitor_mph, thresholds.bat_review_mph)
    )
    out["sprint_level"] = out["sprint_change"].map(
        lambda x: decline_flag_level(x, thresholds.sprint_monitor, thresholds.sprint_review)
    )

    # Role-specific performance metrics. The Master Roster uses positions such as
    # P, C, INF, and OF. FB velocity is pitcher-only; bat and sprint speed are
    # position-player-only. Bodyweight and CI remain applicable to everyone.
    pitcher_mask = out["position"].map(is_pitcher_position).fillna(False)
    position_player_mask = out["position"].map(is_position_player_position).fillna(False)
    out.loc[~pitcher_mask, "velo_level"] = 0
    out.loc[~position_player_mask, ["bat_level", "sprint_level"]] = 0

    # Freshness rule: an observation more than 30 days old can still be shown
    # historically, but it cannot generate a Monitor/Review flag. Freshness is
    # evaluated relative to the selected dashboard as-of date.
    as_of = pd.Timestamp(as_of_date).normalize()
    freshness_map = {
        "bw": ("bw_current_date", "bw_level"),
        "ci": ("ci_current_date", "ci_level"),
        "velo": ("velo_current_date", "velo_level"),
        "bat": ("bat_current_date", "bat_level"),
        "sprint": ("sprint_current_date", "sprint_level"),
    }
    for prefix, (date_col, level_col) in freshness_map.items():
        current_dates = pd.to_datetime(out[date_col], errors="coerce").dt.normalize()
        age_col = f"{prefix}_data_age_days"
        stale_col = f"{prefix}_stale"
        out[age_col] = (as_of - current_dates).dt.days
        out[stale_col] = current_dates.notna() & (out[age_col] > MAX_FLAG_AGE_DAYS)
        out.loc[out[stale_col], level_col] = 0

    level_cols = ["bw_level", "ci_level", "velo_level", "bat_level", "sprint_level"]
    out["flagged_metrics"] = (out[level_cols] > 0).sum(axis=1)
    out["review_metrics"] = (out[level_cols] == 2).sum(axis=1)
    out["overall_level"] = out[level_cols].max(axis=1).astype(int)
    if thresholds.escalate_multi:
        out.loc[out["flagged_metrics"] >= 2, "overall_level"] = 2
    out["Status"] = out["overall_level"].map(level_label)

    def reasons(row) -> str:
        items = []
        if row["bw_level"] > 0:
            items.append(f"BW {row['bw_change_pct']:+.1f}% ({row['bw_change_lb']:+.1f} lb)")
        if row["ci_level"] > 0:
            items.append(f"CI {row['ci_change_pct']:+.1f}%")
        if row["velo_level"] > 0:
            items.append(f"FB velo {row['velo_change']:+.1f} mph")
        if row["bat_level"] > 0:
            items.append(f"Bat speed {row['bat_change']:+.1f} mph")
        if row["sprint_level"] > 0:
            items.append(f"Sprint {row['sprint_change']:+.2f} ft/s")
        if thresholds.escalate_multi and row["overall_level"] == 2 and row["review_metrics"] == 0 and row["flagged_metrics"] >= 2:
            items.append("multi-metric escalation")
        return "; ".join(items) if items else "No threshold exceeded"

    out["Why flagged"] = out.apply(reasons, axis=1)

    # How much fresh, usable comparison data exists for each athlete. Stale
    # comparisons remain visible in detail/history but are not counted as current.
    comparison_map = {
        "bw": "bw_change_pct",
        "ci": "ci_change_pct",
        "velo": "velo_change",
        "bat": "bat_change",
        "sprint": "sprint_change",
    }
    fresh_comparisons = pd.DataFrame(index=out.index)
    applicability = {
        "bw": pd.Series(True, index=out.index),
        "ci": pd.Series(True, index=out.index),
        "velo": pitcher_mask,
        "bat": position_player_mask,
        "sprint": position_player_mask,
    }
    stale_applicable = pd.DataFrame(index=out.index)
    for prefix, comparison_col in comparison_map.items():
        applicable = applicability[prefix].fillna(False)
        fresh_comparisons[prefix] = (
            applicable
            & out[comparison_col].notna()
            & ~out[f"{prefix}_stale"].fillna(False)
        )
        stale_applicable[prefix] = applicable & out[f"{prefix}_stale"].fillna(False)
    out["metrics_with_comparison"] = fresh_comparisons.sum(axis=1)
    out["metrics_applicable"] = pd.DataFrame(applicability).sum(axis=1)
    out["stale_metrics"] = stale_applicable.sum(axis=1)

    status_order = {"Review": 0, "Monitor": 1, "Stable": 2}
    out["_status_order"] = out["Status"].map(status_order).fillna(3)
    return out.sort_values(
        ["_status_order", "flagged_metrics", "team", "athlete"],
        ascending=[True, False, True, True],
        kind="stable",
    ).drop(columns=["_status_order"]).reset_index(drop=True)


# -----------------------------------------------------------------------------
# VISUALS
# -----------------------------------------------------------------------------
def build_metric_change_bar(
    df: pd.DataFrame,
    change_col: str,
    title: str,
    unit: str,
    top_n: int = 20,
    pct: bool = False,
) -> go.Figure:
    work = df[["athlete", "team", "Status", change_col]].dropna().copy()
    work = work.sort_values(change_col).head(top_n)
    fig = go.Figure()
    if work.empty:
        fig.add_annotation(
            text="No valid comparisons for the selected filters.",
            x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
            font={"color": SUBTEXT, "size": 14},
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return base_figure_layout(fig, 360)

    colors = [
        ACCENT_RED if s == "Review" else AMBER if s == "Monitor" else BLUE
        for s in work["Status"]
    ]
    custom = np.column_stack([work["team"], work["Status"]])
    fig.add_trace(go.Bar(
        x=work[change_col],
        y=work["athlete"],
        orientation="h",
        marker={"color": colors},
        customdata=custom,
        hovertemplate=(
            "<b>%{y}</b><br>Team: %{customdata[0]}<br>Status: %{customdata[1]}<br>"
            + title + ": %{x:.2f}" + ("%" if pct else f" {unit}") + "<extra></extra>"
        ),
    ))
    fig.add_vline(x=0, line_color=BORDER, line_width=1.5)
    fig.update_yaxes(
        autorange="reversed", showgrid=False, linecolor=BORDER,
        tickfont={"color": TEXT}, automargin=True,
    )
    fig.update_xaxes(
        title=title + (" (%)" if pct else (f" ({unit})" if unit else "")),
        showgrid=True, gridcolor=GRID, zeroline=False, linecolor=BORDER,
        tickfont={"color": SUBTEXT}, title_font={"color": SUBTEXT},
    )
    return base_figure_layout(fig, max(360, 32 * len(work) + 120))


def build_team_flag_chart(df: pd.DataFrame) -> go.Figure:
    team = (
        df.groupby("team", as_index=False)
        .agg(
            Players=("name_key", "nunique"),
            Review=("Status", lambda s: int((s == "Review").sum())),
            Monitor=("Status", lambda s: int((s == "Monitor").sum())),
        )
    )
    order = {team_name: i for i, team_name in enumerate(TEAM_ORDER)}
    team["_order"] = team["team"].map(order).fillna(999)
    team = team.sort_values(["_order", "team"]).drop(columns="_order")

    fig = go.Figure()
    if team.empty:
        return base_figure_layout(fig, 360)
    fig.add_trace(go.Bar(
        x=team["team"], y=team["Review"], name="Review",
        marker={"color": ACCENT_RED},
    ))
    fig.add_trace(go.Bar(
        x=team["team"], y=team["Monitor"], name="Monitor",
        marker={"color": AMBER},
    ))
    fig.update_layout(barmode="stack", showlegend=True)
    fig.update_xaxes(showgrid=False, linecolor=BORDER, tickfont={"color": SUBTEXT})
    fig.update_yaxes(
        title="Flagged players", rangemode="tozero", dtick=1,
        showgrid=True, gridcolor=GRID, linecolor=BORDER,
        tickfont={"color": SUBTEXT}, title_font={"color": SUBTEXT},
    )
    fig = base_figure_layout(fig, 390)
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "x": 0, "y": 1.12, "font": {"color": SUBTEXT}},
    )
    return fig


def build_flag_metric_chart(df: pd.DataFrame) -> go.Figure:
    metrics = [
        ("Bodyweight", "bw_level"),
        ("CI", "ci_level"),
        ("FB velo", "velo_level"),
        ("Bat speed", "bat_level"),
        ("Sprint speed", "sprint_level"),
    ]
    rows = []
    for label, col in metrics:
        rows.append({
            "Metric": label,
            "Review": int((df[col] == 2).sum()),
            "Monitor": int((df[col] == 1).sum()),
        })
    summary = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=summary["Metric"], x=summary["Review"], name="Review", orientation="h",
        marker={"color": ACCENT_RED},
    ))
    fig.add_trace(go.Bar(
        y=summary["Metric"], x=summary["Monitor"], name="Monitor", orientation="h",
        marker={"color": AMBER},
    ))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(autorange="reversed", showgrid=False, linecolor=BORDER)
    fig.update_xaxes(
        title="Players", dtick=1, rangemode="tozero", showgrid=True,
        gridcolor=GRID, linecolor=BORDER, tickfont={"color": SUBTEXT},
        title_font={"color": SUBTEXT},
    )
    fig = base_figure_layout(fig, 360)
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "x": 0, "y": 1.14, "font": {"color": SUBTEXT}},
    )
    return fig


def build_time_series(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    title: str,
    y_title: str,
    reference_value=None,
) -> go.Figure:
    work = df[[date_col, value_col]].dropna().sort_values(date_col)
    fig = go.Figure()
    if work.empty:
        fig.add_annotation(
            text="No data available.", x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font={"color": SUBTEXT, "size": 14},
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return base_figure_layout(fig, 300)
    fig.add_trace(go.Scatter(
        x=work[date_col], y=work[value_col], mode="lines+markers",
        line={"color": BLUE, "width": 2.4},
        marker={"size": 7, "color": BLUE},
        hovertemplate=f"<b>{title}</b><br>%{{x|%b %d, %Y}}<br>%{{y:.2f}}<extra></extra>",
    ))
    if reference_value is not None and not pd.isna(reference_value):
        fig.add_hline(
            y=float(reference_value), line_color=TEAL, line_dash="dash", line_width=1.5,
            annotation_text="Comparison baseline", annotation_font_color=TEAL,
        )
    fig.update_xaxes(showgrid=False, linecolor=BORDER, tickfont={"color": SUBTEXT})
    fig.update_yaxes(
        title=y_title, showgrid=True, gridcolor=GRID, zeroline=False,
        linecolor=BORDER, tickfont={"color": SUBTEXT}, title_font={"color": SUBTEXT},
    )
    return base_figure_layout(fig, 300)


def build_velo_time_series(df: pd.DataFrame) -> go.Figure:
    """Plot game/current fb_velo and ytd_fb_velo together over time."""
    work = df[["date", "fb_velo", "ytd_fb_velo"]].dropna().sort_values("date")
    fig = go.Figure()
    if work.empty:
        fig.add_annotation(
            text="No data available.", x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font={"color": SUBTEXT, "size": 14},
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return base_figure_layout(fig, 300)

    fig.add_trace(go.Scatter(
        x=work["date"], y=work["fb_velo"], mode="lines+markers",
        name="FB Velo",
        line={"color": ACCENT_RED, "width": 2.3},
        marker={"size": 7, "color": ACCENT_RED},
        hovertemplate="<b>FB Velo</b><br>%{x|%b %d, %Y}<br>%{y:.2f} mph<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=work["date"], y=work["ytd_fb_velo"], mode="lines",
        name="YTD FB Velo",
        line={"color": NAVY_MID, "width": 2.0, "dash": "dash"},
        hovertemplate="<b>YTD FB Velo</b><br>%{x|%b %d, %Y}<br>%{y:.2f} mph<extra></extra>",
    ))
    fig.update_xaxes(showgrid=False, linecolor=BORDER, tickfont={"color": SUBTEXT})
    fig.update_yaxes(
        title="Fastball velocity (mph)", showgrid=True, gridcolor=GRID, zeroline=False,
        linecolor=BORDER, tickfont={"color": SUBTEXT}, title_font={"color": SUBTEXT},
    )
    fig = base_figure_layout(fig, 300)
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "x": 0, "y": 1.12, "font": {"color": SUBTEXT}},
    )
    return fig



# -----------------------------------------------------------------------------
# INDIVIDUAL PLAYER PDF REPORTS
# -----------------------------------------------------------------------------
def safe_filename(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return value.strip("_") or "player"


def _report_metric_status(row: pd.Series, prefix: str, comparison_col: str) -> str:
    if bool(row.get(f"{prefix}_stale", False)):
        return f"Stale >{MAX_FLAG_AGE_DAYS}d"
    if pd.isna(row.get(comparison_col, np.nan)):
        return "No comparison"
    return level_label(int(row.get(f"{prefix}_level", 0)))


def _report_status_color(status: str):
    if status == "Review":
        return HexColor(ACCENT_RED)
    if status == "Monitor":
        return HexColor(AMBER)
    if status.startswith("Stale") or status == "No comparison":
        return HexColor(SUBTEXT)
    return HexColor(GREEN)


def hydration_report_summary(hydration_record: pd.Series | None) -> dict | None:
    """Return the sweat-test result exactly as provided by the source sheet.

    No threshold or salty-sweater classification is inferred in the dashboard.
    If the source Sodium Loss / Results cell is blank, hydration is omitted from
    the individual report entirely.
    """
    if hydration_record is None:
        return None

    result_raw = str(hydration_record.get("result_raw", "") or "").strip()
    if not result_raw:
        return None

    return {
        "value": result_raw,
    }


def _pdf_draw_metric_table(
    c,
    row: pd.Series,
    x: float,
    y_top: float,
    width: float,
) -> float:
    # Bodyweight and CI apply to everyone. Role-specific performance metrics are
    # shown only for the appropriate roster position.
    rows = [
        (
            "Bodyweight",
            fmt(row.get("bw_current_lb"), 1, " lb"),
            fmt(row.get("bw_baseline_lb"), 1, " lb"),
            f"{fmt_signed(row.get('bw_change_lb'), 1, ' lb')} / {fmt_signed(row.get('bw_change_pct'), 1, '%')}",
            _report_metric_status(row, "bw", "bw_change_pct"),
        ),
        (
            "CI",
            fmt(row.get("ci_current"), 1, " N s"),
            fmt(row.get("ci_baseline"), 1, " N s"),
            fmt_signed(row.get("ci_change_pct"), 1, "%"),
            _report_metric_status(row, "ci", "ci_change_pct"),
        ),
    ]

    position = row.get("position", "")
    if is_pitcher_position(position):
        rows.append(
            (
                "FB Velo",
                fmt(row.get("velo_current"), 2, " mph"),
                fmt(row.get("velo_baseline"), 2, " mph"),
                fmt_signed(row.get("velo_change"), 2, " mph"),
                _report_metric_status(row, "velo", "velo_change"),
            )
        )
    elif is_position_player_position(position):
        rows.extend([
            (
                "Bat Speed",
                fmt(row.get("bat_current"), 2, " mph"),
                fmt(row.get("bat_baseline"), 2, " mph"),
                fmt_signed(row.get("bat_change"), 2, " mph"),
                _report_metric_status(row, "bat", "bat_change"),
            ),
            (
                "Sprint Speed",
                fmt(row.get("sprint_current"), 2, " ft/s"),
                fmt(row.get("sprint_baseline"), 2, " ft/s"),
                fmt_signed(row.get("sprint_change"), 2, " ft/s"),
                _report_metric_status(row, "sprint", "sprint_change"),
            ),
        ])

    headers = ["Metric", "Current", "Comparison", "Change", "Status"]
    fractions = [0.18, 0.20, 0.20, 0.23, 0.19]
    col_widths = [width * f for f in fractions]
    row_h = 22

    c.setFillColor(HexColor(NAVY))
    c.roundRect(x, y_top - row_h, width, row_h, 5, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 8.2)
    cx = x
    for header, cw in zip(headers, col_widths):
        c.drawString(cx + 5, y_top - 14.5, header)
        cx += cw

    y = y_top - row_h
    for i, values in enumerate(rows):
        y -= row_h
        c.setFillColor(HexColor("#F8FAFC") if i % 2 == 0 else HexColor("#FFFFFF"))
        c.rect(x, y, width, row_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor(BORDER))
        c.line(x, y, x + width, y)
        cx = x
        for j, (value, cw) in enumerate(zip(values, col_widths)):
            if j == 4:
                c.setFillColor(_report_status_color(str(value)))
                c.setFont("Helvetica-Bold", 7.8)
            else:
                c.setFillColor(HexColor(TEXT))
                c.setFont("Helvetica", 7.8)
            text = "-" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
            max_chars = max(6, int(cw / 4.5))
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "..."
            c.drawString(cx + 5, y + 7.2, text)
            cx += cw
    return y


def _pdf_draw_series_chart(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    dates,
    values,
    unit: str,
    baseline=None,
    second_values=None,
    second_label: str | None = None,
) -> None:
    c.setStrokeColor(HexColor(BORDER))
    c.setFillColor(HexColor("#FFFFFF"))
    c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
    c.setFillColor(HexColor(NAVY))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 8, y + h - 14, title)

    plot_x = x + 30
    plot_y = y + 20
    plot_w = max(20, w - 42)
    plot_h = max(20, h - 42)

    d = pd.to_datetime(pd.Series(dates), errors="coerce")
    v = pd.to_numeric(pd.Series(values), errors="coerce")
    valid = d.notna() & v.notna()
    d = d[valid].reset_index(drop=True)
    v = v[valid].reset_index(drop=True)

    second = None
    if second_values is not None:
        second_all = pd.to_numeric(pd.Series(second_values), errors="coerce")
        second = second_all[valid].reset_index(drop=True)

    if len(v) == 0:
        c.setFillColor(HexColor(SUBTEXT))
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + w / 2, y + h / 2, "No data")
        return

    all_vals = v.tolist()
    if second is not None:
        all_vals += second.dropna().tolist()
    if baseline is not None and not pd.isna(baseline):
        all_vals.append(float(baseline))
    vmin = float(np.nanmin(all_vals))
    vmax = float(np.nanmax(all_vals))
    if np.isclose(vmin, vmax):
        pad = max(abs(vmin) * 0.02, 0.5)
    else:
        pad = (vmax - vmin) * 0.12
    ymin = vmin - pad
    ymax = vmax + pad

    if len(d) == 1 or d.max() == d.min():
        xs = np.array([plot_x + plot_w / 2] * len(d), dtype=float)
    else:
        span = (d.max() - d.min()).total_seconds()
        xs = np.array([
            plot_x + ((dt - d.min()).total_seconds() / span) * plot_w for dt in d
        ])

    def ymap(val):
        return plot_y + ((float(val) - ymin) / max(ymax - ymin, 1e-9)) * plot_h

    c.setStrokeColor(HexColor(GRID))
    c.setLineWidth(0.5)
    for frac in [0.0, 0.5, 1.0]:
        yy = plot_y + frac * plot_h
        c.line(plot_x, yy, plot_x + plot_w, yy)

    if baseline is not None and not pd.isna(baseline):
        c.saveState()
        c.setDash(3, 2)
        c.setStrokeColor(HexColor(TEAL))
        c.setLineWidth(1)
        yy = ymap(float(baseline))
        c.line(plot_x, yy, plot_x + plot_w, yy)
        c.restoreState()

    def draw_line(vals, color, line_width=1.6):
        points = [(float(xx), ymap(val)) for xx, val in zip(xs, vals) if not pd.isna(val)]
        if not points:
            return
        c.setStrokeColor(HexColor(color))
        c.setFillColor(HexColor(color))
        c.setLineWidth(line_width)
        if len(points) > 1:
            path = c.beginPath()
            path.moveTo(points[0][0], points[0][1])
            for px, py in points[1:]:
                path.lineTo(px, py)
            c.drawPath(path, stroke=1, fill=0)
        for px, py in points[-12:]:
            c.circle(px, py, 1.6, fill=1, stroke=0)

    draw_line(v, BLUE)
    if second is not None:
        draw_line(second, NAVY_MID, 1.2)

    c.setFillColor(HexColor(SUBTEXT))
    c.setFont("Helvetica", 6.5)
    c.drawRightString(plot_x - 3, plot_y + plot_h - 2, f"{vmax:.1f}")
    c.drawRightString(plot_x - 3, plot_y - 1, f"{vmin:.1f}")
    if len(d):
        c.drawString(plot_x, y + 6, d.min().strftime("%b %Y"))
        c.drawRightString(plot_x + plot_w, y + 6, d.max().strftime("%b %Y"))
    c.setFillColor(HexColor(TEXT))
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(x + w - 8, y + h - 14, f"{v.iloc[-1]:.2f} {unit}")
    if second is not None and second_label and len(second.dropna()):
        c.setFillColor(HexColor(SUBTEXT))
        c.setFont("Helvetica", 6.5)
        c.drawRightString(x + w - 8, y + h - 24, f"{second_label}: {second.dropna().iloc[-1]:.2f}")


def _pdf_wrap_text(
    c,
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    max_lines: int = 4,
) -> list[str]:
    """Wrap report notes to a small number of PDF lines without overflowing the box."""
    raw = str(text or "").strip()
    if not raw:
        return []

    lines: list[str] = []
    paragraphs = raw.splitlines() or [raw]
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            if lines and len(lines) < max_lines:
                lines.append("")
            continue
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if c.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                    if len(lines) >= max_lines:
                        break
                current = word
        if len(lines) >= max_lines:
            break
        if current:
            lines.append(current)
        if len(lines) >= max_lines:
            break

    # If the source text did not fully fit, mark the last visible line as truncated.
    rendered = " ".join(line for line in lines if line)
    normalized = " ".join(raw.split())
    if len(lines) >= max_lines and rendered != normalized:
        last = lines[-1].rstrip()
        suffix = "..."
        while last and c.stringWidth(last + suffix, font_name, font_size) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last + suffix) if last else suffix
    return lines[:max_lines]


def _pdf_draw_notes_box(
    c,
    x: float,
    y_top: float,
    width: float,
    notes: str,
) -> float:
    """Draw optional staff notes and return the bottom y-coordinate."""
    font_name = "Helvetica"
    font_size = 7.4
    lines = _pdf_wrap_text(c, notes, font_name, font_size, width - 18, max_lines=4)
    if not lines:
        return y_top

    box_h = max(38, 21 + len(lines) * 9)
    y = y_top - box_h
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(HexColor(BORDER))
    c.roundRect(x, y, width, box_h, 6, fill=1, stroke=1)
    c.setFillColor(HexColor(NAVY))
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(x + 9, y_top - 13, "REPORT NOTES")
    c.setFillColor(HexColor(TEXT))
    c.setFont(font_name, font_size)
    line_y = y_top - 24
    for line in lines:
        c.drawString(x + 9, line_y, line)
        line_y -= 9
    return y


def generate_player_report_pdf(
    row: pd.Series,
    bundle: SourceBundle,
    as_of_date,
    report_notes: str = "",
) -> bytes:
    buffer = io.BytesIO()
    page_w, page_h = landscape(letter)
    c = pdf_canvas.Canvas(buffer, pagesize=(page_w, page_h))
    c.setTitle(f"Nutrition Early Warning - {row.get('athlete', 'Player')}")

    # Header
    c.setFillColor(HexColor(NAVY))
    c.rect(0, page_h - 70, page_w, 70, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(34, page_h - 31, "Nutrition Early Warning - Player Report")
    c.setFont("Helvetica", 9)
    c.drawString(34, page_h - 49, f"As of {fmt_date(as_of_date)}")

    athlete = str(row.get("athlete", "Player"))
    team = str(row.get("team", ""))
    position = str(row.get("position", "") or "")
    c.setFont("Helvetica-Bold", 17)
    c.drawRightString(page_w - 34, page_h - 31, athlete)
    c.setFont("Helvetica", 9)
    subtitle = team + (f" | {position}" if position else "")
    c.drawRightString(page_w - 34, page_h - 49, subtitle)

    # Hydration is report-only when an actual result exists.
    hydration_record = get_player_hydration(
        bundle,
        str(row.get("name_key", "")),
        str(row.get("team", "") or ""),
    )
    hydration_summary = hydration_report_summary(hydration_record)

    # Summary cards: keep overall status, plus the source-sheet sweat-test result when present.
    card_y = page_h - 124
    card_h = 38
    card_gap = 8
    cards = [
        (
            "Overall Status",
            str(row.get("Status", "Stable")),
            _report_status_color(str(row.get("Status", "Stable"))),
        ),
    ]
    if hydration_summary is not None:
        cards.append(
            (
                "Sweat Test",
                hydration_summary["value"],
                HexColor(TEAL),
            )
        )

    card_w = 210
    for i, (label, value, color) in enumerate(cards):
        xx = 34 + i * (card_w + card_gap)
        c.setFillColor(HexColor("#FFFFFF"))
        c.setStrokeColor(HexColor(BORDER))
        c.roundRect(xx, card_y, card_w, card_h, 6, fill=1, stroke=1)
        c.setFillColor(HexColor(SUBTEXT))
        c.setFont("Helvetica-Bold", 6.8)
        c.drawString(xx + 8, card_y + 25, label.upper())
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 11.5 if len(value) > 22 else 13)
        display_value = value if len(value) <= 32 else value[:29] + "..."
        c.drawString(xx + 8, card_y + 8, display_value)

    # Flag reason / review cue
    reason = str(row.get("Why flagged", "No threshold exceeded"))
    c.setFillColor(HexColor("#FFF8E8") if row.get("Status") == "Monitor" else HexColor("#FFF1F3") if row.get("Status") == "Review" else HexColor("#F8FAFC"))
    c.setStrokeColor(_report_status_color(str(row.get("Status", "Stable"))))
    c.roundRect(34, page_h - 165, page_w - 68, 27, 6, fill=1, stroke=1)
    c.setFillColor(HexColor(TEXT))
    c.setFont("Helvetica-Bold", 8)
    cue = "Review cue: " + reason
    if len(cue) > 150:
        cue = cue[:147] + "..."
    c.drawString(43, page_h - 154, cue)

    # Metric summary table. No age column and no hydration row.
    table_bottom = _pdf_draw_metric_table(
        c,
        row,
        34,
        page_h - 184,
        page_w - 68,
    )

    # Optional staff notes entered from the report-generation tab.
    notes_bottom = table_bottom
    if str(report_notes or "").strip():
        notes_bottom = _pdf_draw_notes_box(
            c,
            34,
            table_bottom - 9,
            page_w - 68,
            str(report_notes).strip(),
        )

    # History windows used in charts
    as_of = pd.Timestamp(as_of_date).normalize()
    history_start = as_of - pd.Timedelta(days=365)
    key = row.get("name_key")
    jump_player = bundle.jump[
        (bundle.jump["name_key"] == key)
        & (bundle.jump["date"] >= history_start)
        & (bundle.jump["date"] <= as_of)
    ].copy()
    velo_player = bundle.velo[
        (bundle.velo["name_key"] == key)
        & (bundle.velo["date"] >= history_start)
        & (bundle.velo["date"] <= as_of)
    ].copy()
    monthly_player = bundle.monthly[
        (bundle.monthly["name_key"] == key)
        & (bundle.monthly["as_of_date"] >= history_start)
        & (bundle.monthly["as_of_date"] <= as_of)
    ].copy()

    # Role-specific trend panels. Everyone gets BW + CI. Pitchers get FB velo;
    # position players get bat speed + sprint speed.
    chart_defs = [
        (
            "Bodyweight - last 12 months",
            jump_player.get("date", pd.Series(dtype="datetime64[ns]")),
            jump_player.get("bodyweight_lb", pd.Series(dtype=float)),
            "lb", row.get("bw_baseline_lb"), None, None,
        ),
        (
            "CI - last 12 months",
            jump_player.get("date", pd.Series(dtype="datetime64[ns]")),
            jump_player.get("ci", pd.Series(dtype=float)),
            "N s", row.get("ci_baseline"), None, None,
        ),
    ]

    if is_pitcher_position(position):
        chart_defs.append(
            (
                "FB Velo vs YTD - last 12 months",
                velo_player.get("date", pd.Series(dtype="datetime64[ns]")),
                velo_player.get("fb_velo", pd.Series(dtype=float)),
                "mph", None,
                velo_player.get("ytd_fb_velo", pd.Series(dtype=float)), "YTD",
            )
        )
    elif is_position_player_position(position):
        chart_defs.extend([
            (
                "Bat Speed - last 12 months",
                monthly_player.get("as_of_date", pd.Series(dtype="datetime64[ns]")),
                monthly_player.get("monthly_avg_bat_speed", pd.Series(dtype=float)),
                "mph", row.get("bat_baseline"), None, None,
            ),
            (
                "Sprint Speed - last 12 months",
                monthly_player.get("as_of_date", pd.Series(dtype="datetime64[ns]")),
                monthly_player.get("monthly_max_sprint_speed", pd.Series(dtype=float)),
                "ft/s", row.get("sprint_baseline"), None, None,
            ),
        ])

    charts_top = notes_bottom - 12
    chart_gap = 8
    n_charts = len(chart_defs)
    # Keep enough room for a notes box on position-player reports, which use two chart rows.
    chart_h = 84 if (str(report_notes or "").strip() and n_charts == 4) else 96 if str(report_notes or "").strip() else 105
    n_cols = 3 if n_charts == 3 else 2
    chart_w = (page_w - 68 - chart_gap * (n_cols - 1)) / n_cols

    for idx, (title, dates, values, unit, baseline, second_values, second_label) in enumerate(chart_defs):
        chart_row = idx // n_cols
        chart_col = idx % n_cols
        x = 34 + chart_col * (chart_w + chart_gap)
        y = charts_top - chart_h - chart_row * (chart_h + chart_gap)
        _pdf_draw_series_chart(
            c, x, y, chart_w, chart_h,
            title, dates, values, unit, baseline,
            second_values=second_values,
            second_label=second_label,
        )

    c.setFillColor(HexColor(SUBTEXT))
    c.setFont("Helvetica", 6.7)
    c.drawString(
        34, 10,
        f"Flags are review cues only. Metrics with latest data >{MAX_FLAG_AGE_DAYS} days old are shown as stale and cannot generate a flag.",
    )
    c.drawRightString(page_w - 34, 10, "Nutrition Early Warning")
    c.save()
    return buffer.getvalue()


def generate_player_reports_zip(
    alerts_view: pd.DataFrame,
    bundle: SourceBundle,
    as_of_date,
    notes_by_player: dict[str, str] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    notes_by_player = notes_by_player or {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for _, row in alerts_view.sort_values(["team", "athlete"], kind="stable").iterrows():
            player_notes = notes_by_player.get(str(row.get("name_key", "")), "")
            pdf_bytes = generate_player_report_pdf(
                row, bundle, as_of_date, report_notes=player_notes
            )
            team_part = safe_filename(str(row.get("team", "Unassigned")))
            player_part = safe_filename(str(row.get("athlete", "Player")))
            filename = f"{team_part}/{player_part}_nutrition_report.pdf"
            zf.writestr(filename, pdf_bytes)
    return buffer.getvalue()


# -----------------------------------------------------------------------------
# PASSWORD AUTHENTICATION
# -----------------------------------------------------------------------------
def require_password() -> None:
    try:
        configured_password = st.secrets.get("APP_PASSWORD")
    except Exception:
        configured_password = None
    if not configured_password:
        configured_password = os.environ.get("APP_PASSWORD")

    if not configured_password:
        st.error(
            "APP_PASSWORD is not configured. Add APP_PASSWORD to Streamlit Secrets before using the dashboard."
        )
        st.stop()

    if st.session_state.get("password_correct", False):
        return

    def _check_password() -> None:
        entered_password = str(st.session_state.get("app_password_input", ""))
        if hmac.compare_digest(entered_password, str(configured_password)):
            st.session_state["password_correct"] = True
            st.session_state.pop("app_password_input", None)
        else:
            st.session_state["password_correct"] = False

    st.markdown("<div style='max-width:520px;margin:10vh auto 0;'>", unsafe_allow_html=True)
    st.title("Nutrition Early Warning")
    st.write("Enter the app password to continue.")
    with st.form("app_password_form", clear_on_submit=False):
        st.text_input("Password", type="password", key="app_password_input")
        submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")
    if submitted:
        _check_password()
        if st.session_state.get("password_correct", False):
            st.rerun()
    if st.session_state.get("password_correct") is False:
        st.error("Incorrect password.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# -----------------------------------------------------------------------------
# APP
# -----------------------------------------------------------------------------
require_password()

with st.sidebar:
    st.markdown(
        "<div style='height:4px;width:42px;border-radius:999px;background:#C8102E;margin:2px 0 14px;'></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h2 style='color:#FFFFFF;margin:0 0 4px;font-size:25px;letter-spacing:-.03em;'>Nutrition Early Warning</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='color:#AFC3DE;font-size:12px;margin-bottom:17px;'>Bodyweight × performance change monitoring</div>",
        unsafe_allow_html=True,
    )
    refresh = st.button("↻ Refresh data", use_container_width=True, type="primary")

if refresh:
    load_source_data.clear()

try:
    bundle = load_source_data()
except Exception as exc:
    st.error(f"Could not load data. {exc}")
    st.stop()

all_dates = pd.concat(
    [
        bundle.jump["date"],
        bundle.velo["date"],
        bundle.monthly["as_of_date"],
    ],
    ignore_index=True,
).dropna()
if all_dates.empty:
    st.error("No valid dates were found in the source data.")
    st.stop()

min_date = all_dates.min().date()
max_date = all_dates.max().date()

with st.sidebar:
    as_of_date = st.date_input(
        "As-of date",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

    directory_for_teams = build_player_directory(bundle, as_of_date)
    found_teams = [t for t in directory_for_teams["team"].dropna().unique().tolist() if t]
    team_order_map = {team: i for i, team in enumerate(TEAM_ORDER)}
    found_teams = sorted(found_teams, key=lambda x: (team_order_map.get(x, 999), x))
    team_filter = st.selectbox("Team", ["Full Organization"] + found_teams)

    st.markdown("---")
    st.markdown("**Comparison windows**")
    recent_days = st.slider("Recent BW / CI window", 7, 28, 14, 1)
    baseline_days = st.slider("Prior BW / CI baseline", 14, 56, 28, 7)
    bat_min_days = st.slider("Bat-speed minimum data dates", 1, 20, 7, 1)
    sprint_min_days = st.slider("Sprint-speed minimum data dates", 1, 25, 14, 1)

    with st.expander("Alert thresholds", expanded=False):
        st.caption("Review thresholds must be at least as large as Monitor thresholds.")
        bw_direction = st.selectbox("Bodyweight flag direction", ["Gain or loss", "Loss only"])
        bw_monitor_pct = st.slider("BW Monitor |% change|", 0.5, 6.0, 2.0, 0.5)
        bw_review_pct = st.slider("BW Review |% change|", bw_monitor_pct, 10.0, max(4.0, bw_monitor_pct), 0.5)

        ci_monitor_pct = st.slider("CI Monitor decline %", 1.0, 15.0, 5.0, 0.5)
        ci_review_pct = st.slider("CI Review decline %", ci_monitor_pct, 25.0, max(10.0, ci_monitor_pct), 0.5)

        velo_monitor_mph = st.slider("FB velo Monitor decline", 0.25, 3.0, 1.0, 0.25)
        velo_review_mph = st.slider("FB velo Review decline", velo_monitor_mph, 5.0, max(2.0, velo_monitor_mph), 0.25)

        bat_monitor_mph = st.slider("Bat speed Monitor decline", 0.25, 4.0, 1.0, 0.25)
        bat_review_mph = st.slider("Bat speed Review decline", bat_monitor_mph, 6.0, max(2.0, bat_monitor_mph), 0.25)

        sprint_monitor = st.slider("Sprint Monitor decline (ft/s)", 0.10, 2.0, 0.50, 0.10)
        sprint_review = st.slider("Sprint Review decline (ft/s)", sprint_monitor, 3.0, max(1.0, sprint_monitor), 0.10)

        escalate_multi = st.checkbox("Escalate 2+ Monitor metrics to Review", value=True)

thresholds = Thresholds(
    bw_monitor_pct=bw_monitor_pct,
    bw_review_pct=bw_review_pct,
    bw_direction=bw_direction,
    ci_monitor_pct=ci_monitor_pct,
    ci_review_pct=ci_review_pct,
    velo_monitor_mph=velo_monitor_mph,
    velo_review_mph=velo_review_mph,
    bat_monitor_mph=bat_monitor_mph,
    bat_review_mph=bat_review_mph,
    sprint_monitor=sprint_monitor,
    sprint_review=sprint_review,
    escalate_multi=escalate_multi,
)

directory = build_player_directory(bundle, as_of_date)
alerts_all = build_alert_table(
    bundle=bundle,
    directory=directory,
    as_of_date=as_of_date,
    recent_days=recent_days,
    baseline_days=baseline_days,
    bat_min_days=bat_min_days,
    sprint_min_days=sprint_min_days,
    thresholds=thresholds,
)

alerts = alerts_all.copy()
if team_filter != "Full Organization":
    alerts = alerts[alerts["team"] == team_filter].copy()

with st.sidebar:
    st.markdown("---")
    st.caption(bundle.status)
    st.caption(bundle.hydration_status)
    st.caption(f"Bodyweight source column: {bundle.bw_source_col}")

st.title("Nutrition Early Warning")
st.markdown(
    "Track bodyweight alongside CI, fastball velocity, bat speed, and sprint speed. "
    "Flags are intended to create a **review queue**, not label the cause of a change."
)

review_n = int((alerts["Status"] == "Review").sum())
monitor_n = int((alerts["Status"] == "Monitor").sum())
stable_n = int((alerts["Status"] == "Stable").sum())
tracked_n = int(alerts["name_key"].nunique())

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(metric_card("Players in view", f"{tracked_n:,}", BLUE, team_filter), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card("Review", f"{review_n:,}", ACCENT_RED, "Highest-priority queue"), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card("Monitor", f"{monitor_n:,}", AMBER, "Watch for continued change"), unsafe_allow_html=True)
with c4:
    st.markdown(metric_card("Stable", f"{stable_n:,}", GREEN, "No threshold exceeded"), unsafe_allow_html=True)

st.caption(
    f"As of {fmt_date(as_of_date)} · BW/CI recent {recent_days}d vs prior {baseline_days}d · "
    f"FB velo = current fb_velo vs same-row YTD · Bat minimum {bat_min_days} dates/month · "
    f"Sprint minimum {sprint_min_days} dates/month · Data >{MAX_FLAG_AGE_DAYS} days old cannot flag"
)

(
    overview_tab,
    bw_tab,
    ci_tab,
    velo_tab,
    bat_tab,
    sprint_tab,
    hydration_tab,
    player_tab,
    report_tab,
    data_tab,
) = st.tabs([
    "Overview",
    "Bodyweight",
    "CI",
    "FB Velo",
    "Bat Speed",
    "Sprint Speed",
    "Hydration",
    "Player Trends",
    "Player Reports",
    "Data Coverage",
])


# ----- OVERVIEW -----
with overview_tab:
    left, right = st.columns([1.15, 0.85])
    with left:
        with st.container(border=True):
            st.subheader("Priority Queue", anchor=False)
            priority = alerts[alerts["Status"].isin(["Review", "Monitor"])].copy()
            if priority.empty:
                st.success("No players currently exceed the selected alert thresholds.")
            else:
                display = priority[[
                    "athlete", "team", "position", "Status", "Why flagged",
                    "bw_change_pct", "ci_change_pct", "velo_change", "bat_change",
                    "sprint_change", "metrics_with_comparison",
                ]].copy()
                display.columns = [
                    "Player", "Team", "Position", "Status", "Why flagged",
                    "BW Δ %", "CI Δ %", "FB Velo Δ", "Bat Speed Δ",
                    "Sprint Δ", "Comparable Metrics",
                ]
                st.dataframe(
                    display,
                    hide_index=True,
                    use_container_width=True,
                    height=min(720, 44 + 36 * (len(display) + 1)),
                    column_config={
                        "BW Δ %": st.column_config.NumberColumn(format="%+.1f%%"),
                        "CI Δ %": st.column_config.NumberColumn(format="%+.1f%%"),
                        "FB Velo Δ": st.column_config.NumberColumn(format="%+.2f mph"),
                        "Bat Speed Δ": st.column_config.NumberColumn(format="%+.2f mph"),
                        "Sprint Δ": st.column_config.NumberColumn(format="%+.2f ft/s"),
                    },
                )
                csv_download_button(display, "Download priority queue CSV", "nutrition_priority_queue.csv", "priority_csv")

    with right:
        with st.container(border=True):
            st.subheader("Flags by Metric", anchor=False)
            st.plotly_chart(
                build_flag_metric_chart(alerts),
                use_container_width=True,
                config={"displayModeBar": False},
                key="overview_flag_metric_chart",
            )

    if team_filter == "Full Organization":
        with st.container(border=True):
            st.subheader("Team-Level Alert Load", anchor=False)
            st.plotly_chart(
                build_team_flag_chart(alerts_all),
                use_container_width=True,
                config={"displayModeBar": False},
                key="team_flag_chart",
            )
            team_summary = (
                alerts_all.groupby("team", as_index=False)
                .agg(
                    Players=("name_key", "nunique"),
                    Review=("Status", lambda s: int((s == "Review").sum())),
                    Monitor=("Status", lambda s: int((s == "Monitor").sum())),
                    BW_Flags=("bw_level", lambda s: int((s > 0).sum())),
                    CI_Flags=("ci_level", lambda s: int((s > 0).sum())),
                    Velo_Flags=("velo_level", lambda s: int((s > 0).sum())),
                    Bat_Flags=("bat_level", lambda s: int((s > 0).sum())),
                    Sprint_Flags=("sprint_level", lambda s: int((s > 0).sum())),
                )
            )
            team_summary["Flagged %"] = np.where(
                team_summary["Players"] > 0,
                (team_summary["Review"] + team_summary["Monitor"]) / team_summary["Players"] * 100,
                np.nan,
            )
            st.dataframe(
                team_summary.rename(columns={
                    "BW_Flags": "BW Flags", "CI_Flags": "CI Flags",
                    "Velo_Flags": "Velo Flags", "Bat_Flags": "Bat Flags",
                    "Sprint_Flags": "Sprint Flags",
                }),
                hide_index=True,
                use_container_width=True,
                column_config={"Flagged %": st.column_config.NumberColumn(format="%.1f%%")},
            )


# Generic metric tab helper

def render_metric_tab(
    data: pd.DataFrame,
    title: str,
    level_col: str,
    current_col: str,
    baseline_col: str,
    change_col: str,
    change_pct_col: str | None,
    current_date_col: str,
    baseline_date_col: str,
    unit: str,
    change_bar_title: str,
    pct_bar: bool = False,
    digits: int = 2,
    current_label: str = "Current",
    baseline_label: str = "Baseline",
):
    metric_prefix = level_col.removesuffix("_level")
    stale_col = f"{metric_prefix}_stale"
    fresh_mask = (
        ~data[stale_col].fillna(False)
        if stale_col in data.columns
        else pd.Series(True, index=data.index)
    )
    valid = data[data[change_col].notna() & fresh_mask].copy()
    flags = valid[valid[level_col] > 0].copy()
    median_change = valid[change_col].median() if not valid.empty else np.nan

    a, b, c = st.columns(3)
    with a:
        st.markdown(metric_card("Comparable players", str(len(valid)), BLUE), unsafe_allow_html=True)
    with b:
        st.markdown(metric_card("Flagged", str(len(flags)), ACCENT_RED if len(flags) else GREEN), unsafe_allow_html=True)
    with c:
        st.markdown(metric_card("Median change", fmt_signed(median_change, digits, f" {unit}" if unit else ""), TEAL), unsafe_allow_html=True)

    left, right = st.columns([1.05, 0.95])
    with left:
        with st.container(border=True):
            st.subheader(f"Largest {title} Changes", anchor=False)
            st.plotly_chart(
                build_metric_change_bar(
                    valid,
                    change_pct_col if pct_bar and change_pct_col else change_col,
                    change_bar_title,
                    "%" if pct_bar else unit,
                    top_n=25,
                    pct=pct_bar,
                ),
                use_container_width=True,
                config={"displayModeBar": False},
                key=f"bar_{level_col}_{team_filter}_{as_of_date}",
            )
    with right:
        with st.container(border=True):
            st.subheader(f"{title} Detail", anchor=False)
            cols = [
                "athlete", "team", "Status", current_col, baseline_col,
                change_col, current_date_col, baseline_date_col,
            ]
            if change_pct_col:
                cols.insert(6, change_pct_col)
            detail = data[cols].copy()
            current_dates_raw = pd.to_datetime(detail[current_date_col], errors="coerce")
            if stale_col in data.columns:
                detail["Data Status"] = np.where(
                    current_dates_raw.isna(),
                    "No current data",
                    np.where(data.loc[detail.index, stale_col].fillna(False), f"Stale >{MAX_FLAG_AGE_DAYS}d", "Current"),
                )
            else:
                detail["Data Status"] = np.where(current_dates_raw.isna(), "No current data", "Current")
            rename = {
                "athlete": "Player",
                "team": "Team",
                "Status": "Overall Status",
                current_col: current_label,
                baseline_col: baseline_label,
                change_col: "Change",
                current_date_col: "Current As Of",
                baseline_date_col: "Baseline As Of",
            }
            if change_pct_col:
                rename[change_pct_col] = "Change %"
            detail = detail.rename(columns=rename)
            detail["Current As Of"] = detail["Current As Of"].map(fmt_date)
            detail["Baseline As Of"] = detail["Baseline As Of"].map(fmt_date)
            detail = detail.sort_values("Change", na_position="last")
            column_config = {
                current_label: st.column_config.NumberColumn(format=f"%.{digits}f {unit}" if unit else f"%.{digits}f"),
                baseline_label: st.column_config.NumberColumn(format=f"%.{digits}f {unit}" if unit else f"%.{digits}f"),
                "Change": st.column_config.NumberColumn(format=f"%+.{digits}f {unit}" if unit else f"%+.{digits}f"),
            }
            if change_pct_col:
                column_config["Change %"] = st.column_config.NumberColumn(format="%+.1f%%")
            st.dataframe(
                detail,
                hide_index=True,
                use_container_width=True,
                height=560,
                column_config=column_config,
            )
            csv_download_button(
                detail,
                f"Download {title.lower()} CSV",
                f"nutrition_{title.lower().replace(' ', '_')}.csv",
                f"csv_{level_col}",
            )


with bw_tab:
    st.subheader("Bodyweight Change Monitoring", anchor=False)
    st.caption(
        "Current bodyweight is the latest observation in the recent window. Baseline is the median of the immediately preceding window. "
        "Bodyweight is displayed in pounds regardless of whether the source column is kg or lb."
    )
    render_metric_tab(
        alerts,
        title="Bodyweight",
        level_col="bw_level",
        current_col="bw_current_lb",
        baseline_col="bw_baseline_lb",
        change_col="bw_change_lb",
        change_pct_col="bw_change_pct",
        current_date_col="bw_current_date",
        baseline_date_col="bw_baseline_last",
        unit="lb",
        change_bar_title="Bodyweight change",
        pct_bar=True,
        digits=1,
    )

with ci_tab:
    st.subheader("Concentric Impulse Change Monitoring", anchor=False)
    st.caption(
        "Current CI is the average of tests in the recent window; baseline is the average of tests in the immediately preceding window. "
        "Only declines trigger CI alerts."
    )
    render_metric_tab(
        alerts,
        title="CI",
        level_col="ci_level",
        current_col="ci_current",
        baseline_col="ci_baseline",
        change_col="ci_change",
        change_pct_col="ci_change_pct",
        current_date_col="ci_current_date",
        baseline_date_col="ci_baseline_last",
        unit="N·s",
        change_bar_title="CI change",
        pct_bar=True,
        digits=1,
    )

with velo_tab:
    st.subheader("Fastball Velocity Change Monitoring", anchor=False)
    st.caption(
        "Compares the latest fb_velo with ytd_fb_velo from the same row/date. "
        "A negative difference means current fastball velocity is running below the pitcher's YTD fastball velocity. "
        "Only declines trigger velocity alerts."
    )
    pitcher_alerts = alerts[alerts["position"].map(is_pitcher_position).fillna(False)].copy()
    render_metric_tab(
        pitcher_alerts,
        title="FB Velo",
        level_col="velo_level",
        current_col="velo_current",
        baseline_col="velo_baseline",
        change_col="velo_change",
        change_pct_col="velo_change_pct",
        current_date_col="velo_current_date",
        baseline_date_col="velo_baseline_date",
        unit="mph",
        change_bar_title="FB velo vs YTD",
        pct_bar=False,
        digits=2,
        current_label="FB Velo",
        baseline_label="YTD FB Velo",
    )

with bat_tab:
    st.subheader("Bat Speed Change Monitoring", anchor=False)
    st.caption(
        "Compares the latest eligible monthly_avg_bat_speed value with the previous eligible month. "
        f"A month must contain at least {bat_min_days} distinct PP_Sprint data dates. Only declines trigger alerts."
    )
    position_player_alerts = alerts[alerts["position"].map(is_position_player_position).fillna(False)].copy()
    render_metric_tab(
        position_player_alerts,
        title="Bat Speed",
        level_col="bat_level",
        current_col="bat_current",
        baseline_col="bat_baseline",
        change_col="bat_change",
        change_pct_col="bat_change_pct",
        current_date_col="bat_current_date",
        baseline_date_col="bat_baseline_date",
        unit="mph",
        change_bar_title="Bat speed change",
        pct_bar=False,
        digits=2,
    )

with sprint_tab:
    st.subheader("Sprint Speed Change Monitoring", anchor=False)
    st.caption(
        "Compares the latest eligible monthly_max_sprint_speed with the previous eligible month. "
        f"A month must contain at least {sprint_min_days} distinct PP_Sprint data dates to avoid flagging an incomplete monthly maximum too early. "
        "Only declines trigger alerts."
    )
    position_player_alerts = alerts[alerts["position"].map(is_position_player_position).fillna(False)].copy()
    render_metric_tab(
        position_player_alerts,
        title="Sprint Speed",
        level_col="sprint_level",
        current_col="sprint_current",
        baseline_col="sprint_baseline",
        change_col="sprint_change",
        change_pct_col="sprint_change_pct",
        current_date_col="sprint_current_date",
        baseline_date_col="sprint_baseline_date",
        unit="ft/s",
        change_bar_title="Sprint speed change",
        pct_bar=False,
        digits=2,
    )


# ----- HYDRATION -----
with hydration_tab:
    st.subheader("Hydration Testing", anchor=False)
    st.caption(
        "Sweat-sodium testing from the separate Hydration spreadsheet plus the DSL tab in the primary reports sheet. "
        "These results are informational and do not change Review / Monitor / Stable status."
    )
    hydration_view = build_hydration_view(bundle, directory, team_filter)

    if hydration_view.empty:
        st.info("No hydration results are available for the selected team.")
        if bundle.hydration_status:
            st.caption(bundle.hydration_status)
    else:
        hydration_display = hydration_view[[
            "athlete", "team", "position", "sodium_loss_mg_l",
            "classification", "recommendation", "source_tab",
        ]].copy()
        hydration_display.columns = [
            "Player", "Team", "Position", "Sweat Sodium (mg/L)",
            "Classification", "Recommendation", "Source",
        ]
        st.dataframe(
            hydration_display,
            hide_index=True,
            use_container_width=True,
            height=min(760, 44 + 36 * (len(hydration_display) + 1)),
            column_config={
                "Sweat Sodium (mg/L)": st.column_config.NumberColumn(format="%.0f mg/L"),
                "Recommendation": st.column_config.TextColumn(width="large"),
            },
        )
        csv_download_button(
            hydration_display,
            "Download hydration results CSV",
            "hydration_results.csv",
            "hydration_results_csv",
        )
        st.caption(bundle.hydration_status)


# ----- PLAYER TRENDS -----
with player_tab:
    st.subheader("Player Trends", anchor=False)
    player_options = alerts[["name_key", "athlete", "team", "Status"]].copy()
    player_options["label"] = player_options.apply(
        lambda r: f"{r['athlete']} · {r['team']} · {r['Status']}", axis=1
    )
    if player_options.empty:
        st.info("No players are available for the selected filter.")
    else:
        selected_label = st.selectbox(
            "Player",
            player_options["label"].tolist(),
            key="player_trend_selector",
        )
        selected = player_options[player_options["label"] == selected_label].iloc[0]
        key = selected["name_key"]
        row = alerts[alerts["name_key"] == key].iloc[0]

        p1, p2, p3 = st.columns([1, 1, 1])
        with p1:
            st.markdown(metric_card("Current status", row["Status"], ACCENT_RED if row["Status"] == "Review" else AMBER if row["Status"] == "Monitor" else GREEN), unsafe_allow_html=True)
        with p2:
            st.markdown(metric_card("Flagged metrics", str(int(row["flagged_metrics"])), BLUE), unsafe_allow_html=True)
        with p3:
            st.markdown(
                metric_card(
                    "Comparisons available",
                    f"{int(row['metrics_with_comparison'])}/{int(row.get('metrics_applicable', 2))}",
                    TEAL,
                ),
                unsafe_allow_html=True,
            )
        if row["Why flagged"] != "No threshold exceeded":
            st.warning(row["Why flagged"])

        history_start = pd.Timestamp(as_of_date) - pd.Timedelta(days=365)
        jump_player = bundle.jump[
            (bundle.jump["name_key"] == key)
            & (bundle.jump["date"] >= history_start)
            & (bundle.jump["date"] <= pd.Timestamp(as_of_date))
        ].copy()
        velo_player = bundle.velo[
            (bundle.velo["name_key"] == key)
            & (bundle.velo["date"] >= history_start)
            & (bundle.velo["date"] <= pd.Timestamp(as_of_date))
        ].copy()
        monthly_player = bundle.monthly[
            (bundle.monthly["name_key"] == key)
            & (bundle.monthly["as_of_date"] >= history_start)
            & (bundle.monthly["as_of_date"] <= pd.Timestamp(as_of_date))
        ].copy()

        a, b = st.columns(2)
        with a:
            with st.container(border=True):
                st.subheader("Bodyweight", anchor=False)
                st.plotly_chart(
                    build_time_series(
                        jump_player, "date", "bodyweight_lb", "Bodyweight", "Bodyweight (lb)", row.get("bw_baseline_lb")
                    ),
                    use_container_width=True, config={"displayModeBar": False}, key=f"player_bw_{key}",
                )
        with b:
            with st.container(border=True):
                st.subheader("CI", anchor=False)
                st.plotly_chart(
                    build_time_series(
                        jump_player, "date", "ci", "CI", "Concentric impulse (N·s)", row.get("ci_baseline")
                    ),
                    use_container_width=True, config={"displayModeBar": False}, key=f"player_ci_{key}",
                )

        position = row.get("position", "")
        if is_pitcher_position(position):
            with st.container(border=True):
                st.subheader("FB Velo", anchor=False)
                st.plotly_chart(
                    build_velo_time_series(velo_player),
                    use_container_width=True, config={"displayModeBar": False}, key=f"player_velo_{key}",
                )
        elif is_position_player_position(position):
            a, b = st.columns(2)
            with a:
                with st.container(border=True):
                    st.subheader("Bat Speed", anchor=False)
                    st.plotly_chart(
                        build_time_series(
                            monthly_player, "as_of_date", "monthly_avg_bat_speed", "Bat speed", "Monthly avg bat speed (mph)", row.get("bat_baseline")
                        ),
                        use_container_width=True, config={"displayModeBar": False}, key=f"player_bat_{key}",
                    )
            with b:
                with st.container(border=True):
                    st.subheader("Sprint Speed", anchor=False)
                    st.plotly_chart(
                        build_time_series(
                            monthly_player, "as_of_date", "monthly_max_sprint_speed", "Sprint speed", "Monthly max sprint speed (ft/s)", row.get("sprint_baseline")
                        ),
                        use_container_width=True, config={"displayModeBar": False}, key=f"player_sprint_{key}",
                    )


# ----- PLAYER REPORTS -----
with report_tab:
    st.subheader("Individual Player Reports", anchor=False)
    st.caption(
        "Each PDF uses the same current thresholds, freshness rule, team filter, and as-of date as the dashboard. "
        "The report includes the player's current review status, position-appropriate metric comparisons, the source-sheet sweat-test result when available, and 12-month trends."
    )

    report_players = alerts[["name_key", "athlete", "team", "position", "Status"]].copy()
    report_players["label"] = report_players.apply(
        lambda r: f"{r['athlete']} · {r['team']} · {r['Status']}", axis=1
    )

    if report_players.empty:
        st.info("No players are available for the selected team filter.")
    else:
        selected_report_label = st.selectbox(
            "Player report",
            report_players["label"].tolist(),
            key="player_report_selector",
        )
        report_selected = report_players[report_players["label"] == selected_report_label].iloc[0]
        report_row = alerts[alerts["name_key"] == report_selected["name_key"]].iloc[0]

        # Keep separate report notes for each player during the current app session.
        notes_store = st.session_state.setdefault("player_report_notes", {})
        report_name_key = str(report_row.get("name_key", ""))
        report_notes = st.text_area(
            "Report notes",
            value=str(notes_store.get(report_name_key, "")),
            height=110,
            key=f"player_report_notes_input_{safe_filename(report_name_key)}",
            placeholder="Type any context or follow-up notes to include on this player's PDF...",
        )
        notes_store[report_name_key] = report_notes

        report_pdf = generate_player_report_pdf(
            report_row, bundle, as_of_date, report_notes=report_notes
        )

        hydration_record = get_player_hydration(
            bundle,
            str(report_row.get("name_key", "")),
            str(report_row.get("team", "") or ""),
        )
        hydration_summary = hydration_report_summary(hydration_record)

        summary_cols = st.columns([1, 1, 2])
        with summary_cols[0]:
            st.markdown(
                metric_card(
                    "Status",
                    str(report_row["Status"]),
                    ACCENT_RED if report_row["Status"] == "Review" else AMBER if report_row["Status"] == "Monitor" else GREEN,
                ),
                unsafe_allow_html=True,
            )
        if hydration_summary is not None:
            with summary_cols[1]:
                st.markdown(
                    metric_card(
                        "Sweat Test",
                        hydration_summary["value"],
                        TEAL,
                    ),
                    unsafe_allow_html=True,
                )

        st.download_button(
            "Download selected player PDF",
            data=report_pdf,
            file_name=f"{safe_filename(report_row['athlete'])}_nutrition_report.pdf",
            mime="application/pdf",
            key="download_selected_player_pdf",
            use_container_width=True,
            type="primary",
        )

        st.markdown("---")
        st.subheader("Batch Player Reports", anchor=False)
        st.caption(
            f"Creates one separate PDF for every player in the current view ({len(alerts):,} players) and packages them into a ZIP, organized by team."
        )

        notes_store = st.session_state.get("player_report_notes", {})
        current_name_keys = set(alerts["name_key"].astype(str))
        notes_signature = tuple(
            sorted(
                (str(k), str(v))
                for k, v in notes_store.items()
                if str(k) in current_name_keys and str(v).strip()
            )
        )
        batch_signature = (
            str(as_of_date), team_filter, recent_days, baseline_days, bat_min_days, sprint_min_days,
            bw_direction, bw_monitor_pct, bw_review_pct, ci_monitor_pct, ci_review_pct,
            velo_monitor_mph, velo_review_mph, bat_monitor_mph, bat_review_mph,
            sprint_monitor, sprint_review, escalate_multi, notes_signature,
        )
        if st.button("Build ZIP of all player reports", key="build_player_report_zip", use_container_width=True):
            with st.spinner("Building player reports..."):
                st.session_state["player_report_zip_bytes"] = generate_player_reports_zip(
                    alerts, bundle, as_of_date, notes_by_player=notes_store
                )
                st.session_state["player_report_zip_signature"] = batch_signature

        if (
            st.session_state.get("player_report_zip_bytes")
            and st.session_state.get("player_report_zip_signature") == batch_signature
        ):
            zip_team = "full_organization" if team_filter == "Full Organization" else safe_filename(team_filter)
            st.download_button(
                "Download all player reports (.zip)",
                data=st.session_state["player_report_zip_bytes"],
                file_name=f"nutrition_player_reports_{zip_team}_{pd.Timestamp(as_of_date).strftime('%Y%m%d')}.zip",
                mime="application/zip",
                key="download_player_report_zip",
                use_container_width=True,
            )
        elif st.session_state.get("player_report_zip_bytes"):
            st.info("Dashboard settings changed. Rebuild the ZIP so the reports match the current filters and thresholds.")


# ----- DATA COVERAGE -----
with data_tab:
    st.subheader("Data Coverage", anchor=False)
    st.caption(
        f"This separates 'no alert' from 'not enough fresh data to make the comparison.' Any metric whose latest observation is more than {MAX_FLAG_AGE_DAYS} days old is stale and cannot generate an alert."
    )
    coverage = alerts[[
        "athlete", "team", "position", "Status", "metrics_with_comparison", "stale_metrics",
        "bw_current_date", "ci_current_date", "velo_current_date",
        "bat_current_date", "sprint_current_date",
    ]].copy()
    coverage.columns = [
        "Player", "Team", "Position", "Status", "Fresh Comparable Metrics", "Stale Metrics",
        "Last BW", "Last CI", "Last FB Velo", "Last Bat Speed", "Last Sprint Speed",
    ]
    for c in ["Last BW", "Last CI", "Last FB Velo", "Last Bat Speed", "Last Sprint Speed"]:
        coverage[c] = coverage[c].map(fmt_date)
    coverage = coverage.sort_values(["Fresh Comparable Metrics", "Stale Metrics", "Team", "Player"])
    st.dataframe(coverage, hide_index=True, use_container_width=True, height=650)
    csv_download_button(coverage, "Download data coverage CSV", "nutrition_data_coverage.csv", "coverage_csv")

    missing_counts = {
        "Bodyweight": int((alerts["bw_change_pct"].isna() | alerts["bw_stale"]).sum()),
        "CI": int((alerts["ci_change_pct"].isna() | alerts["ci_stale"]).sum()),
        "FB Velo": int((alerts["velo_change"].isna() | alerts["velo_stale"]).sum()),
        "Bat Speed": int((alerts["bat_change"].isna() | alerts["bat_stale"]).sum()),
        "Sprint Speed": int((alerts["sprint_change"].isna() | alerts["sprint_stale"]).sum()),
    }
    st.markdown(
        f"**Players without a fresh valid comparison (missing or >{MAX_FLAG_AGE_DAYS} days old):** "
        + " · ".join(f"{k}: {v}" for k, v in missing_counts.items())
    )

st.markdown("---")
st.caption(
    "Interpretation note: a flag identifies a meaningful change under the selected rules. "
    "It does not establish that nutrition caused the change. Review the athlete's training, health, schedule, role, and measurement context alongside the nutrition record."
)
