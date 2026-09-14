import glob
import os
import threading
import time
from multiprocessing import Event
from unittest import mock

import pytest
import yaml

from yandextank.common.util import Status
from yandextank.core import tankworker
from yandextank.core.tankcore import Lock, LockError
from yandextank.validator.validator import ValidationError


@pytest.fixture
def lock_dir(tmp_path):
    path = tmp_path / 'lock'
    path.mkdir()
    return str(path)


@pytest.fixture
def artifacts_dir(tmp_path):
    path = tmp_path / 'artifacts'
    path.mkdir()
    return str(path)


@pytest.fixture
def make_worker(tmp_path, lock_dir, artifacts_dir, monkeypatch):
    cfg = tmp_path / 'load.yaml'
    cfg.write_text('phantom: {enabled: false}\n')
    workers = []

    def make(core_options=None, **kwargs):
        options = {'ignore_lock': False, 'ammo_validation': 'skip'}
        options.update(core_options or {})

        def fake_core(configs, interrupted, info, **_):
            core = mock.MagicMock()
            core.artifacts_dir = artifacts_dir
            core.lock_dir = lock_dir
            core.test_id = 'test-1'
            core.errors = []
            core.interrupted = interrupted
            core.get_option.return_value = False
            core.config.get_option.side_effect = lambda section, name: options[name]
            core.wait_for_finish.return_value = 0
            core.plugins_end_test.side_effect = lambda rc: rc
            core.plugins_post_process.side_effect = lambda rc: rc
            return core

        monkeypatch.setattr(tankworker, 'TankCore', fake_core)
        worker = tankworker.TankWorker([str(cfg)], **kwargs)
        workers.append(worker)
        return worker

    yield make
    for worker in workers:
        worker.cleanup()


def lock_files(lock_dir):
    return glob.glob(os.path.join(lock_dir, Lock.LOCK_FILE_WILDCARD))


def finish_status(worker):
    with open(os.path.join(worker.folder, tankworker.TankWorker.FINISH_FILENAME)) as f:
        return yaml.safe_load(f)


def test_run_retcode_chain_and_lock_release(make_worker, lock_dir, monkeypatch):
    monkeypatch.setenv('TANK_UPLOADER_OAUTH_TOKEN', 'old')
    worker = make_worker(data_uploader_oauth_token='token')
    core = worker.core
    seen = {}

    def start_test():
        seen['locks'] = len(lock_files(lock_dir))
        seen['status'] = worker.status

    core.plugins_start_test.side_effect = start_test
    core.wait_for_finish.return_value = 21
    core.plugins_end_test.side_effect = lambda rc: rc + 1
    core.plugins_post_process.side_effect = lambda rc: rc + 1

    worker.run()

    assert seen == {'locks': 1, 'status': Status.TEST_RUNNING}
    core.plugins_end_test.assert_called_once_with(21)
    core.plugins_post_process.assert_called_once_with(22)
    assert worker.retcode == 23
    assert worker.status == Status.TEST_FINISHED
    assert lock_files(lock_dir) == []
    core.plugins_cleanup.assert_called_once_with()
    core.close.assert_called_once_with()
    assert os.environ['TANK_UPLOADER_OAUTH_TOKEN'] == 'token'
    status = finish_status(worker)
    assert status['status_code'] == 'FINISHED'
    assert status['exit_code'] == 23
    assert status['test_id'] == 'test-1'


@pytest.mark.parametrize('method', ['plugins_start_test', 'wait_for_finish'])
def test_run_shooting_exception_fails_test_but_post_processes(make_worker, lock_dir, method):
    worker = make_worker()
    core = worker.core
    getattr(core, method).side_effect = RuntimeError('shooting broke')

    worker.run()

    core.plugins_end_test.assert_called_once_with(1)
    core.plugins_post_process.assert_called_once_with(1)
    assert worker.retcode == 1
    assert worker.status == Status.TEST_FINISHED
    assert 'Test interrupted' in worker.msg
    assert 'shooting broke' in worker.msg
    assert lock_files(lock_dir) == []
    status = finish_status(worker)
    assert status['exit_code'] == 1
    assert 'shooting broke' in status['tank_msg']


