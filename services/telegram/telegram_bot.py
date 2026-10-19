import asyncio
import base64
import io
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import cv2
import psutil
import pyautogui
import websockets
from PyQt6.QtCore import QThread

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from core.nlp.command_parser import CommandParser
from core.system.actions import SystemActions
from core.utils.config import get_user_data_path, load_config, save_config

SERVER_HOST = ""
PAIRING_PATH = Path(get_user_data_path("pairing_session.json"))

main_window_instance = None
command_parser_instance = None
active_ws_client = None
pending_token_registration = None
outgoing_queue = None


def get_device_uuid() -> str:
    cfg = load_config()
    dev_id = cfg.get("device_uuid")
    if not dev_id:
        dev_id = str(uuid.uuid4())
        cfg["device_uuid"] = dev_id
        save_config(cfg)
    return dev_id


def get_command_parser():
    global command_parser_instance, main_window_instance
    if main_window_instance and getattr(main_window_instance, "command_parser", None):
        return main_window_instance.command_parser
    if command_parser_instance is None:
        command_parser_instance = CommandParser()
    return command_parser_instance


def get_hardware_status() -> str:
    cpu_usage = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count(logical=True)

    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024 ** 3)
    ram_total = ram.total / (1024 ** 3)
    ram_percent = ram.percent

    disks_info = []
    seen_mounts = set()
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        mount = part.mountpoint
        if mount in seen_mounts:
            continue
        seen_mounts.add(mount)
        try:
            usage = psutil.disk_usage(mount)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            drive_clean = part.device.rstrip("\\").rstrip("/").rstrip(":")
            disks_info.append(
                f"💾 **Диск {drive_clean}:** {free_gb:.1f} ГБ свободно из {total_gb:.1f} ГБ ({usage.percent}%)"
            )
        except (PermissionError, OSError):
            continue

    disks_str = "\n".join(disks_info) if disks_info else "**Диски:** Не удалось определить"

    gpu_info = "Недоступно"
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits"
        out = subprocess.check_output(cmd, shell=True, text=True, creationflags=flags).strip()
        if out:
            parts = [p.strip() for p in out.split(",")]
            if len(parts) >= 5:
                gpu_name, temp, util, mem_used, mem_total = parts[0], parts[1], parts[2], parts[3], parts[4]
                gpu_info = (
                    f"{gpu_name}\n   Температура: {temp}°C | Нагрузка: {util}%\n"
                    f"   VRAM: {int(mem_used)} МБ / {int(mem_total)} МБ"
                )
    except Exception:
        pass

    return (
        f"📊 **Текущий статус ПК:**\n\n"
        f"**Процессор:** {cpu_usage}% ({cpu_count} потоков)\n"
        f"**Оперативная память:** {ram_used:.1f} ГБ / {ram_total:.1f} ГБ ({ram_percent}%)\n"
        f"**Видеокарта:** {gpu_info}\n"
        f"{disks_str}"
    )


def take_screenshot_base64() -> str:
    try:
        shot = pyautogui.screenshot()
        buf = io.BytesIO()
        shot.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[Screenshot Error]: {e}")
        return ""


def take_webcam_base64() -> str:
    global main_window_instance
    frame = None

    if main_window_instance and getattr(main_window_instance, "vision_thread", None):
        if main_window_instance.vision_thread.isRunning():
            frame = main_window_instance.vision_thread.current_frame

    if frame is None:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        ret, frame_read = cap.read()
        cap.release()
        if ret and frame_read is not None:
            frame = frame_read

    if frame is not None:
        success, buffer = cv2.imencode(".png", frame)
        if success and buffer is not None:
            return base64.b64encode(buffer.tobytes()).decode("utf-8")
    return ""


def _save_file_to_downloads(filename: str, b64_data: str) -> str:
    downloads_dir = Path.home() / "Downloads" / "AkiraFiles"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    clean_filename = os.path.basename(filename)
    target_path = downloads_dir / clean_filename

    counter = 1
    base_stem = target_path.stem
    base_ext = target_path.suffix
    while target_path.exists():
        target_path = downloads_dir / f"{base_stem}_{counter}{base_ext}"
        counter += 1

    file_bytes = base64.b64decode(b64_data)
    with open(target_path, "wb") as f:
        f.write(file_bytes)

    if main_window_instance and hasattr(main_window_instance, "chat_history"):
        main_window_instance.chat_history.append(
            f"📥 Получен файл из Telegram: {clean_filename} (сохранён в Downloads/AkiraFiles)\n"
        )

    return str(target_path)


def _enqueue_message(payload: dict):
    global active_ws_client, outgoing_queue
    if active_ws_client and active_ws_client.loop and active_ws_client.loop.is_running() and outgoing_queue:
        active_ws_client.loop.call_soon_threadsafe(outgoing_queue.put_nowait, json.dumps(payload))


def register_pairing_token(token: str, expires_at: float):
    global pending_token_registration
    pending_token_registration = {"token": token, "expires_at": expires_at}
    _enqueue_message({"action": "register_token", "token": token, "expires_at": expires_at})


