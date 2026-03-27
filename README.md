# news-paper-report

매일 아침 관심 분야의 뉴스와 논문을 자동으로 검색하고, AI가 핵심만 선별·요약하여 디스코드로 전달하는 브리핑 봇입니다.

## 주요 기능

- **관심 분야 관리** — CLI 또는 디스코드 슬래시 명령으로 토픽과 검색 태그를 추가/삭제
- **자동 검색** — Google News RSS + Semantic Scholar API에서 토픽당 뉴스 25건, 논문 25건 수집
- **AI 선별 + 요약** — OpenAI Codex 5.2가 50건 중 가장 중요한 뉴스 5건, 논문 5건을 골라 한국어로 요약
- **디스코드 전달** — 매일 오전 7:30 (KST) 자동 전송
- **즉시 실행** — `/report_now` 명령으로 원하는 시점에 바로 리포트 생성 가능

## 구조

```
news-paper-report/
├── setup.sh                    # 원클릭 셋업 & 실행 스크립트
├── requirements.txt
├── .env.example                # 환경 변수 템플릿
└── src/
    ├── main.py                 # CLI 엔트리 포인트 + 스케줄러
    ├── auth/
    │   └── codex_oauth.py      # ~/.codex/auth.json 공용 OAuth 토큰 관리
    ├── topics/
    │   └── manager.py          # 토픽/태그 CRUD (JSON 파일 기반)
    ├── search/
    │   ├── google_news.py      # Google News RSS 검색
    │   ├── semantic_scholar.py  # Semantic Scholar API 검색
    │   └── aggregator.py       # 검색 결과 병렬 수집 + 통합
    ├── summarizer/
    │   └── codex_summarizer.py # Codex 5.2 선별 + 요약
    └── delivery/
        └── discord_bot.py      # 디스코드 봇 (슬래시 명령 + 리포트 전송)
```

## 사전 준비

1. **Python 3.10+**
2. **ChatGPT Plus/Pro 구독** — Codex 5.2 OAuth 사용을 위해 필요
3. **Codex CLI 로그인** — `codex` 명령을 한 번 실행하여 `~/.codex/auth.json`에 토큰 저장
4. **디스코드 봇 토큰** — [Discord Developer Portal](https://discord.com/developers/applications)에서 봇 생성 후 토큰 발급
5. **디스코드 채널 ID** — 리포트를 받을 채널의 ID (개발자 모드 켜고 채널 우클릭 → ID 복사)

## 설치 및 실행

```bash
git clone https://github.com/Khun0313/news-paper-report.git
cd news-paper-report

# .env 파일 설정
cp .env.example .env
# DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID 입력

# 원클릭 실행 (가상환경 생성 + 의존성 설치 + 봇 실행)
./setup.sh
```

또는 수동으로:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src run
```

## CLI 사용법

```bash
# 인증 상태 확인
python -m src status

# 관심 분야 등록
python -m src add "AI" -d "인공지능 연구 동향" -t "LLM, transformer, machine learning"

# 관심 분야 목록
python -m src topics

# 관심 분야 삭제
python -m src remove "AI"

# 태그 추가/삭제
python -m src add-tags "AI" -t "GPT, diffusion model"
python -m src remove-tags "AI" -t "diffusion model"

# 리포트 즉시 생성 (터미널 출력, 디스코드 없이)
python -m src report
```

## 디스코드 슬래시 명령

| 명령 | 설명 |
|------|------|
| `/add_topic` | 관심 분야 추가 (이름, 설명, 태그 입력) |
| `/remove_topic` | 관심 분야 삭제 |
| `/list_topics` | 등록된 관심 분야 목록 |
| `/add_tags` | 기존 분야에 태그 추가 |
| `/remove_tags` | 기존 분야에서 태그 삭제 |
| `/report_now` | 즉시 리포트 생성 |

## 환경 변수

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `DISCORD_BOT_TOKEN` | O | — | 디스코드 봇 토큰 |
| `DISCORD_CHANNEL_ID` | O | — | 리포트 전송 채널 ID |
| `SCHEDULE_TIME` | X | `07:30` | 일일 리포트 전송 시각 (24시간 형식) |
| `TIMEZONE` | X | `Asia/Seoul` | 스케줄 기준 타임존 |
| `DATA_DIR` | X | `~/.config/news-paper-report` | 토픽 데이터 저장 경로 |

## 인증 방식

별도의 로그인 과정 없이, Codex CLI가 저장한 `~/.codex/auth.json` 토큰을 공용으로 사용합니다. 토큰 만료 시 자동으로 갱신하며, 갱신된 토큰은 `auth.json`에 다시 저장되어 Codex CLI와 동기화됩니다.

## 라이선스

MIT
