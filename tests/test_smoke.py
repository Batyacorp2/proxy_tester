def test_version():
    from proxy_tester import __version__
    assert isinstance(__version__, str) and len(__version__) > 0
