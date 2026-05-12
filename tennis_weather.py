# 테니스 코트 위치·요일·시간대를 입력받아 기상청 실제 날씨를 조회하는 Streamlit 앱
import math
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

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
.ncst-box {
    background: #e3f2fd; border-radius: 12px; padding: 0.9rem 1.4rem;
    margin-bottom: 1.2rem; border-left: 5px solid #2196F3;
    font-size: 1rem; color: #1a1a1a;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# KST 시간 (Streamlit Cloud는 UTC → +9시간 보정 필수)
# =========================================================
KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)

# =========================================================
# 상수
# =========================================================
KMA_SERVICE_KEY = "Hn3PmYG7QWq9z5mBu7FqIg"
KMA_FCST_URL  = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst"
KMA_ULTRA_URL = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst"
KMA_NCST_URL  = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"

DAY_MAP = {"월요일":0,"화요일":1,"수요일":2,"목요일":3,"금요일":4,"토요일":5,"일요일":6}
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
    location  = st.text_input("📍 테니스장 위치", value="대구 북구 산격동")
    day       = st.selectbox("📅 운동 요일", list(DAY_MAP.keys()), index=1)
    time_slot = st.selectbox("⏰ 시간대", list(TIME_SLOT_MAP.keys()), index=2)
    st.markdown("---")
    st.caption("v0.8.0 — KST 시간 보정 + 초단기실황 안정화")

# =========================================================
# 위치 변환
# =========================================================
@st.cache_data(ttl=86400)
def geocode(location: str):
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "TennisTimeWeatherApp/1.0"}
    parts = location.split()
    candidates = [location] + [" ".join(parts[:i]) for i in range(len(parts)-1, 0, -1)]
    for query in candidates:
        if not query.strip():
            continue
        try:
            resp = requests.get(url, params={"q": query, "format": "json", "limit": 1, "countrycodes": "kr"},
                                headers=headers, timeout=10)
            results = resp.json()
            if results:
                r = results[0]
                return float(r["lat"]), float(r["lon"]), r.get("display_name", query).split(",")[0]
        except Exception:
            continue
    return None, None, None

def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT = 30.0, 60.0, 126.0, 38.0
    XO, YO = 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    sn = math.log(math.cos(SLAT1*D) / math.cos(SLAT2*D)) / \
         math.log(math.tan(math.pi*0.25 + SLAT2*D*0.5) / math.tan(math.pi*0.25 + SLAT1*D*0.5))
    sf = (math.tan(math.pi*0.25 + SLAT1*D*0.5) ** sn) * math.cos(SLAT1*D) / sn
    ro = re * sf / (math.tan(math.pi*0.25 + OLAT*D*0.5) ** sn)
    ra = re * sf / (math.tan(math.pi*0.25 + lat*D*0.5) ** sn)
    theta = (lon - OLON) * D * sn
    if theta > math.pi:  theta -= 2 * math.pi
    if theta < -math.pi: theta += 2 * math.pi
    return int(ra*math.sin(theta) + XO + 1.5), int(ro - ra*math.cos(theta) + YO + 1.5)

# =========================================================
# 기준시각 계산 (모두 KST 기준)
# =========================================================
def get_base_datetime() -> tuple[str, str]:
    """단기예보: 매 3시간 발표, 10분 여유, KST 기준"""
    t = now_kst() - timedelta(minutes=10)
    valid = [h for h in [2, 5, 8, 11, 14, 17, 20, 23] if h <= t.hour]
    if valid:
        return t.strftime("%Y%m%d"), f"{max(valid):02d}00"
    return (t - timedelta(days=1)).strftime("%Y%m%d"), "2300"

def get_ultra_base_datetime() -> tuple[str, str]:
    """초단기예보: 매시 30분 발표, 10분 여유, KST 기준"""
    t = now_kst() - timedelta(minutes=10)
    if t.minute >= 30:
        return t.strftime("%Y%m%d"), f"{t.hour:02d}30"
    h = t.hour - 1
    d = t if h >= 0 else t - timedelta(days=1)
    return d.strftime("%Y%m%d"), f"{h % 24:02d}30"

def get_ncst_base_datetime() -> tuple[str, str]:
    """초단기실황: 매시 정각 발표, 10분 여유, KST 기준"""
    t = now_kst() - timedelta(minutes=5)
    return t.strftime("%Y%m%d"), f"{t.hour:02d}00"

def get_prev_ncst_base_datetime() -> tuple[str, str]:
    """초단기실황 실패 시 한 시간 전 시각으로 재시도"""
    t = now_kst() - timedelta(minutes=5) - timedelta(hours=1)
    return t.strftime("%Y%m%d"), f"{t.hour:02d}00"

