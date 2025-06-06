import streamlit as st
import pandas as pd
import yfinance as yf
import re
import plotly.graph_objects as go
from datetime import datetime
from datetime import timedelta
from sqlalchemy import create_engine
import base64
from itertools import combinations
import swisseph as swe

DATABASE_URL = "postgresql://numeroniq-db_owner:npg_EWIGjD91LKxP@ep-muddy-boat-a15emu03-pooler.ap-southeast-1.aws.neon.tech/numeroniq-db?sslmode=require"
engine = create_engine(DATABASE_URL)

st.set_page_config(page_title="Numeroniq", layout="wide")

# Inject CSS and JS to disable text selection and right-click
st.markdown("""
    <style>
    * {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }

    /* Specifically target tables */
    div[data-testid="stTable"] {
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
        user-select: none !important;
    }

    /* Also target the scrollable dataframe area */
    .css-1wmy9hl, .css-1xarl3l {
        user-select: none !important;
    }
    </style>

    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
    """, unsafe_allow_html=True)

# Disable right click with JavaScript
st.markdown("""
    <script>
    document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at top left, #e6cbb6, #fde6ef, #dcf7fc, #c2f0f7);
        }
        .block-container {
            background: radial-gradient(circle at top left, #e6cbb6, #fde6ef, #dcf7fc, #c2f0f7);
            padding: 2rem;
            border-radius: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# Define custom CSS for the table background
custom_css = """
<style>
.scroll-table {
    overflow-x: auto;
    max-height: 500px;
    border: 1px solid #ccc;
}

.scroll-table table {
    width: 100%;
    border-collapse: collapse;
    background-color: #f0f8ff; /* Light blue background */
}

.scroll-table th, .scroll-table td {
    padding: 8px;
    border: 1px solid #ddd;
    text-align: left;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

aspect_config = {
    "Sun→Ketu": {"from": "Sun", "to": "Ketu", "angles": [0, 90, 120]},
    "Venus→Ketu": {"from": "Venus", "to": "Ketu", "angles": [0, 120]},
}

planet_map = {
    'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY, 'Venus': swe.VENUS,
    'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturn': swe.SATURN,
    'Rahu': swe.MEAN_NODE, 'Ketu': swe.TRUE_NODE
}

def angular_diff(from_deg, to_deg):
    return round((to_deg - from_deg) % 360, 2)

def check_aspects(from_deg, to_deg, angles, label):
    for angle in angles:
        if abs(angular_diff(from_deg, to_deg) - angle) <= 0.5:
            return f"{label} ≈ {angle}°"
    return None

def get_d9_longitude(lon):
    sign_index = int(lon // 30)
    pos_in_sign = lon % 30
    navamsa_index = int(pos_in_sign // (30 / 9))
    if sign_index in [0, 3, 6, 9]: start = sign_index
    elif sign_index in [1, 4, 7, 10]: start = (sign_index + 8) % 12
    else: start = (sign_index + 4) % 12
    d9_sign_index = (start + navamsa_index) % 12
    deg_in_navamsa = pos_in_sign % (30 / 9)
    return d9_sign_index * 30 + deg_in_navamsa * 9

def check_mm_aspects(from_deg, to_deg):
    angles = [0, 90, 180]
    matched = []
    diff1 = angular_diff(from_deg, to_deg)
    diff2 = angular_diff(to_deg, from_deg)
    for angle in angles:
        if abs(diff1 - angle) <= 1:
            matched.append(f"Moon→Mercury ≈ {angle}°")
        if abs(diff2 - angle) <= 1:
            matched.append(f"Mercury→Moon ≈ {angle}°")
    return ", ".join(matched) if matched else "0"

def get_d9_longitude(longitude_deg):
    sign_index = int(longitude_deg // 30)
    pos_in_sign = longitude_deg % 30
    navamsa_index = int(pos_in_sign // (30 / 9))
    if sign_index in [0, 3, 6, 9]:
        start = sign_index
    elif sign_index in [1, 4, 7, 10]:
        start = (sign_index + 8) % 12
    else:
        start = (sign_index + 4) % 12
    d9_sign_index = (start + navamsa_index) % 12
    deg_in_navamsa = pos_in_sign % (30 / 9)
    return d9_sign_index * 30 + deg_in_navamsa * 9

def classify_sign_type(sign_number):
        for k, v in sign_types.items():
            if sign_number in v:
                return k
        return "Unknown"

def get_planet_deg(jd, name):
    flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    lon = swe.calc_ut(jd, planets[name], flag)[0][0]
    if name == "Ketu":
        lon = (swe.calc_ut(jd, planets["Rahu"], flag)[0][0] + 180) % 360
    return lon

def get_day_type(jd):
    flag = swe.FLG_SIDEREAL | swe.FLG_SPEED
    data = {}
    for name in planets:
        lon, speed = swe.calc_ut(jd, planets[name], flag)[0][0:2]
        if name == "Ketu":
            lon = (swe.calc_ut(jd, planets["Rahu"], flag)[0][0] + 180) % 360
            speed = -speed
        data[name] = {"deg": lon, "speed": speed}

    for p1, p2 in combinations(data.keys(), 2):
        r1, r2 = planet_rank.get(p1, 999), planet_rank.get(p2, 999)
        fast, slow = (p1, p2) if r1 < r2 else (p2, p1)
        d1, d2 = data[fast]["deg"], data[slow]["deg"]
        diff = (d1 - d2 + 360) % 360
        if diff > 180:
            diff -= 360
        if abs(diff) <= 1:
            return "Red Day" if diff < 0 else "Green Day"
    return "-"

from itertools import combinations

def get_planet_data(jd, name, pid):
    flag = swe.FLG_SIDEREAL | swe.FLG_SPEED
    lon, speed = swe.calc_ut(jd, pid, flag)[0][0:2]
    if name == "Ketu":
        lon = (swe.calc_ut(jd, swe.TRUE_NODE, flag)[0][0] + 180) % 360
        speed = -speed
    return round(lon, 2), round(speed, 4)

def signed_diff(fast_deg, slow_deg):
    diff = (fast_deg - slow_deg + 360) % 360
    if diff > 180:
        diff -= 360
    return round(diff, 2)


nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
        "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
        "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
        "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
        "Uttara Bhadrapada", "Revati"
    ]

planets = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
    "Ketu": swe.TRUE_NODE,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO
}

st.title("📊 Numeroniq")

st.html("""
<style>
[data-testid=stElementToolbarButton]:first-of-type {
    display: none;
}
</style>
""")

# === Toggle between filtering methods ===
st.sidebar.title("📊 Navigation")
filter_mode = st.sidebar.radio(
    "Choose Filter Mode:", 
    [
        "Navamasa",
        "Planetary Conjunctions",
        "Planetary Report",
        "Moon–Mercury Aspects",
        "Planetary Aspects",
        "Swapt Nadi Chakra",
        "Planetary Ingress",
        "AOT Monthly Calendar"
        ])

if filter_mode == "Navamasa":
    st.header("🌌 Navamasa (D1 & D9 Planetary Chart)")

    import swisseph as swe
    import datetime
    import pandas as pd

    # === Setup Swiss Ephemeris ===
    swe.set_ephe_path("C:/ephe")  # Replace with actual path
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

    # === User Input ===
    birth_dt = st.date_input("Select Date", value=datetime.date.today())
    birth_time = st.time_input("Select Time", value=datetime.time(9, 0))
    datetime_obj = datetime.datetime.combine(birth_dt, birth_time)

    timezone_offset = 5.5  # IST
    latitude = 19.076
    longitude = 72.8777

    utc_dt = datetime_obj - datetime.timedelta(hours=timezone_offset)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60)

    # === Constants ===
    signs = [
        'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
        'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
    ]

    sign_lords = [
        'Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury',
        'Venus', 'Mars', 'Jupiter', 'Saturn', 'Saturn', 'Jupiter'
    ]    

    custom_d1_map = {sign: i+1 for i, sign in enumerate(signs)}
    custom_d9_map = {
        "Aries": 1, "Taurus": 2, "Gemini": 3, "Leo": 4, "Cancer": 5, "Virgo": 6,
        "Libra": 7, "Scorpio": 8, "Sagittarius": 9, "Capricorn": 10, "Aquarius": 11, "Pisces": 12
    }

    # === Helper: Navamsa D9 Sign Logic ===
    def get_d9_sign_index(longitude_deg):
        sign_index = int(longitude_deg // 30)
        pos_in_sign = longitude_deg % 30
        navamsa_index = int(pos_in_sign // (30 / 9))
        if sign_index in [0, 3, 6, 9]: start = sign_index
        elif sign_index in [1, 4, 7, 10]: start = (sign_index + 8) % 12
        else: start = (sign_index + 4) % 12
        return (start + navamsa_index) % 12

    # === Planetary Calculations ===
    rows = []
    longitudes = {}
    flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
    navamsa_size = 30 / 9

    for name, pid in planets.items():
        lon = swe.calc_ut(jd, pid, flag)[0][0]
        if name == "Ketu":
            lon = (swe.calc_ut(jd, swe.TRUE_NODE, flag)[0][0] + 180) % 360

        longitudes[name] = round(lon, 2)

        sign_index = int(lon // 30)
        rashi = signs[sign_index]
        d1_sign_number = custom_d1_map[rashi]
        rashi_lord = sign_lords[sign_index]

        pos_in_sign = lon % 30
        deg_in_sign = f"{int(pos_in_sign)}° {int((pos_in_sign % 1) * 60):02d}'"

        nak_index = int((lon % 360) // (360 / 27))
        nakshatra = nakshatras[nak_index]

        d9_sign_index = get_d9_sign_index(lon)
        d9_sign = signs[d9_sign_index]
        d9_sign_number = custom_d9_map[d9_sign]
        deg_in_d9_total = (pos_in_sign % navamsa_size) * 9
        deg_in_d9_sign = f"{int(deg_in_d9_total)}° {int((deg_in_d9_total % 1) * 60):02d}'"
        d9_long = d9_sign_index * 30 + deg_in_d9_total

        rows.append({
            "Planet": name,
            "Longitude (deg)": round(lon, 2),
            "Sign": rashi,
            "D1 Sign #": d1_sign_number,
            "Sign Lord": rashi_lord,
            "Nakshatra": nakshatra,
            "Degrees in Sign": deg_in_sign,
            "Navamsa (D9) Sign": d9_sign,
            "D9 Sign #": d9_sign_number,
            "Degrees in D9 Sign": deg_in_d9_sign,
            "D9 Longitude (deg)": round(d9_long, 2)
        })

    df = pd.DataFrame(rows)

    # === D1/D9 Degree Difference Tables ===
    def angular_diff(a, b): return round((b - a) % 360, 2)
    def create_diff_table(deg_dict): return pd.DataFrame([
        [angular_diff(deg_dict[p1], deg_dict[p2]) for p2 in deg_dict]
        for p1 in deg_dict
    ], index=deg_dict.keys(), columns=deg_dict.keys())

    d1_table = create_diff_table(longitudes)
    d9_table = create_diff_table({row["Planet"]: row["D9 Longitude (deg)"] for row in rows})

    # === Type Classification (Movable/Fixed/Dual) ===
    def classify(num):
        if num in [1, 4, 7, 10]: return "Movable"
        elif num in [2, 5, 8, 11]: return "Fixed"
        elif num in [3, 6, 9, 12]: return "Dual"
        return "Unknown"

    df["D1 Type"] = df["D1 Sign #"].apply(classify)
    df["D9 Type"] = df["D9 Sign #"].apply(classify)

    def summary(df, col):
        cats = ["Movable", "Fixed", "Dual"]
        return pd.DataFrame([{
            "Category": cat,
            "Planets": ", ".join(df[df[col] == cat]["Planet"]),
            "Total": len(df[df[col] == cat])
        } for cat in cats])

    d1_class = summary(df, "D1 Type")
    d9_class = summary(df, "D9 Type")

    # === Render All as Styled HTML Tables ===
    st.markdown("### 🪐 Planetary Positions (D1 + D9)")
    st.markdown(f'<div class="scroll-table">{df.to_html(index=False)}</div>', unsafe_allow_html=True)

    st.markdown("### 📘 D1 Longitudinal Differences (0–360°)")
    st.markdown(f'<div class="scroll-table">{d1_table.to_html()}</div>', unsafe_allow_html=True)

    st.markdown("### 📙 D9 Longitudinal Differences (0–360°)")
    st.markdown(f'<div class="scroll-table">{d9_table.to_html()}</div>', unsafe_allow_html=True)

    st.markdown("### 📊 D1 Sign Type Classification")
    st.markdown(f'<div class="scroll-table">{d1_class.to_html(index=False)}</div>', unsafe_allow_html=True)

    st.markdown("### 📊 D9 Sign Type Classification")
    st.markdown(f'<div class="scroll-table">{d9_class.to_html(index=False)}</div>', unsafe_allow_html=True)

elif filter_mode == "Planetary Conjunctions":
    st.header("🪐 Planetary Conjunctions (±1°) with Nakshatra, Pada & Zodiac")

    import swisseph as swe
    import datetime
    import pandas as pd
    from itertools import combinations

    # Setup
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

    # Date Range Input
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.date(2025, 6, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime.date(2025, 6, 30))

    # Planet order by speed
    planet_order = ["Moon", "Mercury", "Venus", "Sun", "Mars",
                    "Jupiter", "Rahu", "Ketu", "Saturn",
                    "Uranus", "Neptune", "Pluto"]
    planet_rank = {planet: i for i, planet in enumerate(planet_order)}

    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.TRUE_NODE,
        "Ketu": swe.TRUE_NODE,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO
    }

    nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
        "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
        "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
        "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
        "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
        "Uttara Bhadrapada", "Revati"
    ]

    zodiacs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]

    def get_nakshatra_and_pada(degree):
        nak_index = int(degree // (360 / 27))
        pada = int((degree % (360 / 27)) // 3.3333) + 1
        return nakshatras[nak_index], pada

    def get_zodiac(degree):
        return zodiacs[int(degree // 30)]

    def signed_diff(fast_deg, slow_deg):
        diff = (fast_deg - slow_deg + 360) % 360
        if diff > 180:
            diff -= 360
        return round(diff, 2)

    def get_planet_data(jd, name, pid):
        flag = swe.FLG_SIDEREAL | swe.FLG_SPEED
        lon, speed = swe.calc_ut(jd, pid, flag)[0][0:2]
        if name == "Ketu":
            lon = (swe.calc_ut(jd, swe.TRUE_NODE, flag)[0][0] + 180) % 360
            speed = -speed
        return round(lon, 2), round(speed, 4)

    # Iterate over days
    current = start_date
    results = []

    while current <= end_date:
        jd = swe.julday(current.year, current.month, current.day, 0)
        planet_data = {}

        for name, pid in planets.items():
            lon, speed = get_planet_data(jd, name, pid)
            planet_data[name] = {"deg": lon, "speed": speed}

        for p1, p2 in combinations(planet_data.keys(), 2):
            r1, r2 = planet_rank.get(p1, 999), planet_rank.get(p2, 999)
            fast, slow = (p1, p2) if r1 < r2 else (p2, p1)

            d1 = planet_data[fast]["deg"]
            d2 = planet_data[slow]["deg"]
            diff = signed_diff(d1, d2)

            if abs(diff) <= 1.0:
                midpoint = (d1 + d2) / 2 % 360
                nakshatra, pada = get_nakshatra_and_pada(midpoint)
                zodiac = get_zodiac(midpoint)

                results.append({
                    "Date": current.strftime("%Y-%m-%d"),
                    "Planet 1": f"{fast} ({d1}° / {planet_data[fast]['speed']}°/day)",
                    "Planet 2": f"{slow} ({d2}° / {planet_data[slow]['speed']}°/day)",
                    "Degree Difference": diff,
                    "Nakshatra": nakshatra,
                    "Pada": pada,
                    "Zodiac": zodiac,
                    "Day Type": "Red Day" if diff < 0 else "Green Day"
                })

        current += datetime.timedelta(days=1)

    df = pd.DataFrame(results)

    if df.empty:
        st.warning("No conjunctions found within ±1° for the selected date range.")
    else:
        st.markdown("### 🔭 Conjunction Report")

        def styled_html_table(df):
            rows = []
            for _, row in df.iterrows():
                bg_color = "#ffe6e6" if row["Day Type"] == "Red Day" else "#e6ffe6"
                row_html = "<tr style='background-color:{}'>".format(bg_color)
                for val in row:
                    row_html += f"<td>{val}</td>"
                row_html += "</tr>"
                rows.append(row_html)

            header = "".join([f"<th>{col}</th>" for col in df.columns])
            html_table = f"""
            <div class="scroll-table">
                <table>
                    <thead><tr>{header}</tr></thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
            """
            return html_table

        st.markdown(styled_html_table(df), unsafe_allow_html=True)

elif filter_mode == "Planetary Report":
    st.header("📅 Daily Planetary Summary Report (D1 + D9 + Conjunctions)")

    import swisseph as swe
    import datetime
    import pandas as pd
    from itertools import combinations

    # === Input Range ===
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.date(2025, 6, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime.date(2025, 6, 30))

    swe.set_ephe_path("C:/ephe")  
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
    timezone_offset = 5.5  

    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.TRUE_NODE,
        "Ketu": swe.TRUE_NODE,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO
    }

    signs = [
        'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
        'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
    ]
    custom_d1_map = {sign: i + 1 for i, sign in enumerate(signs)}
    custom_d9_map = {
        "Aries": 1, "Taurus": 2, "Gemini": 3, "Leo": 4,
        "Cancer": 5, "Virgo": 6, "Libra": 7, "Scorpio": 8,
        "Sagittarius": 9, "Capricorn": 10, "Aquarius": 11, "Pisces": 12
    }
    sign_types = {
        "Movable": [1, 4, 7, 10],
        "Fixed":   [2, 5, 8, 11],
        "Dual":    [3, 6, 9, 12]
    }

    planet_order = [
        "Moon", "Mercury", "Venus", "Sun", "Mars",
        "Jupiter", "Rahu", "Ketu", "Saturn",
        "Uranus", "Neptune", "Pluto"
    ]
    planet_rank = {planet: i for i, planet in enumerate(planet_order)}

    def get_d9_sign_index(longitude_deg):
        sign_index = int(longitude_deg // 30)
        pos_in_sign = longitude_deg % 30
        navamsa_index = int(pos_in_sign // (30 / 9))
        if sign_index in [0, 3, 6, 9]:
            start = sign_index
        elif sign_index in [1, 4, 7, 10]:
            start = (sign_index + 8) % 12
        else:
            start = (sign_index + 4) % 12
        return (start + navamsa_index) % 12
    
    def classify_sign_type(sign_number):
        if sign_number in sign_types["Movable"]:
            return "Movable"
        elif sign_number in sign_types["Fixed"]:
            return "Fixed"
        elif sign_number in sign_types["Dual"]:
            return "Dual"
        return "Unknown"

    def get_conjunction_day_info(jd):
        """
        Returns (day_type, reason). If any two planets are within ±1° on this JD:
         - day_type = "Red Day" if (fast_lon - slow_lon) < 0,
                      "Green Day" if > 0.
         - reason = "<Fast>-<Slow>: <signed_diff>°"
        Otherwise returns ("-", "").
        """
        flag = swe.FLG_SIDEREAL | swe.FLG_SPEED

        planet_data = {}
        for name, pid in planets.items():
            lon, speed = swe.calc_ut(jd, pid, flag)[0][0:2]
            if name == "Ketu":
                true_node_lon = swe.calc_ut(jd, swe.TRUE_NODE, flag)[0][0]
                lon = (true_node_lon + 180) % 360
                speed = -speed
            planet_data[name] = {"lon": lon, "speed": speed}

        # 2) Check each pair for |difference| ≤ 1°
        for p1, p2 in combinations(planet_data.keys(), 2):
            r1 = planet_rank.get(p1, 999)
            r2 = planet_rank.get(p2, 999)
            fast, slow = (p1, p2) if r1 < r2 else (p2, p1)

            d1 = planet_data[fast]["lon"]
            d2 = planet_data[slow]["lon"]
            diff = (d1 - d2 + 360) % 360
            if diff > 180:
                diff -= 360
            diff = round(diff, 2)

            if abs(diff) <= 1.0:
                day_type = "Red Day" if diff < 0 else "Green Day"
                reason = f"{fast}-{slow}: {diff}°"
                return day_type, reason

        return "-", ""

    # === Helper: Minimal Absolute Circular Difference ===
    def minimal_abs_diff(a, b):
        """
        Given two angles a, b (0–360), return the minimal |a-b| around the circle (0–180).
        """
        raw = abs((a - b + 360) % 360)
        return min(raw, 360 - raw)

    # === Build the Report Rows ===
    report_rows = []
    current_date = start_date

    while current_date <= end_date:
        jd = swe.julday(current_date.year, current_date.month, current_date.day, 0)

        # 2) Conjunction “Day Type” & “Reason”
        day_type, reason = get_conjunction_day_info(jd)

        # 3) Collect D1 & D9 classification and longitudes for all planets
        d1_types = []
        d9_types = []
        moon_d1_type = mercury_d1_type = None
        moon_d1_lon = mercury_d1_lon = None
        moon_d9_lon = mercury_d9_lon = None

        for name, pid in planets.items():
            # 3a) D1 (sidereal) longitude at 00:00 UTC
            lon = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)[0][0]
            if name == "Ketu":
                true_node_lon = swe.calc_ut(jd, swe.TRUE_NODE, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)[0][0]
                lon = (true_node_lon + 180) % 360

            # Record D1 longitudes for Moon & Mercury
            if name == "Moon":
                moon_d1_lon = lon
            if name == "Mercury":
                mercury_d1_lon = lon

            # Classify D1 sign type
            sign_index = int(lon // 30)
            rashi = signs[sign_index]
            d1_sign_num = custom_d1_map[rashi]
            d1_type = classify_sign_type(d1_sign_num)
            d1_types.append(d1_type)

            if name == "Moon":
                moon_d1_type = d1_type
            if name == "Mercury":
                mercury_d1_type = d1_type

            # 3b) Compute D9 (Navamsa) longitude:
            navamsa_size = 30 / 9
            pos_in_sign = lon % 30
            nav_sign_idx = get_d9_sign_index(lon)
            d9_deg_in_sign = (pos_in_sign % navamsa_size) * 9
            d9_lon = nav_sign_idx * 30 + d9_deg_in_sign

            # Record D9 longitudes for Moon & Mercury
            if name == "Moon":
                moon_d9_lon = d9_lon
            if name == "Mercury":
                mercury_d9_lon = d9_lon

            # Classify D9 sign
            d9_sign = signs[nav_sign_idx]
            d9_sign_num = custom_d9_map[d9_sign]
            d9_type = classify_sign_type(d9_sign_num)
            d9_types.append(d9_type)

        # 4) Count Movable/Fixed in D1 & D9
        d1_movable_count = d1_types.count("Movable")
        d1_fixed_count   = d1_types.count("Fixed")
        d9_movable_count = d9_types.count("Movable")
        d9_fixed_count   = d9_types.count("Fixed")

        # 5a) D1 combined classification
        if moon_d1_type == mercury_d1_type:
            mm_d1_status = f"Moon & Mercury: {moon_d1_type}"
        else:
            mm_d1_status = f"Moon: {moon_d1_type}, Mercury: {mercury_d1_type}"

        # 5b) D9 combined classification
        moon_d9_type = classify_sign_type(custom_d9_map[signs[int(moon_d9_lon // 30)]])
        mercury_d9_type = classify_sign_type(custom_d9_map[signs[int(mercury_d9_lon // 30)]])

        if moon_d9_type == mercury_d9_type:
            mm_d9_status = f"Moon & Mercury: {moon_d9_type}"
        else:
            mm_d9_status = f"Moon: {moon_d9_type}, Mercury: {mercury_d9_type}"


        # 6) Compute Moon→Mercury and Mercury→Moon diffs for D1
        #    → raw signed diff (0–360), convert to (−180…+180)
        raw_m2me_d1 = (moon_d1_lon - mercury_d1_lon + 360) % 360
        if raw_m2me_d1 > 180:
            raw_m2me_d1 -= 360
        raw_m2me_d1 = round(raw_m2me_d1, 2)

        raw_me2m_d1 = (mercury_d1_lon - moon_d1_lon + 360) % 360
        if raw_me2m_d1 > 180:
            raw_me2m_d1 -= 360
        raw_me2m_d1 = round(raw_me2m_d1, 2)

        # Minimal absolute difference (0–180)
        min_m2me_d1 = minimal_abs_diff(moon_d1_lon, mercury_d1_lon)
        min_me2m_d1 = minimal_abs_diff(mercury_d1_lon, moon_d1_lon)

        # If within ±1° of {0, 90, 180}, show that key angle; otherwise show actual
        def label_diff(min_diff):
            for target in (0, 90, 180):
                if abs(min_diff - target) <= 1:
                    return f"{target}°"
            return f"{min_diff:.2f}°"

        label_m2me_d1 = label_diff(min_m2me_d1)
        label_me2m_d1 = label_diff(min_me2m_d1)
        mm_d1_label = f"{label_m2me_d1} / {label_me2m_d1}"

        # 7) Compute Moon→Mercury and Mercury→Moon diffs for D9
        raw_m2me_d9 = (moon_d9_lon - mercury_d9_lon + 360) % 360
        if raw_m2me_d9 > 180:
            raw_m2me_d9 -= 360
        raw_m2me_d9 = round(raw_m2me_d9, 2)

        raw_me2m_d9 = (mercury_d9_lon - moon_d9_lon + 360) % 360
        if raw_me2m_d9 > 180:
            raw_me2m_d9 -= 360
        raw_me2m_d9 = round(raw_me2m_d9, 2)

        min_m2me_d9 = minimal_abs_diff(moon_d9_lon, mercury_d9_lon)
        min_me2m_d9 = minimal_abs_diff(mercury_d9_lon, moon_d9_lon)

        label_m2me_d9 = label_diff(min_m2me_d9)
        label_me2m_d9 = label_diff(min_me2m_d9)
        mm_d9_label = f"{label_m2me_d9} / {label_me2m_d9}"

        # 8) Append row
        report_rows.append({
            "Date": current_date.strftime("%Y-%m-%d"),
            "Day Type": day_type,
            "Reason": reason,
            "D1 Movable": d1_movable_count,
            "D9 Movable": d9_movable_count,
            "D1 Fixed": d1_fixed_count,
            "D9 Fixed": d9_fixed_count,
            "Moon & Mercury D1": mm_d1_label,
            "Moon & Mercury D9": mm_d9_label,
            "Moon & Mercury D1 Type": mm_d1_status,
            "Moon & Mercury D9 Type": mm_d9_status
            })

        current_date += datetime.timedelta(days=1)

    # Create DataFrame
    df = pd.DataFrame(report_rows)

    # === Render Highlighted HTML Table ===
    def render_highlighted_report(df):
        rows_html = []
        for _, row in df.iterrows():
            status = row["Moon & Mercury D1 Type"]
            if status.strip() == "Moon & Mercury: Movable":
                style = "background-color: black; color: white;"
            elif status.strip() == "Moon & Mercury: Fixed":
                style = "background-color: #ffcccc;"
            else:
                style = ""


            cells = "".join([f"<td>{row[col]}</td>" for col in df.columns])
            rows_html.append(f"<tr style='{style}'>{cells}</tr>")

        header_html = "".join([f"<th>{col}</th>" for col in df.columns])
        html = f"""
        <div class="scroll-table">
            <table>
                <thead><tr>{header_html}</tr></thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        """
        return html

    st.markdown("### 📊 Final Daily Report Table")
    st.markdown(render_highlighted_report(df), unsafe_allow_html=True)

elif filter_mode == "Moon–Mercury Aspects":
    st.header("🌕 Mercury–Moon Aspects (D1 & D9 ±1°)")

    import swisseph as swe
    import pandas as pd
    import re
    from datetime import datetime, timedelta
    from collections import defaultdict

    # === Setup ===
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

    LAT = 19.076
    LON = 72.8777
    TZ_OFFSET = 5.5  # IST

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime(2025, 6, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime(2025, 6, 30))

    # Time Ranges
    D1_START_HOUR, D1_END_HOUR = 0, 23
    D9_START_HOUR, D9_END_HOUR = 8, 16

    # Helpers
    def angular_diff(from_deg, to_deg):
        return round((to_deg - from_deg) % 360, 2)

    def check_aspects(from_deg, to_deg):
        angles = [0, 90, 180]
        matched = []
        diff1 = angular_diff(from_deg, to_deg)
        diff2 = angular_diff(to_deg, from_deg)
        for angle in angles:
            if abs(diff1 - angle) <= 1:
                matched.append(f"Moon→Mercury ≈ {angle}°")
            if abs(diff2 - angle) <= 1:
                matched.append(f"Mercury→Moon ≈ {angle}°")
        return matched if matched else ["nan"]

    def get_d9_longitude(longitude_deg):
        sign_index = int(longitude_deg // 30)
        pos_in_sign = longitude_deg % 30
        navamsa_index = int(pos_in_sign // (30 / 9))
        if sign_index in [0, 3, 6, 9]:
            start = sign_index
        elif sign_index in [1, 4, 7, 10]:
            start = (sign_index + 8) % 12
        else:
            start = (sign_index + 4) % 12
        d9_sign_index = (start + navamsa_index) % 12
        deg_in_navamsa = pos_in_sign % (30 / 9)
        d9_long = d9_sign_index * 30 + deg_in_navamsa * 9
        return d9_long

    def extract_angles(aspect_str):
        if aspect_str == "nan":
            return set()
        return set(re.findall(r"(Moon→Mercury|Mercury→Moon) ≈ (\d+)°", aspect_str))

    # === Process Dates ===
    results_d1 = []
    results_d9 = []

    for day in pd.date_range(start_date, end_date):
        # D1 window
        for hour in range(D1_START_HOUR, D1_END_HOUR + 1):
            dt = datetime(day.year, day.month, day.day, hour, 0)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
            moon = swe.calc_ut(jd, swe.MOON, flag)[0][0]
            mercury = swe.calc_ut(jd, swe.MERCURY, flag)[0][0]
            aspects = check_aspects(moon, mercury)
            if aspects != ["nan"]:
                results_d1.append({
                    "Date": dt.date(),
                    "Time (IST)": dt.time(),
                    "D1 Aspects": ", ".join(aspects)
                })

        # D9 window
        for hour in range(D9_START_HOUR, D9_END_HOUR + 1):
            dt = datetime(day.year, day.month, day.day, hour, 0)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
            moon = swe.calc_ut(jd, swe.MOON, flag)[0][0]
            mercury = swe.calc_ut(jd, swe.MERCURY, flag)[0][0]
            moon_d9 = get_d9_longitude(moon)
            mercury_d9 = get_d9_longitude(mercury)
            aspects = check_aspects(moon_d9, mercury_d9)
            if aspects != ["nan"]:
                results_d9.append({
                    "Date": dt.date(),
                    "Time (IST)": dt.time(),
                    "D9 Aspects": ", ".join(aspects)
                })

    # === Group By Date ===
    all_dates = pd.date_range(start=start_date, end=end_date).date
    grouped_d1 = defaultdict(set)
    grouped_d1_times = defaultdict(list)
    grouped_d9 = defaultdict(set)
    grouped_d9_times = defaultdict(list)

    for row in results_d1:
        d = row["Date"]
        grouped_d1[d].update(extract_angles(row["D1 Aspects"]))
        grouped_d1_times[d].append(str(row["Time (IST)"]))

    for row in results_d9:
        d = row["Date"]
        grouped_d9[d].update(extract_angles(row["D9 Aspects"]))
        grouped_d9_times[d].append(str(row["Time (IST)"]))

    # === Build Summary ===
    summary = []
    for d in all_dates:
        d1_text = ", ".join([f"{dir} ≈ {deg}°" for dir, deg in sorted(grouped_d1[d])]) if grouped_d1[d] else "0"
        d9_text = ", ".join([f"{dir} ≈ {deg}°" for dir, deg in sorted(grouped_d9[d])]) if grouped_d9[d] else "0"
        d1_times = sorted(set(grouped_d1_times[d]))[0] if grouped_d1_times[d] else "0"
        d9_times = ", ".join(sorted(set(grouped_d9_times[d]))) if grouped_d9_times[d] else "0"

        # === NEW: Get D1 and D9 signs for Moon & Mercury
        utc_dt = datetime(d.year, d.month, d.day, 0, 0) - timedelta(hours=TZ_OFFSET)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)

        moon_d1 = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)[0][0]
        mercury_d1 = swe.calc_ut(jd, swe.MERCURY, swe.FLG_SIDEREAL | swe.FLG_SWIEPH)[0][0]

        moon_d1_sign = int(moon_d1 // 30)
        mercury_d1_sign = int(mercury_d1 // 30)

        # D9 conversion
        def get_sign_from_deg(deg):
            signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                    'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
            return signs[int(deg // 30)]

        moon_d9 = get_d9_longitude(moon_d1)
        mercury_d9 = get_d9_longitude(mercury_d1)

        moon_d1_sign_name = get_sign_from_deg(moon_d1)
        mercury_d1_sign_name = get_sign_from_deg(mercury_d1)

        moon_d9_sign_name = get_sign_from_deg(moon_d9)
        mercury_d9_sign_name = get_sign_from_deg(mercury_d9)

        # Check if they're in Gemini, Virgo, or Cancer
        target_signs = ["Gemini", "Virgo", "Cancer"]

        def build_status(moon_sign, mercury_sign):
            parts = []
            if moon_sign in target_signs:
                parts.append(f"Moon: {moon_sign}")
            if mercury_sign in target_signs:
                parts.append(f"Mercury: {mercury_sign}")
            return ", ".join(parts) if parts else "None"

        d1_signs_status = build_status(moon_d1_sign_name, mercury_d1_sign_name)
        d9_signs_status = build_status(moon_d9_sign_name, mercury_d9_sign_name)

        summary.append({
            "Date": d,
            "D1 Aspects": d1_text,
            "D1 Aspect Time(s)": d1_times,
            "Moon–Mercury D1 Signs": d1_signs_status,
            "D9 Aspects": d9_text,
            "D9 Aspect Time(s)": d9_times,
            "Moon–Mercury D9 Signs": d9_signs_status
        })


        df_summary = pd.DataFrame(summary)

    # 🔥 Filter out rows where both D1 and D9 aspects are "0"
    df_summary_filtered = df_summary[
        (df_summary["D1 Aspects"] != "0") | (df_summary["D9 Aspects"] != "0")
    ]


    st.markdown("### 📅 Final Moon–Mercury Aspect Table")
    def render_aspect_table(df):
        rows_html = []
        for _, row in df.iterrows():
            d1 = row["D1 Aspects"]
            d9 = row["D9 Aspects"]
            if d1 != "0" or d9 != "0":
                style = "background-color: black; color: white;"
            else:
                style = ""

            row_cells = "".join([f"<td>{val}</td>" for val in row])
            rows_html.append(f"<tr style='{style}'>{row_cells}</tr>")

        header_html = "".join([f"<th>{col}</th>" for col in df.columns])
        table_html = f"""
        <div class="scroll-table">
            <table>
                <thead><tr>{header_html}</tr></thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        """
        return table_html

    st.markdown(render_aspect_table(df_summary_filtered), unsafe_allow_html=True)

elif filter_mode == "Planetary Aspects":
    st.header("🔭 Planetary Aspect Report")

    import swisseph as swe
    import pandas as pd
    from datetime import datetime, timedelta
    from collections import defaultdict

    # Setup
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

    LAT = 19.076
    LON = 72.8777
    TZ_OFFSET = 5.5

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime(2025, 6, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime(2025, 6, 30))

    D1_START_HOUR, D1_END_HOUR = 0, 23
    D9_START_HOUR, D9_END_HOUR = 8, 16

    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

    def get_sign(lon):
        return signs[int(lon // 30)]

    def angular_diff(from_deg, to_deg):
        return round((to_deg - from_deg) % 360, 2)

    def check_aspects(from_deg, to_deg, angles, label):
        matched = []
        for angle in angles:
            if abs(angular_diff(from_deg, to_deg) - angle) <= 0.5:
                matched.append(f"{label} ≈ {angle}°")
        return matched if matched else ["nan"]

    def get_d9_longitude(lon):
        sign_index = int(lon // 30)
        pos_in_sign = lon % 30
        navamsa_index = int(pos_in_sign // (30 / 9))
        if sign_index in [0, 3, 6, 9]:
            start = sign_index
        elif sign_index in [1, 4, 7, 10]:
            start = (sign_index + 8) % 12
        else:
            start = (sign_index + 4) % 12
        d9_sign_index = (start + navamsa_index) % 12
        deg_in_navamsa = pos_in_sign % (30 / 9)
        return d9_sign_index * 30 + deg_in_navamsa * 9

    # === Aspect Config ===
    aspect_config = {
        "Sun→Ketu": {"from": "Sun", "to": "Ketu", "angles": [0, 90, 120]},
        "Venus→Ketu": {"from": "Venus", "to": "Ketu", "angles": [0, 120]},
    }

    planet_map = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY, 'Venus': swe.VENUS,
        'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE, 'Ketu': swe.TRUE_NODE  # Ketu = Rahu + 180
    }

    results_d1 = defaultdict(list)
    results_d9 = defaultdict(list)

    for day in pd.date_range(start_date, end_date):
        # D1 loop
        for hour in range(D1_START_HOUR, D1_END_HOUR + 1):
            dt = datetime(day.year, day.month, day.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

            longitudes = {}
            for name, code in planet_map.items():
                lon = swe.calc_ut(jd, code, flag)[0][0]
                if name == "Ketu":
                    lon = (swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0] + 180) % 360
                longitudes[name] = lon

            for label, config in aspect_config.items():
                aspects = check_aspects(longitudes[config["from"]], longitudes[config["to"]], config["angles"], label)
                if aspects != ["nan"]:
                    results_d1[dt.date()].append((label, aspects[0], dt.time()))

        # D9 loop
        for hour in range(D9_START_HOUR, D9_END_HOUR + 1):
            dt = datetime(day.year, day.month, day.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

            longitudes = {}
            for name, code in planet_map.items():
                lon = swe.calc_ut(jd, code, flag)[0][0]
                if name == "Ketu":
                    lon = (swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0] + 180) % 360
                longitudes[name] = get_d9_longitude(lon)

            for label, config in aspect_config.items():
                aspects = check_aspects(longitudes[config["from"]], longitudes[config["to"]], config["angles"], label)
                if aspects != ["nan"]:
                    results_d9[dt.date()].append((label, aspects[0], dt.time()))

    # === Build Summary Table ===
    summary = []
    all_dates = pd.date_range(start=start_date, end=end_date).date

    for d in all_dates:
        d1_aspects = [a[1] for a in results_d1[d]]
        d1_times = [str(a[2]) for a in results_d1[d]]
        d9_aspects = [a[1] for a in results_d9[d]]
        d9_times = [str(a[2]) for a in results_d9[d]]

        summary.append({
            "Date": d,
            "D1 Aspects": d1_aspects[0] if d1_aspects else "0",
            "D1 Aspects Time": d1_times[0] if d1_times else "0",
            "D9 Aspects": d9_aspects[0] if d9_aspects else "0",
            "D9 Aspects Time": d9_times[0] if d9_times else "0"
        })

    df = pd.DataFrame(summary)

    # ✅ Only show rows with at least one aspect
    df_filtered = df[(df["D1 Aspects"] != "0") | (df["D9 Aspects"] != "0")]

    # === Render Table ===
    def render_aspect_html(df):
        rows = []
        for _, row in df.iterrows():
            style = "background-color: black; color: white;"
            row_html = "<tr style='{}'>".format(style)
            row_html += "".join(f"<td>{val}</td>" for val in row)
            row_html += "</tr>"
            rows.append(row_html)

        header = "".join([f"<th>{col}</th>" for col in df.columns])
        table = f"""
        <div class="scroll-table">
            <table>
                <thead><tr>{header}</tr></thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """
        return table

    st.markdown("### 🧭 Daily Planetary Aspect Hits")
    st.markdown(render_aspect_html(df_filtered), unsafe_allow_html=True)

elif filter_mode == "Swapt Nadi Chakra":
    st.header("🌀 Swapt Nadi Chakra Report")

    import swisseph as swe
    import pandas as pd
    from datetime import datetime, timedelta

    # === Setup ===
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
    LAT, LON = 19.076, 72.8777
    TZ_OFFSET = 5.5

    # === User Input ===
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime(2025, 1, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime(2025, 6, 3))

    # === Nadi Classification Setup ===
    nakshatras = [
        "Ashwani", "Bharni", "Krittika", "Rohini", "Mrigsira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
        "Magha", "P.Phalguni", "U.Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshta",
        "Mula", "P.Ashadha", "U.Ashadha", "Abhijit", "Sharavana", "Dhanishta", "Satabhisha",
        "P.Bhadra Pada", "U.Bhadra Pada", "Revati"
    ]

    nadi_map = {
        'Bharni': 'Prachanda', 'Krittika': 'Prachanda', 'Vishakha': 'Prachanda', 'Anuradha': 'Prachanda',
        'Ashwani': 'Pawan', 'Rohini': 'Pawan', 'Swati': 'Pawan', 'Jyeshta': 'Pawan',
        'Mrigsira': 'Dahan', 'Chitra': 'Dahan', 'Mula': 'Dahan', 'Revati': 'Dahan',
        'Ardra': 'Soumya', 'Hasta': 'Soumya', 'P.Ashadha': 'Soumya', 'U.Bhadra Pada': 'Soumya',
        'Punarvasu': 'Neera', 'U.Phalguni': 'Neera', 'U.Ashadha': 'Neera', 'P.Bhadra Pada': 'Neera',
        'Pushya': 'Jala', 'P.Phalguni': 'Jala', 'Abhijit': 'Jala', 'Satabhisha': 'Jala',
        'Ashlesha': 'Amrit', 'Magha': 'Amrit', 'Sharavana': 'Amrit', 'Dhanishta': 'Amrit'
    }

    planet_list = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY, 'Venus': swe.VENUS,
        'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE, 'Ketu': swe.TRUE_NODE
    }

    def get_nakshatra(degree):
        return nakshatras[int(degree // (360 / 27))]

    def get_longitude(jd, planet, flag):
        if planet == 'Ketu':
            rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0]
            return (rahu_lon + 180) % 360
        return swe.calc_ut(jd, planet_list[planet], flag)[0][0]

    # === Build Daily Table ===
    daily_data = []
    for day in pd.date_range(start=start_date, end=end_date):
        row = {"Date": day.date(), "Prachanda": [], "Pawan": [], "Dahan": [], "Soumya": [], "Neera": [], "Jala": [], "Amrit": []}
        dt = datetime(day.year, day.month, day.day, 9, 0)
        utc_dt = dt - timedelta(hours=TZ_OFFSET)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60)
        flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

        for planet in planet_list:
            lon = get_longitude(jd, planet, flag)
            nak = get_nakshatra(lon)
            nadi = nadi_map.get(nak)
            if nadi:
                row[nadi].append(planet)

        for nadi in ["Prachanda", "Pawan", "Dahan", "Soumya", "Neera", "Jala", "Amrit"]:
            row[nadi] = ", ".join(row[nadi]) if row[nadi] else ""

        daily_data.append(row)

    df_nadi = pd.DataFrame(daily_data)

    # === Display as HTML Table ===
    st.markdown("### 🔮 Daily Nadi Chakra Classification Table")
    html_table = df_nadi.to_html(index=False)
    st.markdown(f'<div class="scroll-table">{html_table}</div>', unsafe_allow_html=True)

elif filter_mode == "Planetary Ingress":
    st.header("🚪 Planetary Ingress Report (Excluding Moon)")

    import swisseph as swe
    import pandas as pd
    from datetime import datetime, timedelta

    # === Setup ===
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

    LAT, LON = 19.076, 72.8777
    TZ_OFFSET = 5.5  # IST

    # === User Date Input ===
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime(2025, 1, 1))
    with col2:
        end_date = st.date_input("End Date", value=datetime(2025, 6, 30))

    # === Planets to Track (excluding Moon) ===
    planet_list = {
        'Sun': swe.SUN,
        'Mercury': swe.MERCURY,
        'Venus': swe.VENUS,
        'Mars': swe.MARS,
        'Jupiter': swe.JUPITER,
        'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE,
        'Ketu': swe.TRUE_NODE  # calculated as opposite of Rahu
    }

    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

    def get_sign_name(degree):
        return signs[int(degree // 30)]

    # === Ingress Detection ===
    results = []
    last_sign = {}

    for day in pd.date_range(start=start_date, end=end_date):
        dt = datetime(day.year, day.month, day.day, 0)
        utc_dt = dt - timedelta(hours=TZ_OFFSET)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
        flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

        for name, code in planet_list.items():
            lon = swe.calc_ut(jd, code, flag)[0][0]
            if name == "Ketu":
                lon = (swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0] + 180) % 360

            current_sign = get_sign_name(lon)

            if name not in last_sign:
                last_sign[name] = current_sign
            elif last_sign[name] != current_sign:
                results.append({
                    "Date": dt.date(),
                    "Planet": name,
                    "From Sign": last_sign[name],
                    "To Sign": current_sign
                })
                last_sign[name] = current_sign
 
    df_ingress = pd.DataFrame(results)

    # === Render as HTML Table ===
    st.markdown("### 📆 Planetary Ingress Events")
    if not df_ingress.empty:
        html = df_ingress.to_html(index=False)
        st.markdown(f'<div class="scroll-table">{html}</div>', unsafe_allow_html=True)
    else:
        st.info("No ingress events found in selected date range.")

elif filter_mode == "AOT Monthly Calendar":
    st.header("📅 AOT Monthly Report")

    import swisseph as swe
    import pandas as pd
    from datetime import datetime, timedelta

    # === Config
    swe.set_ephe_path("C:/ephe")
    swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)
    LAT = 19.0760
    LON = 72.8777
    TZ_OFFSET = 5.5  # IST

    # === Input
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.today() - timedelta(days=30), key="aot_start")
    with col2:
        end_date = st.date_input("End Date", value=datetime.today(), key="aot_end")

    nadi_map = {
    'Bharni': 'Prachanda', 'Krittika': 'Prachanda', 'Vishakha': 'Prachanda', 'Anuradha': 'Prachanda',
    'Ashwani': 'Pawan', 'Rohini': 'Pawan', 'Swati': 'Pawan', 'Jyeshta': 'Pawan',
    'Mrigsira': 'Dahan', 'Chitra': 'Dahan', 'Mula': 'Dahan', 'Revati': 'Dahan',
    'Ardra': 'Soumya', 'Hasta': 'Soumya', 'P.Ashadha': 'Soumya', 'U.Bhadra Pada': 'Soumya',
    'Punarvasu': 'Neera', 'U.Phalguni': 'Neera', 'U.Ashadha': 'Neera', 'P.Bhadra Pada': 'Neera',
    'Pushya': 'Jala', 'P.Phalguni': 'Jala', 'Abhijit': 'Jala', 'Satabhisha': 'Jala',
    'Ashlesha': 'Amrit', 'Magha': 'Amrit', 'Sharavana': 'Amrit', 'Dhanishta': 'Amrit'
    }

    nakshatras = [
        "Ashwani", "Bharni", "Krittika", "Rohini", "Mrigsira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
        "Magha", "P.Phalguni", "U.Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshta",
        "Mula", "P.Ashadha", "U.Ashadha", "Abhijit", "Sharavana", "Dhanishta", "Satabhisha",
        "P.Bhadra Pada", "U.Bhadra Pada", "Revati"
    ]

    def get_nakshatra_name(degree):
        return nakshatras[int(degree // (360 / 27))]

    nadi_types = ["Prachanda", "Pawan", "Dahan", "Soumya", "Neera", "Jala", "Amrit"]

    planet_list = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mercury': swe.MERCURY, 'Venus': swe.VENUS,
        'Mars': swe.MARS, 'Jupiter': swe.JUPITER, 'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE, 'Ketu': swe.TRUE_NODE  # Ketu will be 180° from Rahu
    }

    # === Planet definitions
    planets = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
        "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE, "Ketu": swe.TRUE_NODE,
        "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
    }

    signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
             'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    
    def get_sign_name(degree):
        return signs[int(degree // 30)]
    
    planet_ingress_signs = {}
    planet_list_ingress = {
        'Sun': swe.SUN,
        'Mercury': swe.MERCURY,
        'Venus': swe.VENUS,
        'Mars': swe.MARS,
        'Jupiter': swe.JUPITER,
        'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE,
        'Ketu': swe.TRUE_NODE  # Opposite of Rahu
    }

    def classify_sign_type(num):
        if num in [1, 4, 7, 10]:
            return "Movable"
        elif num in [2, 5, 8, 11]:
            return "Fixed"
        elif num in [3, 6, 9, 12]:
            return "Dual"
        return "Unknown"

    custom_d1_map = {sign: i + 1 for i, sign in enumerate(signs)}
    sign_types = {
        "Movable": [1, 4, 7, 10],
        "Fixed": [2, 5, 8, 11],
        "Dual": [3, 6, 9, 12]
    }

    planet_order = ["Moon", "Mercury", "Venus", "Sun", "Mars",
                    "Jupiter", "Rahu", "Ketu", "Saturn", "Uranus", "Neptune", "Pluto"]
    planet_rank = {p: i for i, p in enumerate(planet_order)}

    def classify_sign_type(sign_number):
        for k, v in sign_types.items():
            if sign_number in v:
                return k
        return "Unknown"

    # === Loop through dates
    rows = []
    current = start_date
    while current <= end_date:
        utc_dt = datetime(current.year, current.month, current.day) - timedelta(hours=TZ_OFFSET)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day)
        jd2 = swe.julday(current.year, current.month, current.day, 0)

        planet_data = {}
        for name, pid in planets.items():
            lon, speed = get_planet_data(jd2, name, pid)
            planet_data[name] = {"deg": lon, "speed": speed}

        day_type = "-"
        for p1, p2 in combinations(planet_data.keys(), 2):
            r1 = planet_rank.get(p1, 999)
            r2 = planet_rank.get(p2, 999)
            fast, slow = (p1, p2) if r1 < r2 else (p2, p1)

            d1 = planet_data[fast]["deg"]
            d2 = planet_data[slow]["deg"]
            diff = signed_diff(d1, d2)

            if abs(diff) <= 1.0:
                day_type = "Red Day" if diff < 0 else "Green Day"
                break

        # === Fixed Time: 9:00 AM IST for D1 and D9 Type Classification
        classification_dt = datetime(current.year, current.month, current.day, 9, 0)
        utc_dt_class = classification_dt - timedelta(hours=TZ_OFFSET)
        jd_class = swe.julday(utc_dt_class.year, utc_dt_class.month, utc_dt_class.day, utc_dt_class.hour + utc_dt_class.minute / 60)

        d1_types = {"Movable": [], "Fixed": [], "Dual": []}
        d9_types = {"Movable": [], "Fixed": [], "Dual": []}
        flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

        for name, pid in planets.items():
            lon = swe.calc_ut(jd_class, pid, flag)[0][0]
            if name == "Ketu":
                rahu_lon = swe.calc_ut(jd_class, swe.MEAN_NODE, flag)[0][0]
                lon = (rahu_lon + 180) % 360

            # === D1 classification
            d1_sign_index = int(lon // 30)
            d1_sign_number = d1_sign_index + 1
            d1_type = classify_sign_type(d1_sign_number)
            d1_types[d1_type].append(name)

            # === D9 classification
            def get_d9_longitude(lon):
                sign_index = int(lon // 30)
                pos_in_sign = lon % 30
                navamsa_index = int(pos_in_sign // (30 / 9))
                if sign_index in [0, 3, 6, 9]:
                    start = sign_index
                elif sign_index in [1, 4, 7, 10]:
                    start = (sign_index + 8) % 12
                else:
                    start = (sign_index + 4) % 12
                d9_sign_index = (start + navamsa_index) % 12
                deg_in_navamsa = pos_in_sign % (30 / 9)
                return d9_sign_index * 30 + deg_in_navamsa * 9

            d9_lon = get_d9_longitude(lon)
            d9_sign_index = int(d9_lon // 30)
            d9_sign_number = d9_sign_index + 1
            d9_type = classify_sign_type(d9_sign_number)
            d9_types[d9_type].append(name)

        # Format result strings
        d1_classified_str = " | ".join([f"{k}: {', '.join(v)}" for k, v in d1_types.items() if v])
        d9_classified_str = " | ".join([f"{k}: {', '.join(v)}" for k, v in d9_types.items() if v])

        # === Moon Nakshatra & Pada (Lahiri, 9:00 IST)
        moon_dt = datetime(current.year, current.month, current.day, 9, 0)
        moon_utc = moon_dt - timedelta(hours=TZ_OFFSET)
        moon_jd = swe.julday(moon_utc.year, moon_utc.month, moon_utc.day, moon_utc.hour + moon_utc.minute / 60.0)

        moon_lon = swe.calc_ut(moon_jd, swe.MOON)[0][0]

        nak_index = int(moon_lon // (360 / 27))
        moon_nak = nakshatras[nak_index]
        moon_pada = int(((moon_lon % (360 / 27)) // (360 / 27 / 4)) + 1)


        ingress_changes = []

        flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH
        for name, code in planet_list_ingress.items():
            lon = swe.calc_ut(jd, code, flag)[0][0]
            if name == "Ketu":
                rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0]
                lon = (rahu_lon + 180) % 360

            current_sign = get_sign_name(lon)

            if name not in planet_ingress_signs:
                planet_ingress_signs[name] = current_sign
            elif planet_ingress_signs[name] != current_sign:
                ingress_changes.append((name, planet_ingress_signs[name], current_sign))
                planet_ingress_signs[name] = current_sign

        # === D1 Aspect Detection
        d1_aspect_result = "0"
        for hour in range(0, 24):
            dt = datetime(current.year, current.month, current.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd_hour = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

            longitudes = {}
            for name, code in planet_map.items():
                lon = swe.calc_ut(jd_hour, code, flag)[0][0]
                if name == "Ketu":
                    lon = (swe.calc_ut(jd_hour, swe.MEAN_NODE, flag)[0][0] + 180) % 360
                longitudes[name] = lon

            for label, config in aspect_config.items():
                asp = check_aspects(longitudes[config["from"]], longitudes[config["to"]], config["angles"], label)
                if asp:
                    d1_aspect_result = asp
                    break
            if d1_aspect_result != "0":
                break

        # === D9 Aspect Detection
        d9_aspect_result = "0"
        for hour in range(8, 17):  # 8 AM to 4 PM
            dt = datetime(current.year, current.month, current.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd_hour = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

            longitudes = {}
            for name, code in planet_map.items():
                lon = swe.calc_ut(jd_hour, code, flag)[0][0]
                if name == "Ketu":
                    lon = (swe.calc_ut(jd_hour, swe.MEAN_NODE, flag)[0][0] + 180) % 360
                longitudes[name] = get_d9_longitude(lon)

            for label, config in aspect_config.items():
                asp = check_aspects(longitudes[config["from"]], longitudes[config["to"]], config["angles"], label)
                if asp:
                    d9_aspect_result = asp
                    break
            if d9_aspect_result != "0":
                break

        nadi_result = {n: [] for n in nadi_types}
        flag = swe.FLG_SIDEREAL | swe.FLG_SWIEPH

        for planet in planet_list:
            if planet == 'Ketu':
                rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE, flag)[0][0]
                lon = (rahu_lon + 180) % 360
            else:
                lon = swe.calc_ut(jd, planet_list[planet], flag)[0][0]

            nak = get_nakshatra_name(lon)
            nadi = nadi_map.get(nak)
            if nadi:
                nadi_result[nadi].append(planet)

            # Optional: combine only Prachanda & Pawan for now
            prachanda_str = ", ".join(nadi_result["Prachanda"]) if nadi_result["Prachanda"] else ""
            pawan_str = ", ".join(nadi_result["Pawan"]) if nadi_result["Pawan"] else ""


        # Julian Day
        # === Moon Nakshatra & Pada (Lahiri, 9:00 IST)
        asc_dt = datetime(current.year, current.month, current.day, 9, 0)
        asc_utc = asc_dt - timedelta(hours=TZ_OFFSET)
        asc_jd = swe.julday(asc_utc.year, asc_utc.month, asc_utc.day, asc_utc.hour + asc_utc.minute / 60.0)

        flags = swe.FLG_SIDEREAL
        ascmc, cusp = swe.houses_ex(asc_jd, LAT, LON, b'A', flags)
        asc = ascmc[0]

        nak_index = int(asc // (360 / 27))
        pada = int(((asc % (360 / 27)) // (360 / 27 / 4)) + 1)
        nak = nakshatras[nak_index]


        # === Moon–Mercury D1 Type
        moon_d1 = get_planet_deg(jd, "Moon")
        mercury_d1 = get_planet_deg(jd, "Mercury")
        moon_sign = int(moon_d1 // 30)
        mercury_sign = int(mercury_d1 // 30)
        moon_d1_type = classify_sign_type(custom_d1_map[signs[moon_sign]])
        mercury_d1_type = classify_sign_type(custom_d1_map[signs[mercury_sign]])

        if moon_d1_type == mercury_d1_type:
            mm_d1_status = f"Moon & Mercury: {moon_d1_type}"
        else:
            mm_d1_status = f"Moon: {moon_d1_type}, Mercury: {mercury_d1_type}"

        # === Moon–Mercury D9 Type
        moon_d9 = get_d9_longitude(moon_d1)
        mercury_d9 = get_d9_longitude(mercury_d1)
        moon_d9_sign = int(moon_d9 // 30)
        mercury_d9_sign = int(mercury_d9 // 30)
        moon_d9_type = classify_sign_type(moon_d9_sign + 1)
        mercury_d9_type = classify_sign_type(mercury_d9_sign + 1)

        if moon_d9_type == mercury_d9_type:
            mm_d9_status = f"Moon & Mercury: {moon_d9_type}"
        else:
            mm_d9_status = f"Moon: {moon_d9_type}, Mercury: {mercury_d9_type}"

        # === Moon–Mercury D1 Aspect (0–23 IST)
        d1_aspect = "0"
        for hour in range(0, 24):
            dt = datetime(current.year, current.month, current.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd_hour = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            m_deg = get_planet_deg(jd_hour, "Moon")
            mc_deg = get_planet_deg(jd_hour, "Mercury")
            asp = check_mm_aspects(m_deg, mc_deg)
            if asp != "0":
                d1_aspect = asp
                break

        # === Moon–Mercury D9 Aspect (8–16 IST)
        d9_aspect = "0"
        for hour in range(8, 17):
            dt = datetime(current.year, current.month, current.day, hour)
            utc_dt = dt - timedelta(hours=TZ_OFFSET)
            jd_hour = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour)
            m_deg = get_planet_deg(jd_hour, "Moon")
            mc_deg = get_planet_deg(jd_hour, "Mercury")
            m_d9 = get_d9_longitude(m_deg)
            mc_d9 = get_d9_longitude(mc_deg)
            asp = check_mm_aspects(m_d9, mc_d9)
            if asp != "0":
                d9_aspect = asp
                break

        rows.append({
            "Date": current.strftime("%Y-%m-%d"),
            "Day Type": day_type,
            "Moon & Mercury D1 Type": mm_d1_status,
            "Moon & Mercury D9 Type": mm_d9_status,
            "D1 Aspect": d1_aspect,
            "D9 Aspect": d9_aspect,
            "Ascendant Nakshatra": nak,
            "Ascendant Pada": pada,
            "Prachanda": prachanda_str,
            "Pawan": pawan_str,
            "D1 Aspects": d1_aspect_result,
            "D9 Aspects": d9_aspect_result,
            "Ingress Planet": ingress_changes[0][0] if ingress_changes else "",
            "From Sign": ingress_changes[0][1] if ingress_changes else "",
            "To Sign": ingress_changes[0][2] if ingress_changes else "",
            "Moon Nakshatra": moon_nak,
            "Moon Pada": moon_pada,
            "Planets M/F/D D1": d1_classified_str,
            "Planets M/F/D D9": d9_classified_str,
            })

        current += timedelta(days=1)

    df = pd.DataFrame(rows)

    st.markdown("### 📊 Daily AOT View (with Moon–Mercury Aspects)")
    html = df.to_html()
    st.markdown(f'<div class="scroll-table">{html}</div>', unsafe_allow_html=True)
