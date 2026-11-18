"""14주차 과제 화면: Gemini 키 없이 내 FastAPI만 호출합니다."""
import base64
import io
from pathlib import Path

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

st.set_page_config(page_title="옷 사진 코디 도우미", page_icon="👕")
try:
    API_URL = str(st.secrets["API_URL"]).rstrip("/")
    ACCESS_CODE = str(st.secrets["APP_ACCESS_CODE"])
except (KeyError, FileNotFoundError):
    st.error("앱 설정의 Secrets에 API_URL과 APP_ACCESS_CODE를 설정하세요.")
    st.stop()

try:
    response = requests.get(f"{API_URL}/", timeout=30)
    response.raise_for_status()
    info = response.json()
    fields = info["fields"]
    if not isinstance(fields, list) or not all(isinstance(name, str) for name in fields):
        raise ValueError("결과 칸 형식 오류")
except (requests.RequestException, ValueError, KeyError, TypeError):
    st.error("API 서버에 연결할 수 없습니다. API_URL과 백엔드 배포 상태를 확인하세요.")
    st.stop()

st.title(f"{info.get('icon', '👕')} {info.get('name', '옷 사진 코디 도우미')}")
st.caption(info.get("description", ""))
st.info("옷 한 벌을 펼쳐 촬영하세요. 얼굴·신분증·카드 번호가 보이는 사진은 올리지 마세요.")


def analyze(raw):
    try:
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        if len(encoded) > 4_000_000:
            st.error("사진이 너무 큽니다. 작은 사진을 선택하세요.")
            return
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        st.error("사진을 읽을 수 없습니다. 정상적인 JPG 또는 PNG 파일을 선택하세요.")
        return
    try:
        response = requests.post(
            f"{API_URL}/analyze", json={"image_b64": encoded},
            headers={"X-Access-Code": ACCESS_CODE}, timeout=130,
        )
        try:
            data = response.json()
        except ValueError:
            st.error(f"서버 응답을 읽을 수 없습니다. 상태 번호: {response.status_code}")
            return
        if response.status_code != 200:
            st.error(f"상태 번호 {response.status_code}: {data.get('detail', '요청 실패')}")
            return
        result = data["result"]
        st.session_state["analysis_result"] = result
        st.session_state["analysis_tokens"] = data.get("tokens")
    except requests.RequestException:
        st.error("API 요청이 지연되거나 연결에 실패했습니다. 잠시 뒤 다시 시도하세요.")
    except (KeyError, TypeError, AttributeError):
        st.error("서버 응답의 결과 형식이 올바르지 않습니다.")


camera = st.camera_input("옷 사진 촬영") if st.toggle("카메라 켜기") else None
upload = st.file_uploader("또는 옷 사진 올리기", type=["jpg", "jpeg", "png", "webp"])
photo = camera if camera is not None else upload
if photo is not None:
    st.image(photo, width=300)
if st.button("옷 사진 분석하기", disabled=photo is None, type="primary"):
    st.session_state.pop("analysis_result", None)
    with st.spinner("사진을 정리하고 있습니다..."):
        analyze(photo.getvalue())

sample = Path(__file__).with_name("fashion_example.png")
if not sample.exists():
    # 직접 만든 도형 그림을 예시로 사용합니다. 개인정보는 포함하지 않습니다.
    example = Image.new("RGB", (800, 800), "#f5f2eb")
    draw = ImageDraw.Draw(example)
    draw.polygon([(245,160),(335,130),(465,130),(555,160),(675,290),
                  (575,385),(530,335),(530,670),(270,670),(270,335),
                  (225,385),(125,290)], fill="#3978bc", outline="#173a64", width=6)
    draw.arc((335,95,465,215), 0, 180, fill="#173a64", width=8)
    draw.line([(275,637),(525,637)], fill="#7ca7d5", width=4)
    example.save(sample)
if sample.exists():
    with st.expander("예시 사진 보기"):
        st.image(str(sample), width=300)
        st.caption("코드로 만든 파란색 반소매 티셔츠 그림입니다. 실제 의류 사진과 차이가 있습니다.")
    if st.button("예시 사진으로 해 보기", key="sample"):
        st.session_state.pop("analysis_result", None)
        with st.spinner("예시 사진을 분석하고 있습니다..."):
            analyze(sample.read_bytes())

if "analysis_result" in st.session_state:
    st.subheader("분석 결과")
    result = st.session_state["analysis_result"]
    st.table([{"칸": name, "내용": result.get(name, "확인 불가")} for name in fields])
    st.caption(f"상태 번호 200 · 사용 토큰 {st.session_state.get('analysis_tokens')}")
    st.caption("사진의 조명에 따라 색상이 다르게 보일 수 있습니다. 실제 옷과 비교해 확인하세요.")
