# -*- coding: utf-8 -*-
"""bench_lock 单元测试：不需要台架，任何机器可跑（pytest -m "not hil"）"""
import json

import pytest

from helpers.bench_lock import BenchLock, LockBusy


@pytest.fixture
def lock(tmp_path):
    return BenchLock(str(tmp_path / "bench.lock"), stale_after_s=3600)


def test_acquire_release_cycle(lock):
    lock.acquire()
    lock.release()
    lock.acquire()          # 释放后可立即重拿
    lock.release()


def test_second_acquire_rejected(lock):
    lock.acquire()
    with pytest.raises(LockBusy):
        BenchLock(lock.path).acquire()
    lock.release()


def test_stale_lock_cleaned(tmp_path):
    path = str(tmp_path / "bench.lock")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"pid": 99999999, "machine": "X", "user": "Y",
                   "time": "2000-01-01 00:00:00"}, f)
    lk = BenchLock(path, stale_after_s=3600)
    lk.acquire()            # 死 PID + 陈旧时间 → 自动清理并获取
    lk.release()
