# PROMPT.md --- Batch MP4 Audio Loudness Normalizer

## 1. Role and objective

Act as a senior Python audio-software engineer. Design and implement a
reliable, Windows-friendly **interactive command-line application** that
batch-normalizes the audio loudness of MP4 files so consecutive videos
are less likely to sound dramatically louder or quieter when played at
the same system volume.

The application must run locally, must not require a GUI, and must not
upload media to a server. Do **not** use Tkinter, PyQt, web UI, or any
other graphical interface. The user experience should be a polished
interactive CLI with menus, tables, progress bars, clear validation, and
actionable error messages.

Use **EBU R128 loudness measurement based on ITU-R BS.1770**,
implemented through FFmpeg's `loudnorm` filter. Do not invent a new
loudness-measurement algorithm and do not use peak normalization as the
primary loudness-matching method.

## 2. Product requirements

### Primary workflow

1.  Start the program in a terminal.
2.  Present an interactive menu:
    -   Add individual MP4 files.
    -   Add all supported files from a folder.
    -   Include files from subfolders (optional setting).
    -   Remove files / clear queue.
    -   Choose normalization mode and target.
    -   Review the queue and analysis status.
    -   Analyze the batch.
    -   Preview the proposed gain/normalization decisions.
    -   Process the batch.
    -   View a processing report / re-run failed items.
    -   Exit.
3.  Analyze the audio of every queued file before making batch-wide
    decisions.
4.  Calculate one common batch target or use a user-selected fixed
    target.
5.  Normalize each file using FFmpeg, protecting against excessive true
    peaks.
6.  Verify output loudness and true peak by analyzing the exported
    files.
7.  Write outputs to a user-selected directory without overwriting
    originals by default.
8.  Produce a readable summary and a machine-readable JSON or CSV
    report.

### Required CLI qualities

-   Interactive, keyboard-friendly menus; no GUI.
-   Use Rich for readable tables, status panels, progress bars, and
    color where supported.
-   Use Typer for command entry points and support both interactive use
    and useful non-interactive command-line flags.
-   Use `pathlib.Path` throughout.
-   Support paths containing spaces and non-ASCII characters on Windows.
-   Never build shell commands by concatenating untrusted path strings.
    Use `subprocess.run([...], shell=False, ...)`.
-   Show a clear dry-run / preview before processing.
-   Support cancellation between files and handle Ctrl+C without
    corrupting completed outputs.
-   Continue processing other files when one file fails, and report each
    failure.
-   Avoid excessive terminal output from FFmpeg; capture logs and show
    useful error excerpts when needed.
-   Keep the application local-first and CPU-friendly. Do not require a
    GPU or any AI model.

## 3. Audio loudness algorithm

### Standards and metrics

Use FFmpeg's `loudnorm` filter, which implements EBU R128 loudness
normalization using ITU-R BS.1770 measurement principles. Understand and
expose these metrics: - **Integrated loudness (`I`, LUFS):** overall
gated loudness of the program. - **True peak (`TP`, dBTP):** estimated
inter-sample peak, not merely the highest PCM sample. - **Loudness range
(`LRA`, LU):** a measure of loudness variation over time. - **Target
loudness (`I`):** desired integrated loudness. - **Target true peak
(`TP`):** maximum permitted true peak target. - **Target LRA (`LRA`):**
target loudness range used by the filter's dynamic mode; it is not a
promise that every source will have that exact range.

Use LUFS and dBTP labels accurately. Do not confuse peak amplitude with
perceived loudness.

### Normalization modes

Implement at least these modes:

**A. Batch-relative (default)** 1. Analyze every source file and obtain
its integrated loudness and true peak. 2. Exclude failed, silent, or
invalid measurements from target calculation, but retain those files in
the report with a clear status. 3. Calculate the batch target as the
**median** of valid files' integrated loudness values. Explain in CLI
help that the median is robust against one unusually loud or quiet
outlier. 4. Allow a user-configurable maximum gain-up limit and maximum
gain-down limit. Use conservative defaults and make them visible in the
preview. 5. Calculate each file's nominal gain correction as
`target_lufs - measured_integrated_lufs`. 6. Do not apply gain-only
linear normalization if the requested adjustment would violate the
true-peak ceiling. If necessary, constrain the adjustment, flag the
file, and/or use FFmpeg `loudnorm` dynamic mode according to the
selected policy. 7. Clearly report when peak constraints mean a file
cannot reach the batch target without dynamic processing.