def send_alert_to_server(base64_img: str, caption: str):
    _enqueue_message({"action": "security_alert", "image_base64": base64_img, "caption": caption})


def send_text_to_server(text: str):
    _enqueue_message({"action": "text_notification", "text": text})


def start_download_watcher_local():
    global active_ws_client
    if active_ws_client and active_ws_client.download_watcher:
        if active_ws_client.loop and active_ws_client.loop.is_running():
            active_ws_client.loop.call_soon_threadsafe(active_ws_client.download_watcher.start)
            _enqueue_message({"action": "watcher_started_local"})


def stop_download_watcher_local():
    global active_ws_client
    if active_ws_client and active_ws_client.download_watcher:
        if active_ws_client.loop and active_ws_client.loop.is_running():
            active_ws_client.loop.call_soon_threadsafe(active_ws_client.download_watcher.stop)
            _enqueue_message({"action": "watcher_stopped_local"})


class DownloadWatcher:
    def __init__(self):
        self.running = False
        self.task = None

    def start(self):
        self.stop()
        self.running = True
        self.task = asyncio.create_task(self._watch_loop())
        print("[DownloadWatcher]: Режим наблюдения за закачками запущен", flush=True)

    def stop(self):
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    def cancel_shutdown(self):
        self.stop()
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run("shutdown /a", shell=True, creationflags=flags)
        print("[DownloadWatcher]: Автовыключение отменено", flush=True)

    async def _watch_loop(self):
        try:
            last_net = psutil.net_io_counters().bytes_recv
            d_init = psutil.disk_io_counters()
            last_disk = d_init.write_bytes if d_init else 0

            quiet_seconds = 0
            has_seen_active = False
            notified_active = False

            while self.running:
                await asyncio.sleep(3)
                cur_net = psutil.net_io_counters().bytes_recv
                d_cur = psutil.disk_io_counters()
                cur_disk = d_cur.write_bytes if d_cur else 0

                net_speed = (cur_net - last_net) / 3.0
                disk_speed = (cur_disk - last_disk) / 3.0

                last_net = cur_net
                last_disk = cur_disk

                # Фиксация активного скачивания (>300 КБ/с сети или >2 МБ/с записи диска)
                if net_speed > 300 * 1024 or disk_speed > 2 * 1024 * 1024:
                    has_seen_active = True
                    quiet_seconds = 0
                    if not notified_active:
                        notified_active = True
                        mb_val = max(net_speed / (1024 * 1024), disk_speed / (1024 * 1024))
                        _enqueue_message({
                            "action": "text_notification",
                            "text": f"📥 *Активная загрузка обнаружена!*\nТекущая скорость: ~{mb_val:.1f} МБ/с.\nПродолжаю следить..."
                        })
                elif net_speed < 200 * 1024 and disk_speed < 1.2 * 1024 * 1024:
                    quiet_seconds += 3

                # Условие завершения:
                # Либо мы зафиксировали активную закачку и после неё прошло 25 сек тишины,
                # Либо если скачивание уже закончилось к моменту включения и прошло 45 сек тишины
                should_finish = (has_seen_active and quiet_seconds >= 25) or (
                            not has_seen_active and quiet_seconds >= 45)

                if should_finish:
                    self.running = False
                    _enqueue_message({"action": "download_completed"})
                    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    subprocess.run("shutdown /s /t 60", shell=True, creationflags=flags)
                    print("[DownloadWatcher]: Закачки завершены, запущен таймер на 60с перед выключением", flush=True)
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[DownloadWatcher Error]: {e}", flush=True)


class TelegramBotThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        global main_window_instance, active_ws_client
        main_window_instance = parent
        active_ws_client = self
        self.loop = None
        self.ws = None
        self._running = True
        self.download_watcher = DownloadWatcher()

    def run(self):
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._client_loop())
        finally:
            self.loop.close()

    async def _client_loop(self):
        global pending_token_registration, outgoing_queue
        device_id = get_device_uuid()
        ws_url = f"ws://{SERVER_HOST}/ws/{device_id}"

        if outgoing_queue is None:
            outgoing_queue = asyncio.Queue()

        while self._running:
            try:
                # Короткий ping_interval 10с для мгновенного обнаружения переключения VPN
                async with websockets.connect(
                        ws_url,
                        open_timeout=5,
                        close_timeout=5,
                        ping_interval=10,
                        ping_timeout=5
                ) as ws:
                    self.ws = ws
                    print(f"[TelegramBot]: Связь с сервером установлена (UUID: {device_id})", flush=True)

                    if pending_token_registration and time.time() < pending_token_registration.get("expires_at", 0):
                        await ws.send(json.dumps({
                            "action": "register_token",
                            "token": pending_token_registration["token"],
                            "expires_at": pending_token_registration["expires_at"]
                        }))
                    elif PAIRING_PATH.exists():
                        try:
                            with open(PAIRING_PATH, "r", encoding="utf-8") as f:
                                sess = json.load(f)
                            if sess.get("status") == "pending" and time.time() < sess.get("expires_at", 0):
                                await ws.send(json.dumps({
                                    "action": "register_token",
                                    "token": sess["token"],
                                    "expires_at": sess["expires_at"]
                                }))
                        except Exception:
                            pass

                    async def sender_task():
                        while self._running and not getattr(ws, "closed", False):
                            try:
                                msg = await outgoing_queue.get()
                                await ws.send(msg)
                                outgoing_queue.task_done()
                            except asyncio.CancelledError:
                                break
                            except Exception:
                                break

                    async def receiver_task():
                        while self._running and not getattr(ws, "closed", False):
                            try:
                                msg_text = await ws.recv()
                                data = json.loads(msg_text)
                                if data.get("status") == "token_registered":
                                    continue
                                asyncio.create_task(self._handle_server_message(data))
                            except asyncio.CancelledError:
                                break
                            except Exception:
                                break

                    t_send = asyncio.create_task(sender_task())
                    t_recv = asyncio.create_task(receiver_task())

                    done, pending = await asyncio.wait(
                        [t_send, t_recv],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for p in pending:
                        p.cancel()
                    for d in done:
                        try:
                            d.result()
                        except Exception:
                            pass

            except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                self.ws = None
                if not self._running:
                    break
                await asyncio.sleep(2)
            except Exception as e:
                self.ws = None
                if not self._running:
                    break
                await asyncio.sleep(2)

    async def _handle_server_message(self, data: dict):
        action = data.get("action")
        req_id = data.get("req_id")
        payload = data.get("payload", {})

        if action == "pairing_success":
            user_id = data.get("user_id")
            user_name = data.get("user_name")
            cfg = load_config()
            if "api_keys" not in cfg:
                cfg["api_keys"] = {}
            cfg["api_keys"]["telegram_admin_id"] = user_id
            save_config(cfg)

            os.makedirs(PAIRING_PATH.parent, exist_ok=True)
            session_data = {"status": "paired", "user_id": user_id, "user_name": user_name}
            with open(PAIRING_PATH, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=4)
            print(f"[TelegramBot]: ПК успешно привязан к {user_name} ({user_id})!", flush=True)
            return

        resp_payload = {}
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        if action == "save_incoming_file":
            filename = payload.get("filename", "file.bin")
            b64_data = payload.get("file_base64", "")
            try:
                saved_path = await self.loop.run_in_executor(None, _save_file_to_downloads, filename, b64_data)
                resp_payload = {"saved_path": saved_path}
            except Exception as e:
                resp_payload = {"error": str(e)}

        elif action == "screenshot":
            base64_img = await self.loop.run_in_executor(None, take_screenshot_base64)
            resp_payload = {"image_base64": base64_img}
        elif action == "webcam":
            base64_img = await self.loop.run_in_executor(None, take_webcam_base64)
            resp_payload = {"image_base64": base64_img}
        elif action == "status":
            st = await self.loop.run_in_executor(None, get_hardware_status)
            resp_payload = {"text": st}
        elif action == "lock":
            if main_window_instance and getattr(main_window_instance, "presence_manager", None):
                main_window_instance.presence_manager.set_manual_absence(grace_period=10)
            SystemActions.lock_screen()
            resp_payload = {"text": "Заблокировала твой ПК 🔒"}
        elif action == "restart":
            subprocess.run("shutdown /r /t 5", shell=True, creationflags=flags)
            resp_payload = {"text": "Перезагружаю компьютер... 🔄"}
        elif action == "shutdown":
            subprocess.run("shutdown /s /t 5", shell=True, creationflags=flags)
            resp_payload = {"text": "Выключаю ПК. До связи! 👋"}
        elif action == "shutdown_now":
            self.download_watcher.stop()
            subprocess.run("shutdown /s /t 0", shell=True, creationflags=flags)
            resp_payload = {"text": "Выключаю прямо сейчас"}
        elif action == "start_download_watcher":
            self.download_watcher.start()
            resp_payload = {"text": "Слежение запущено"}
        elif action == "stop_download_watcher":
            self.download_watcher.stop()
            resp_payload = {"text": "Слежение остановлено"}
        elif action == "cancel_shutdown":
            self.download_watcher.cancel_shutdown()
            resp_payload = {"text": "Выключение отменено"}
        elif action == "chat":
            text = payload.get("text", "")
            parser = get_command_parser()
            result = await self.loop.run_in_executor(None, parser.process_command, text, None, False, None)
            if isinstance(result, dict):
                reply_text = result.get("chat", "") or result.get("voice", "") or "Команда принята"
            else:
                reply_text = str(result)
            resp_payload = {"text": reply_text}

        if req_id:
            answer = {"req_id": req_id, "payload": resp_payload}
            _enqueue_message(answer)

    def stop(self):
        self._running = False
        if hasattr(self, 'download_watcher'):
            self.download_watcher.stop()
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.wait(3000)