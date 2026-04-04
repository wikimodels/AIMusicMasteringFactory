# =============================================================
# LIMINAL PHONK - Full Workflow Script
# Step 1: Clean folders
# Step 2: Copy files from Downloads\Liminal Phonk to wav_input
# Step 3: Rename WAV -> Filename.wav (stay in wav_input)
#         Rename TXT -> Filename.txt (move to metadata\)
# =============================================================

$dest     = "D:\GitHub\AIMusicMasteringFactory\sound\wav_input"
$metaDir  = "D:\GitHub\AIMusicMasteringFactory\metadata"
$source   = "C:\Users\Vitali\Downloads\Liminal Phonk"

# ── STEP 1: Clean ─────────────────────────────────────────────
Write-Host "[1] Cleaning folders..." -ForegroundColor Cyan

$foldersToClean = @(
    "D:\GitHub\AIMusicMasteringFactory\sound\mp3_drops_output",
    $dest,
    "D:\GitHub\AIMusicMasteringFactory\sound\wav_output",
    "D:\GitHub\AIMusicMasteringFactory\video\video_input",
    "D:\GitHub\AIMusicMasteringFactory\video\video_output",
    $metaDir
)
foreach ($f in $foldersToClean) {
    if (Test-Path $f) {
        Remove-Item "$f\*" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  Cleaned : $f"
    } else {
        New-Item -ItemType Directory -Path $f -Force | Out-Null
        Write-Host "  Created : $f"
    }
}

# ── STEP 2: Copy ──────────────────────────────────────────────
Write-Host "[2] Copying from source..." -ForegroundColor Cyan
$sourceItems = [System.IO.Directory]::GetFiles($source)
foreach ($f in $sourceItems) {
    $fname = [System.IO.Path]::GetFileName($f)
    [System.IO.File]::Copy($f, [System.IO.Path]::Combine($dest, $fname), $true)
}
Write-Host "  Files in wav_input: $((Get-ChildItem $dest).Count)"

# ── STEP 3: Rename + Move metadata ────────────────────────────
Write-Host "[3] Renaming tracks and sorting metadata..." -ForegroundColor Cyan

# UUID -> [title for .txt content, filename base (no spaces, no special chars)]
$map = [ordered]@{
    "acc08cfe-76cf-4457-8c1a-5f7ab9f2225c" = [PSCustomObject]@{ title="Cave Echo Anemoia";                              file="Cave_Echo_Anemoia" }
    "37f86b72-2fdc-43cd-b630-73d03c7ecf90" = [PSCustomObject]@{ title="Sub-Bass Rumble in Empty Corridors";             file="Sub-Bass_Rumble_in_Empty_Corridors" }
    "8ad1ab0b-009d-4e00-b1a5-13aa08ce7d5a" = [PSCustomObject]@{ title="You've Been Here Before";                        file="Youve_Been_Here_Before" }
    "de07c70f-7ad0-4166-a8f6-09290ce8836e" = [PSCustomObject]@{ title="Dissociative Episode";                           file="Dissociative_Episode" }
    "7f7d3035-8aa5-42c5-b6dd-be5063f6fdcc" = [PSCustomObject]@{ title="Empty Hallway Phonk";                            file="Empty_Hallway_Phonk" }
    "aa4bb17a-9aa2-434c-afbf-93f3542672c6" = [PSCustomObject]@{ title="Core Memory Glitch";                             file="Core_Memory_Glitch" }
    "3376e2ed-17fa-46d6-8e4f-386d889cd7c8" = [PSCustomObject]@{ title="The Void Level";                                 file="The_Void_Level" }
    "73d06445-5334-4526-80fe-4f6c2321cf09" = [PSCustomObject]@{ title="Corporate Liminal";                              file="Corporate_Liminal" }
    "591af4a0-69ba-4e36-9c66-48d6c0cc9476" = [PSCustomObject]@{ title="Anemoia Slowed Pitched Down";                   file="Anemoia_Slowed_Pitched_Down" }
    "7eaae750-45a8-400c-8163-b838e0500043" = [PSCustomObject]@{ title="Intrusive Thoughts";                             file="Intrusive_Thoughts" }
    "edd8d87d-e39c-4046-a45c-b53880455fe1" = [PSCustomObject]@{ title="Existential Dread";                              file="Existential_Dread" }
    "ca3b2c44-512a-45c1-b4b3-763b2605baad" = [PSCustomObject]@{ title="Backrooms A24 Drift";                            file="Backrooms_A24_Drift" }
    "5837393a-aa11-415a-8200-908c17963d93" = [PSCustomObject]@{ title="Level 188 Liminal Hotel";                        file="Level_188_Liminal_Hotel" }
    "d31bf1e3-f48c-4e1e-ad63-372d55b4b917" = [PSCustomObject]@{ title="The Suburbs Are Repeating";                     file="The_Suburbs_Are_Repeating" }
    "baf6de6e-cf1a-4c12-9aba-2aa0156c9de5" = [PSCustomObject]@{ title="Urbancore Nightwalk";                            file="Urbancore_Nightwalk" }
    "ceeab059-6f3b-4dbe-bfaa-bdff6ec2559c" = [PSCustomObject]@{ title="Severance Office";                               file="Severance_Office" }
    "41647c60-1bb1-49fc-b74a-50ff20072e3c" = [PSCustomObject]@{ title="Muffled Screams Underwater";                    file="Muffled_Screams_Underwater" }
    "367addca-ef7a-4d5c-ae69-8c999cfe3b6f" = [PSCustomObject]@{ title="Cryptidcore";                                    file="Cryptidcore" }
    "a2f37540-6f6d-45b9-bccd-74078401c26f" = [PSCustomObject]@{ title="Threshold State";                                file="Threshold_State" }
    "037bbc90-2259-4e6f-8873-87fa36e4eac3" = [PSCustomObject]@{ title="Poolrooms at 3AM";                               file="Poolrooms_at_3AM" }
    "e37c0a6e-6798-4ef5-8252-ed1c8bc9ca5d" = [PSCustomObject]@{ title="Concrete Basement Drone";                        file="Concrete_Basement_Drone" }
    "f0568e7d-a8a8-4e15-b266-a20b68fe2a85" = [PSCustomObject]@{ title="Level 0 Suffocation";                            file="Level_0_Suffocation" }
    "3f93b761-3c61-4a21-a156-a1472c13b94c" = [PSCustomObject]@{ title="Rain on Window Wave Phonk";                     file="Rain_on_Window_Wave_Phonk" }
    "4c4993c4-7c0f-40ca-b272-b1287e548dac" = [PSCustomObject]@{ title="Liminal Memory Glitch";                          file="Liminal_Memory_Glitch" }
    "a60dcb08-cd4a-4240-8b50-a7e53498fbbd" = [PSCustomObject]@{ title="The Music From a Room That Doesnt Exist";        file="The_Music_From_a_Room_That_Doesnt_Exist" }
    "ca1152c0-34db-43ac-ae09-8df69a5a2969" = [PSCustomObject]@{ title="Dead Mall Church Bells";                         file="Dead_Mall_Church_Bells" }
}

