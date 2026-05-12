# 테니스 코트 위치·요일·시간대를 입력받아 실제 날씨를 조회하는 Streamlit 앱
import streamlit as st
import requests
from datetime import datetime, timedelta

# =========================================================
# 기본 설정 및 스타일
# =========================================================
st.set_page_config(page_title="Tennis Time Weather", page_icon="🎾", layout="wide")

st.markdown("""
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
</style>
""", unsafe_allow_html=True)

# =========================================================
# 상수
# =========================================================
DAY_MAP = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6}

# rep: 점수 계산 기준 시간, start/end: 표시 범위 (앞뒤 1시간 포함)
TIME_SLOT_MAP = {
    "새벽 (06:00~09:00)": {"rep": 7,  "start": 5,  "end": 10},
    "낮 (12:00~15:00)":   {"rep": 13, "start": 11, "end": 16},
    "저녁 (19:00~22:00)": {"rep": 20, "start": 18, "end": 23},
}

# =========================================================
# 사이드바
# =========================================================
with st.sidebar:
    st.title("🎾 Tennis Time")
    location = st.text_input("📍 테니스장 위치", value="대구 북구 칠성동")
    day = st.selectbox("📅 운동 요일", list(DAY_MAP.keys()), index=1)
    time_slot = st.selectbox("⏰ 시간대", list(TIME_SLOT_MAP.keys()), index=2)
    st.markdown("---")
    st.caption("(v)버전 0.4.0 — Open-Meteo 실시간 연동")

# =========================================================
# 날씨 API (Open-Meteo, 무료·키 불필요)
# =========================================================
@st.cache_data(ttl=1800)
def geocode(location: str):
    """위치명 → (위도, 경도, 확인된 지명). Nominatim으로 한국 주소 정확도 확보."""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "TennisTimeWeatherApp/1.0"}
    parts = location.split()
    candidates = [location] + [" ".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]
    for query in candidates:
        if not query.strip():
            continue
        try:
            resp = requests.get(
                url,
                params={"q": query, "format": "json", "limit": 1, "countrycodes": "kr"},
                headers=headers,
                timeout=10,
            )
            results = resp.json()
            if results:
                r = results[0]
                display = r.get("display_name", query).split(",")[0]
                return float(r["lat"]), float(r["lon"]), display
        except Exception:
            continue
    return None, None, None


@st.cache_data(ttl=1800)
def fetch_hourly_data(lat: float, lon: float, target_date: str) -> dict | None:
    """Open-Meteo에서 해당 날짜의 시간별 전체 데이터 반환"""
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,apparent_temperature,relativehumidity_2m,precipitation_probability,precipitation,windspeed_10m,uv_index",
            "timezone": "Asia/Seoul",
            "forecast_days": 8,
        }
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()["hourly"]
    except Exception:
        return None


def extract_hour(hourly: dict, target_date: str, hour: int) -> dict | None:
    times = hourly["time"]
    target = f"{target_date}T{hour:02d}:00"
    if target not in times:
        return None
    idx = times.index(target)
    return {
        "hour":       hour,
        "temp":       round(hourly["temperature_2m"][idx], 1),
        "feels_like": round(hourly["apparent_temperature"][idx], 1),
        "humidity":   hourly["relativehumidity_2m"][idx],
        "rain_prob":  hourly["precipitation_probability"][idx],
        "precip":     round(hourly["precipitation"][idx], 1),
        "wind_speed": round(hourly["windspeed_10m"][idx], 1),
        "uv":         round(hourly["uv_index"][idx], 1),
    }


def get_target_date(day_name: str) -> str:
    today = datetime.now()
    days_ahead = (DAY_MAP[day_name] - today.weekday()) % 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


# =========================================================
# 데이터 조회
# =========================================================
lat, lon, place_name = geocode(location)

if lat is None:
    st.error(f"'{location}' 위치를 찾을 수 없습니다. 다른 지명으로 입력해 보세요.")
    st.stop()

target_date = get_target_date(day)
slot = TIME_SLOT_MAP[time_slot]

