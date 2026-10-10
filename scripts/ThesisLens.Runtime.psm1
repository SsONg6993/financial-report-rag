Set-StrictMode -Version Latest

function Get-ThesisLensRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

function Get-RuntimePaths {
    $root = Get-ThesisLensRoot
    $runtime = Join-Path $root ".runtime"
    return @{
        Root = $root
        Runtime = $runtime
        State = Join-Path $runtime "state.json"
        Logs = Join-Path $runtime "logs"
    }
}

function Initialize-RuntimeDirectory {
    $paths = Get-RuntimePaths
    New-Item -ItemType Directory -Force -Path $paths.Runtime, $paths.Logs | Out-Null
    return $paths
}

function Rotate-RuntimeLog([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    if ((Get-Item -LiteralPath $Path).Length -lt 2MB) { return }
    for ($index = 4; $index -ge 1; $index--) {
        $source = "$Path.$index"
        $destination = "$Path." + ($index + 1)
        if (Test-Path -LiteralPath $source) {
            Move-Item -LiteralPath $source -Destination $destination -Force
        }
    }
    Move-Item -LiteralPath $Path -Destination "$Path.1" -Force
}

function Write-RuntimeLog([string]$Level, [string]$Message) {
    $paths = Initialize-RuntimeDirectory
    $path = Join-Path $paths.Logs "runtime-manager.log"
    Rotate-RuntimeLog $path
    $safe = $Message -replace '(?i)(token|key|secret|password)=[^\s]+', '$1=[redacted]'
    Add-Content -LiteralPath $path -Encoding utf8 -Value (
        "{0} {1} {2}" -f (Get-Date).ToUniversalTime().ToString("o"), $Level, $safe
    )
}

function Read-RuntimeState {
    $paths = Get-RuntimePaths
    if (-not (Test-Path -LiteralPath $paths.State)) { return @{} }
    try {
        $value = Get-Content -Raw -LiteralPath $paths.State | ConvertFrom-Json
        $state = @{}
        foreach ($property in $value.PSObject.Properties) {
            $state[$property.Name] = $property.Value
        }
        return $state
    } catch {
        Write-RuntimeLog "WARN" "Runtime state file is invalid; it will not be trusted."
        return @{}
    }
}

function Write-RuntimeState([hashtable]$State) {
    $paths = Initialize-RuntimeDirectory
    $temporary = Join-Path $paths.Runtime ("state-{0}.tmp" -f [guid]::NewGuid().ToString("N"))
    $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporary -Encoding utf8
    Move-Item -LiteralPath $temporary -Destination $paths.State -Force
}

function Get-CurrentCommit {
    $root = Get-ThesisLensRoot
    $commit = (& git -C $root rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $commit) { return "unknown" }
    return $commit.Trim()
}

function Get-ConfiguredValue([string]$Name, [string]$Default) {
    $environment = [Environment]::GetEnvironmentVariable($Name)
    if ($environment) { return $environment.Trim() }
    $envFile = Join-Path (Get-ThesisLensRoot) ".env"
    if (Test-Path -LiteralPath $envFile) {
        $line = Get-Content -LiteralPath $envFile | Where-Object {
            $_ -match "^\s*$([regex]::Escape($Name))\s*="
        } | Select-Object -Last 1
        if ($line) {
            $value = ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
            if ($value) { return $value }
        }
    }
    return $Default
}

function Invoke-LocalJson([string]$Uri, [int]$TimeoutSeconds = 3) {
    try {
        return Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec $TimeoutSeconds -ErrorAction Stop
    } catch {
        return $null
    }
}

function Get-PortOwner([int]$Port) {
    try {
        $listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
        if ($listeners.Count -gt 0) { return [int]$listeners[0].OwningProcess }
    } catch { }
    foreach ($line in (& netstat -ano -p tcp 2>$null)) {
        if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
            return [int]$Matches[1]
        }
    }
    return $null
}

function Get-ProcessRecord([int]$ProcessId) {
    try {
        return Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction Stop
    } catch {
        return $null
    }
}

