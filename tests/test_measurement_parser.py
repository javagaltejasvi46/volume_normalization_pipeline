from pathlib import Path

from batch_audio_leveler.ffmpeg.analyzer import parse_loudnorm_output


def test_parse_valid_loudnorm_with_surrounding_noise():
    stderr_sample = """
ffmpeg version 7.1-essentials_build-www.gyan.dev Copyright (c) 2000-2024
configuration: --enable-gpl
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'sample.mp4':
  Duration: 00:01:23.45, start: 0.000000, bitrate: 1200 kb/s
    Stream #0:0[0x1](und): Video: h264
    Stream #0:1[0x2](und): Audio: aac
Stream mapping:
  Stream #0:1 -> #0:0
[Parsed_loudnorm_0 @ 000001b4e0c6e900] 
{
	"input_i" : "-21.45",
	"input_tp" : "-3.20",
	"input_lra" : "6.80",
	"input_thresh" : "-31.90",
	"output_i" : "-16.02",
	"output_tp" : "-1.50",
	"output_lra" : "6.50",
	"output_thresh" : "-26.40",
	"normalization_type" : "linear",
	"target_offset" : "0.02"
}
[out#0/null @ 000001b4e0c5bfc0] video:0KiB audio:750KiB subtitle:0KiB other streams:0KiB
size=N/A time=00:01:23.45 bitrate=N/A speed=45.2x
"""
    m = parse_loudnorm_output(stderr_sample, Path("sample.mp4"), stream_index=1)

    assert m.measurement_valid is True
    assert m.is_silent is False
    assert m.integrated_lufs == -21.45
    assert m.true_peak_dbtp == -3.20
    assert m.loudness_range_lu == 6.80
    assert m.threshold_lufs == -31.90
    assert m.target_offset == 0.02
    assert m.audio_stream_index == 1


def test_parse_silent_audio():
    stderr_sample = """
[Parsed_loudnorm_0 @ 00000239710ead00] 
{
	"input_i" : "-inf",
	"input_tp" : "-inf",
	"input_lra" : "0.00",
	"input_thresh" : "-70.00",
	"output_i" : "-inf",
	"output_tp" : "-inf",
	"output_lra" : "0.00",
	"output_thresh" : "-70.00",
	"normalization_type" : "linear",
	"target_offset" : "inf"
}
"""
    m = parse_loudnorm_output(stderr_sample, Path("silent.mp4"))

    assert m.measurement_valid is False
    assert m.is_silent is True
    assert m.integrated_lufs is None
    assert m.true_peak_dbtp is None


def test_parse_near_silent_audio():
    stderr_sample = """
[Parsed_loudnorm_0 @ 00000239710ead00] 
{
	"input_i" : "-74.50",
	"input_tp" : "-65.00",
	"input_lra" : "0.00",
	"input_thresh" : "-84.00",
	"output_i" : "-70.00",
	"output_tp" : "-60.00",
	"output_lra" : "0.00",
	"output_thresh" : "-80.00",
	"normalization_type" : "linear",
	"target_offset" : "0.00"
}
"""
    m = parse_loudnorm_output(stderr_sample, Path("near_silent.mp4"))

    assert m.measurement_valid is False
    assert m.is_silent is True


def test_parse_corrupted_output_no_json():
    stderr_sample = "ffmpeg: invalid option or stream error occurred"
    m = parse_loudnorm_output(stderr_sample, Path("corrupt.mp4"))

    assert m.measurement_valid is False
    assert m.is_silent is False
    assert m.integrated_lufs is None


def test_parse_none_or_empty_stderr():
    m_none = parse_loudnorm_output(None, Path("none.mp4"))
    assert m_none.measurement_valid is False
    assert m_none.is_silent is False
    assert m_none.integrated_lufs is None

    m_empty = parse_loudnorm_output("", Path("empty.mp4"))
    assert m_empty.measurement_valid is False
    assert m_empty.is_silent is False
    assert m_empty.integrated_lufs is None
