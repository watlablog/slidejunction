import subprocess
import sys

import slidejunction
from slidejunction import Deck
from slidejunction.cli import main


def test_package_can_be_imported() -> None:
    assert slidejunction.__name__ == "slidejunction"
    assert slidejunction.Deck is Deck


def test_cli_main(capsys) -> None:
    assert main() == 0

    captured = capsys.readouterr()
    assert captured.out == "SlideJunction\n"
    assert captured.err == ""


def test_module_entrypoint() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "slidejunction"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout == "SlideJunction\n"
    assert completed.stderr == ""
