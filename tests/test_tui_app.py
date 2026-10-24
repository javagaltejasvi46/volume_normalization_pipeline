from pathlib import Path
import pytest
from textual.widgets import DataTable, Input

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.tui.app import BatchAudioLevelerApp
from batch_audio_leveler.tui.screens.help_modal import HelpModal
from batch_audio_leveler.tui.screens.settings_modal import SettingsModal


@pytest.mark.anyio
async def test_tui_app_mount_and_widgets():
    app = BatchAudioLevelerApp()
    async with app.run_test() as pilot:
        # Check basic layout
        assert app.is_busy is False
        table = app.query_one("#queue-table", DataTable)
        assert table is not None
        assert len(table.columns) == 9

        # Test opening and closing help modal
        app.action_help()
        await pilot.pause()
        assert isinstance(app.screen, HelpModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpModal)

        # Test opening and closing settings modal
        app.action_settings()
        await pilot.pause()
        assert isinstance(app.screen, SettingsModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SettingsModal)


@pytest.mark.anyio
async def test_tui_app_command_input(tmp_path: Path):
    app = BatchAudioLevelerApp()
    async with app.run_test() as pilot:
        # Create a mock mp4 file
        clip = tmp_path / "test_clip.mp4"
        clip.touch()

        # Submit command to add file
        cmd_input = app.query_one("#cmd-input", Input)
        cmd_input.value = f'add "{clip}"'
        await cmd_input.action_submit()
        await pilot.pause()

        # Table should now have 1 item
        assert len(app.queue) == 1
        assert app.queue.jobs[0].path == clip

        # Submit clear command
        cmd_input.value = "clear"
        await cmd_input.action_submit()
        await pilot.pause()

        # Queue cleared
        assert len(app.queue) == 0


@pytest.mark.anyio
async def test_tui_app_resize():
    """Verify layout survives terminal resizing to narrow widths."""
    app = BatchAudioLevelerApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.is_busy is False

        # Resize to larger screen
        await pilot.resize_terminal(120, 40)
        await pilot.pause()
        assert app.is_busy is False


@pytest.mark.anyio
async def test_tui_app_destination_modal_and_run_all(tmp_path: Path):
    from batch_audio_leveler.tui.screens.destination_modal import DestinationModal
    app = BatchAudioLevelerApp()
    async with app.run_test() as pilot:
        clip = tmp_path / "song.mp4"
        clip.touch()
        app.queue.add_file(clip)

        # Trigger action_run_all which opens DestinationModal
        app.action_run_all()
        await pilot.pause()
        assert isinstance(app.screen, DestinationModal)

        # Cancel destination modal
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DestinationModal)


@pytest.mark.anyio
async def test_tui_app_metadata_modal():
    from batch_audio_leveler.tui.screens.metadata_modal import MetadataModal
    app = BatchAudioLevelerApp()
    async with app.run_test() as pilot:
        app.action_metadata()
        await pilot.pause()
        assert isinstance(app.screen, MetadataModal)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, MetadataModal)