function Test-ProcessRecord([object]$Record, [string]$Kind) {
    if (-not $Record -or -not $Record.CommandLine) { return $false }
    $root = [regex]::Escape((Get-ThesisLensRoot))
    switch ($Kind) {
        "backend" { return $Record.CommandLine -match $root -and $Record.CommandLine -match "uvicorn\s+backend\.main:app" }
        "frontend" { return $Record.CommandLine -match $root -and $Record.CommandLine -match "(?i)(npm|next).*?(dev|start)" }
        "ollama" { return $Record.CommandLine -match '(?i)ollama(\.exe)?"?\s+serve' }
        default { return $false }
    }
}

function Test-StateProcess([object]$Entry, [string]$Kind) {
    if (-not $Entry -or -not $Entry.pid) { return $false }
    $record = Get-ProcessRecord ([int]$Entry.pid)
    $matches = Test-ProcessRecord $record $Kind
    $rootPid = if ($Entry.PSObject.Properties.Name -contains "root_pid") { $Entry.root_pid } else { $null }
    if (-not $matches -and $rootPid) {
        $rootRecord = Get-ProcessRecord ([int]$rootPid)
        $descendants = @(Get-Descendants ([int]$rootPid))
        $matches = (Test-ProcessRecord $rootRecord $Kind) -and $descendants.Contains([int]$Entry.pid)
    }
    if (-not $matches) { return $false }
    if ($Entry.started_at -and $record.CreationDate) {
        try {
            if ($Entry.started_at -is [datetime]) {
                $expected = $Entry.started_at.ToUniversalTime()
            } else {
                $expected = [datetime]::Parse(
                    [string]$Entry.started_at,
                    [Globalization.CultureInfo]::InvariantCulture,
                    [Globalization.DateTimeStyles]::RoundtripKind
                ).ToUniversalTime()
            }
            if ($record.CreationDate -is [datetime]) {
                $actual = $record.CreationDate.ToUniversalTime()
            } else {
                $actual = ([Management.ManagementDateTimeConverter]::ToDateTime($record.CreationDate)).ToUniversalTime()
            }
            if ([math]::Abs(($actual - $expected).TotalSeconds) -gt 5) { return $false }
        } catch { return $false }
    }
    return $true
}

function Get-Descendants([int]$RootPid) {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $ids = [System.Collections.Generic.List[int]]::new()
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootPid)
    while ($pending.Count -gt 0) {
        $parent = $pending.Dequeue()
        foreach ($process in $all | Where-Object { [int]$_.ParentProcessId -eq $parent }) {
            $id = [int]$process.ProcessId
            if (-not $ids.Contains($id)) {
                $ids.Add($id)
                $pending.Enqueue($id)
            }
        }
    }
    $result = $ids.ToArray()
    [array]::Reverse($result)
    return $result
}

function Stop-TrackedComponent([hashtable]$State, [string]$Kind) {
    if (-not $State.ContainsKey($Kind)) { return $false }
    $entry = $State[$Kind]
    if (-not (Test-StateProcess $entry $Kind)) {
        Write-RuntimeLog "WARN" "Refused to stop $Kind because process ownership could not be verified."
        throw "Refusing to stop ${Kind}: tracked PID ownership cannot be verified. No process was terminated."
    }
    if ($Kind -eq "backend" -and $entry.instance_id) {
        $health = Invoke-LocalJson "http://127.0.0.1:8000/api/health"
        if ($health -and $health.instance_id -and $health.instance_id -ne $entry.instance_id) {
            throw "Refusing to stop Backend: the listener instance does not match the tracked process."
        }
    }
    $rootPid = if ($entry.PSObject.Properties.Name -contains "root_pid") { $entry.root_pid } else { $null }
    $pid = if ($rootPid) { [int]$rootPid } else { [int]$entry.pid }
    foreach ($child in (Get-Descendants $pid)) {
        Stop-Process -Id $child -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $pid -ErrorAction Stop
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Get-Process -Id $pid -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
        throw "$Kind did not stop cleanly. Force-kill was not attempted."
    }
    $State.Remove($Kind)
    Write-RuntimeLog "INFO" "Stopped verified $Kind process PID $pid."
    return $true
}

function Wait-ForJson(
    [string]$Uri,
    [int]$Seconds = 45,
    [int]$RequestTimeoutSeconds = 2
) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $result = Invoke-LocalJson $Uri $RequestTimeoutSeconds
        if ($result) { return $result }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $null
}

