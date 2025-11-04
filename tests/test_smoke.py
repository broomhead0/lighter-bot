def test_imports():
    import core.main  # noqa: F401
    import modules.maker_engine  # noqa: F401
    import modules.market_data_listener  # noqa: F401
    import modules.telemetry  # noqa: F401

    assert True
