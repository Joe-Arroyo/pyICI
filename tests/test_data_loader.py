"""Characterization test for data_loader.run_data_analysis (data-in / result-out)."""
from analysis.data_loader import run_data_analysis


def _write(tmp_path, text):
    p = tmp_path / "test.txt"
    p.write_text(text, encoding="utf-8")
    return p


def test_run_data_analysis_multicycle(tmp_path):
    _write(tmp_path,
        "cycle\tt/s\tE/V\tI/mA\n"
        "1\t0\t3.00\t10\n"
        "1\t1\t3.10\t10\n"
        "1\t2\t3.10\t0\n"
        "1\t3\t3.09\t0\n")
    result = run_data_analysis(str(tmp_path), "test.txt")
    assert result is not None
    assert list(result.df_raw.columns) == ["cycle", "t/s", "E/V", "I/mA"]
    assert result.cycle_list == [1]
    assert result.data_format == "multi_cycle"
    assert 1 in result.ici_starts


def test_run_data_analysis_missing_file_returns_none(tmp_path):
    assert run_data_analysis(str(tmp_path), "does_not_exist.txt") is None