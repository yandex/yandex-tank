import os

from yandextank.stepper.main import StepperWrapper


class FakeCore(object):
    artifacts_base_dir = os.path.realpath('.')


def make_wrapper(cache_dir, use_caching):
    wrapper = StepperWrapper(FakeCore(), {})
    wrapper.use_caching = use_caching
    wrapper.cache_dir = cache_dir
    return wrapper


def test_stpd_respects_cache_dir_without_caching(tmp_path):
    wrapper = make_wrapper(str(tmp_path), use_caching=False)
    stpd = wrapper._StepperWrapper__get_stpd_filename()
    assert os.path.dirname(stpd) == str(tmp_path)
    assert os.path.basename(stpd) == 'ammo.stpd'