**B. Fixed target** 1. Let the user choose a target integrated loudness,
with a sensible default such as `-16 LUFS`. 2. Let the user configure
the true-peak ceiling, with a conservative default such as `-2 dBTP`. 3.
Use two-pass loudness normalization for each file. 4. Report target
deviations caused by source characteristics or peak constraints.

**C. Optional advanced mode: dynamic normalization** - Expose FFmpeg
`loudnorm` dynamic mode as an explicit option for material that cannot
reach the target through linear gain alone. - Explain that dynamic mode
may alter short-term dynamics and is not identical to gain-only
normalization. - Do not silently apply aggressive compression or
limiting in the default mode. - Do not promise that all moments will
have identical perceived loudness; normalization aligns program
loudness, not every instant.

### FFmpeg two-pass workflow

Use a proper two-pass workflow per file: 1. **Measurement pass:** run
FFmpeg with `loudnorm` configured for the desired targets and
`print_format=json`, directing output to the null muxer. Parse the JSON
measurement fields robustly. 2. **Normalization pass:** use measured
values (`measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`,
and `offset`) with `linear=true` where appropriate. Use dynamic mode
when selected or required by the policy. 3. **Verification pass:**
analyze the output again and compare achieved integrated loudness and
true peak against the configured tolerances.

Use the exact field names emitted by the installed FFmpeg version;
tolerate harmless log prefixes and unrelated stderr text. If parsing
fails, preserve the diagnostic log and mark the item as failed instead
of guessing measurements.

Do not assume linear mode will always be possible. Check the FFmpeg
`loudnorm` documentation / installed version behavior during
implementation. If the filter falls back to dynamic mode or the target
cannot be reached under peak constraints, report it accurately.

### Batch-target and peak policy

-   The common target is the median integrated loudness of valid files
    unless the user chooses fixed-target mode.
-   The target calculation must be performed only after all source files
    have been analyzed.
-   True-peak protection takes precedence over reaching an exact target.
-   If a file's current true peak is `source_tp` and the nominal gain is
    `gain_db`, estimate its gain-adjusted peak as `source_tp + gain_db`
    as a useful first check, but rely on FFmpeg's measured output for
    verification.
-   Never silently clip audio. Never treat sample-peak normalization as
    a replacement for true-peak-aware processing.
-   Do not force every file's LRA to a common value by default.
-   If the batch has too few valid measurements or all files are
    silent/invalid, stop target calculation and explain how to fix the
    issue.
-   Make the target and peak ceiling configurable. Validate plausible
    numeric ranges and reject non-finite values.

## 4. Video and stream handling

-   Preserve video without re-encoding by default: map the original
    video stream and use `-c:v copy`.
-   Normalize the selected audio stream and encode it to AAC at a
    high-quality bitrate (configurable; default may be 192 kb/s for
    stereo).
-   Preserve relevant metadata and chapters where feasible.
-   Preserve subtitles and other non-audio streams when feasible, using
    explicit mapping and safe codec handling. If a stream cannot be
    copied into MP4, report the limitation and offer a documented
    fallback rather than silently dropping it.
-   Default to the first audio stream, but detect multiple audio streams
    and ask the user whether to process the first, all audio streams, or
    choose a stream. Do not silently claim all tracks were normalized if
    only one was.
-   Support MP4 as the required input format. Keep extension handling
    case-insensitive. A future extension point may support MOV/M4V, but
    do not expand scope unless implemented and tested.
-   Write to a temporary output file in the destination directory and
    rename it to the final path only after FFmpeg succeeds and
    verification passes. Clean up partial temporary files on failure.
-   Never overwrite source files. If an output name already exists, ask
    whether to skip, choose a new name, or overwrite an existing output
    only after explicit confirmation.
-   Avoid unnecessary video re-encoding to preserve quality and reduce
    processing time.
-   Preserve duration as closely as the chosen audio encoding permits.

## 5. Proposed architecture

Use a small layered architecture with explicit boundaries:

``` text
Full-screen Textual TUI (Rich rendering)
        |
        v
Application / Workflow Orchestrator
  - queue management
  - mode and target configuration
  - batch lifecycle
  - cancellation and retry
        |
        +--------------------+
        |                    |
        v                    v
Media Probe             Batch Target Calculator
(FFprobe)               - median or fixed target
        |                    ^
        v                    |
Audio Analyzer -------------+
(FFmpeg loudnorm measurement)
        |
        v
Normalization Planner
  - nominal correction
  - true-peak feasibility
  - linear/dynamic policy
  - dry-run preview
        |
        v
FFmpeg Processor
  - two-pass normalization
  - stream mapping / output encoding
  - temp-file management
        |
        v
Output Verifier
  - post-process loudness analysis
  - target deviation / true-peak checks
        |
        v
Report Writer + Structured Logging
(CSV/JSON + log file)
```

