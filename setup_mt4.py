"""One-shot MT4 setup. Run this ON THE LAPTOP that has MT4 installed:

    python setup_mt4.py

It finds your MT4 terminal data folder(s), copies the US30 Sentinel EA into
MQL4\\Experts, tries to compile it with MetaEditor, and points
MT4_FILES_DIR in config.py at the right folder. The only steps it cannot
do (MT4 allows them only by hand, by design) are printed at the end:
attaching the EA to your US30 M5 chart and enabling live trading.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
EA_SOURCE = REPO / "mt4" / "US30Sentinel.mq4"
CONFIG = REPO / "config.py"


def find_terminals(appdata: str | None = None) -> list[Path]:
    """MT4 data folders live under %APPDATA%\\MetaQuotes\\Terminal\\<id>\\
    and are recognisable by their MQL4 subfolder. Newest first."""
    base = Path(appdata or os.environ.get("APPDATA", "")) \
        / "MetaQuotes" / "Terminal"
    if not base.is_dir():
        return []
    found = [d for d in base.iterdir() if (d / "MQL4").is_dir()]
    return sorted(found, key=lambda d: d.stat().st_mtime, reverse=True)


def install_ea(terminal: Path) -> Path:
    experts = terminal / "MQL4" / "Experts"
    experts.mkdir(parents=True, exist_ok=True)
    dest = experts / EA_SOURCE.name
    shutil.copy2(EA_SOURCE, dest)
    return dest


def find_metaeditor(terminal: Path) -> Path | None:
    """origin.txt in the data folder names the install dir (UTF-16)."""
    origin = terminal / "origin.txt"
    if not origin.exists():
        return None
    for encoding in ("utf-16", "utf-8"):
        try:
            install_dir = Path(origin.read_text(encoding=encoding).strip())
            break
        except (UnicodeError, UnicodeDecodeError):
            continue
    else:
        return None
    for name in ("metaeditor.exe", "metaeditor64.exe"):
        exe = install_dir / name
        if exe.exists():
            return exe
    return None


def compile_ea(metaeditor: Path, ea_path: Path) -> bool:
    try:
        subprocess.run([str(metaeditor), f"/compile:{ea_path}"],
                       timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return ea_path.with_suffix(".ex4").exists()


def set_config_files_dir(files_dir: Path, config_path: Path = CONFIG) -> None:
    text = config_path.read_text()
    new = re.sub(r"(?m)^MT4_FILES_DIR\s*=.*$",
                 f'MT4_FILES_DIR = r"{files_dir}"', text, count=1)
    config_path.write_text(new)


def pick(terminals: list[Path]) -> Path:
    if len(terminals) == 1:
        return terminals[0]
    print("Multiple MT4 terminals found:")
    for i, t in enumerate(terminals, 1):
        print(f"  {i}. {t}")
    while True:
        answer = input(f"Which one runs US30? [1-{len(terminals)}, "
                       f"Enter for 1]: ").strip() or "1"
        if answer.isdigit() and 1 <= int(answer) <= len(terminals):
            return terminals[int(answer) - 1]


def main() -> int:
    if not EA_SOURCE.exists():
        print(f"EA source not found at {EA_SOURCE} - run from the repo root.")
        return 1

    terminals = find_terminals()
    if not terminals:
        print("No MT4 data folder found under %APPDATA%\\MetaQuotes\\Terminal.")
        print("Is MT4 installed on this machine? (Run this script on the "
              "laptop with MT4, not elsewhere.)")
        return 1

    terminal = pick(terminals)
    print(f"\nUsing terminal: {terminal}")

    dest = install_ea(terminal)
    print(f"1. EA installed  -> {dest}")

    metaeditor = find_metaeditor(terminal)
    if metaeditor and compile_ea(metaeditor, dest):
        print("2. EA compiled   -> US30Sentinel.ex4 ready")
    else:
        print("2. Could not auto-compile. Either restart MT4 (it compiles "
              "sources on startup) or open MetaEditor (F4), open "
              "US30Sentinel.mq4 and press Compile.")

    files_dir = terminal / "MQL4" / "Files"
    files_dir.mkdir(parents=True, exist_ok=True)
    set_config_files_dir(files_dir)
    print(f"3. config.py     -> MT4_FILES_DIR = {files_dir}")

    print("""
Remaining steps (MT4 only allows these by hand):
  4. In MT4: open the US30 chart, set timeframe to M5.
  5. Drag 'US30Sentinel' from Navigator > Expert Advisors onto the chart;
     in the dialog tick 'Allow live trading' on the Common tab.
     Leave InpEnableTrading = false for the first (dry-run) session.
  6. Make sure the AutoTrading toolbar button is ON (green).
  7. Run the bot:  python main.py --mt4
  8. When you're happy with the dry run ON A DEMO ACCOUNT, re-attach
     the EA with InpEnableTrading = true.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