# =========================================================
# API 호출
# =========================================================
@st.cache_data(ttl=1800)
def fetch_kma_forecast(nx, ny, base_date, base_time) -> dict | None:
    try:
        r = requests.get(KMA_FCST_URL, params={
            "authKey": KMA_SERVICE_KEY, "pageNo": 1, "numOfRows": 1000,
            "dataType": "JSON", "base_date": base_date, "base_time": base_time,
            "nx": nx, "ny": ny}, timeout=15)
        out = {}
        for item in r.json()["response"]["body"]["items"]["item"]:
            k = (item["fcstDate"], item["fcstTime"])
            out.setdefault(k, {})[item["category"]] = item["fcstValue"]
        return out
    except Exception:
        return None

@st.cache_data(ttl=1800)
def fetch_kma_ultra_forecast(nx, ny, base_date, base_time) -> dict | None:
    try:
        r = requests.get(KMA_ULTRA_URL, params={
            "authKey": KMA_SERVICE_KEY, "pageNo": 1, "numOfRows": 1000,
            "dataType": "JSON", "base_date": base_date, "base_time": base_time,
            "nx": nx, "ny": ny}, timeout=15)
        out = {}
        for item in r.json()["response"]["body"]["items"]["item"]:
            k = (item["fcstDate"], item["fcstTime"])
            out.setdefault(k, {})[item["category"]] = item["fcstValue"]
        return out
    except Exception:
        return None

@st.cache_data(ttl=600)
def fetch_kma_ncst(nx, ny, base_date, base_time) -> dict | None:
    """초단기실황: 실패 시 None 반환"""
    try:
        r = requests.get(KMA_NCST_URL, params={
            "authKey": KMA_SERVICE_KEY, "pageNo": 1, "numOfRows": 100,
            "dataType": "JSON", "base_date": base_date, "base_time": base_time,
            "nx": nx, "ny": ny}, timeout=15)
        body = r.json().get("response", {}).get("body", {})
        items = body.get("items", {})
        if not items or items == "":
            return None
        return {item["category"]: item["obsrValue"] for item in items["item"]}
    except Exception:
        return None

# =========================================================
# 데이터 파싱
# =========================================================
def _feels_like(tmp, wsd):
    if tmp <= 10 and wsd >= 1.3:
        return 13.12 + 0.6215*tmp - 11.37*(wsd**0.16) + 0.3965*tmp*(wsd**0.16)
    return tmp

def _parse_precip(raw):
    try:
        return float(raw.replace("mm","").replace("미만","").strip()) if raw != "강수없음" else 0.0
    except Exception:
        return 0.1 if raw != "강수없음" else 0.0

SKY_MAP = {"1":"☀️ 맑음","3":"⛅ 구름많음","4":"☁️ 흐림"}
PTY_MAP = {"0":"-","1":"🌧 비","2":"🌨 비/눈","3":"❄️ 눈","4":"🌦 소나기",
           "5":"🌧 빗방울","6":"🌨 빗방울/눈날림","7":"❄️ 눈날림"}

def extract_kma_hour(forecast, target_date, hour) -> dict | None:
    data = forecast.get((target_date.replace("-",""), f"{hour:02d}00"))
    if not data: return None
    try:
        tmp, wsd = float(data.get("TMP",0)), float(data.get("WSD",0))
        return {"hour": hour, "temp": round(tmp,1), "feels_like": round(_feels_like(tmp,wsd),1),
                "humidity": int(data.get("REH",0)), "rain_prob": int(data.get("POP",0)),
                "precip": _parse_precip(data.get("PCP","강수없음")), "wind_speed": round(wsd,1),
                "sky": SKY_MAP.get(data.get("SKY","1"),"-"),
                "pty": PTY_MAP.get(data.get("PTY","0"),"-")}
    except Exception:
        return None

def extract_ultra_hour(forecast, target_date, hour) -> dict | None:
    data = forecast.get((target_date.replace("-",""), f"{hour:02d}00"))
    if not data: return None
    try:
        tmp, wsd = float(data.get("T1H",0)), float(data.get("WSD",0))
        return {"hour": hour, "temp": round(tmp,1), "feels_like": round(_feels_like(tmp,wsd),1),
                "humidity": int(data.get("REH",0)), "rain_prob": None,
                "precip": _parse_precip(data.get("RN1","강수없음")), "wind_speed": round(wsd,1),
                "sky": SKY_MAP.get(data.get("SKY","1"),"-"),
                "pty": PTY_MAP.get(data.get("PTY","0"),"-")}
    except Exception:
        return None