### Suggested package structure

``` text
batch-audio-leveler/
├── pyproject.toml
├── README.md
├── PROMPT.md
├── src/
│   └── batch_audio_leveler/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                 # Typer entry point
│       ├── ui.py                  # Textual screens, widgets, bindings
│       ├── config.py              # Validated configuration and defaults
│       ├── models.py              # FileJob, AudioMeasurement, JobResult
│       ├── queue_manager.py       # File/folder discovery and de-duplication
│       ├── ffmpeg/
│       │   ├── discovery.py       # Locate/check ffmpeg and ffprobe
│       │   ├── probe.py           # Stream and metadata inspection
│       │   ├── analyzer.py        # R128/loudnorm measurement
│       │   ├── command_builder.py # Safe argument-list construction
│       │   ├── processor.py       # Normalization execution
│       │   └── verifier.py        # Output re-analysis
│       ├── normalization/
│       │   ├── targets.py         # Batch median and fixed target
│       │   └── planner.py         # Gain/peak feasibility and strategy
│       ├── reporting/
│       │   ├── csv_report.py
│       │   ├── json_report.py
│       │   └── logging_setup.py
│       └── utils/
│           ├── paths.py
│           └── cancellation.py
└── tests/
    ├── test_targets.py
    ├── test_planner.py
    ├── test_command_builder.py
    ├── test_measurement_parser.py
    ├── test_queue_manager.py
    └── integration/
        └── test_ffmpeg_pipeline.py
```

## 6. Data models

Create typed data models (dataclasses or Pydantic models) for at least:

### `AudioMeasurement`

-   `path`
-   `audio_stream_index`
-   `integrated_lufs`
-   `true_peak_dbtp`
-   `loudness_range_lu`
-   `threshold_lufs`
-   `measurement_valid`
-   `is_silent`
-   `raw_ffmpeg_json`
-   `measured_at`

### `NormalizationPlan`

-   `path`
-   `batch_target_lufs`
-   `requested_gain_db`
-   `planned_mode` (`linear` or `dynamic`)
-   `true_peak_ceiling_dbtp`
-   `peak_constraint_applied`
-   `expected_target_reachable`
-   `warnings`

### `JobResult`

-   `source_path`
-   `output_path`
-   `status` (`queued`, `analyzed`, `processing`, `verified`, `skipped`,
    `failed`, `cancelled`)
-   `before_measurement`
-   `after_measurement`
-   `error_message`
-   `warnings`
-   `started_at`
-   `finished_at`
-   `processing_seconds`

Represent unavailable measurements as `None`, not fake numeric values
such as zero. Handle NaN, infinity, missing JSON keys, and silent inputs
explicitly.

## 7. Interactive CLI UX

The initial full-screen TUI should show: - Application name and version. - FFmpeg
/ FFprobe availability and version. - Current queue count. - Selected
mode and target policy. - Output directory.

Suggested dashboard layout (do not implement as a plain numbered menu):

``` text
BATCH AUDIO LEVELER
────────────────────────────────────────────────────────
Queue: 12 files | Mode: Batch median | True peak: -2 dBTP

1. Add MP4 files
2. Add folder
3. Review / remove queued files
4. Configure normalization
5. Analyze batch
6. Preview normalization plan
7. Process batch
8. View results / retry failures
9. Change output directory
0. Exit
Select an option:
```

Use `Rich` tables for source path, duration, integrated LUFS, true peak,
proposed adjustment, expected status, output path, and verification
result. Keep paths readable by truncating only for display, never for
processing.

Configuration options should include: - Batch median vs fixed target. -
Fixed target LUFS. - True-peak ceiling dBTP. - Output directory. - Audio
bitrate. - Audio stream selection. - Linear-only vs allow dynamic
mode. - Gain-up / gain-down limits. - Whether to include subfolders. -
Existing-output behavior. - Report format. - Optional loudness tolerance
for verification.

Do not overwhelm the user with every advanced option at startup. Provide
sensible defaults and an Advanced Settings submenu.

## 8. FFmpeg dependency and Windows distribution

-   Check whether `ffmpeg` and `ffprobe` are available on `PATH`.
-   Display actionable setup guidance if either is missing.
-   Support a user-configured FFmpeg binary path.
-   Do not download or execute binaries without explicit user consent.
-   Keep FFmpeg invocation isolated behind a small adapter so packaging
    or binary discovery can change later.
-   The project should be compatible with packaging as a Windows
    executable using PyInstaller, but the initial development workflow
    must work from a Python virtual environment.
