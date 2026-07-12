# 유튜브 AI 트렌드 자동 리포트

매일 밤 자동으로 유튜브에서 최근 24시간의 AI 관련 영상(Claude·ChatGPT·Gemini)을 검색하고, 조회수 상위 영상을 **Gemini가 직접 시청·요약**해 로컬 마크다운 리포트로 저장합니다.

Gemini 무료 티어 토큰이 소진되면 자동으로 폴백합니다:

```
① Gemini 영상 시청 (기본, 가장 깊음)
② claude -p — 로컬 Claude Code CLI로 자막+메타데이터 분석
③ Gemini 텍스트 분석 (토큰 거의 안 씀)
```

만든 과정과 시행착오는 블로그 글 참고:
[유튜브 AI 트렌드를 매일 밤 자동으로 받아보기](https://junstellar.github.io/p/youtube-ai-trend-report-automation/)

## 설치 (최초 1회)

```
py -m pip install -r requirements.txt
```

## 키 설정 (최초 1회)

1. `.env.example` 을 복사해서 `.env` 로 이름 변경
2. `.env` 안에 실제 키 두 개 입력
   - `YOUTUBE_API_KEY` : Google Cloud Console → YouTube Data API v3 키
   - `GEMINI_API_KEY` : Google AI Studio 키
3. `.env` 는 절대 공유 금지 (git에도 안 올라가게 설정돼 있음)

## 실행

```
py trend.py
```

끝나면 `reports\trend-YYYY-MM-DD.md` 에 리포트가 생깁니다. 영상마다 어떤 엔진이 분석했는지(🎬 영상 시청 / 🤖 claude -p / 📝 텍스트) 표시됩니다.

## 설정 바꾸기

`config.py` 에서 키워드, 수집 기간(HOURS), 분석 개수(TOP_N), 모델, 폴백 사용 여부 등을 조정.

## 매일 밤 자동 실행 (Windows)

작업 스케줄러에 `run.bat` 을 등록:

```powershell
$action  = New-ScheduledTaskAction -Execute "run.bat" -WorkingDirectory "<이 폴더 경로>"
$trigger = New-ScheduledTaskTrigger -Daily -At 23:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "YouTubeTrendReport" -Action $action -Trigger $trigger -Settings $settings -Force
```

PC가 꺼져 있었으면 켜질 때 실행됩니다(StartWhenAvailable).
