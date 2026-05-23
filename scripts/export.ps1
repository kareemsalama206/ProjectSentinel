$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputZip = Join-Path $projectRoot "ProjectSentinel.zip"
$exportRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ProjectSentinel-export-" + [System.Guid]::NewGuid().ToString("N"))
$cleanRoot = Join-Path $exportRoot "ProjectSentinel"

$excludedNames = @(
    ".coverage",
    ".DS_Store",
    ".env",
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "ProjectSentinel.zip",
    "test_projectsentinel.db",
    "venv"
)

$forbiddenZipPatterns = @(
    "(^|/)node_modules/",
    "(^|/)dist/",
    "(^|/)build/",
    "(^|/)__pycache__/",
    "(^|/)\.pytest_cache/",
    "(^|/)\.venv/",
    "(^|/)venv/",
    "(^|/)coverage/",
    "(^|/)\.env$",
    "(^|/)test_projectsentinel\.db$",
    "\.pyc$",
    "\.zip$"
)

function Test-ExcludedItem {
    param(
        [Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item
    )

    if ($excludedNames -contains $Item.Name) {
        return $true
    }

    if (-not $Item.PSIsContainer -and $Item.Extension -eq ".pyc") {
        return $true
    }

    if (-not $Item.PSIsContainer -and $Item.Extension -eq ".zip") {
        return $true
    }

    return $false
}

function Copy-CleanTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        if (Test-ExcludedItem -Item $item) {
            continue
        }

        $target = Join-Path $Destination $item.Name
        if ($item.PSIsContainer) {
            Copy-CleanTree -Source $item.FullName -Destination $target
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $target
        }
    }
}

function Test-CleanZip {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $violations = @()
        foreach ($entry in $zip.Entries) {
            $entryName = $entry.FullName.Replace("\", "/")
            foreach ($pattern in $forbiddenZipPatterns) {
                if ($entryName -match $pattern) {
                    $violations += $entryName
                    break
                }
            }
        }

        if ($violations.Count -gt 0) {
            $sample = ($violations | Select-Object -First 20) -join "`n"
            throw "Clean export verification failed. Forbidden generated artifacts were found:`n$sample"
        }
    } finally {
        $zip.Dispose()
    }
}

try {
    New-Item -ItemType Directory -Force -Path $exportRoot | Out-Null
    Copy-CleanTree -Source $projectRoot -Destination $cleanRoot

    if (Test-Path -LiteralPath $outputZip) {
        Remove-Item -LiteralPath $outputZip -Force
    }

    Compress-Archive -Path $cleanRoot -DestinationPath $outputZip -Force
    Test-CleanZip -ZipPath $outputZip
    Write-Host "Created clean export: $outputZip"
    Write-Host "Verified clean export: no generated artifacts or nested ZIP files found."
} finally {
    if (Test-Path -LiteralPath $exportRoot) {
        $resolvedExportRoot = (Resolve-Path $exportRoot).Path
        $tempRoot = [System.IO.Path]::GetTempPath()
        if (-not $resolvedExportRoot.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to delete non-temp export path: $resolvedExportRoot"
        }
        Remove-Item -LiteralPath $resolvedExportRoot -Recurse -Force
    }
}