-   Document FFmpeg licensing and distribution considerations. Do not
    bundle FFmpeg binaries by default without reviewing their license
    and build configuration.
-   Do not require Python to be installed on the end user's machine when
    using a correctly packaged PyInstaller build.

## 9. Reliability, security, and performance

-   Use `subprocess.run` with an argument list and `shell=False`.
-   Apply configurable subprocess timeouts where practical.
-   Catch missing executable, permission, invalid-media, disk-full,
    decode, encode, and process-termination errors.
-   Check output-directory writability and available disk space where
    practical.
-   Do not load entire video/audio files into Python memory.
-   Let FFmpeg stream media from disk.
-   Default to sequential processing for predictable resource use;
    optionally allow a small configurable worker count after testing.
-   Make logs useful without leaking unrelated environment information.
-   Ensure cancellation terminates the active FFmpeg process cleanly and
    removes incomplete temporary files.
-   Do not delete source files.
-   Make processing idempotent where possible and avoid duplicate queue
    entries after resolving paths.
-   Use type hints and docstrings for public APIs.
-   Separate business logic from terminal rendering so the normalization
    planner can be tested without a terminal.

## 10. Testing requirements

Use pytest. Include unit tests for: - Median target calculation with
odd/even batch sizes. - Fixed target mode. - Empty batch and all-invalid
batch. - Silent files and unavailable loudness measurements. - True-peak
feasibility calculations. - Gain limits and warning generation. - FFmpeg
JSON parsing when logs include unrelated lines. - Paths with spaces and
Unicode. - Duplicate files and recursive folder discovery. - Existing
output names and no-overwrite behavior. - Command construction and
stream mapping. - Failed FFmpeg process and cleanup of temporary
outputs. - Output verification thresholds. - Ctrl+C / cancellation
behavior where practical.

Integration tests should generate short synthetic audio/video fixtures
with FFmpeg when FFmpeg is installed, and should be skipped with a clear
reason when it is not. Verify that: - output MP4 exists and can be
probed; - video stream is copied where applicable; - audio stream is
present; - duration remains close to the input; - measured output
loudness is near the intended target when feasible; - true peak respects
the configured policy within expected codec/measurement tolerance; -
original input remains unchanged.

Do not make tests depend on external downloads or internet access.

## 11. Documentation

Create a README that includes: - Purpose and limitations. - Python and
FFmpeg prerequisites. - Windows setup and virtual-environment
commands. - How to launch interactive mode. - Examples of
non-interactive CLI usage. - Explanation of LUFS, dBTP, integrated
loudness, true peak, LRA, linear normalization, and dynamic mode. -
Examples of the batch-median and fixed-target workflows. - Output and
report behavior. - Troubleshooting common FFmpeg and codec issues. -
Packaging notes for Windows.

## 12. Definition of done

The first release is complete when: 1. The application launches as an
interactive terminal application on Windows. 2. A user can queue
multiple MP4 files and analyze the entire batch. 3. The default batch
target is calculated from the median of valid integrated loudness
measurements. 4. The application previews its normalization plan before
modifying/exporting anything. 5. It normalizes using FFmpeg `loudnorm`
with a correct measurement-and-processing workflow. 6. True-peak
constraints are respected or explicitly reported as infeasible. 7. The
original video is copied rather than re-encoded by default. 8. Source
files are never overwritten by default. 9. Outputs are re-analyzed and
results are reported. 10. Failures in individual files do not stop the
entire batch. 11. Unit and integration tests cover the key algorithmic
and media-handling paths. 12. The README explains setup, usage,
limitations, and Windows packaging.

## 13. Implementation instructions to the coding agent

Implement in small, verifiable stages: 1. Inspect the repository and
state any existing conventions before changing files. 2. Create the
package skeleton, configuration models, and tests. 3. Implement FFmpeg
discovery and stream probing. 4. Implement and test loudness JSON
parsing. 5. Implement batch target calculation and normalization
planning as pure functions. 6. Implement two-pass processing and
temporary-output handling. 7. Implement post-process verification and
reports. 8. Build the interactive Rich/Typer CLI around the tested
services. 9. Add integration tests and documentation. 10. Run tests, fix
failures, and provide a concise summary of files created, commands run,
test results, and known limitations.

Do not claim a feature or test is complete unless it has actually been
implemented and verified. When a requirement conflicts with FFmpeg
behavior or media-container limitations, explain the trade-off and
implement the safest explicit behavior rather than silently degrading
the output.


## 14. Full-screen terminal UI requirements (important)

