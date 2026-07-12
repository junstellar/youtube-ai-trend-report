# -*- coding: utf-8 -*-
"""
매일 밤 유튜브 AI 트렌드 리포트 생성기 (A안 + 3단 폴백)
  1) YouTube Data API 로 최근 영상 검색·수집 (제목/조회수/URL)
  2) 조회수 상위 N개를 분석:
       ① Gemini 로 영상 URL 직접 시청 (기본, 제일 깊음)
       ② 토큰 소진 시 → claude -p (CLI 로그인 시 자동 활성화)
       ③ 그래도 안 되면 → Gemini 텍스트 분석 (자막+제목+설명, 토큰 거의 안 씀)
  3) 로컬 마크다운 리포트로 저장
"""

import os
import re
import sys
import glob
import time
import subprocess
import datetime as dt

import requests
from dotenv import load_dotenv

# 윈도우 콘솔에서 한글이 깨지지 않게
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from google import genai
from google.genai import types

import config

# 자막 라이브러리 (없어도 동작 — 폴백 품질만 낮아짐)
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _HAS_TRANSCRIPT = True
except Exception:
    _HAS_TRANSCRIPT = False

# ── 키 로드 ────────────────────────────────────────────────
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not YOUTUBE_API_KEY or not GEMINI_API_KEY:
    sys.exit("[에러] .env 파일에 YOUTUBE_API_KEY / GEMINI_API_KEY 를 넣어주세요.")

YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

PROMPT_VIDEO = (
    "이 유튜브 영상을 보고 아래 형식으로 한국어로 정리해줘.\n"
    "- 핵심 요약: 3줄 이내\n"
    "- 다룬 AI 기능/키워드: 쉼표로 구분\n"
    "- 실용 팁: 시청자가 바로 써먹을 만한 것 1가지\n"
    "어그로성이거나 알맹이 없으면 '내용 빈약'이라고 솔직히 적어줘."
)

PROMPT_TEXT = (
    "아래는 어떤 유튜브 영상의 제목·설명·자막(있으면)이다. "
    "영상을 직접 보지 못했으니 이 텍스트만으로 아래 형식으로 한국어로 정리해줘. "
    "자막이 없어 근거가 부족하면 무리하게 지어내지 말 것.\n"
    "- 핵심 요약: 3줄 이내\n"
    "- 다룬 AI 기능/키워드: 쉼표로 구분\n"
    "- 실용 팁: 시청자가 바로 써먹을 만한 것 1가지\n"
    "어그로성이거나 알맹이 없으면 '내용 빈약'이라고 솔직히 적어줘. "
    "인사말·서론 없이 바로 정리만 출력."
)


# ── 1단계: 유튜브에서 최근 영상 검색 ───────────────────────
def search_recent_videos():
    published_after = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=config.HOURS)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    video_ids = {}  # id -> keyword (중복 제거)
    for kw in config.KEYWORDS:
        params = {
            "key": YOUTUBE_API_KEY,
            "part": "snippet",
            "q": kw,
            "type": "video",
            "order": "relevance",  # 조회수순 대신 관련도순 → 엉뚱한 대형채널 배제
            "publishedAfter": published_after,
            "maxResults": config.RESULTS_PER_KEYWORD,
        }
        if config.REGION_CODE:
            params["regionCode"] = config.REGION_CODE
        if config.RELEVANCE_LANGUAGE:
            params["relevanceLanguage"] = config.RELEVANCE_LANGUAGE

        r = requests.get(YT_SEARCH, params=params, timeout=30)
        r.raise_for_status()
        for item in r.json().get("items", []):
            vid = item["id"].get("videoId")
            if vid and vid not in video_ids:
                video_ids[vid] = kw
        print(f"  검색: '{kw}' → 누적 {len(video_ids)}개")

    return video_ids


