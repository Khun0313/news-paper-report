#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"

echo "=== 1. git pull ==="
git pull

echo ""
echo "=== 2. 가상환경 설정 ==="
if [ ! -d "$VENV_DIR" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv "$VENV_DIR"
else
    echo "기존 가상환경 사용"
fi

source "$VENV_DIR/bin/activate"

echo ""
echo "=== 3. 의존성 설치 ==="
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "=== 4. 환경 변수 확인 ==="
if [ ! -f "$ENV_FILE" ]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    echo "⚠️  .env 파일이 생성되었습니다. 아래 항목을 설정하세요:"
    echo "    - DISCORD_BOT_TOKEN"
    echo "    - DISCORD_CHANNEL_ID"
    echo ""
    echo "설정 후 다시 실행하세요."
    exit 1
fi

# .env에서 필수 값 확인
source "$ENV_FILE"
if [ -z "${DISCORD_BOT_TOKEN:-}" ] || [ "$DISCORD_BOT_TOKEN" = "your_discord_bot_token_here" ]; then
    echo "❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다. .env 파일을 수정하세요."
    exit 1
fi
if [ -z "${DISCORD_CHANNEL_ID:-}" ] || [ "$DISCORD_CHANNEL_ID" = "your_channel_id_here" ]; then
    echo "❌ DISCORD_CHANNEL_ID가 설정되지 않았습니다. .env 파일을 수정하세요."
    exit 1
fi

echo ""
echo "=== 5. Codex 인증 확인 ==="
if [ -f "$HOME/.codex/auth.json" ]; then
    echo "✅ ~/.codex/auth.json 확인됨"
else
    echo "❌ ~/.codex/auth.json 없음. codex CLI로 먼저 로그인하세요."
    exit 1
fi

echo ""
echo "=== 6. 봇 실행 ==="
exec python -m src run