The interface must look and behave like a modern terminal application such as Claude Code CLI, not like a classic numbered console menu. Use **Textual** for the main interface. Rich is available underneath Textual for styled rendering, but Rich alone is not the main UI framework.

### Layout
Build a responsive, full-screen TUI with these areas:
- **Header:** app name, version, FFmpeg availability, current operation, and ready/running/error state.
- **Sidebar or settings panel:** queue count, normalization mode, target LUFS, true-peak ceiling, output folder, and processing options.
- **Main panel:** scrollable queue table with filename, duration, source LUFS, source true peak, proposed adjustment, status, progress, and verification result.
- **Activity/log panel:** recent actions, current file, concise warnings, and errors. Allow scrolling and copying/selecting text where terminal support permits.
- **Command/action bar:** persistent input field or action area for commands such as `add`, `folder`, `analyze`, `preview`, `process`, `settings`, `report`, and `quit`.
- **Footer:** context-sensitive keyboard shortcuts and help.

The layout must adapt to narrower terminal sizes without crashing. Hide or collapse secondary panels at small widths and provide a useful minimum-size warning if the terminal is too small.

### Visual style
- Use a restrained dark-terminal aesthetic with clear contrast, subtle borders, and a consistent status palette.
- Use distinct states: queued, analyzing, ready, processing, verified, warning, failed, skipped, and cancelled.
- Use progress bars and spinners for live operations, not simulated progress.
- Show batch summary cards or compact status blocks for queue size, analyzed count, verified count, errors, target LUFS, and true-peak ceiling.
- Use concise human-readable errors with an optional expanded diagnostic view.
- Do not print a stream of raw FFmpeg logs over the interface. Capture them and surface relevant excerpts in the activity panel or a details view.
- Do not claim sample values in the UI are real until the analyzer has measured them. Use `—` or `Not analyzed` for unknown values.

### Interactivity and keyboard controls
Provide consistent keyboard bindings, for example:
- `A`: analyze batch
- `P`: preview normalization plan
- `Enter`: open or confirm the selected action
- `Space`: select/unselect a queue item when applicable
- `R`: retry failed jobs
- `O`: choose/open output directory where supported
- `S`: open settings
- `/` or `:`: focus command input
- `?`: help
- `Q`: quit, with confirmation if jobs are running

Use Textual's `App`, `Screen`, `ModalScreen`, reactive attributes, `DataTable`, `ProgressBar`, `Input`, `Log`, `Footer`, and keyboard bindings as appropriate. Avoid implementing the whole application as one giant UI class; keep business logic in services and the UI as a presentation/controller layer.

### Responsive live processing
- Run blocking FFmpeg work outside the UI event loop using Textual workers or an equivalent safe worker mechanism.
- Marshal worker results back to the UI safely; never mutate widgets from arbitrary background threads.
- Update progress when a file starts, completes analysis, begins processing, finishes verification, or fails.
- FFmpeg may not provide a trustworthy exact percentage for every stage. In that case show an indeterminate spinner or stage indicator instead of inventing a percentage.
- Support cancelling the batch and cancelling the current operation cleanly.
- Keep the dashboard responsive during subprocess execution.
- Add a selected-file details screen or modal showing full path, stream information, measurements, planned action, FFmpeg diagnostic excerpt, and output verification.

### Command input behavior
The command bar should accept simple commands as a convenience, but the primary actions must also be discoverable through visible buttons or keyboard shortcuts. Examples:
- `add <path>`
- `folder <path>`
- `analyze`
- `preview`
- `process`
- `settings`
- `report`
- `retry`
- `help`
- `quit`

Handle quoted paths and paths containing spaces. Validate commands and display helpful usage errors without exiting the app. Keep a small history of commands for the current session only; persistent history is not required.

### TUI testing
- Unit-test command parsing and application services independently from the UI.
- Use Textual's testing utilities (for example, `App.run_test`) to test initial rendering, keyboard bindings, adding files, navigation, settings changes, queue updates, progress/status changes, errors, and cancellation.
- Avoid tests that depend on exact terminal colors or brittle screen coordinates.
- Verify the UI remains usable when the terminal is resized.
- The app must still offer non-interactive command mode for automation and batch scripts, but the default `python -m batch_audio_leveler` launch should open the full-screen TUI.

### Additional definition of done
- The default launch opens the full-screen Textual interface, not a numbered prompt menu.
- The queue and measurements update live as background jobs complete.
- The user can operate the core workflow with keyboard shortcuts and visible actions.
- The activity panel surfaces meaningful progress and actionable errors.
- No long-running FFmpeg process freezes the UI.
- UI tests cover core navigation and at least one simulated analysis/processing lifecycle.