$ok = 0
$missing = @()

foreach ($uuid in $map.Keys) {
    $entry    = $map[$uuid]
    $title    = $entry.title
    $fileBase = $entry.file

    $newWavName = "$fileBase.wav"
    $newTxtName = "$fileBase.txt"   # same base, .txt only (no .wav.txt)

    # Find WAV
    $wavFile = Get-ChildItem -Path $dest |
               Where-Object { $_.Name -match [regex]::Escape($uuid) -and $_.Extension -eq ".wav" } |
               Select-Object -First 1

    # Find TXT (original name has .wav.txt)
    $txtFile = Get-ChildItem -Path $dest |
               Where-Object { $_.Name -match [regex]::Escape($uuid) -and $_.Name -like "*.txt" } |
               Select-Object -First 1

    if (-not $wavFile) {
        $missing += $uuid
        continue
    }

    $oldWavName = $wavFile.Name

    # --- Process TXT: update content, rename, MOVE to metadata ---
    if ($txtFile) {
        $raw = [System.IO.File]::ReadAllText($txtFile.FullName, [System.Text.Encoding]::UTF8)
        $raw = $raw -replace [regex]::Escape("Metadata for: $oldWavName"), "Metadata for: $newWavName"
        $raw = $raw -replace '(?m)^Title: .*', "Title: $title"
        [System.IO.File]::WriteAllText($txtFile.FullName, $raw, [System.Text.Encoding]::UTF8)

        # If target already exists in metadata -> add date suffix to avoid overwrite
        $metaDestPath = Join-Path $metaDir $newTxtName
        if (Test-Path $metaDestPath) {
            $dateStamp = (Get-Date -Format "yyyy-MM-dd_HHmm")
            $newTxtName = "$fileBase`_$dateStamp.txt"
            $metaDestPath = Join-Path $metaDir $newTxtName
            Write-Host "  CONFLICT -> renamed to $newTxtName" -ForegroundColor Yellow
        }
        Move-Item -Path $txtFile.FullName -Destination $metaDestPath -Force
    }

    # --- Rename WAV in place ---
    Rename-Item -Path $wavFile.FullName -NewName $newWavName -Force

    Write-Host "  OK  $title" -ForegroundColor Green
    $ok++
}

Write-Host ""
Write-Host "Renamed: $ok / $($map.Count)" -ForegroundColor Cyan

if ($missing.Count -gt 0) {
    Write-Host "Missing UUIDs:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
}

Write-Host ""
Write-Host "WAV files in wav_input ($((Get-ChildItem $dest -Filter '*.wav').Count)):" -ForegroundColor Cyan
Get-ChildItem $dest -Filter "*.wav" | Sort-Object Name | ForEach-Object { Write-Host "  $($_.Name)" }

Write-Host ""
Write-Host "TXT files in metadata ($((Get-ChildItem $metaDir -Filter '*.txt').Count)):" -ForegroundColor Cyan
Get-ChildItem $metaDir -Filter "*.txt" | Sort-Object Name | ForEach-Object { Write-Host "  $($_.Name)" }

Write-Host ""
Write-Host "[DONE]" -ForegroundColor Green
