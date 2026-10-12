from pathlib import Path
from typer.testing import CliRunner

from batch_audio_leveler.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "batch-audio-leveler" in result.output or "Usage" in result.output


def test_cli_process_help():
    result = runner.invoke(app, ["process", "--help"])
    assert result.exit_code == 0
    assert "--output-dir" in result.output
    assert "--target" in result.output
    assert "--peak" in result.output


def test_cli_process_no_files():
    result = runner.invoke(app, ["process"])
    assert result.exit_code != 0