function Get-BackendListenerDecision(
    [object]$Listener,
    [object]$Health,
    [string]$Commit,
    [bool]$StateOwned
) {
    if (-not $Listener) { return "start" }
    if ($Health -and $Health.service -eq "ThesisLens Backend" -and $Health.build_commit -eq $Commit) {
        return "reuse"
    }
    if ($StateOwned) { return "replace" }
    return "refuse"
}

function Start-Backend([hashtable]$State, [string]$Commit) {
    $root = Get-ThesisLensRoot
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Project Python environment is missing: $python"
    }
    & $python -c "import fastapi, uvicorn, requests" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependencies are incomplete. Run .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    }
    $listener = Get-PortOwner 8000
    $health = Invoke-LocalJson "http://127.0.0.1:8000/api/health"
    $stateOwned = $State.ContainsKey("backend") -and (Test-StateProcess $State.backend "backend")
    $decision = Get-BackendListenerDecision $listener $health $Commit $stateOwned
    if ($decision -eq "reuse") {
            Write-RuntimeLog "INFO" "Reused matching healthy Backend on port 8000."
            return $health
    }
    if ($decision -eq "replace") {
        Write-RuntimeLog "INFO" "Replacing verified stale Backend on port 8000."
        [void](Stop-TrackedComponent $State "backend")
    }
    if ($decision -eq "refuse") {
        $identity = "an unrelated or unverifiable process"
        if ($health -and ($health.status -eq "ok" -or $health.service -eq "ThesisLens Backend")) {
            $identity = "an older or unmanaged ThesisLens Backend"
        }
        throw "Port 8000 is occupied by $identity (PID $listener). Ownership could not be verified, so nothing was terminated. Close that process or confirm its ownership manually."
    }
    $paths = Initialize-RuntimeDirectory
    Rotate-RuntimeLog (Join-Path $paths.Logs "backend-stdout.log")
    Rotate-RuntimeLog (Join-Path $paths.Logs "backend-stderr.log")
    $instance = [guid]::NewGuid().ToString("N")
    $previousCommit = $env:THESISLENS_BUILD_COMMIT
    $previousInstance = $env:THESISLENS_RUNTIME_INSTANCE
    try {
        $env:THESISLENS_BUILD_COMMIT = $Commit
        $env:THESISLENS_RUNTIME_INSTANCE = $instance
        $process = Start-Process -FilePath $python -ArgumentList @(
            "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"
        ) -WorkingDirectory $root -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $paths.Logs "backend-stdout.log") `
          -RedirectStandardError (Join-Path $paths.Logs "backend-stderr.log")
    } finally {
        $env:THESISLENS_BUILD_COMMIT = $previousCommit
        $env:THESISLENS_RUNTIME_INSTANCE = $previousInstance
    }
    $State.backend = @{
        pid = $process.Id
        root_pid = $process.Id
        started_at = $process.StartTime.ToUniversalTime().ToString("o")
        instance_id = $instance
        build_commit = $Commit
    }
    Write-RuntimeState $State
    $health = Wait-ForJson "http://127.0.0.1:8000/api/health" 45
    if (-not $health -or $health.instance_id -ne $instance -or $health.build_commit -ne $Commit) {
        throw "Backend did not become ready with the expected build. See .runtime\logs\backend-stderr.log"
    }
    $listenerPid = Get-PortOwner 8000
    $listenerRecord = if ($listenerPid) { Get-ProcessRecord $listenerPid } else { $null }
    if ($listenerRecord) {
        $State.backend.pid = $listenerPid
        $State.backend.started_at = $listenerRecord.CreationDate.ToUniversalTime().ToString("o")
        Write-RuntimeState $State
    }
    Write-RuntimeLog "INFO" "Started Backend PID $($process.Id) build $($Commit.Substring(0, [math]::Min(12, $Commit.Length)))."
    return $health
}

function Resolve-OllamaExecutable {
    $command = Get-Command ollama.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return $null
}

function Start-Or-ReuseOllama([hashtable]$State) {
    $baseUrl = Get-ConfiguredValue "OLLAMA_BASE_URL" (Get-ConfiguredValue "OLLAMA_URL" "http://127.0.0.1:11434")
    $model = Get-ConfiguredValue "OLLAMA_MODEL" "qwen3:4b"
    try { $uri = [uri]$baseUrl } catch { throw "OLLAMA_BASE_URL is invalid." }
    if ($uri.Host -notin @("localhost", "127.0.0.1", "::1")) {
        throw "Configured Ollama endpoint is not local. ThesisLens will not enable a remote LLM automatically."
    }
    $tags = Invoke-LocalJson ($baseUrl.TrimEnd('/') + "/api/tags") 3
    if (-not $tags) {
        $ollama = Resolve-OllamaExecutable
        if (-not $ollama) {
            Write-RuntimeLog "WARN" "Ollama is not installed; General AI remains unavailable."
            return @{ status = "service_unavailable"; model = $model }
        }
        $paths = Initialize-RuntimeDirectory
        Rotate-RuntimeLog (Join-Path $paths.Logs "ollama-stdout.log")
        Rotate-RuntimeLog (Join-Path $paths.Logs "ollama-stderr.log")
        $process = Start-Process -FilePath $ollama -ArgumentList @("serve") -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $paths.Logs "ollama-stdout.log") `
          -RedirectStandardError (Join-Path $paths.Logs "ollama-stderr.log")
        $State.ollama = @{
            pid = $process.Id
            started_at = $process.StartTime.ToUniversalTime().ToString("o")
            managed = $true
        }
        Write-RuntimeState $State
        $tags = Wait-ForJson ($baseUrl.TrimEnd('/') + "/api/tags") 60
        if (-not $tags) {
            Write-RuntimeLog "WARN" "Ollama was started but is still unavailable after the readiness window."
            return @{ status = "loading"; model = $model }
        }
        Write-RuntimeLog "INFO" "Started local Ollama PID $($process.Id)."
    } else {
        Write-RuntimeLog "INFO" "Reused existing local Ollama service."
    }
    $installed = @($tags.models | ForEach-Object { if ($_.name) { $_.name } elseif ($_.model) { $_.model } })
    if ($installed -notcontains $model) {
        Write-RuntimeLog "WARN" "Configured Ollama model is not installed. No download was attempted."
        return @{ status = "model_missing"; model = $model }
    }
    return @{ status = "ready"; model = $model }
}

