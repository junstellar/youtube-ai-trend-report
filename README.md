# YouTube AI Trend Report

Automatically searches YouTube every night for AI-related videos (Claude, ChatGPT, Gemini) from the last 24 hours, has **Gemini watch and summarize** the top videos by view count, and saves a local Markdown report.

When the Gemini free-tier token quota runs out, the pipeline falls back automatically:

```
① Gemini watches the video URL directly (default, deepest analysis)
② claude -p — local Claude Code CLI analyzes transcript + metadata
③ Gemini text analysis (uses almost no tokens)
```

The build story and lessons learned (in Korean):
[유튜브 AI 트렌드를 매일 밤 자동으로 받아보기](https://junstellar.github.io/p/youtube-ai-trend-report-automation/)

## Install (once)

```
py -m pip install -r requirements.txt
```

## API keys (once)

1. Copy `.env.example` to `.env`
2. Fill in the two keys:
   - `YOUTUBE_API_KEY` — Google Cloud Console → YouTube Data API v3
   - `GEMINI_API_KEY` — Google AI Studio
3. Never share `.env` (it is git-ignored)

## Run

```
py trend.py
```

The report is written to `reports\trend-YYYY-MM-DD.md`. Each video is tagged with the engine that analyzed it (🎬 video watch / 🤖 claude -p / 📝 text).

## Configuration

Adjust keywords, collection window (`HOURS`), number of videos to analyze (`TOP_N`), model, and fallback options in `config.py`.

## Nightly automation (Windows)

Register `run.bat` with Task Scheduler:

```powershell
$action  = New-ScheduledTaskAction -Execute "run.bat" -WorkingDirectory "<this folder>"
$trigger = New-ScheduledTaskTrigger -Daily -At 23:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "YouTubeTrendReport" -Action $action -Trigger $trigger -Settings $settings -Force
```

If the PC was off at the scheduled time, the task runs at the next boot (`StartWhenAvailable`).