# ── 2단계: 조회수 등 통계 붙이고 상위 N개 추리기 ───────────
def enrich_and_rank(video_ids):
    ids = list(video_ids.keys())
    videos = []
    # videos.list 는 한 번에 50개까지
    for i in range(0, len(ids), 50):
        chunk = ids[i : i + 50]
        r = requests.get(
            YT_VIDEOS,
            params={
                "key": YOUTUBE_API_KEY,
                "part": "snippet,statistics",
                "id": ",".join(chunk),
            },
            timeout=30,
        )
        r.raise_for_status()
        for item in r.json().get("items", []):
            stats = item.get("statistics", {})
            sn = item["snippet"]
            title = sn["title"]
            channel = sn["channelTitle"]
            desc = sn.get("description", "")

            haystack = f"{title} {channel} {desc}".lower()

            # 1) 차단 단어가 있으면 스킵
            if any(bw.lower() in haystack for bw in config.BLOCK_WORDS):
                continue

            # 2) AI 모델 이름이 하나도 없으면 스킵 (NASA·정치뉴스 등 배제)
            if config.REQUIRE_ANY and not any(
                rw.lower() in haystack for rw in config.REQUIRE_ANY
            ):
                continue

            videos.append(
                {
                    "id": item["id"],
                    "title": title,
                    "channel": channel,
                    "desc": desc,
                    "published": sn["publishedAt"],
                    "views": int(stats.get("viewCount", 0)),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
            )

    videos.sort(key=lambda v: v["views"], reverse=True)
    return videos[: config.TOP_N]


# ── 폴백 도구들 ────────────────────────────────────────────
def find_claude_exe():
    """이 PC의 claude.exe 경로 자동 탐색 (버전 폴더가 바뀌어도 최신 선택)."""
    if config.CLAUDE_EXE and os.path.exists(config.CLAUDE_EXE):
        return config.CLAUDE_EXE
    pattern = os.path.join(
        os.environ.get("APPDATA", ""), "Claude", "claude-code", "*", "claude.exe"
    )
    cands = glob.glob(pattern)
    if not cands:
        return None

    def ver_key(p):
        m = re.search(r"claude-code[\\/](\d+)\.(\d+)\.(\d+)", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    cands.sort(key=ver_key)
    return cands[-1]


def get_transcript(video_id):
    """영상 자막 텍스트(한/영 우선). 실패하면 빈 문자열."""
    if not _HAS_TRANSCRIPT:
        return ""
    langs = ["ko", "en", "en-US", "en-GB"]
    try:
        try:  # 구버전 API
            segs = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            text = " ".join(s["text"] for s in segs)
        except AttributeError:  # 신버전(v1.0+) API
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
            text = " ".join(sn.text for sn in fetched)
        return text[: config.TRANSCRIPT_MAX_CHARS]
    except Exception:
        return ""


def build_text_context(v):
    """폴백(claude/gemini-text)에 넣을 텍스트 뭉치 구성."""
    parts = [f"제목: {v['title']}", f"채널: {v['channel']}", f"URL: {v['url']}"]
    if v.get("desc"):
        parts.append(f"설명:\n{v['desc'][:1500]}")
    tr = get_transcript(v["id"])
    v["_has_transcript"] = bool(tr)
    if tr:
        parts.append(f"자막:\n{tr}")
    return "\n".join(parts)


def is_quota_error(msg):
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def is_transient(msg):
    return any(k in msg for k in ("503", "UNAVAILABLE", "500", "INTERNAL"))


def gemini_video(client, v, gen_config):
    """① 영상 URL 직접 시청. 반환 (텍스트|None, 토큰소진여부)."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=config.MODEL,
                config=gen_config,
                contents=types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=v["url"])),
                        types.Part(text=PROMPT_VIDEO),
                    ]
                ),
            )
            return resp.text.strip(), False
        except Exception as e:
            msg = str(e)
            if is_quota_error(msg):
                return None, True  # 토큰 소진 → 즉시 폴백 (재시도 낭비 X)
            if is_transient(msg) and attempt < config.MAX_RETRIES:
                time.sleep(15)
                continue
            return None, False
    return None, False


def gemini_text(client, context):
    """③ 텍스트만으로 분석 (토큰 거의 안 씀). 반환 (텍스트|None)."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=config.MODEL,
                contents=PROMPT_TEXT + "\n\n---\n" + context,
            )
            return resp.text.strip()
        except Exception as e:
            msg = str(e)
            if is_quota_error(msg) and attempt < config.MAX_RETRIES:
                time.sleep(35)
                continue
            if is_transient(msg) and attempt < config.MAX_RETRIES:
                time.sleep(10)
                continue
            return None
    return None


def claude_headless(exe, context):
    """② claude -p 로 텍스트 분석. 미로그인/실패면 None."""
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "-p", PROMPT_TEXT],
            input=context,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=config.CLAUDE_TIMEOUT,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
    except Exception:
        return None
    out = (proc.stdout or "").strip()
    blob = (out + " " + (proc.stderr or "")).lower()
    if proc.returncode != 0 or not out or "login" in blob or "not logged in" in blob:
        return None
    return out