function Start-Frontend([hashtable]$State, [string]$Commit) {
    $root = Get-ThesisLensRoot
    $frontend = Join-Path $root "frontend"
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
    if (-not $npm) { throw "npm.cmd is unavailable. Install Node.js before starting ThesisLens." }
    if (-not (Test-Path -LiteralPath (Join-Path $frontend "node_modules"))) {
        throw "Frontend dependencies are missing. Run npm ci in the frontend folder."
    }
    $listener = Get-PortOwner 3000
    if ($listener) {
        try {
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($page.Content -match "ThesisLens") {
                Write-RuntimeLog "INFO" "Reused existing ThesisLens Frontend on port 3000."
                return
            }
        } catch { }
        throw "Port 3000 is occupied by an unrelated or unverifiable process (PID $listener). Nothing was terminated."
    }
    $paths = Initialize-RuntimeDirectory
    Rotate-RuntimeLog (Join-Path $paths.Logs "frontend-stdout.log")
    Rotate-RuntimeLog (Join-Path $paths.Logs "frontend-stderr.log")
    $previousCommit = $env:NEXT_PUBLIC_THESISLENS_BUILD_COMMIT
    try {
        $env:NEXT_PUBLIC_THESISLENS_BUILD_COMMIT = $Commit
        $process = Start-Process -FilePath $npm.Source -ArgumentList @("--prefix", $frontend, "run", "dev") `
          -WorkingDirectory $frontend -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $paths.Logs "frontend-stdout.log") `
          -RedirectStandardError (Join-Path $paths.Logs "frontend-stderr.log")
    } finally {
        $env:NEXT_PUBLIC_THESISLENS_BUILD_COMMIT = $previousCommit
    }
    $State.frontend = @{
        pid = $process.Id
        root_pid = $process.Id
        started_at = $process.StartTime.ToUniversalTime().ToString("o")
        build_commit = $Commit
    }
    Write-RuntimeState $State
    $ready = $false
    $deadline = (Get-Date).AddSeconds(60)
    do {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 750
    } while ((Get-Date) -lt $deadline)
    if (-not $ready) { throw "Frontend did not become ready. See .runtime\logs\frontend-stderr.log" }
    $listenerPid = Get-PortOwner 3000
    $listenerRecord = if ($listenerPid) { Get-ProcessRecord $listenerPid } else { $null }
    if ($listenerRecord) {
        $State.frontend.pid = $listenerPid
        $State.frontend.started_at = $listenerRecord.CreationDate.ToUniversalTime().ToString("o")
        Write-RuntimeState $State
    }
    Write-RuntimeLog "INFO" "Started Frontend PID $($process.Id)."
}