hourly_data = fetch_hourly_data(lat, lon, target_date)
if hourly_data is None:
    st.error("날씨 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

weather = extract_hour(hourly_data, target_date, slot["rep"])
if weather is None:
    st.error("날씨 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.stop()

hourly_range = [
    w for h in range(slot["start"], slot["end"] + 1)
    if (w := extract_hour(hourly_data, target_date, h)) is not None
]

# =========================================================
# 운동 점수 계산
# =========================================================
def calculate_play_score(w: dict) -> int:
    score = 100
    if w["rain_prob"] >= 70:   score -= 60
    elif w["rain_prob"] >= 40: score -= 35
    if w["wind_speed"] >= 8:   score -= 30
    elif w["wind_speed"] >= 5: score -= 15
    if w["humidity"] >= 85:    score -= 15
    if w["uv"] >= 8:           score -= 10
    return max(score, 0)

play_score = calculate_play_score(weather)

if play_score >= 85:   play_status, status_message = "🎾 최적", "경기하기 완벽한 날씨입니다!"
elif play_score >= 65: play_status, status_message = "👍 양호", "무난하게 플레이 가능합니다."
elif play_score >= 45: play_status, status_message = "⚠️ 주의", "기상 상황을 확인하세요."
else:                  play_status, status_message = "🌧 비추천", "실내 코트 예약을 권장합니다."

# =========================================================
# 드레스 코드 추천
# =========================================================
def get_dress_code(w: dict) -> str:
    temp = w["feels_like"]
    wind = w["wind_speed"]
    if temp >= 28:
        return "🩳 <b>반바지 + 반팔</b><br>통풍이 잘 되는 쿨링 소재를 적극 추천합니다."
    elif temp >= 22:
        return "👕 <b>반바지 + 반팔</b><br>운동 후 땀이 식을 때를 위해 가벼운 겉옷을 챙기세요."
    elif temp >= 15:
        if wind >= 4:
            return "🧥 <b>긴바지/반바지 + 얇은 바람막이 필수</b><br>바람이 불어 체감 온도가 떨어집니다."
        else:
            return "👖 <b>긴바지 + 긴팔 (또는 반팔+웜업 자켓)</b><br>가벼운 웜업용 겉옷으로 시작하기 좋은 날씨입니다."
    else:
        return "🥶 <b>긴바지 + 따뜻한 겉옷</b><br>충분히 몸이 풀리기 전까지 겉옷을 벗지 마세요."

dress_code = get_dress_code(weather)

# =========================================================
# 메인 화면
# =========================================================
st.title("🎾 테니스 타임 날씨 알리미")
st.caption(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  데이터: Open-Meteo")
st.markdown("---")

col_main, col_sub = st.columns([2, 1])

with col_main:
    st.subheader(f"📍 {place_name} ({day} {time_slot})")
    st.caption(f"기준 날짜: {target_date} {slot['rep']:02d}:00  |  좌표: {lat:.4f}, {lon:.4f}")
    st.markdown(
        f'<div class="score-box"><h1>{play_score}점</h1><h3>{play_status}</h3><p>{status_message}</p></div>',
        unsafe_allow_html=True
    )

with col_sub:
    st.subheader("👕 드레스 코드")
    st.markdown(f'<div class="tip-box">{dress_code}</div>', unsafe_allow_html=True)

# =========================================================
# 시간별 날씨 지표
# =========================================================
st.markdown("---")
st.subheader(f"🌤 시간별 날씨 지표  ({slot['start']:02d}:00 ~ {slot['end']:02d}:00)")

th_base = "padding:6px 10px; text-align:center; font-size:0.82rem; border-bottom:2px solid #ccc;"
td_base = "padding:5px 10px; text-align:center; font-size:0.82rem;"

header_cells = ""
for w in hourly_range:
    is_core = slot["start"] + 1 <= w["hour"] <= slot["end"] - 1
    bg = "background:#e8f5e9;" if is_core else ""
    header_cells += f'<th style="{th_base}{bg}">{"🟢 " if is_core else ""}{w["hour"]:02d}:00</th>'

def tr(label, values, unit=""):
    cells = "".join(f'<td style="{td_base}">{v}{unit}</td>' for v in values)
    return f'<tr><td style="{td_base} font-weight:600; text-align:left;">{label}</td>{cells}</tr>'

table_html = f"""
<table style="width:100%; border-collapse:collapse; font-family:sans-serif;">
  <thead><tr><th style="{th_base} text-align:left;">항목</th>{header_cells}</tr></thead>
  <tbody>
    {tr("강수확률 / 강수량", [f'{w["rain_prob"]}% / {w["precip"]}mm' for w in hourly_range])}
    {tr("체감온도", [w["feels_like"] for w in hourly_range], "°C")}
    {tr("풍속",    [w["wind_speed"] for w in hourly_range], "m/s")}
    {tr("자외선",  [w["uv"] for w in hourly_range])}
    {tr("습도",    [w["humidity"] for w in hourly_range], "%")}
  </tbody>
</table>
"""
st.markdown(table_html, unsafe_allow_html=True)

st.markdown("---")
st.caption("Tennis Time Weather v0.4.0 — Open-Meteo 실시간 연동")