def get_target_date(day_name: str) -> str:
    today = now_kst()
    return (today + timedelta(days=(DAY_MAP[day_name] - today.weekday()) % 7)).strftime("%Y-%m-%d")

# =========================================================
# 위치 조회
# =========================================================
lat, lon, place_name = geocode(location)
if lat is None:
    st.error(f"'{location}' 위치를 찾을 수 없습니다.")
    st.stop()

nx, ny      = latlon_to_grid(lat, lon)
target_date = get_target_date(day)
slot        = TIME_SLOT_MAP[time_slot]
now         = now_kst()

# =========================================================
# 예보 종류 자동 선택
# =========================================================
target_dt  = datetime.strptime(f"{target_date} {slot['rep']:02d}:00", "%Y-%m-%d %H:%M")
hours_diff = (target_dt - now).total_seconds() / 3600
use_ultra  = (target_date == now.strftime("%Y-%m-%d")) and (0 <= hours_diff <= 6)

if use_ultra:
    base_date, base_time = get_ultra_base_datetime()
    forecast       = fetch_kma_ultra_forecast(nx, ny, base_date, base_time)
    extract_fn     = extract_ultra_hour
    forecast_label = "초단기예보"
else:
    base_date, base_time = get_base_datetime()
    if (datetime.strptime(target_date, "%Y-%m-%d") - now).days > 3:
        st.warning("기상청 단기예보는 최대 3일 후까지만 제공됩니다.")
        st.stop()
    forecast       = fetch_kma_forecast(nx, ny, base_date, base_time)
    extract_fn     = extract_kma_hour
    forecast_label = "단기예보"

if forecast is None:
    st.error("기상청 날씨 데이터를 불러오지 못했습니다.")
    st.stop()

weather = extract_fn(forecast, target_date, slot["rep"])
if weather is None:
    st.error(f"{target_date} {slot['rep']:02d}:00 예보 데이터가 없습니다.")
    st.stop()

hourly_range = [w for h in range(slot["start"], slot["end"]+1)
                if (w := extract_fn(forecast, target_date, h)) is not None]

# =========================================================
# 운동 점수
# =========================================================
HEAVY_PTY = {"🌧 비", "🌨 비/눈", "❄️ 눈", "🌦 소나기"}
LIGHT_PTY  = {"🌧 빗방울", "🌨 빗방울/눈날림", "❄️ 눈날림"}

def calculate_play_score(w: dict) -> int:
    score = 100
    if w["pty"] in HEAVY_PTY:       score -= 60
    elif w["pty"] in LIGHT_PTY:     score -= 20
    elif w["rain_prob"] is not None:
        if w["rain_prob"] >= 70:    score -= 40
        elif w["rain_prob"] >= 40:  score -= 20
    if w["wind_speed"] >= 8:        score -= 25
    elif w["wind_speed"] >= 5:      score -= 12
    if w["humidity"] >= 85:         score -= 10
    if "흐림" in w["sky"]:           score -= 5
    return max(score, 0)

if hourly_range:
    play_score = int(sum(calculate_play_score(w) for w in hourly_range) / len(hourly_range))
else:
    play_score = calculate_play_score(weather)

if play_score >= 85:   play_status, status_message = "🎾 최적", "경기하기 완벽한 날씨입니다!"
elif play_score >= 65: play_status, status_message = "👍 양호", "무난하게 플레이 가능합니다."
elif play_score >= 45: play_status, status_message = "⚠️ 주의", "기상 상황을 확인하세요."
else:                  play_status, status_message = "🌧 비추천", "실내 코트 예약을 권장합니다."

# =========================================================
# 드레스 코드
# =========================================================
def get_dress_code(w: dict) -> str:
    temp, wind = w["feels_like"], w["wind_speed"]
    if temp >= 28:   return "🩳 <b>반바지 + 반팔</b><br>통풍이 잘 되는 쿨링 소재를 적극 추천합니다."
    elif temp >= 22: return "👕 <b>반바지 + 반팔</b><br>운동 후 땀이 식을 때를 위해 가벼운 겉옷을 챙기세요."
    elif temp >= 15:
        if wind >= 4: return "🧥 <b>긴바지/반바지 + 얇은 바람막이 필수</b><br>바람이 불어 체감 온도가 떨어집니다."
        return "👖 <b>긴바지 + 긴팔 (또는 반팔+웜업 자켓)</b><br>가벼운 웜업용 겉옷으로 시작하기 좋은 날씨입니다."
    return "🥶 <b>긴바지 + 따뜻한 겉옷</b><br>충분히 몸이 풀리기 전까지 겉옷을 벗지 마세요."

