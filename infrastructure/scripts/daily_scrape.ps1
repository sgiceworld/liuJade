# Daily scraping agent wrapper (run by Task Scheduler "JadeScrapeDaily" at 08:50).
# Locates the bundled claude CLI, injects proxy env, runs headless claude -p
# with docs/daily_scrape_prompt.txt, logs to scraped_data/_daily_agent.log.
$ErrorActionPreference = 'Continue'
$repo = 'D:\liuJade'
$log = Join-Path $repo 'scraped_data\_daily_agent.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"[$stamp] daily scrape agent: start" | Add-Content -Path $log -Encoding UTF8

# latest bundled CLI from the VSCode extension
$extRoot = Join-Path $env:USERPROFILE '.vscode\extensions'
$claudeExe = Get-ChildItem -Path $extRoot -Directory -Filter 'anthropic.claude-code-*' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
    ForEach-Object { Join-Path $_.FullName 'resources\native-binary\claude.exe' }
if (-not $claudeExe -or -not (Test-Path $claudeExe)) {
    "[$stamp] ERROR: claude.exe not found under $extRoot" |
        Add-Content -Path $log -Encoding UTF8
    exit 1
}

# stop condition: handoff doc marked DONE
$handoff = Join-Path $repo 'docs\scraping_handoff.md'
if (Test-Path $handoff) {
    $statusLine = (Select-String -Path $handoff -Pattern '^\*\*[^\r\n]*: DONE' |
        Select-Object -First 1).Line
    if ($statusLine -match 'DONE') {
        "[$stamp] handoff status=DONE, skip" | Add-Content -Path $log -Encoding UTF8
        exit 0
    }
}

# proxy + UTF-8 for the scraping stack (tnm.jp etc. unreachable without proxy)
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
$env:HTTP_PROXY  = 'http://127.0.0.1:7890'
$env:NO_PROXY    = 'localhost,127.0.0.1'
$env:PYTHONIOENCODING = 'utf-8'

$prompt = Get-Content -Path (Join-Path $repo 'docs\daily_scrape_prompt.txt') -Raw -Encoding UTF8

Set-Location $repo
& $claudeExe -p $prompt --dangerously-skip-permissions 2>&1 |
    Tee-Object -FilePath $log -Append
$code = $LASTEXITCODE
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"[$stamp] daily scrape agent: end, exit=$code" | Add-Content -Path $log -Encoding UTF8
exit $code
