import socket
import struct
import subprocess
import shutil
import os


class ESCPOSPrinter:
    """透過 TCP socket 傳送 ESC/POS 指令到網路 POS 印表機 (port 9100)"""

    # ESC/POS 常用指令
    ESC = b'\x1b'
    GS = b'\x1d'
    INIT = b'\x1b\x40'           # 初始化印表機
    CUT = b'\x1d\x56\x00'       # 全切紙
    PARTIAL_CUT = b'\x1d\x56\x01'  # 半切紙
    FEED_AND_CUT = b'\x1d\x56\x42\x03'  # 走紙後切紙

    # 對齊
    ALIGN_LEFT = b'\x1b\x61\x00'
    ALIGN_CENTER = b'\x1b\x61\x01'
    ALIGN_RIGHT = b'\x1b\x61\x02'

    # 字體樣式
    BOLD_ON = b'\x1b\x45\x01'
    BOLD_OFF = b'\x1b\x45\x00'
    DOUBLE_HEIGHT_ON = b'\x1b\x21\x10'
    DOUBLE_WIDTH_ON = b'\x1b\x21\x20'
    DOUBLE_SIZE_ON = b'\x1b\x21\x30'
    NORMAL_SIZE = b'\x1b\x21\x00'

    # 走紙
    FEED_ONE_LINE = b'\x1b\x64\x01'
    FEED_THREE_LINES = b'\x1b\x64\x03'

    def __init__(self, host, port=9100, timeout=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.buffer = bytearray()

    def _append(self, data):
        if isinstance(data, str):
            self.buffer.extend(data.encode('big5', errors='replace'))
        else:
            self.buffer.extend(data)
        return self

    def init(self):
        """初始化印表機"""
        self._append(self.INIT)
        return self

    def text(self, content):
        """加入文字"""
        self._append(content)
        return self

    def newline(self, count=1):
        """換行"""
        self._append(b'\n' * count)
        return self

    def align(self, position='left'):
        """設定對齊方式: left, center, right"""
        alignments = {
            'left': self.ALIGN_LEFT,
            'center': self.ALIGN_CENTER,
            'right': self.ALIGN_RIGHT,
        }
        self._append(alignments.get(position, self.ALIGN_LEFT))
        return self

    def bold(self, on=True):
        """粗體開關"""
        self._append(self.BOLD_ON if on else self.BOLD_OFF)
        return self

    def double_size(self, on=True):
        """雙倍大小開關"""
        self._append(self.DOUBLE_SIZE_ON if on else self.NORMAL_SIZE)
        return self

    def separator(self, char='-', width=32):
        """印出分隔線"""
        self._append(char * width)
        self.newline()
        return self

    def feed(self, lines=3):
        """走紙"""
        self._append(b'\x1b\x64' + struct.pack('B', lines))
        return self

    def cut(self, partial=False):
        """切紙"""
        self._append(self.PARTIAL_CUT if partial else self.FEED_AND_CUT)
        return self

    def send(self):
        """透過 TCP socket 傳送所有緩衝區的指令到印表機"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            sock.sendall(bytes(self.buffer))
            sock.close()
            self.buffer = bytearray()
            return True, '列印成功！'
        except socket.timeout:
            return False, f'連線逾時：無法連接到 {self.host}:{self.port}'
        except ConnectionRefusedError:
            return False, f'連線被拒絕：{self.host}:{self.port} 未開放'
        except OSError as e:
            return False, f'網路錯誤：{str(e)}'
        finally:
            self.buffer = bytearray()


def print_receipt(host, port, store_name, items, total, note=''):
    """
    列印一張收據

    Args:
        host: 印表機 IP
        port: 印表機 port (預設 9100)
        store_name: 店名
        items: 商品列表 [{"name": "品名", "qty": 數量, "price": 單價}, ...]
        total: 總金額
        note: 備註
    """
    printer = ESCPOSPrinter(host, port)

    printer.init()

    # 店名 (置中、大字)
    printer.align('center')
    printer.double_size(True)
    printer.text(store_name)
    printer.newline(2)
    printer.double_size(False)

    # 分隔線
    printer.separator('=')

    # 商品明細
    printer.align('left')
    for item in items:
        name = item.get('name', '')
        qty = item.get('qty', 1)
        price = item.get('price', 0)
        line_total = qty * price
        line = f"{name}"
        printer.text(line)
        printer.newline()
        detail = f"  {qty} x ${price}"
        # 在右邊對齊小計
        spaces = 32 - len(detail) - len(f"${line_total}")
        if spaces < 1:
            spaces = 1
        detail += ' ' * spaces + f"${line_total}"
        printer.text(detail)
        printer.newline()

    # 分隔線
    printer.separator('=')

    # 總金額
    printer.bold(True)
    printer.align('right')
    printer.text(f"總計: ${total}")
    printer.newline(2)
    printer.bold(False)

    # 備註
    if note:
        printer.align('left')
        printer.separator('-')
        printer.text(f"備註: {note}")
        printer.newline()

    # 頁尾
    printer.align('center')
    printer.text('謝謝光臨！')
    printer.newline()

    # 走紙 + 切紙
    printer.feed(4)
    printer.cut()

    return printer.send()


def print_text(host, port, content, encoding='big5'):
    """
    直接列印純文字

    Args:
        host: 印表機 IP
        port: 印表機 port
        content: 文字內容
        encoding: 編碼 (預設 big5，適合繁體中文)
    """
    printer = ESCPOSPrinter(host, port)
    printer.init()
    printer.align('left')
    printer.text(content)
    printer.newline(2)
    printer.feed(4)
    printer.cut()
    return printer.send()


# ============================================================
# ADB 列印功能 (透過 ADB over WiFi 控制 Sunmi 印表機)
# ============================================================

def find_adb():
    """尋找 adb 執行檔路徑"""
    # 先找系統 PATH
    adb = shutil.which('adb')
    if adb:
        return adb

    # 常見 Windows 路徑
    common_paths = [
        os.path.expanduser('~/Desktop/platform-tools/adb.exe'),
        os.path.expanduser('~/Desktop/platform-tools/adb'),
        'C:/platform-tools/adb.exe',
        os.path.expandvars('%LOCALAPPDATA%/Android/Sdk/platform-tools/adb.exe'),
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path

    return None


def adb_connect(host, port=5555):
    """連線到 ADB over WiFi"""
    adb = find_adb()
    if not adb:
        return False, '找不到 adb，請確認 platform-tools 已下載'

    try:
        result = subprocess.run(
            [adb, 'connect', f'{host}:{port}'],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if 'connected' in output.lower():
            return True, f'ADB 連線成功：{host}:{port}'
        else:
            return False, f'ADB 連線失敗：{output}'
    except subprocess.TimeoutExpired:
        return False, f'ADB 連線逾時：{host}:{port}'
    except Exception as e:
        return False, f'ADB 錯誤：{str(e)}'


def adb_print_text(host, content, adb_port=5555):
    """透過 ADB 呼叫 Sunmi 印表機列印文字"""
    adb = find_adb()
    if not adb:
        return False, '找不到 adb，請確認 platform-tools 已下載'

    device = f'{host}:{adb_port}'

    try:
        # 確保已連線
        subprocess.run(
            [adb, 'connect', device],
            capture_output=True, text=True, timeout=10
        )

        # 透過 am (Activity Manager) 發送列印 intent 到 Sunmi 印表機服務
        # 方法: 將內容寫入暫存檔，再用 Sunmi 的列印服務印出
        escaped = content.replace("'", "'\\''")

        # 使用 Sunmi 的 content provider 或直接寫入印表機裝置
        # Sunmi T2 的印表機 serial device 通常是 /dev/ttyS1
        commands = [
            # 嘗試方法 1: 透過 Sunmi 的 am broadcast
            f"am broadcast -a woyou.aidlservice.jiuiv5.IWoyouService "
            f"--es text '{escaped}'",
            # 嘗試方法 2: 直接寫入印表機裝置
            f"echo '{escaped}' > /dev/ttyS1",
            # 嘗試方法 3: 使用 lp 指令
            f"echo '{escaped}' | lp",
        ]

        for cmd in commands:
            result = subprocess.run(
                [adb, '-s', device, 'shell', cmd],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and 'error' not in result.stderr.lower():
                return True, f'列印成功 (ADB)'

        # 如果以上都失敗，嘗試用 Sunmi 的 content provider
        # 寫入暫存檔再用 cat 送到印表機
        write_cmd = f"echo '{escaped}' > /tmp/print_job.txt"
        subprocess.run(
            [adb, '-s', device, 'shell', write_cmd],
            capture_output=True, text=True, timeout=10
        )

        print_cmd = "cat /tmp/print_job.txt > /dev/ttyS1 2>/dev/null || cat /tmp/print_job.txt > /dev/ttyS0 2>/dev/null"
        result = subprocess.run(
            [adb, '-s', device, 'shell', print_cmd],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            return True, '列印成功 (ADB serial)'
        else:
            return False, f'列印失敗：{result.stderr or "印表機裝置不可存取"}'

    except subprocess.TimeoutExpired:
        return False, 'ADB 指令逾時'
    except Exception as e:
        return False, f'ADB 錯誤：{str(e)}'


def adb_setup_wifi(host, adb_port=5555):
    """初次設定：透過 USB 開啟 ADB over WiFi (只需執行一次)"""
    adb = find_adb()
    if not adb:
        return False, '找不到 adb，請確認 platform-tools 已下載'

    try:
        # 先確認 USB 有連線
        result = subprocess.run(
            [adb, 'devices'],
            capture_output=True, text=True, timeout=10
        )
        devices = result.stdout.strip().split('\n')
        usb_devices = [d for d in devices[1:] if d.strip() and 'device' in d]

        if not usb_devices:
            return False, '沒有偵測到 USB 連線的裝置。請用 USB 線連接 Sunmi 和電腦。'

        # 切換到 TCP/IP 模式
        result = subprocess.run(
            [adb, 'tcpip', str(adb_port)],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            # 連線到 WiFi ADB
            subprocess.run(
                [adb, 'connect', f'{host}:{adb_port}'],
                capture_output=True, text=True, timeout=10
            )
            return True, f'已開啟 WiFi ADB！現在可以拔掉 USB 線了。\n裝置：{host}:{adb_port}'
        else:
            return False, f'設定失敗：{result.stderr}'

    except Exception as e:
        return False, f'錯誤：{str(e)}'
