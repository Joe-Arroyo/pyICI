"""F17: the loader must read non-UTF-8 cycler files (Windows-1252 / Latin-1),
not just UTF-8, instead of raising UnicodeDecodeError on load.

A tiny tab-delimited table whose header carries the micro sign (µ): in cp1252
that is byte 0xB5, which is NOT valid UTF-8 on its own, so a UTF-8-only reader
raises UnicodeDecodeError on this file.
"""
import pandas as pd
import pytest

from analysis import data_loader as dl

_HEADER = "t/s\tE/V\tI/\u00b5A"          # µ = U+00B5
_ROWS = ["0.0\t3.00\t10", "1.0\t3.05\t10", "2.0\t3.07\t0"]
_TEXT = "\n".join([_HEADER] + _ROWS) + "\n"


def _write(path, encoding):
    path.write_bytes(_TEXT.encode(encoding))
    return str(path)


def test_detect_encoding_utf8(tmp_path):
    p = _write(tmp_path / "utf8.txt", "utf-8")
    assert dl._detect_encoding(p) in ("utf-8", "utf-8-sig")


def test_detect_encoding_cp1252(tmp_path):
    # µ (0xB5) is invalid UTF-8, so detection must fall back past utf-8 to cp1252
    p = _write(tmp_path / "cp1252.txt", "cp1252")
    assert dl._detect_encoding(p) == "cp1252"


def test_cp1252_file_loads_and_matches_utf8(tmp_path):
    p_utf8 = _write(tmp_path / "u.txt", "utf-8")
    p_cp = _write(tmp_path / "c.txt", "cp1252")

    d_utf8, _, enc_utf8 = dl.inspect_data_file(p_utf8)
    d_cp, _, enc_cp = dl.inspect_data_file(p_cp)

    df_utf8 = dl._read_table(p_utf8, d_utf8, enc_utf8)
    df_cp = dl._read_table(p_cp, d_cp, enc_cp)      # raised UnicodeDecodeError before F17

    pd.testing.assert_frame_equal(df_utf8, df_cp)
    assert "I/\u00b5A" in df_cp.columns


def test_peek_columns_cp1252(tmp_path):
    p_cp = _write(tmp_path / "peek.txt", "cp1252")
    cols = dl.peek_columns(p_cp)
    assert "I/\u00b5A" in cols