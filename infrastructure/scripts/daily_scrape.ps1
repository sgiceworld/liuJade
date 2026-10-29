# Daily scraping agent wrapper (run by Task Scheduler "JadeScrapeDaily" at 08:50).
# Locates the bundled claude CLI, injects proxy env, runs headless claude -p
# with docs/daily_scrape_prompt.txt, logs to scraped_data/_daily_agent.log.
$ErrorActionPreference = 'Continue'
$repo = 'D:\liuJade'
$log = Join-Path $repo 'scraped_data\_daily_agent.log'
$lastOut = Join-Path $repo 'scraped_data\_agent_last.txt'
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
# scrub SDK model overrides leaked from VSCode sessions (standalone CLI must pick its own model)
Remove-Item Env:ANTHROPIC_MODEL -ErrorAction SilentlyContinue

# pre-flight: wait for Clash proxy. Both the LLM API (api.deepseek.com, 直连不通)
# and overseas museum sites need it; right after wake/login Clash may take minutes
# to start, otherwise ECONNREFUSED kills the whole run.
$proxyUp = $false
for ($i = 0; $i -lt 30; $i++) {
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port 7890 `
            -InformationLevel Quiet -WarningAction SilentlyContinue) {
        $proxyUp = $true
        break
    }
    Start-Sleep -Seconds 20
}
if (-not $proxyUp) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    "[$stamp] ERROR: proxy 127.0.0.1:7890 not up after 10min, abort" |
        Add-Content -Path $log -Encoding UTF8
    exit 1
}

$promptFile = Join-Path $repo 'docs\daily_scrape_prompt.txt'

Set-Location $repo
# cmd-level pipe+redirect keeps claude's UTF-8 output intact
# (PowerShell native-command capture mangles it to UTF-16 mojibake)
$cmd = "type `"$promptFile`" | `"$claudeExe`" -p --dangerously-skip-permissions > `"$lastOut`" 2>&1"
cmd /c $cmd
$code = $LASTEXITCODE

$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"[$stamp] daily scrape agent: end, exit=$code" | Add-Content -Path $log -Encoding UTF8
if (Test-Path $lastOut) {
    Get-Content -Path $lastOut -Encoding UTF8 |
        Add-Content -Path $log -Encoding UTF8
}
exit $code
