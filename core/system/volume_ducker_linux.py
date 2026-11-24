import os
import re
import shutil
import subprocess
import threading

try:
    import pulsectl
    _HAS_PULSECTL = True
except ImportError:
    pulsectl = None
    _HAS_PULSECTL = False

_SKIP_BINARIES = ("akira", "python", "pycharm")


class VolumeDucker:
    """
    Приглушение фоновых аудиопотоков на Linux (PulseAudio / PipeWire-Pulse).
    Использует pulsectl (если установлен) или pactl list sink-inputs / set-sink-input-volume.
    """

    def __init__(self):
        self.saved_volumes = {}
        self._lock = threading.Lock()
        self._duck_count = 0
        self._pactl_path = shutil.which("pactl")

    @staticmethod
    def _should_skip_stream(pid_str: str, binary: str, app_name: str, current_pid: int) -> bool:
        try:
            if pid_str and int(pid_str) == current_pid:
                return True
        except ValueError:
            pass
        combined = f"{binary} {app_name}".lower()
        return any(tok in combined for tok in _SKIP_BINARIES)

    def _duck_via_pulsectl(self, factor: float) -> bool:
        if not _HAS_PULSECTL:
            return False
        current_pid = os.getpid()
        with pulsectl.Pulse("akira-volume-ducker") as pulse:
            for si in pulse.sink_input_list():
                props = getattr(si, "proplist", {}) or {}
                pid_str = str(props.get("application.process.id", ""))
                binary = str(props.get("application.process.binary", ""))
                app_name = str(props.get("application.name", getattr(si, "name", "")))
                if self._should_skip_stream(pid_str, binary, app_name, current_pid):
                    continue
                cur_vol = float(getattr(si.volume, "value_flat", 1.0))
                if si.index not in self.saved_volumes:
                    self.saved_volumes[si.index] = cur_vol
                orig_vol = self.saved_volumes[si.index]
                pulse.volume_set_all_chans(si, max(0.01, min(1.5, orig_vol * factor)))
        return True

    def _restore_via_pulsectl(self) -> bool:
        if not _HAS_PULSECTL:
            return False
        with pulsectl.Pulse("akira-volume-ducker") as pulse:
            for si in pulse.sink_input_list():
                if si.index in self.saved_volumes:
                    try:
                        pulse.volume_set_all_chans(si, self.saved_volumes[si.index])
                    except Exception:
                        pass
        self.saved_volumes.clear()
        return True

    def _list_pactl_sink_inputs(self) -> list[dict]:
        if not self._pactl_path:
            self._pactl_path = shutil.which("pactl")
        if not self._pactl_path:
            return []
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        res = subprocess.run(
            [self._pactl_path, "list", "sink-inputs"],
            capture_output=True,
            text=True,
            env=env,
            timeout=2.0,
        )
        if res.returncode != 0:
            return []

        items = []
        cur = None
        for line in res.stdout.splitlines():
            m_id = re.match(r"^Sink Input #(\d+)", line.strip())
            if m_id:
                if cur:
                    items.append(cur)
                cur = {"id": int(m_id.group(1)), "vol_pct": 100, "pid": "", "binary": "", "name": ""}
                continue
            if not cur:
                continue
            s = line.strip()
            if s.startswith("Volume:"):
                pct_matches = re.findall(r"(\d+)%", s)
                if pct_matches:
                    cur["vol_pct"] = int(pct_matches[0])
            elif s.startswith("application.process.id"):
                m = re.search(r'"([^"]*)"', s)
                if m:
                    cur["pid"] = m.group(1)
            elif s.startswith("application.process.binary"):
                m = re.search(r'"([^"]*)"', s)
                if m:
                    cur["binary"] = m.group(1)
            elif s.startswith("application.name"):
                m = re.search(r'"([^"]*)"', s)
                if m:
                    cur["name"] = m.group(1)
        if cur:
            items.append(cur)
        return items

    def _duck_via_pactl(self, factor: float):
        inputs = self._list_pactl_sink_inputs()
        if not inputs or not self._pactl_path:
            return
        current_pid = os.getpid()
        for item in inputs:
            if self._should_skip_stream(item["pid"], item["binary"], item["name"], current_pid):
                continue
            idx = item["id"]
            if idx not in self.saved_volumes:
                self.saved_volumes[idx] = item["vol_pct"]
            orig_pct = self.saved_volumes[idx]
            target_pct = max(1, min(150, int(round(orig_pct * factor))))
            try:
                subprocess.run(
                    [self._pactl_path, "set-sink-input-volume", str(idx), f"{target_pct}%"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                )
            except Exception:
                pass

    def _restore_via_pactl(self):
        if not self._pactl_path:
            self._pactl_path = shutil.which("pactl")
        if not self._pactl_path:
            self.saved_volumes.clear()
            return
        for idx, orig_pct in list(self.saved_volumes.items()):
            pct_val = int(round(orig_pct * 100)) if isinstance(orig_pct, float) and orig_pct <= 1.5 else int(orig_pct)
            try:
                subprocess.run(
                    [self._pactl_path, "set-sink-input-volume", str(idx), f"{max(0, min(150, pct_val))}%"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.5,
                )
            except Exception:
                pass
        self.saved_volumes.clear()

    def _duck_async(self, factor=0.05):
        try:
            if not self._duck_via_pulsectl(factor):
                self._duck_via_pactl(factor)
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}", flush=True)

    def duck(self, factor=0.05):
        with self._lock:
            self._duck_count += 1
            if self._duck_count == 1:
                threading.Thread(target=self._duck_async, args=(factor,), daemon=True).start()
            try:
                from core.system.actions import ym_manager
                ym_manager.duck(factor)
            except Exception:
                pass

    def _restore_async(self):
        if not self.saved_volumes:
            return
        try:
            if not self._restore_via_pulsectl():
                self._restore_via_pactl()
        except Exception as e:
            print(f"[Volume Ducker Error]: {e}", flush=True)

    def restore(self):
        with self._lock:
            if self._duck_count > 0:
                self._duck_count -= 1
            if self._duck_count == 0:
                threading.Thread(target=self._restore_async, daemon=True).start()
                try:
                    from core.system.actions import ym_manager
                    ym_manager.unduck()
                except Exception:
                    pass

    def force_restore(self):
        with self._lock:
            self._duck_count = 0
            threading.Thread(target=self._restore_async, daemon=True).start()
            try:
                from core.system.actions import ym_manager
                ym_manager.unduck()
            except Exception:
                pass
