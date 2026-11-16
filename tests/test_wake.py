from ecoflow_nut.wake import WAKE_FOR, WakeFile, main
from tests.factories import at


def test_a_wake_lasts_wake_for(tmp_path):
    wake = WakeFile(tmp_path / "data" / "wake-until")
    assert not wake.active(at(0))
    until = wake.start(at(0))
    assert until == at(0) + WAKE_FOR
    assert wake.active(until - WAKE_FOR / 2)
    assert not wake.active(until)


def test_cancel_and_a_garbled_file_mean_no_wake(tmp_path):
    wake = WakeFile(tmp_path / "wake-until")
    wake.start(at(0))
    wake.cancel()
    assert wake.until() is None
    wake.cancel()
    (tmp_path / "wake-until").write_text("not a date")
    assert not wake.active(at(0))


def test_the_command_starts_and_cancels(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WAKE_FILE", str(tmp_path / "wake-until"))
    assert main([]) == 0
    assert (tmp_path / "wake-until").exists()
    assert "on line until" in capsys.readouterr().out
    assert main(["--cancel"]) == 0
    assert not (tmp_path / "wake-until").exists()
