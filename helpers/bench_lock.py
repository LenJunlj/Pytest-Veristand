# -*- coding: utf-8 -*-
"""台架互斥锁：跨进程文件锁（Windows 适用）

原则：
- 原子创建（O_CREAT|O_EXCL）保证同一时刻只有一个使用者拿到锁；
- 锁文件记录 PID/机器/用户/时间，占用冲突时直接告诉用户"谁占着台架"；
- 陈锁（持有进程已死，或超过 stale_after_s 未释放）自动清理，不会永久锁死台架。

注意：锁保护的是"台架"这个共享资源。台架机本机 + CI（同机 runner）天然覆盖；
远程开发机如走共享盘路径也能参与，否则按 README 的约定"远程只附加、只读"。
"""
import ctypes
import json
import os
import time


class LockBusy(RuntimeError):
    """台架被占用。"""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        return bool(ok) and exit_code.value == STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


class BenchLock:
    def __init__(self, path, stale_after_s=43200):
        self.path = path
        self.stale_after_s = stale_after_s
        self._fd = None

    def acquire(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        for _attempt in range(2):        # 第 2 轮只在清掉陈锁后重试
            try:
                self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, json.dumps({
                    "pid": os.getpid(),
                    "machine": os.environ.get("COMPUTERNAME", "?"),
                    "user": os.environ.get("USERNAME", "?"),
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                }, ensure_ascii=False).encode("utf-8"))
                return self
            except FileExistsError:
                holder = self._read_holder()
                if holder and self._is_stale(holder):
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                    continue
                raise LockBusy(
                    f"台架正被占用: {holder or '未知持有者'}（锁文件 {self.path}）。"
                    f"如确认无人使用，可手动删除该锁文件。")
        raise LockBusy(f"无法获取台架锁（清理陈锁后仍失败）：{self.path}")

    def _read_holder(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _is_stale(self, holder):
        # 进程已死 → 陈锁；或持有超过 stale_after_s → 陈锁
        try:
            if not _pid_alive(int(holder.get("pid", 0))):
                return True
        except (TypeError, ValueError):
            return True
        try:
            taken = time.mktime(time.strptime(holder["time"], "%Y-%m-%d %H:%M:%S"))
            if time.time() - taken > self.stale_after_s:
                return True
        except Exception:
            pass
        return False

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
                try:
                    os.remove(self.path)
                except OSError:
                    pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
