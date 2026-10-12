from batch_audio_leveler.tui.command_parser import CommandHistory, parse_command_line


def test_parse_simple_command():
    cmd = parse_command_line("analyze")
    assert cmd is not None
    assert cmd.action == "analyze"
    assert cmd.args == []


def test_parse_command_with_slash_and_colon():
    cmd1 = parse_command_line("/help")
    assert cmd1 is not None
    assert cmd1.action == "help"

    cmd2 = parse_command_line(":quit")
    assert cmd2 is not None
    assert cmd2.action == "quit"


def test_parse_quoted_paths_and_spaces():
    cmd = parse_command_line('add "C:\\My Videos\\vacation clip.mp4"')
    assert cmd is not None
    assert cmd.action == "add"
    assert len(cmd.args) == 1
    assert cmd.args[0] == "C:\\My Videos\\vacation clip.mp4"


def test_parse_folder_command():
    cmd = parse_command_line('folder "D:\\Media Files"')
    assert cmd is not None
    assert cmd.action == "folder"
    assert cmd.args[0] == "D:\\Media Files"


def test_parse_empty_line():
    assert parse_command_line("") is None
    assert parse_command_line("   ") is None
    assert parse_command_line("/") is None


def test_command_history():
    hist = CommandHistory(max_size=5)
    hist.add("analyze")
    hist.add("process")

    # Up arrow (previous)
    assert hist.previous() == "process"
    assert hist.previous() == "analyze"
    # Reached top
    assert hist.previous() == "analyze"

    # Down arrow (next)
    assert hist.next() == "process"
    assert hist.next() == ""
