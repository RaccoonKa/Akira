"""
Linux-реализация ZapretManager (Linux Mint / Ubuntu):
Управление системной службой zapret (systemd) или нативным nfqws + nftables/iptables через pkexec.
"""

import os
import shlex
import shutil
import subprocess
import tempfile
import time
import psutil
from core.utils.config import load_config


class ZapretManager:
    STRATEGIES = [
        {
            "name": "Системная служба zapret (автоконфиг /opt/zapret)",
            "mode": "service",
            "args": [],
        },
        {
            "name": "nfqws: Универсальный обход (Fake + Split2 для HTTPS/QUIC)",
            "mode": "nfqws",
            "args": [
                "--dpi-desync=fake,split2",
                "--dpi-desync-repeats=6",
                "--dpi-desync-fooling=badseq",
                "--dpi-desync-fake-tls=0x00000000",
            ],
        },
        {
            "name": "nfqws: Multisplit (YouTube / Discord TLS+QUIC)",
            "mode": "nfqws",
            "args": [
                "--dpi-desync=multisplit",
                "--dpi-desync-split-pos=1,midsld",
                "--dpi-desync-fooling=md5sig",
            ],
        },
        {
            "name": "nfqws: Fake + Disorder2 (мягкий режим DPI)",
            "mode": "nfqws",
            "args": [
                "--dpi-desync=fake,disorder2",
                "--dpi-desync-ttl=5",
                "--dpi-desync-repeats=4",
            ],
        },
        {
            "name": "nfqws: Split2 TTL auto (резервная стратегия)",
            "mode": "nfqws",
            "args": [
                "--dpi-desync=split2",
                "--dpi-desync-ttl=0",
                "--dpi-desync-autottl=2",
            ],
        },
    ]

    _PROCESS_NAMES = ("nfqws", "tpws")
    _PID_FILE = os.path.join(tempfile.gettempdir(), "akira_zapret_nfqws.pid")

    def __init__(self):
        self.process_name = "nfqws"

    def _find_zapret_dir(self) -> str | None:
        cfg = load_config()
        custom_path = cfg.get("zapret_path", "") or cfg.get("paths", {}).get("zapret", "")
        if custom_path and os.path.exists(custom_path):
            return custom_path if os.path.isdir(custom_path) else os.path.dirname(custom_path)

        candidates = [
            "/opt/zapret",
            "/usr/share/zapret",
            "/usr/local/share/zapret",
            os.path.expanduser("~/zapret"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                return c
        return None

    def _find_nfqws_bin(self) -> str | None:
        which_bin = shutil.which("nfqws")
        if which_bin:
            return which_bin

        search_roots = []
        zdir = self._find_zapret_dir()
        if zdir:
            search_roots.append(zdir)
        search_roots.extend(["/opt/zapret", "/usr/share/zapret", "/usr/local/bin"])

        for root_dir in search_roots:
            if not os.path.exists(root_dir):
                continue
            for rel in (
                "nfqws",
                os.path.join("nfq", "nfqws"),
                os.path.join("binaries", "linux-x86_64", "nfqws"),
                os.path.join("binaries", "x86_64", "nfqws"),
                os.path.join("binaries", "linux-arm64", "nfqws"),
            ):
                cand = os.path.join(root_dir, rel)
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    return cand
        return None

    def _has_systemd_service(self) -> bool:
        for unit in ("/etc/systemd/system/zapret.service", "/lib/systemd/system/zapret.service", "/usr/lib/systemd/system/zapret.service"):
            if os.path.exists(unit):
                return True
        systemctl = shutil.which("systemctl")
        if systemctl:
            try:
                res = subprocess.run([systemctl, "list-unit-files", "zapret.service"], capture_output=True, text=True, timeout=2.0)
                if res.returncode == 0 and "zapret.service" in res.stdout:
                    return True
            except Exception:
                pass
        return False

    def is_installed(self) -> bool:
        return self._has_systemd_service() or self._find_nfqws_bin() is not None

    def get_install_hint(self) -> str:
        return (
            "Нативный Zapret для Linux (nfqws / служба zapret) не найден в системе. "
            "Установи bol-van/zapret (обычно в /opt/zapret через install_easy.sh), и я смогу включать и переключать обход через запрос прав администратора."
        )

    def get_strategies_menu(self) -> str:
        lines = [f"{i + 1}. {s['name']}" for i, s in enumerate(self.STRATEGIES)]
        return "\n".join(lines)

    def is_running(self) -> bool:
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in self._PROCESS_NAMES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        systemctl = shutil.which("systemctl")
        if systemctl and self._has_systemd_service():
            try:
                res = subprocess.run([systemctl, "is-active", "--quiet", "zapret"], timeout=2.0)
                if res.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def _run_pkexec_script(self, script_body: str, timeout: float = 30.0) -> tuple[bool, str]:
        pkexec = shutil.which("pkexec")
        if not pkexec:
            return False, "Не найдена утилита pkexec (Polkit) для повышения прав."

        tmp_script = None
        try:
            fd, tmp_script = tempfile.mkstemp(prefix="akira_zapret_", suffix=".sh")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nset -e\n" + script_body + "\n")
            os.chmod(tmp_script, 0o700)
            res = subprocess.run([pkexec, "/bin/sh", tmp_script], capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return True, ""
            err = (res.stderr or res.stdout or "").strip()
            if res.returncode in (126, 127) and not err:
                err = "Операция отменена пользователем."
            return False, err or f"Код возврата pkexec: {res.returncode}"
        except Exception as e:
            return False, str(e)
        finally:
            if tmp_script and os.path.exists(tmp_script):
                try:
                    os.remove(tmp_script)
                except OSError:
                    pass

    def _build_stop_commands(self) -> str:
        lines = [
            f'if [ -f {shlex.quote(self._PID_FILE)} ]; then kill $(cat {shlex.quote(self._PID_FILE)}) 2>/dev/null || true; rm -f {shlex.quote(self._PID_FILE)}; fi',
            "pkill -x nfqws 2>/dev/null || true",
            "pkill -x tpws 2>/dev/null || true",
            "if command -v nft >/dev/null 2>&1; then nft delete table inet akira_zapret 2>/dev/null || true; fi",
            "if command -v iptables >/dev/null 2>&1; then iptables -t mangle -D OUTPUT -j AKIRA_ZAPRET 2>/dev/null || true; iptables -t mangle -F AKIRA_ZAPRET 2>/dev/null || true; iptables -t mangle -X AKIRA_ZAPRET 2>/dev/null || true; fi",
        ]
        if self._has_systemd_service():
            lines.append("systemctl stop zapret 2>/dev/null || true")
        return "\n".join(lines)

    def start_strategy_by_index(self, index: int) -> str:
        if index < 1 or index > len(self.STRATEGIES):
            return f"Неверный номер обхода. Выбери от 1 до {len(self.STRATEGIES)}."

        if not self.is_installed():
            return self.get_install_hint()

        strat = self.STRATEGIES[index - 1]
        if strat["mode"] == "service":
            if self._has_systemd_service():
                script = "\n".join([
                    self._build_stop_commands(),
                    "systemctl restart zapret",
                ])
                ok, err = self._run_pkexec_script(script)
                if ok:
                    return f"Запустила #{index}: {strat['name']}"
                return f"Не удалось запустить службу zapret: {err}"
            # Если службы systemd нет — запускаем универсальный nfqws
            strat = self.STRATEGIES[1]

        nfqws_bin = self._find_nfqws_bin()
        if not nfqws_bin:
            return self.get_install_hint()

        args_joined = " ".join(shlex.quote(a) for a in strat["args"])
        cmd_nfqws = (
            f"nohup {shlex.quote(nfqws_bin)} --qnum=200 {args_joined} "
            f">/dev/null 2>&1 & echo $! > {shlex.quote(self._PID_FILE)}"
        )

        # Настройка очередей NFQUEUE (сначала nftables, fallback iptables)
        firewall_setup = "\n".join([
            "if command -v nft >/dev/null 2>&1; then",
            "  nft add table inet akira_zapret",
            "  nft add chain inet akira_zapret output '{ type filter hook output priority mangle; policy accept; }'",
            "  nft add rule inet akira_zapret output tcp dport '{ 80, 443 }' ct original packets 1-6 queue num 200 bypass",
            "  nft add rule inet akira_zapret output udp dport 443 ct original packets 1-6 queue num 200 bypass",
            "elif command -v iptables >/dev/null 2>&1; then",
            "  iptables -t mangle -N AKIRA_ZAPRET 2>/dev/null || true",
            "  iptables -t mangle -F AKIRA_ZAPRET",
            "  iptables -t mangle -A AKIRA_ZAPRET -p tcp --dport 443 -m connbytes --connbytes 1:6 --connbytes-dir original --connbytes-mode packets -j NFQUEUE --queue-num 200 --queue-bypass",
            "  iptables -t mangle -A AKIRA_ZAPRET -p udp --dport 443 -m connbytes --connbytes 1:6 --connbytes-dir original --connbytes-mode packets -j NFQUEUE --queue-num 200 --queue-bypass",
            "  iptables -t mangle -I OUTPUT -j AKIRA_ZAPRET",
            "fi",
        ])

        script = "\n".join([
            self._build_stop_commands(),
            firewall_setup,
            cmd_nfqws,
        ])

        ok, err = self._run_pkexec_script(script)
        if not ok:
            return f"Не удалось запустить обход #{index}: {err}"

        for _ in range(12):
            time.sleep(0.15)
            if self.is_running():
                return f"Запустила #{index}: {strat['name']}"
        return f"Не удалось подтвердить запуск nfqws для #{index}."

    def start(self) -> str:
        default_idx = 1 if self._has_systemd_service() else 2
        return self.start_strategy_by_index(default_idx)

    def stop(self) -> str:
        was_active = self.is_running()
        if not was_active:
            return "Запрет уже выключен"

        ok, err = self._run_pkexec_script(self._build_stop_commands())
        if ok:
            return "Выключила Запрет"
        return f"Не удалось выключить Запрет: {err}"