# =========================================================
# 화면 출력
# =========================================================
st.title("🎾 테니스 타임 날씨 알리미")
st.caption(
    f"최종 업데이트: {now.strftime('%Y-%m-%d %H:%M')} KST  |  "
    f"예보 데이터: 기상청 {forecast_label}  |  발표: {base_date} {base_time}"
)

# ── 초단기실황 (현재 → 실패 시 1시간 전으로 재시도) ────
ncst_date, ncst_time = get_ncst_base_datetime()
ncst = fetch_kma_ncst(nx, ny, ncst_date, ncst_time)
ncst_retry = False
if ncst is None:
    ncst_date, ncst_time = get_prev_ncst_base_datetime()
    ncst = fetch_kma_ncst(nx, ny, ncst_date, ncst_time)
    ncst_retry = True

if ncst:
    n_tmp  = float(ncst.get("T1H", 0))
    n_wsd  = float(ncst.get("WSD", 0))
    n_reh  = int(float(ncst.get("REH", 0)))
    n_vec  = int(float(ncst.get("VEC", 0)))
    n_rn1  = _parse_precip(ncst.get("RN1", "강수없음"))
    n_pty  = PTY_MAP.get(ncst.get("PTY","0"), "-")
    n_feel = round(_feels_like(n_tmp, n_wsd), 1)
    dirs   = ["북","북동","동","남동","남","남서","서","북서","북"]
    n_dir  = dirs[round(n_vec / 45) % 8]
    rain_badge = f"🌧 {n_rn1}mm/h &nbsp;|&nbsp; {n_pty}" if n_pty != "-" else "☀️ 강수없음"
    retry_note = " ⚠️ (1시간 전 데이터)" if ncst_retry else ""
    st.markdown(
        f'<div class="ncst-box">'
        f'<b>📡 현재 실황{retry_note}</b>'
        f' ({ncst_date[4:6]}월 {ncst_date[6:8]}일 {ncst_time[:2]}:00 KST 기준)'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'🌡️ <b>{n_tmp}°C</b> (체감 {n_feel}°C)'
        f'&nbsp;|&nbsp; 💨 {n_wsd}m/s ({n_dir})'
        f'&nbsp;|&nbsp; 💧 습도 {n_reh}%'
        f'&nbsp;|&nbsp; {rain_badge}'
        f'</div>',
        unsafe_allow_html=True
    )
else:
    st.warning("📡 현재 실황 데이터를 불러오지 못했습니다.")

st.markdown("---")

col_main, col_sub = st.columns([2, 1])
with col_main:
    st.subheader(f"📍 {place_name} ({day} {time_slot})")
    st.caption(f"기준 날짜: {target_date} {slot['rep']:02d}:00  |  격자: nx={nx}, ny={ny}")
    st.markdown(
        f'<div class="score-box"><h1>{play_score}점</h1><h3>{play_status}</h3><p>{status_message}</p></div>',
        unsafe_allow_html=True
    )
with col_sub:
    st.subheader("👕 드레스 코드")
    st.markdown(f'<div class="tip-box">{get_dress_code(weather)}</div>', unsafe_allow_html=True)

# ── 시간별 예보 테이블 ────────────────────────────────────
st.markdown("---")
st.subheader(f"🌤 시간별 날씨 지표  ({slot['start']:02d}:00 ~ {slot['end']:02d}:00)")

if use_ultra:
    st.info("⚡ 오늘 6시간 이내 시간대 — **초단기예보** 적용 중")

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
        return (f'<tr><td style="{td} font-weight:600; text-align:left;">{label}</td>'
                + "".join(f'<td style="{td}">{v}</td>' for v in values) + '</tr>')

    precip_row = (tr("강수량", [f'{w["precip"]}mm' for w in hourly_range]) if use_ultra
                  else tr("강수확률/강수량", [f'{w["rain_prob"]}% / {w["precip"]}mm' for w in hourly_range]))

    st.markdown(f"""
    <table style="width:100%; border-collapse:collapse; font-family:sans-serif;">
      <thead><tr><th style="{th} text-align:left;">항목</th>{header_cells}</tr></thead>
      <tbody>
        {tr("하늘상태",    [w["sky"] for w in hourly_range])}
        {tr("강수형태",    [w["pty"] for w in hourly_range])}
        {precip_row}
        {tr("기온 / 체감", [f'{w["temp"]}°C / {w["feels_like"]}°C' for w in hourly_range])}
        {tr("풍속",       [f'{w["wind_speed"]}m/s' for w in hourly_range])}
        {tr("습도",       [f'{w["humidity"]}%' for w in hourly_range])}
      </tbody>
    </table>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("Tennis Time Weather v0.8.0 — KST 시간 보정 + 초단기실황 안정화")