# ── 3단계: 3단 폴백 분석 ───────────────────────────────────
def analyze_videos(videos):
    client = genai.Client(api_key=GEMINI_API_KEY)
    gen_config = types.GenerateContentConfig(media_resolution=config.MEDIA_RESOLUTION)

    claude_exe = find_claude_exe() if config.USE_CLAUDE_FALLBACK else None
    if claude_exe:
        print(f"  claude 폴백 준비됨: {claude_exe}")
    else:
        print("  claude 폴백 없음 → 토큰 소진 시 Gemini 텍스트 분석으로 대체")

    gemini_video_ok = True   # 영상시청 가능 여부(토큰 소진되면 False)
    claude_ok = bool(claude_exe)  # claude -p 가능 여부(한 번 실패하면 False)

    for idx, v in enumerate(videos):
        tag = v["title"][:38]
        done = False

        # ① Gemini 영상 시청
        if gemini_video_ok:
            text, quota = gemini_video(client, v, gen_config)
            if text:
                v["analysis"], v["engine"] = text, "🎬 Gemini (영상 시청)"
                print(f"  [영상] {tag}...")
                done = True
            elif quota:
                gemini_video_ok = False
                print("  ⚠️ Gemini 영상 토큰 한도 도달 → 텍스트 기반 폴백으로 전환")

        # 폴백이 필요하면 텍스트 뭉치 준비
        if not done:
            context = build_text_context(v)

            # ② claude -p
            if claude_ok:
                out = claude_headless(claude_exe, context)
                if out:
                    v["analysis"], v["engine"] = out, "🤖 Claude -p (자막/메타)"
                    print(f"  [claude] {tag}...")
                    done = True
                else:
                    claude_ok = False  # 미로그인 등 → 이후 재시도 안 함
                    print("  ⚠️ claude -p 사용 불가(미로그인?) → Gemini 텍스트로")

            # ③ Gemini 텍스트
            if not done:
                out = gemini_text(client, context)
                if out:
                    src = "자막" if v.get("_has_transcript") else "제목/설명"
                    v["analysis"], v["engine"] = out, f"📝 Gemini (텍스트·{src})"
                    print(f"  [텍스트] {tag}...")
                    done = True

        if not done:
            v["analysis"] = "(모든 분석 엔진 실패 — 토큰 한도 또는 일시 오류)"
            v["engine"] = "❌ 실패"
            print(f"  ❌ 실패: {tag}...")

        if idx < len(videos) - 1:
            time.sleep(config.SLEEP_BETWEEN)

    return videos


# ── 4단계: 마크다운 리포트 저장 ────────────────────────────
def write_report(videos):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    today = dt.datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(config.OUTPUT_DIR, f"trend-{today}.md")

    # 엔진별 집계
    tally = {}
    for v in videos:
        tally[v.get("engine", "?")] = tally.get(v.get("engine", "?"), 0) + 1
    tally_str = ", ".join(f"{k} {n}개" for k, n in tally.items())

    lines = [
        f"# 오늘의 유튜브 AI 트렌드 ({today})",
        "",
        f"최근 {config.HOURS}시간 · 키워드: {', '.join(config.KEYWORDS)}",
        f"조회수 상위 {len(videos)}개 · 분석엔진: {tally_str}",
        "",
        "---",
        "",
    ]
    for i, v in enumerate(videos, 1):
        lines += [
            f"## {i}. {v['title']}",
            "",
            f"- **채널**: {v['channel']}",
            f"- **조회수**: {v['views']:,}",
            f"- **업로드**: {v['published']}",
            f"- **분석엔진**: {v.get('engine', '?')}",
            f"- **링크**: {v['url']}",
            "",
            v.get("analysis", ""),
            "",
            "---",
            "",
        ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    print("[1/4] 유튜브 검색 중...")
    ids = search_recent_videos()
    if not ids:
        sys.exit("수집된 영상이 없습니다. 키워드/기간을 조정해보세요.")

    print("[2/4] 조회수 통계 붙이고 순위 매기는 중...")
    top = enrich_and_rank(ids)

    print(f"[3/4] 상위 {len(top)}개 분석 중... (영상시청→claude→텍스트 순 폴백)")
    top = analyze_videos(top)

    print("[4/4] 리포트 저장 중...")
    path = write_report(top)
    print(f"\n완료 ✅  →  {path}")


if __name__ == "__main__":
    main()
