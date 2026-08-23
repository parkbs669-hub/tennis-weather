# 테니스 코트 위치·요일·시간대를 입력받아 Open-Meteo 날씨를 조회하는 Streamlit 앱
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="Tennis Time Weather",
    page_icon="🎾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    '''
<style>
.main { padding-top: 1rem; }
.score-box {
    padding: 1.5rem; border-radius: 14px; text-align: center;
    margin-bottom: 1.5rem; background-color: #f0faf0; border: 2px solid #4CAF50;
    color: #1a1a1a;
}
.score-box h1, .score-box h3, .score-box p { color: #1a1a1a !important; }
.tip-box {
    padding: 1.2rem; border-radius: 12px; background-color: #fff8f0;
    border-left: 5px solid #FF9800;
    font-size: 1.1rem; line-height: 1.5; color: #1a1a1a;
}
.ncst-box {
    background: #e3f2fd; border-radius: 12px; padding: 0.9rem 1.4rem;
    margin-bottom: 1.2rem; border-left: 5px solid #2196F3;
    font-size: 1rem; color: #1a1a1a;
}
.coupang-box {
    padding: 1rem; border-radius: 10px; background-color: #ffffff;
    border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    height: 100%;
}
@media screen and (max-width: 768px) {
    header[data-testid="stHeader"]::after,
    .stApp > header::after {
        content: "위치, 날짜, 시간대변경";
        position: fixed !important;
        top: 18px !important;
        left: 55px !important;
        color: #FF4B4B !important;
        font-size: 1.05rem !important;
        font-weight: 900 !important;
        z-index: 999999 !important;
        pointer-events: none !important;
        white-space: nowrap !important;
        background: rgba(255, 255, 255, 0.7);
        padding: 0 5px;
        border-radius: 5px;
    }
}
[data-testid="collapsedControl"]::after {
    content: "  ← 위치·날짜·시간대 변경";
    font-size: 0.85rem;
    color: #1976D2 !important;
    font-weight: 600;
    white-space: nowrap;
}
</style>
''',
    unsafe_allow_html=True,
)

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


DAY_MAP = {
    "월요일": 0,
    "화요일": 1,
    "수요일": 2,
    "목요일": 3,
    "금요일": 4,
    "토요일": 5,
    "일요일": 6,
}

TIME_SLOT_MAP = {
    "새벽 (06:00~09:00)": {"rep": 7, "start": 5, "end": 10},
    "낮 (12:00~15:00)": {"rep": 13, "start": 11, "end": 16},
    "저녁 (19:00~22:00)": {"rep": 20, "start": 18, "end": 23},
}


def get_today_time_slot_index() -> int:
    hour = now_kst().hour
    if hour < 12:
        return 0
    if hour < 19:
        return 1
    return 2


def _wmo_sky(code: int) -> str:
    if code <= 1:
        return "☀️ 맑음"
    if code == 2:
        return "⛅ 구름많음"
    return "☁️ 흐림"


def _wmo_pty(code: int) -> str:
    if code in {51, 53, 55, 61, 63, 65, 80, 81, 82}:
        return "🌧 비"
    if code in {71, 73, 75, 85, 86}:
        return "❄️ 눈"
    if code in {56, 57, 66, 67}:
        return "🌨 비/눈"
    if code in {95, 96, 99}:
        return "⛈️ 뇌우"
    return "-"


HEAVY_WMO = {63, 65, 81, 82, 95, 96, 99, 73, 75, 85, 86}
LIGHT_WMO = {51, 53, 55, 61, 71, 80}


with st.sidebar:
    st.title("🎾 Tennis Time Weather")
    st.markdown("### ⚙️ 위치 · 날짜 · 시간대 변경")
    st.divider()

    location = st.text_input("📍 테니스장 위치", value="대구 북구 산격동")
    day = st.selectbox(
        "📅 운동 요일",
        list(DAY_MAP.keys()),
        index=now_kst().weekday(),
    )
    time_slot = st.selectbox(
        "⏰ 시간대",
        list(TIME_SLOT_MAP.keys()),
        index=get_today_time_slot_index(),
    )

    st.divider()
    st.caption("v0.9.1 — Open-Meteo 기반")


# =========================================================
# 위치 변환
# Open-Meteo Geocoding을 우선 사용하고, 실패할 때만 Nominatim을 사용한다.
# =========================================================
def _location_candidates(location: str) -> list[str]:
    """상세 주소가 검색되지 않을 때 상위 지역으로 단계적으로 축약한다."""
    clean = " ".join(location.strip().split())
    if not clean:
        return []

    parts = clean.split()
    candidates = [clean]
    for i in range(len(parts) - 1, 0, -1):
        candidate = " ".join(parts[:i])
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


@st.cache_data(ttl=86400, show_spinner=False)
def geocode(location: str):
    candidates = _location_candidates(location)

    # 1) Open-Meteo 공식 Geocoding API
    # 날씨 API와 같은 서비스 계열을 사용해 Streamlit Cloud 등에서
    # Nominatim 접속 제한이 발생해도 위치 검색이 가능하게 한다.
    open_meteo_url = "https://geocoding-api.open-meteo.com/v1/search"
    for query in candidates:
        try:
            resp = requests.get(
                open_meteo_url,
                params={
                    "name": query,
                    "count": 10,
                    "language": "ko",
                    "format": "json",
                    "countryCode": "KR",
                },
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results") or []
            if results:
                r = results[0]
                place_name = r.get("name") or query
                admin1 = r.get("admin1")
                if admin1 and admin1 not in place_name:
                    place_name = f"{admin1} {place_name}"
                return float(r["latitude"]), float(r["longitude"]), place_name
        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue

    # 2) 보조 fallback: OpenStreetMap Nominatim
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "TennisTimeWeatherApp/0.9.1 (weather app)"}
    for query in candidates:
        try:
            resp = requests.get(
                nominatim_url,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                    "countrycodes": "kr",
                },
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                r = results[0]
                return (
                    float(r["lat"]),
                    float(r["lon"]),
                    r.get("display_name", query).split(",")[0],
                )
        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue

    return None, None, None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_open_meteo(lat: float, lon: float) -> dict | None:
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": (
                    "temperature_2m,apparent_temperature,precipitation_probability,"
                    "precipitation,windspeed_10m,relativehumidity_2m,weathercode"
                ),
                "current": (
                    "temperature_2m,apparent_temperature,precipitation,"
                    "windspeed_10m,winddirection_10m,relativehumidity_2m,weathercode"
                ),
                "timezone": "Asia/Seoul",
                "forecast_days": 7,
                "windspeed_unit": "ms",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if "hourly" not in data:
            return None
        return data
    except (requests.RequestException, ValueError):
        return None


def extract_hour(data: dict, target_date: str, hour: int) -> dict | None:
    times = data["hourly"]["time"]
    target_ts = f"{target_date}T{hour:02d}:00"
    if target_ts not in times:
        return None
    i = times.index(target_ts)
    h = data["hourly"]
    wmo = int(h["weathercode"][i] or 0)
    return {
        "hour": hour,
        "temp": round(float(h["temperature_2m"][i] or 0), 1),
        "feels_like": round(float(h["apparent_temperature"][i] or 0), 1),
        "humidity": int(h["relativehumidity_2m"][i] or 0),
        "rain_prob": int(h["precipitation_probability"][i] or 0),
        "precip": round(float(h["precipitation"][i] or 0), 1),
        "wind_speed": round(float(h["windspeed_10m"][i] or 0), 1),
        "sky": _wmo_sky(wmo),
        "pty": _wmo_pty(wmo),
        "wmo": wmo,
    }


def get_target_date(day_name: str) -> str:
    today = now_kst()
    days_ahead = (DAY_MAP[day_name] - today.weekday()) % 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


lat, lon, place_name = geocode(location)
if lat is None:
    st.error(
        f"'{location}' 위치를 찾을 수 없습니다. "
        "예: '대구', '대구 북구', '동탄'처럼 시·구·동 이름으로 다시 입력해 주세요."
    )
    st.stop()

target_date = get_target_date(day)
slot = TIME_SLOT_MAP[time_slot]
now = now_kst()

target_dt = datetime.strptime(
    f"{target_date} {slot['rep']:02d}:00", "%Y-%m-%d %H:%M"
)
hours_diff = (target_dt - now).total_seconds() / 3600

if (datetime.strptime(target_date, "%Y-%m-%d") - now).days > 6:
    st.warning("예보는 최대 7일 후까지 제공됩니다.")
    st.stop()

forecast = fetch_open_meteo(lat, lon)
if forecast is None:
    st.error("날씨 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

weather = extract_hour(forecast, target_date, slot["rep"])
if weather is None:
    if target_date == now.strftime("%Y-%m-%d") and hours_diff < 0:
        st.warning("⏰ 운동 시간과 장소를 설정하세요. 위 상단 >> 를 클릭하세요.")
    else:
        st.error(f"{target_date} {slot['rep']:02d}:00 예보 데이터가 없습니다.")
    st.stop()

hourly_range = [
    w
    for h in range(slot["start"], slot["end"] + 1)
    if (w := extract_hour(forecast, target_date, h)) is not None
]


def calculate_play_score(w: dict) -> int:
    score = 100
    wmo = w.get("wmo", 0)
    if wmo in HEAVY_WMO:
        score -= 60
    elif wmo in LIGHT_WMO:
        score -= 20
    elif w["rain_prob"] >= 70:
        score -= 40
    elif w["rain_prob"] >= 40:
        score -= 20

    if w["wind_speed"] >= 8:
        score -= 25
    elif w["wind_speed"] >= 5:
        score -= 12

    if w["humidity"] >= 85:
        score -= 10
    if "흐림" in w["sky"]:
        score -= 5
    return max(score, 0)


if hourly_range:
    play_score = int(
        sum(calculate_play_score(w) for w in hourly_range) / len(hourly_range)
    )
else:
    play_score = calculate_play_score(weather)

if play_score >= 85:
    play_status, status_message = "🎾 최적", "경기하기 완벽한 날씨입니다!"
elif play_score >= 65:
    play_status, status_message = "👍 양호", "무난하게 플레이 가능합니다."
elif play_score >= 45:
    play_status, status_message = "⚠️ 주의", "기상 상황을 확인하세요."
else:
    play_status, status_message = "🌧 비추천", "실내 코트 예약을 권장합니다."


EMOJI_MAP = {
    "반바지": "🩳",
    "긴바지": "👖",
    "반팔": "👕",
    "긴팔": "🧥",
    "민소매": "🎽",
    "바람막이": "🧥",
    "웜업 자켓": "🧥",
    "방풍 자켓": "🧥",
    "방수 자켓": "🧥",
    "겉옷": "🧥",
    "패딩": "🧥",
    "기모": "🧶",
    "우비": "🌂",
    "장갑": "🧤",
    "모자": "🧢",
    "선글라스": "🕶️",
    "선크림": "🧴",
    "타월": "🧻",
    "핫팩": "🔥",
    "이온음료": "🥤",
    "물병": "☕",
    "보온 물병": "☕",
    "쿨링 스프레이": "💨",
    "얼음 타월": "🧊",
    "여벌 옷": "👕",
    "여벌 상의": "👕",
}


def auto_emoji(text: str) -> str:
    for keyword in sorted(EMOJI_MAP, key=len, reverse=True):
        emoji = EMOJI_MAP[keyword]
        if f"{emoji} {keyword}" in text or f"{emoji}{keyword}" in text:
            continue
        text = text.replace(keyword, f"{emoji} {keyword}")
    return text


def get_dress_code(w: dict) -> str:
    temp = w["feels_like"]
    wind = w["wind_speed"]
    humidity = w.get("humidity", 0)
    rain_prob = w.get("rain_prob", 0)
    lines = []

    if temp >= 33:
        lines.append("<b>반바지 + 민소매/반팔 (쿨링 소재)</b>")
        lines.append("🥵 폭염 수준! 선크림 · 선글라스 · 모자 필수!")
        lines.append("얼음 타월 · 쿨링 스프레이 준비, 🚰 체인지오버마다 수분 보충하세요.")
    elif temp >= 28:
        lines.append("<b>반바지 + 반팔 (통풍 소재)</b>")
        lines.append("🌡️ 더운 날씨! 속건성 소재 추천, 선크림 꼭 바르세요.")
        lines.append("이온음료를 넉넉히 챙기세요.")
    elif temp >= 22:
        lines.append("<b>반바지 + 반팔</b>")
        lines.append("🌤️ 쾌적한 날씨! 운동 후 땀이 식을 수 있으니 가벼운 겉옷을 챙기세요.")
    elif temp >= 15:
        if wind >= 4:
            lines.append("<b>긴바지(또는 반바지) + 얇은 바람막이 필수</b>")
            lines.append("🌬️ 바람이 불어 체감 온도 ⬇️ 웜업 시 겉옷 입고 시작하세요.")
        else:
            lines.append("<b>긴바지 + 긴팔 (또는 반팔 + 웜업 자켓)</b>")
            lines.append("🌿 가벼운 겉옷으로 시작하기 좋은 날씨입니다.")
    elif temp >= 10:
        lines.append("<b>긴바지 + 긴팔 + 웜업 자켓</b>")
        lines.append("🥶 쌀쌀합니다! 🤸 충분한 스트레칭 후 겉옷을 벗으세요.")
        if wind >= 4:
            lines.append("💨 바람까지 불어 체감 온도 ⬇️⬇️ 방풍 자켓을 추천합니다.")
    else:
        lines.append("<b>긴바지 + 기모/패딩 겉옷 + 장갑</b>")
        lines.append("⛄ 매우 춥습니다! 🧣 몸이 완전히 풀리기 전까지 겉옷을 벗지 마세요.")
        lines.append("핫팩 · 보온 물병을 챙기면 좋습니다.")

    if rain_prob >= 70:
        lines.append("<br>🌧️⚠️ <b>비 올 확률이 높습니다!</b> 방수 자켓 · 여벌 옷 · 타월을 꼭 챙기세요.")
    elif rain_prob >= 40:
        lines.append("<br>🌂☁️ 비 가능성이 있습니다. 가벼운 우비나 바람막이를 준비하세요.")

    if humidity >= 80 and temp >= 22:
        lines.append("💦😓 습도가 높아 땀이 잘 안 마릅니다. 속건·흡습 소재 필수, 여벌 상의를 추천합니다.")

    return auto_emoji("<br>".join(lines))


def get_coupang_recommendations(w: dict) -> list:
    recs = []
    temp = w["feels_like"]
    wind = w["wind_speed"]
    rain_prob = w["rain_prob"]

    if rain_prob >= 40:
        recs.append({"name": "실내 테니스화", "link": "https://link.coupang.com/a/example_indoor_shoes", "desc": "비가 올 확률이 높습니다. 실내 코트를 대비하세요!", "emoji": "👟"})
        recs.append({"name": "스포츠 타월", "link": "https://link.coupang.com/a/example_towel", "desc": "땀과 비를 닦을 수 있는 스포츠 타월", "emoji": "🧻"})
    elif temp >= 28:
        recs.append({"name": "쿨링 넥워머 / 암슬리브", "link": "https://link.coupang.com/a/example_cool", "desc": "더운 날씨에 자외선 차단과 쿨링을 동시에!", "emoji": "🧊"})
        recs.append({"name": "이온음료 박스", "link": "https://link.coupang.com/a/example_drink", "desc": "땀을 많이 흘리는 날엔 수분 보충이 필수입니다.", "emoji": "🥤"})
    elif temp <= 10:
        recs.append({"name": "테니스 방한 장갑", "link": "https://link.coupang.com/a/example_gloves", "desc": "추운 날씨에 손의 감각을 유지하세요.", "emoji": "🧤"})
        recs.append({"name": "경량 패딩 조끼", "link": "https://link.coupang.com/a/example_vest", "desc": "활동성을 유지하면서 체온을 보호해줍니다.", "emoji": "🦺"})
    elif wind >= 5:
        recs.append({"name": "가벼운 바람막이", "link": "https://link.coupang.com/a/example_windbreaker", "desc": "바람이 부는 날씨엔 체온 유지가 중요합니다.", "emoji": "🧥"})
        recs.append({"name": "테니스 모자", "link": "https://link.coupang.com/a/example_cap", "desc": "바람에 머리카락이 날리지 않게 고정해줍니다.", "emoji": "🧢"})
    else:
        recs.append({"name": "테니스 공 (새 캔)", "link": "https://link.coupang.com/a/example_balls", "desc": "운동하기 딱 좋은 날씨! 새 공으로 기분 좋게 플레이하세요.", "emoji": "🎾"})
        recs.append({"name": "테니스 오버그립", "link": "https://link.coupang.com/a/example_grip", "desc": "쾌적한 플레이를 위한 쫀쫀한 새 그립", "emoji": "🏸"})
    return recs


st.title("🎾 테니스 타임 날씨 알리미")
st.caption(
    f"최종 업데이트: {now.strftime('%Y-%m-%d %H:%M')} KST  |  예보 데이터: Open-Meteo"
)

cur = forecast.get("current", {})
n_tmp = float(cur.get("temperature_2m", 0) or 0)
n_feel = float(cur.get("apparent_temperature", 0) or 0)
n_wsd = float(cur.get("windspeed_10m", 0) or 0)
n_wdir = int(float(cur.get("winddirection_10m", 0) or 0))
n_reh = int(float(cur.get("relativehumidity_2m", 0) or 0))
n_rn1 = float(cur.get("precipitation", 0) or 0)
n_wmo = int(cur.get("weathercode", 0) or 0)
n_pty = _wmo_pty(n_wmo)
dirs = ["북", "북동", "동", "남동", "남", "남서", "서", "북서", "북"]
n_dir = dirs[round(n_wdir / 45) % 8]
rain_badge = (
    f"🌧 {n_rn1}mm/h &nbsp;|&nbsp; {n_pty}" if n_pty != "-" else "☀️ 강수없음"
)

st.markdown(
    f'<div class="ncst-box">'
    f'<b>📡 현재 실황</b> ({now.strftime("%m월 %d일 %H:%M")} KST 기준)'
    f'&nbsp;&nbsp;|&nbsp;&nbsp;'
    f'🌡️ <b>{n_tmp}°C</b> (체감 {round(n_feel, 1)}°C)'
    f'&nbsp;|&nbsp; 💨 {n_wsd}m/s ({n_dir})'
    f'&nbsp;|&nbsp; 💧 습도 {n_reh}%'
    f'&nbsp;|&nbsp; {rain_badge}'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("---")
col_main, col_sub = st.columns([2, 1])
with col_main:
    st.subheader(f"📍 {place_name} ({day} {time_slot})")
    st.caption(f"기준 날짜: {target_date} {slot['rep']:02d}:00")
    st.markdown(
        f'<div class="score-box"><h1>{play_score}점</h1><h3>{play_status}</h3><p>{status_message}</p></div>',
        unsafe_allow_html=True,
    )
with col_sub:
    st.subheader("👕 드레스 코드")
    st.markdown(
        f'<div class="tip-box">{get_dress_code(weather)}</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")
st.subheader("🛒 날씨 맞춤 추천 테니스 용품 (쿠팡 파트너스)")
recs = get_coupang_recommendations(weather)
cols = st.columns(len(recs))
for i, rec in enumerate(recs):
    with cols[i]:
        st.markdown(
            f"""
        <div class="coupang-box">
            <h4>{rec['emoji']} <a href="{rec['link']}" target="_blank" style="text-decoration:none; color:#1a1a1a;">{rec['name']}</a></h4>
            <p style="font-size:0.9rem; color:#555;">{rec['desc']}</p>
            <a href="{rec['link']}" target="_blank" style="display:inline-block; padding:8px 12px; background-color:#118eff; color:white; border-radius:4px; text-decoration:none; font-weight:bold; font-size:0.85rem;">쿠팡에서 보기 👉</a>
        </div>
        """,
            unsafe_allow_html=True,
        )

st.caption(
    "※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다. (예시 링크로 동작 중입니다)"
)

st.markdown("---")
st.subheader(
    f"🌤 시간별 날씨 지표  ({slot['start']:02d}:00 ~ {slot['end']:02d}:00)"
)

if not hourly_range:
    st.warning("해당 시간대 예보 데이터가 없습니다.")
else:
    th = "padding:6px 10px; text-align:center; font-size:0.82rem; border-bottom:2px solid #ccc;"
    td = "padding:5px 10px; text-align:center; font-size:0.82rem;"

    header_cells = ""
    for w in hourly_range:
        is_core = slot["start"] + 1 <= w["hour"] <= slot["end"] - 1
        bg = "background:#e8f5e9;" if is_core else ""
        header_cells += f'<th style="{th}{bg}">{"🟢 " if is_core else ""}{w["hour"]:02d}:00</th>'

    def tr(label, values):
        return (
            f'<tr><td style="{td} font-weight:600; text-align:left;">{label}</td>'
            + "".join(f'<td style="{td}">{v}</td>' for v in values)
            + "</tr>"
        )

    st.markdown(
        f'''
    <table style="width:100%; border-collapse:collapse; font-family:sans-serif;">
      <thead><tr><th style="{th} text-align:left;">항목</th>{header_cells}</tr></thead>
      <tbody>
        {tr("하늘상태", [w["sky"] for w in hourly_range])}
        {tr("강수형태", [w["pty"] for w in hourly_range])}
        {tr("강수확률/강수량", [f'{w["rain_prob"]}% / {w["precip"]}mm' for w in hourly_range])}
        {tr("기온 / 체감", [f'{w["temp"]}°C / {w["feels_like"]}°C' for w in hourly_range])}
        {tr("풍속", [f'{w["wind_speed"]}m/s' for w in hourly_range])}
        {tr("습도", [f'{w["humidity"]}%' for w in hourly_range])}
      </tbody>
    </table>
    ''',
        unsafe_allow_html=True,
    )

st.markdown("---")
st.caption("Tennis Time Weather v0.9.1 — Open-Meteo 기반")
