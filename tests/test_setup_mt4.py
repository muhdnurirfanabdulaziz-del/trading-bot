from pathlib import Path

from setup_mt4 import find_terminals, install_ea, set_config_files_dir


def make_terminal(base: Path, name: str) -> Path:
    t = base / "MetaQuotes" / "Terminal" / name
    (t / "MQL4" / "Experts").mkdir(parents=True)
    (t / "MQL4" / "Files").mkdir(parents=True)
    return t


class TestSetup:
    def test_finds_only_real_terminals(self, tmp_path):
        make_terminal(tmp_path, "ABC123")
        # a folder without MQL4 (e.g. the Community subfolder) is skipped
        (tmp_path / "MetaQuotes" / "Terminal" / "Help").mkdir(parents=True)
        found = find_terminals(appdata=str(tmp_path))
        assert [t.name for t in found] == ["ABC123"]

    def test_no_metaquotes_dir(self, tmp_path):
        assert find_terminals(appdata=str(tmp_path)) == []

    def test_install_copies_ea(self, tmp_path):
        t = make_terminal(tmp_path, "ABC123")
        dest = install_ea(t)
        assert dest.exists()
        assert dest.name == "ICTBridge.mq4"
        assert "InpEnableTrading" in dest.read_text()

    def test_config_rewrite_targets_assignment_not_comment(self, tmp_path):
        cfg = tmp_path / "config.py"
        cfg.write_text(
            '# example: MT4_FILES_DIR = r"C:\\old\\path"\n'
            'MT4_FILES_DIR = ""\n'
            'MT4_MAX_LOTS = 5.0\n')
        target = tmp_path / "MQL4" / "Files"
        set_config_files_dir(target, config_path=cfg)
        text = cfg.read_text()
        assert f'MT4_FILES_DIR = r"{target}"' in text
        assert '# example: MT4_FILES_DIR = r"C:\\old\\path"' in text
        assert 'MT4_MAX_LOTS = 5.0' in text
        # the file must still be valid Python
        compile(text, "config.py", "exec")
