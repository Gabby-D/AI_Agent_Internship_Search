from internship_search.cli import main


def test_version_command_runs(capsys):
    exit_code = main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "0.1.0"