@pytest.mark.parametrize(
    'method, plugins_cleaned',
    [
        ('plugins_configure', False),
        ('plugins_prepare_test', True),
        ('plugins_post_process', True),
    ],
)
def test_run_exception_outside_shooting_reraised_with_failed_retcode(make_worker, lock_dir, method, plugins_cleaned):
    worker = make_worker()
    core = worker.core
    getattr(core, method).side_effect = RuntimeError('core broke')

    with pytest.raises(RuntimeError, match='core broke'):
        worker.run()

    assert worker.retcode == 1
    assert worker.status == Status.TEST_FINISHED
    assert core.plugins_start_test.called == (method == 'plugins_post_process')
    assert core.plugins_cleanup.called == plugins_cleaned
    core.close.assert_called_once_with()
    assert lock_files(lock_dir) == []
    status = finish_status(worker)
    assert status['exit_code'] == 1
    assert 'core broke' in status['tank_msg']


def test_run_ammo_validation_failure_stops_before_shooting(make_worker, lock_dir, monkeypatch):
    messages = mock.MagicMock(errors=['bad line'])
    messages.brief.return_value = 'bad ammo'
    monkeypatch.setattr(tankworker, 'validate_ammo', mock.MagicMock(return_value=messages))
    worker = make_worker(core_options={'ammo_validation': 'fail_on_error'})

    with pytest.raises(ValidationError, match='bad ammo'):
        worker.run()

    worker.core.plugins_start_test.assert_not_called()
    assert worker.retcode == 1
    assert finish_status(worker)['exit_code'] == 1
    assert lock_files(lock_dir) == []


def test_run_lock_busy_without_wait_fails(make_worker, lock_dir):
    worker = make_worker()
    # Чужой lock ставим после конструктора, иначе он упадёт ещё в __init__.
    foreign = Lock('other', 'other_dir').acquire(lock_dir)

    with pytest.raises(RuntimeError, match='Lock file present'):
        worker.run()

    worker.core.plugins_configure.assert_not_called()
    assert worker.retcode == 1
    assert 'Lock file(s) found' in worker.msg
    assert lock_files(lock_dir) == [foreign.lock_file]
    assert finish_status(worker)['exit_code'] == 1


def test_run_lock_busy_with_wait_retries_until_free(make_worker, lock_dir, monkeypatch):
    worker = make_worker(wait_lock=True)
    foreign = Lock('other', 'other_dir').acquire(lock_dir)
    sleep = mock.MagicMock(side_effect=lambda _: foreign.release())
    monkeypatch.setattr(tankworker.time, 'sleep', sleep)

    worker.run()

    sleep.assert_called_once_with(5)
    worker.core.plugins_start_test.assert_called_once_with()
    assert worker.retcode == 0
    assert lock_files(lock_dir) == []


def test_run_interrupted_before_lock_fails(make_worker):
    worker = make_worker()
    worker.stop()

    with pytest.raises(KeyboardInterrupt):
        worker.run()

    worker.core.plugins_configure.assert_not_called()
    assert worker.retcode == 1
    assert worker.status == Status.TEST_FINISHED


def test_run_interrupted_while_waiting_for_start_command(make_worker, lock_dir):
    worker = make_worker(run_shooting_event=Event())
    core = worker.core
    statuses = []

    def stop():
        statuses.append(worker.status)
        worker.stop()

    core.plugins_prepare_test.side_effect = lambda: threading.Timer(0.05, stop).start()

    started = time.monotonic()
    worker.run()

    # Остановка во время ожидания должна замечаться быстро, а не через длинный таймаут опроса.
    assert time.monotonic() - started < 2
    assert statuses == [Status.TEST_WAITING_FOR_A_COMMAND_TO_RUN]
    core.plugins_start_test.assert_not_called()
    core.plugins_end_test.assert_called_once_with(1)
    assert worker.retcode == 1
    assert 'Test stopped before shooting started' in worker.msg
    assert lock_files(lock_dir) == []


