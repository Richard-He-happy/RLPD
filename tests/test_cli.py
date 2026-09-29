from rlpd.cli import main


def test_cli_version(capsys):
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0
    assert "rlpd 0.1.0" in capsys.readouterr().out
