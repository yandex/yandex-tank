import glob
import os
import pytest

from yandextank.core.tankcore import Lock, LockError

TEST_DIR = './test_lock'


def setup_module(module):
    if not os.path.exists(TEST_DIR):
        os.makedirs(TEST_DIR)


def teardown_module(module):
    # clear all .lock files
    for fname in glob.glob(os.path.join(TEST_DIR, Lock.LOCK_FILE_WILDCARD)):
        os.remove(fname)


def setup_function(fn):
    # clear all .lock files
    for fname in glob.glob(os.path.join(TEST_DIR, Lock.LOCK_FILE_WILDCARD)):
        os.remove(fname)


def test_acquire():
    Lock('123', 'tests/123').acquire(TEST_DIR)
    with pytest.raises(LockError):
        Lock('124', 'test/124').acquire(TEST_DIR)


def test_load():
    lock = Lock('123', 'tests/123').acquire(TEST_DIR)
    lock_loaded = Lock.load(lock.lock_file)
    assert lock_loaded.info == lock.info


def test_ignore():
    Lock('123', 'tests/123').acquire(TEST_DIR)
    Lock('124', 'tests/124').acquire(TEST_DIR, ignore=True)
    assert len(glob.glob(os.path.join(TEST_DIR, Lock.LOCK_FILE_WILDCARD))) == 2


def test_release():
    lock = Lock('123', 'tests/123').acquire(TEST_DIR)
    assert len(glob.glob(os.path.join(TEST_DIR, Lock.LOCK_FILE_WILDCARD))) == 1
    lock.release()
    assert len(glob.glob(os.path.join(TEST_DIR, Lock.LOCK_FILE_WILDCARD))) == 0


def test_running_ids():
    Lock('123', 'tests/123').acquire(TEST_DIR)
    Lock('124', 'tests/124').acquire(TEST_DIR, ignore=True)
    assert set(Lock.running_ids(TEST_DIR)) == {'123', '124'}
