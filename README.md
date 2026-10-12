# Batch MP4 Audio Loudness Normalizer (`batch-audio-leveler`)

A robust, Windows-friendly command-line application that batch-normalizes audio loudness across MP4 video collections using **EBU R128 / ITU-R BS.1770** loudness measurement via FFmpeg's `loudnorm` filter.

Consecutive video playback sounds consistent without abrupt volume jumps, while video streams are preserved without quality loss (`-c:v copy`) and audio is protected against true-peak clipping.

---

## Table of Contents

- [Key Features](#key-features)
- [Audio Engineering Concepts](#audio-engineering-concepts)
  - [Integrated Loudness (LUFS)](#integrated-loudness-lufs)
  - [True Peak (dBTP)](#true-peak-dbtp)
  - [Loudness Range (LRA)](#loudness-range-lra)
  - [Linear vs Dynamic Normalization](#linear-vs-dynamic-normalization)
- [Prerequisites](#prerequisites)
- [Installation and Setup](#installation-and-setup)
- [Usage](#usage)
  - [Interactive Mode (Recommended)](#interactive-mode-recommended)
  - [Non-Interactive CLI Mode](#non-interactive-cli-mode)
- [Workflows](#workflows)
  - [Batch-Median Workflow (Default)](#batch-median-workflow-default)
  - [Fixed-Target Workflow](#fixed-target-workflow)
- [Outputs and Reports](#outputs-and-reports)
- [Windows Executable Packaging (PyInstaller)](#windows-executable-packaging-pyinstaller)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)

---

## Key Features

- **Local-First & CPU-Friendly**: No cloud uploads, no GUI overhead, no heavy AI models.
- **Two-Pass EBU R128 Normalization**: Uses FFmpeg's `loudnorm` filter with ITU-R BS.1770 measurement principles.
- **Video Stream Copy (`-c:v copy`)**: Fast processing that copies video tracks directly without lossy re-encoding.
- **True-Peak Ceiling Protection**: Pre-flight feasibility analysis ensures audio never clips beyond your configured ceiling (default: `-2.0 dBTP`).
- **Batch Median Normalization**: Automatically aligns files to the median integrated loudness of the valid batch items, resilient against quiet or loud outliers.
- **Two-Pass Verification**: Analyzes exported files after processing to verify achieved loudness and true peak against configurable tolerances.
- **Safe File Handling**: Never overwrites source files. Processes into temporary files and atomically renames them only upon success and verification.
- **Interactive Terminal UI**: Polished Rich interface with menus, tables, real-time progress bars, and graceful Ctrl+C cancellation.
- **Comprehensive Reporting**: Generates both human-readable summaries and machine-readable CSV & JSON reports.

---

## Audio Engineering Concepts

### Integrated Loudness (LUFS)
**LUFS** (Loudness Units relative to Full Scale) represents perceived loudness measured over the entire program duration using psychoacoustic gating (K-weighting curve specified by ITU-R BS.1770). Unlike simple RMS or peak meters, LUFS mirrors human ear sensitivity:
- Streaming standard targets typically range from **-14 LUFS** (YouTube, Spotify) to **-16 LUFS** (Apple Music, podcasts) and **-23/-24 LUFS** (Broadcast EBU R128 / ATSC A/85).
- A 1 LU change corresponds to approximately 1 dB perceived gain change.

### True Peak (dBTP)
**dBTP** (Decibels True Peak) measures the maximum analog signal peak reconstructed between digital samples (inter-sample peaks). Simple sample peak normalization fails to detect peaks that occur between samples during digital-to-analog conversion or lossy compression (AAC/MP3), causing clipping distortion on consumer DACs.
- Recommended broadcast/streaming ceiling: **-1.0 dBTP** to **-2.0 dBTP**.

### Loudness Range (LRA)
**LRA** (Loudness Range in LU) quantifies the statistical variation between soft and loud passages in a program (excluding background silence and extreme transients).

### Linear vs Dynamic Normalization
- **Linear Normalization**: Applies a fixed gain correction across the entire track. Preserves original dynamic relationships and micro-dynamics exactly.
- **Dynamic Normalization**: When a file cannot reach the target loudness via linear gain without exceeding the true peak ceiling, dynamic mode engages FFmpeg `loudnorm`'s internal limiter and compressor to constrain peaks while lifting quieter passages.

---

## Prerequisites

1. **Python 3.10+** (Tested on Python 3.12).
2. **FFmpeg & FFprobe 5.0+** with `loudnorm` filter support (FFmpeg 7.1 recommended).

### Installing FFmpeg on Windows:
Using `winget`:
```powershell
winget install Gyan.FFmpeg
```
Or download from [Gyan.dev FFmpeg Builds](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` directory to your Windows `PATH`.

---

## Installation and Setup

1. **Clone repository and create a virtual environment**:
```powershell
cd e:\teju\volume_normalization_pipeline\volume_normalization_pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Install the package in editable mode**:
```powershell
pip install -e .
```

To include development and test dependencies:
```powershell
pip install -e ".[dev]"
```

---

## Usage

### Interactive Mode (Modern Full-Screen TUI)

Simply run:
```powershell
batch-audio-leveler
```
or:
```powershell
python -m batch_audio_leveler
```

The application launches a modern, responsive full-screen terminal interface built with **Textual**:

- **Top Bar**: Displays application version, FFmpeg/FFprobe availability status, and current operation state.
- **Summary Metrics Bar**: Live status cards for Queue Count, Analyzed Files, Verified Files, Failed Items, Batch Target LUFS, and Peak Ceiling dBTP.
- **Queue & Plan Table**: Real-time table displaying queued files, duration, measured source LUFS, source true peak, proposed gain, normalization mode, and verification results.
- **Activity & Diagnostics Panel**: Live log of recent operations, current file status, concise warnings, and error excerpts.
- **Quick Action Buttons & Command Bar**:
  - Clickable buttons or quick hotkeys: `[A]` Analyze, `[P]` Preview, `[X]` Process, `[Space]` File Details, `[S]` Settings, `[C]` Cancel, `[?]` Help, `[Q]` Quit.
  - Persistent command input bar supporting commands with quotes and spaces: `add <path>`, `folder <path>`, `analyze`, `preview`, `process`, `settings`, `report`, `retry`, `clear`, `help`, `quit`.

#### Keyboard Shortcuts:
- `A`: Analyze batch (Pass 1 EBU R128 measurement)
- `P`: Preview normalization plan
- `X`: Process batch (Pass 2 normalization + Pass 3 verification)
- `Space`: Open detailed inspection modal for the highlighted queue item
- `S`: Open Settings modal (mode, target LUFS, peak ceiling, bitrate, dynamic mode)
- `R`: Retry failed jobs
- `C`: Cancel currently active background task cleanly
- `/` or `:`: Focus the bottom command input bar
- `?`: Open Help modal
- `Q`: Quit application (with confirmation if busy)

Run unattended batch normalization directly from PowerShell:

```powershell
# Normalize all MP4 files in a directory using Batch Median mode
batch-audio-leveler process --folder "C:\Videos\MyCollection" --recursive --output-dir "C:\Videos\Normalized"

# Normalize with Fixed Target (-16 LUFS) and -2 dBTP ceiling
batch-audio-leveler process "video1.mp4" "video2.mp4" --mode fixed --target -16.0 --peak -2.0 --bitrate 192k

# Allow dynamic compression when peak limit is exceeded
batch-audio-leveler process --folder "C:\Recordings" --allow-dynamic --output-dir "C:\Normalized"
```

CLI options:
- `FILES...`: List of MP4 file paths.
- `--folder, -f`: Folder containing MP4 files.
- `--recursive, -r`: Scan folder and subfolders recursively.
- `--output-dir, -o`: Output destination folder (default: `./normalized_output`).
- `--mode, -m`: Target strategy (`median` or `fixed`, default: `median`).
- `--target, -t`: Target integrated LUFS for fixed mode (default: `-16.0`).
- `--peak, -p`: True peak ceiling in dBTP (default: `-2.0`).
- `--bitrate, -b`: AAC audio bitrate (default: `192k`).
- `--allow-dynamic`: Allow dynamic loudnorm compression if linear gain exceeds peak ceiling.
- `--overwrite`: Overwrite destination files if they exist.

---

## Workflows

### Batch-Median Workflow (Default)
1. **Queue Files**: Add multiple MP4 files or folders.
2. **Analysis Pass**: FFmpeg measures integrated LUFS, true peak dBTP, LRA, and threshold for every file.
3. **Target Calculation**: The median of valid, non-silent integrated LUFS values is chosen as the batch target.
4. **Pre-flight Plan**: Nominal gains are calculated (`target - measured`). The planner verifies if each file's true peak would exceed the ceiling. If a file cannot reach target linearly without clipping, gain is clamped or dynamic mode is selected according to user policy.
5. **Preview**: Review the table of adjustments before touching media.
6. **Execution**: Video streams are copied, audio is normalized into temporary files, verified, and renamed to destination paths.

### Fixed-Target Workflow
1. User sets a fixed target (e.g. `-16.0 LUFS` for streaming or `-24.0 LUFS` for broadcast).
2. All valid files are adjusted directly toward that standard.

---

## Outputs and Reports

Upon completion, reports are automatically generated in the output directory:
- **`batch_report_<timestamp>.csv`**: Tabular summary of all source and output paths, LUFS and true peak values before and after processing, processing duration, and warnings.
- **`batch_report_<timestamp>.json`**: Machine-readable JSON dump of all analysis, planning, and verification data.
- **`batch_audio_leveler.log`**: Structured execution logs.

---

## Windows Executable Packaging (PyInstaller)

To build a standalone Windows `.exe` that does not require Python on the target machine:

```powershell
pip install pyinstaller
pyinstaller --onefile --name "batch-audio-leveler" --clean src/batch_audio_leveler/__main__.py
```

The resulting executable will be located in the `dist/` directory:
```powershell
.\dist\batch-audio-leveler.exe
```

> **Note on FFmpeg**: FFmpeg binaries should be distributed according to their respective license (GPL or LGPL). The application expects `ffmpeg.exe` and `ffprobe.exe` either on `PATH` or configured via the interface.

---

## Troubleshooting

- **"FFmpeg NOT FOUND"**:
  Ensure FFmpeg is installed and the directory containing `ffmpeg.exe` is added to your user or system `PATH` environment variable. Run `ffmpeg -version` in PowerShell to test.
- **"Audio is silent or near-silent"**:
  Files with integrated loudness below `-70 LUFS` or `-inf` are automatically excluded from target calculations and skipped during normalization to prevent amplifying ambient noise floor.
- **"Peak ceiling constraint applied"**:
  When linear mode is selected and boosting a file would cause its true peak to exceed the ceiling (e.g., `-2 dBTP`), gain is conservatively restricted to preserve peak headroom without clipping. To allow compression and reach the target loudness, enable **Allow Dynamic Mode**.

---

## Testing

Run the test suite with `pytest`:

```powershell
pytest -v
```

All 33 unit and integration tests validate:
- Median and fixed target algorithms.
- Loudness measurement JSON parsing across silent, noisy, and prefix-laden FFmpeg stderr.
- Command builder argument generation and `-c:v copy` validation.
- Queue de-duplication, Unicode paths, and spaces in filenames.
- True-peak feasibility checks and gain clamping.
- Subprocess cancellation and clean-up of temporary files.
- Full end-to-end integration test with synthetic video and audio fixtures.