function Get-ThesisLensStatus {
    $state = Read-RuntimeState
    $health = Invoke-LocalJson "http://127.0.0.1:8000/api/health"
    $readiness = Invoke-LocalJson "http://127.0.0.1:8000/api/readiness" 15
    $frontendReady = $false
    try {
        $frontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        $frontendReady = $frontendResponse.StatusCode -eq 200
    } catch { }
    $commit = Get-CurrentCommit
    $backendStatus = "offline"
    if ($health) {
        if ($health.build_commit -and $health.build_commit -ne $commit) { $backendStatus = "version_mismatch" }
        elseif ($health.service -eq "ThesisLens Backend") { $backendStatus = "online" }
        else { $backendStatus = "unmanaged_or_legacy" }
    }
    return [ordered]@{
        backend = $backendStatus
        backend_build = if ($health -and $health.build_commit) { $health.build_commit } else { $null }
        expected_build = $commit
        backend_pid = Get-PortOwner 8000
        frontend = if ($frontendReady) { "ready" } else { "unavailable" }
        frontend_pid = Get-PortOwner 3000
        market_pulse = if ($readiness) { $readiness.market_pulse.status } else { "backend_unavailable" }
        general_ai = if ($readiness) { $readiness.ollama.status } else { "backend_unavailable" }
        configured_model = if ($readiness) { $readiness.ollama.model } else { Get-ConfiguredValue "OLLAMA_MODEL" "qwen3:4b" }
        database = if ($readiness) { $readiness.database.status } else { "unknown" }
        managed_backend = $state.ContainsKey("backend") -and (Test-StateProcess $state.backend "backend")
        managed_frontend = $state.ContainsKey("frontend") -and (Test-StateProcess $state.frontend "frontend")
    }
}

function Start-ThesisLens([switch]$NoBrowser) {
    $state = Read-RuntimeState
    $commit = Get-CurrentCommit
    Write-RuntimeLog "INFO" "Startup requested."
    $health = Start-Backend $state $commit
    $ollama = Start-Or-ReuseOllama $state
    Start-Frontend $state $commit
    $readiness = Wait-ForJson "http://127.0.0.1:8000/api/readiness" 30 15
    if (-not $readiness) { throw "Backend liveness succeeded but readiness could not be read." }
    Write-RuntimeState $state
    Write-Host "ThesisLens is ready." -ForegroundColor Green
    Write-Host "  Backend: $($health.build_commit.Substring(0, [math]::Min(12, $health.build_commit.Length)))"
    Write-Host "  Market Pulse: $($readiness.market_pulse.status)"
    Write-Host "  General AI: $($ollama.status) ($($ollama.model))"
    Write-Host "  Frontend: http://127.0.0.1:3000"
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:3000" }
}

function Stop-ThesisLens {
    $state = Read-RuntimeState
    Write-RuntimeLog "INFO" "Shutdown requested."
    foreach ($kind in @("frontend", "backend", "ollama")) {
        if ($state.ContainsKey($kind)) {
            try { [void](Stop-TrackedComponent $state $kind) }
            catch { Write-Warning $_.Exception.Message }
        }
    }
    Write-RuntimeState $state
    Write-Host "Stopped all verified ThesisLens-managed processes. Unmanaged processes were left untouched."
}

Export-ModuleMember -Function Start-ThesisLens, Stop-ThesisLens, Get-ThesisLensStatus