def test_run_waits_for_start_command(make_worker):
    run_event = Event()
    worker = make_worker(run_shooting_event=run_event)
    statuses = []

    def command():
        statuses.append(worker.status)
        run_event.set()

    worker.core.plugins_prepare_test.side_effect = lambda: threading.Timer(0.05, command).start()

    worker.run()

    assert statuses == [Status.TEST_WAITING_FOR_A_COMMAND_TO_RUN]
    worker.core.plugins_start_test.assert_called_once_with()
    assert worker.retcode == 0


def test_run_core_errors_reach_finish_status(make_worker):
    worker = make_worker()
    core = worker.core

    def post_process(rc):
        # Ошибки ядро дописывает и в post_process — они тоже должны попасть в файл.
        core.errors.append('phantom exited with return code 1.')
        return rc

    core.plugins_post_process.side_effect = post_process

    worker.run()

    assert 'phantom exited with return code 1.' in worker.msg
    assert 'phantom exited with return code 1.' in finish_status(worker)['tank_msg']


def test_run_failing_cleanup_action_does_not_skip_lock_release(make_worker, lock_dir):
    worker = make_worker()
    worker.core.plugins_cleanup.side_effect = RuntimeError('cleanup broke')

    worker.run()

    assert lock_files(lock_dir) == []
    assert 'Exception occurred during cleanup action plugins cleanup' in worker.msg
    worker.core.close.assert_called_once_with()


def test_init_raises_when_locked(make_worker, lock_dir):
    Lock('other', 'other_dir').acquire(lock_dir)

    with pytest.raises(LockError, match='Another test is running'):
        make_worker()


def test_init_ignore_lock_runs_alongside_foreign_lock(make_worker, lock_dir):
    foreign = Lock('other', 'other_dir').acquire(lock_dir)
    worker = make_worker(core_options={'ignore_lock': True})
    seen = []
    worker.core.plugins_start_test.side_effect = lambda: seen.append(len(lock_files(lock_dir)))

    worker.run()

    assert seen == [2]
    assert worker.retcode == 0
    assert lock_files(lock_dir) == [foreign.lock_file]


@pytest.mark.parametrize(
    'mode, errors, raises',
    [
        ('fail_on_error', ['bad line'], True),
        ('FAIL_ON_ERROR', [], False),
        ('inform', ['bad line'], False),
    ],
)
def test_validate_ammo_modes(make_worker, monkeypatch, mode, errors, raises):
    messages = mock.MagicMock(errors=errors)
    messages.brief.return_value = 'bad ammo'
    validate = mock.MagicMock(return_value=messages)
    monkeypatch.setattr(tankworker, 'validate_ammo', validate)
    worker = make_worker(core_options={'ammo_validation': mode})

    if raises:
        with pytest.raises(ValidationError, match='bad ammo'):
            worker._validate_ammo()
    else:
        worker._validate_ammo()
    validate.assert_called_once_with(worker.core.resource_manager, worker.core)


def test_validate_ammo_inform_swallows_validator_crash(make_worker, monkeypatch):
    monkeypatch.setattr(tankworker, 'validate_ammo', mock.MagicMock(side_effect=OSError('no ammo')))
    worker = make_worker(core_options={'ammo_validation': 'inform'})

    worker._validate_ammo()


def test_validate_ammo_skip_does_not_validate(make_worker, monkeypatch):
    validate = mock.MagicMock()
    monkeypatch.setattr(tankworker, 'validate_ammo', validate)
    worker = make_worker(core_options={'ammo_validation': 'skip'})

    worker._validate_ammo()

    validate.assert_not_called()


def test_validate_ammo_unknown_mode(make_worker):
    worker = make_worker(core_options={'ammo_validation': 'sometimes'})

    with pytest.raises(ValidationError, match='Unknown ammo_validation value: sometimes'):
        worker._validate_ammo()


def test_cleanup_runs_all_handlers_and_collects_errors(make_worker):
    worker = make_worker()
    error = RuntimeError('handler broke')
    ok = mock.MagicMock()
    worker._cleanups[:0] = [
        tankworker.CleanupHandler('broken', mock.MagicMock(side_effect=error)),
        tankworker.CleanupHandler('ok', ok),
    ]

    assert worker.cleanup() == [error]
    ok.assert_called_once_with()


