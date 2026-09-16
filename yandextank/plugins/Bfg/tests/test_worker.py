import sys
import types
from unittest.mock import MagicMock

from yandextank.plugins.Bfg.worker import BFGGreen


def test_bfg_green_skips_ssl_monkey_patch(monkeypatch):
    """BFGGreen must not monkey-patch ssl: requests already imported it.

    Regression test for the recursive ssl import / MonkeyPatchWarning seen when
    running a BFG green worker with a gun that imports ``requests`` (see #891).
    """
    captured = {}

    def fake_patch_all(**kwargs):
        captured.update(kwargs)

    monkey_mod = types.ModuleType("gevent.monkey")
    monkey_mod.patch_all = fake_patch_all
    queue_mod = types.ModuleType("gevent.queue")
    queue_mod.Queue = lambda *args, **kwargs: None
    gevent_mod = types.ModuleType("gevent")
    gevent_mod.monkey = monkey_mod
    gevent_mod.queue = queue_mod
    gevent_mod.spawn = lambda fn: None

    monkeypatch.setitem(sys.modules, "gevent", gevent_mod)
    monkeypatch.setitem(sys.modules, "gevent.monkey", monkey_mod)
    monkeypatch.setitem(sys.modules, "gevent.queue", queue_mod)

    worker = BFGGreen(
        gun=MagicMock(),
        instances=1,
        stpd_filename="dummy",
        green_threads_per_instance=0,
    )
    worker.quit = MagicMock()
    worker.quit.is_set.return_value = True

    worker._worker()

    assert captured.get("thread") is False
    assert captured.get("select") is False
    assert captured.get("ssl") is False
