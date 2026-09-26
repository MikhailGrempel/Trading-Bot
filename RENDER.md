# Render 배포

페이퍼 트레이딩 UI(`ui.py`)를 Render **Web Service**로 올리는 방법입니다. 실거래 주문은 없으며, Kraken 공개 15분봉만 사용합니다.

## 사전 조건

- GitHub(또는 GitLab)에 `Tradingbot` 저장소 푸시
- Render 계정 ([render.com](https://render.com))

## 방법 A — Blueprint (`render.yaml`)

1. Render Dashboard → **New** → **Blueprint**
2. 저장소 연결, 브랜치 **`dev`** (또는 배포할 브랜치)
3. Root Directory가 monorepo 안의 `Tradingbot`이면 Render 서비스 설정에서 **Root Directory** = `Tradingbot` 로 지정
4. **Apply** → `tradingbot-paper` Web Service 생성

## 방법 B — 수동 Web Service

| 항목 | 값 |
|------|-----|
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt && cd web && npm install && npm run build` |
| **Start Command** | `python ui.py` |
| **Health Check Path** | `/health` |

Python 버전: `runtime.txt` (`python-3.12.10`) 또는 환경 변수 `PYTHON_VERSION=3.12.10`

## 환경 변수 (선택)

| Key | 설명 |
|-----|------|
| `RENDER_EXTERNAL_URL` | Render가 자동 설정 (HTTPS 공개 URL). CORS에 사용됩니다. |
| `HOST` | 기본: `PORT`가 있으면 `0.0.0.0` |
| `PORT` | Render가 자동 설정 — **수동으로 바꾸지 마세요** |

## 배포 후

- 공개 URL: `https://<service-name>.onrender.com`
- **Dashboard**에서 Start → 15분봉이 닫힐 때마다 페이퍼 매매 진행
- `/health` → `{"ok":true}`

## 제한 (알아두기)

1. **Free 플랜**: 유휴 시 슬립 → 첫 접속이 느릴 수 있음
2. **디스크**: `data/paper_state.json`은 재배포/재시작 시 초기화될 수 있음 (영구 디스크는 유료 옵션)
3. **데모용**: 공개 URL이면 누구나 Start/Stop 가능 — 클라이언트 데모용으로 적합, 실계정·비밀키는 넣지 마세요

## 로컬과 동일하게

```bash
python ui.py
# http://127.0.0.1:8765
```

Render에서는 `PORT`만 다르고 동일한 `ui.py`가 실행됩니다.