def test_save_finish_status_marks_finished(make_worker):
    worker = make_worker()
    worker.status = Status.TEST_RUNNING
    worker.retcode = 21
    worker.add_msgs('first', 'second')
    worker.info.update(['uploader', 'job_no'], 123)
    worker.info.update(['autostop', 'reason'], 'http(5xx, 10%, 5s)')
    worker.info.update(['autostop', 'rc'], 21)

    worker.save_finish_status()

    status = finish_status(worker)
    assert status['status_code'] == 'FINISHED'
    assert status['exit_code'] == 21
    assert status['lunapark_id'] == 123
    assert status['tank_msg'] == 'first\nsecond'
    assert status['autostop'] == {'reason': 'http(5xx, 10%, 5s)', 'rc': 21}
    assert worker.status == Status.TEST_RUNNING


def test_get_status_without_autostop(make_worker):
    status = make_worker().get_status()

    assert status['status_code'] == 'INITIATED'
    assert status['exit_code'] == 0
    assert 'autostop' not in status


def test_get_status_from_parent_sees_child_msgs_and_info(make_worker):
    run_event = Event()
    worker = make_worker(run_shooting_event=run_event)

    def prepare_test():
        worker.info.update(['uploader', 'job_no'], 123)
        worker.info.update(['uploader', 'web_link'], 'https://lunapark/123')
        worker.info.update(['autostop', 'rc'], 21)
        worker.add_msgs('from child')

    worker.core.plugins_prepare_test.side_effect = prepare_test
    # Настоящий дочерний процесс, как в tankapi: пишет он, а статус во время стрельбы читает родитель.
    worker.start()
    try:
        deadline = time.monotonic() + 30
        while worker.status != Status.TEST_WAITING_FOR_A_COMMAND_TO_RUN and time.monotonic() < deadline:
            time.sleep(0.01)
        status = worker.get_status()
    finally:
        run_event.set()
        worker.join(30)

    assert status['status_code'] == 'WAITING_FOR_A_COMMAND_TO_RUN'
    assert status['lunapark_id'] == 123
    assert status['lunapark_url'] == 'https://lunapark/123'
    assert status['autostop'] == {'rc': 21}
    assert status['tank_msg'] == 'from child'
    assert worker.exitcode == 0


def test_combine_configs_order_and_default_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'load.yaml').write_text('core: {debug: true}\n')

    combined = tankworker.TankWorker._combine_configs(
        [], ['phantom.instances=200'], ['{core: {lock_dir: /tmp}}'], [{'cli': 1}]
    )

    assert combined == [
        {'core': {'debug': True}},
        {'phantom': {'package': 'yandextank.plugins.Phantom', 'instances': 200}},
        {'core': {'lock_dir': '/tmp'}},
        {'cli': 1},
    ]


def test_load_cfg_rejects_non_dict_yaml(tmp_path):
    cfg = tmp_path / 'load.yaml'
    cfg.write_text('- just\n- a list\n')

    with pytest.raises(ValidationError, match='should be a yaml'):
        tankworker.load_cfg(str(cfg))


def test_parse_and_check_patches_rejects_non_dict():
    assert tankworker.parse_and_check_patches(['{core: {debug: true}}']) == [{'core': {'debug': True}}]
    with pytest.raises(ValidationError, match='should be a dict'):
        tankworker.parse_and_check_patches(['- a'])


@pytest.mark.parametrize('option', ['phantom.instances', 'instances=200'])
def test_parse_options_rejects_malformed_option(option):
    with pytest.raises(ValidationError, match=option):
        tankworker.parse_options([option])


@pytest.mark.parametrize(
    'name, content, expected',
    [
        ('load.yaml', '[tank]\nkey = value\n', False),
        ('load.json', '[tank]\nkey = value\n', False),
        ('load.ini', '[tank]\nkey = value\n', True),
        ('load.conf', 'key: value\n', False),
    ],
    ids=['yaml-ext', 'json-ext', 'ini-section', 'no-section-header'],
)
def test_is_ini(tmp_path, name, content, expected):
    cfg = tmp_path / name
    cfg.write_text(content)

    assert tankworker.is_ini(str(cfg)) is expected
