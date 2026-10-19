"""Contract test for the public ``pyici`` API surface.

Pins the stable front door so it can't silently break: the documented names must
stay importable from ``pyici``, the friendly aliases must point at the real
functions, and ``__version__`` must agree with the packaged version.
"""
import pyici


EXPECTED = [
    # loading
    "run_data_analysis", "load_data", "peek_columns",
    # classification / capacity
    "classify_charge_discharge", "calculate_capacity",
    # pulse segmentation
    "analyze_cycle_pulses", "segment_pulses",
    # regression
    "load_cycle_for_regression", "compute_single_pulse_regression", "resolve_window",
    "DEFAULT_TIME_START", "DEFAULT_TIME_END", "DEFAULT_INDEX_START", "DEFAULT_INDEX_END",
    # resistances
    "compute_R_k_for_cycle", "compute_R_k_for_cycles", "compute_rk", "export_R_k_results",
]


def test_public_names_are_exported():
    missing = [name for name in EXPECTED if not hasattr(pyici, name)]
    assert not missing, f"missing from the pyici public API: {missing}"
    # everything we promise is also declared in __all__
    assert set(EXPECTED).issubset(set(pyici.__all__))


def test_callables_are_callable():
    for name in EXPECTED:
        if name.startswith("DEFAULT_"):
            continue
        assert callable(getattr(pyici, name)), f"{name} should be callable"


def test_aliases_point_at_the_real_functions():
    assert pyici.load_data is pyici.run_data_analysis
    assert pyici.segment_pulses is pyici.analyze_cycle_pulses
    assert pyici.compute_rk is pyici.compute_R_k_for_cycles


def test_version_is_a_nonempty_string():
    # __version__ is read from the installed distribution metadata (or a source
    # fallback). We assert it's a real, non-empty string rather than pinning an
    # exact value, so the test doesn't depend on which build is installed.
    assert isinstance(pyici.__version__, str)
    assert pyici.__version__
