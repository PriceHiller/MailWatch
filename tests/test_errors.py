from mailwatch.errors import ShutdownRequested


def test_shutdown_requested_is_an_exception() -> None:
    assert issubclass(ShutdownRequested, Exception)
