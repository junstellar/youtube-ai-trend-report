# -*- coding: utf-8 -*-
"""
설정 파일 — 여기 값만 바꾸면 동작이 달라집니다.
API 키는 여기 넣지 말고 .env 파일에 넣으세요.
"""

# 검색할 키워드 (하나씩 검색해서 합칩니다). 구체적일수록 노이즈가 적어요.
# 3대 모델(Claude/ChatGPT/Gemini) × 뉴스·새 기능·활용 앵글로 구성.
KEYWORDS = [
    # --- 뉴스 / 업데이트 ---
    "ChatGPT 업데이트",
    "Claude 업데이트",
    "Gemini 새 기능",
    "OpenAI 발표",
    # --- 새 기능 / 발표 (영어권 채널이 제일 빠름) ---
    "ChatGPT new feature",
    "Claude AI update",
    "Gemini update",
    # --- 활용 / 인기 스킬 ---
    "ChatGPT 활용법",
    "Claude Code",
]

# 제목/설명/채널에 이 중 하나라도 없으면 버림 (AI 모델 관련 영상만 남김)
REQUIRE_ANY = [
    "claude", "클로드", "anthropic",
    "chatgpt", "gpt", "지피티", "챗지피티", "openai", "오픈ai",
    "gemini", "제미나이",
]

# 제목/채널에 이 단어가 들어가면 버림 (엉뚱한 영상 차단)
BLOCK_WORDS = [
    "Sun Gemini", "Catering", "Serial", "Promo", "Comedy",
    "Telugu", "Jathara", "Devatha", "홍보", "드라마", "예고",
    "NASA", "Moon Base",
]

# 최근 몇 시간 이내 영상만 수집할지 (오늘/어제 것만 보려면 24)
HOURS = 24

# 조회수 상위 몇 개를 Gemini로 심층 분석할지 (토큰/비용 조절 핵심)
TOP_N = 6

# 키워드당 YouTube 검색 결과 개수 (많을수록 쿼터 소모)
RESULTS_PER_KEYWORD = 15

# Gemini 모델 (에러 나면 "gemini-2.0-flash" 로 바꿔보세요)
MODEL = "gemini-2.5-flash"

# 영상 화질 처리 수준: 낮을수록 토큰(비용) 절약. LOW / MEDIUM / HIGH
MEDIA_RESOLUTION = "MEDIA_RESOLUTION_LOW"

# 무료 티어 분당 토큰 한도 대응: 영상 사이 대기(초), 429 시 재시도 횟수
SLEEP_BETWEEN = 20
MAX_RETRIES = 3

# ── 폴백 설정 (Gemini 토큰 소진 시) ──────────────────────────
# 분석 순서: ① Gemini 영상시청 → ② claude -p → ③ Gemini 텍스트분석
USE_CLAUDE_FALLBACK = True   # 토큰 소진 시 claude -p 시도 (CLI 로그인돼 있어야 작동)
CLAUDE_EXE = ""              # 비우면 자동 탐색(%APPDATA%\Claude\claude-code\*\claude.exe)
CLAUDE_TIMEOUT = 240         # claude -p 한 번 최대 대기(초)
TRANSCRIPT_MAX_CHARS = 8000  # 폴백 분석에 넣을 자막 최대 길이

# 검색 지역/언어 (한국 트렌드 위주면 그대로, 글로벌이면 "" 로)
REGION_CODE = "KR"
RELEVANCE_LANGUAGE = "ko"

# 리포트를 저장할 폴더
OUTPUT_DIR = r"C:\Project\Claude\youtube-trend\reports"
