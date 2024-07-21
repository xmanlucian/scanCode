import tkinter as tk
import uuid
from tkinter import ttk
import configparser
import threading
import time
import os
from gtts import gTTS
import socket
import requests  # 用于发送HTTP请求


class BarcodeScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Barcode Scanner")
        self.root.attributes('-fullscreen', True)  # 设置全屏

        self.config = self.load_config()
        self.last_sync_time = time.time()

        self.setup_gui()

        #每60秒检测一次网络状态
        self.root.after(60000, self.check_network)
        self.check_network()
        self.start_sync_thread()

    def load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        return config

    def setup_gui(self):
        self.tree = ttk.Treeview(self.root, columns=('Time', 'Barcode', 'Status'), show='headings')
        self.tree.heading('Time', text='Time')
        self.tree.heading('Barcode', text='Barcode')
        self.tree.heading('Status', text='Status')

        self.style = ttk.Style()
        self.style.configure('Treeview', font=('Helvetica', 100))
        self.style.configure('Treeview.Heading', font=('Helvetica', 50, 'bold'))

        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind('<Configure>', self.adjust_column_widths)

        self.network_status_label = tk.Label(self.root, text="Network Status: Checking...")
        self.network_status_label.pack()
        self.network_status_label.place(relx=0.0, rely=1, anchor='sw')

        self.network_status_label.config(font=('Helvetica', 50))

        # self.scan_status.label 的字体大小设置为 50
        self.scan_status_label = tk.Label(self.root, text="Scan Status: Waiting...")
        self.scan_status_label.pack()
        # self.scan_status_label.place(relx=0.5, rely=1.0, anchor='s')
        self.scan_status_label.config(font=('Helvetica', 50))



        self.current_barcode = ""

        self.entry = tk.Entry(self.root)
        self.entry.pack()
        self.entry.pack_forget()

        self.root.bind_all('<Key>', self.process_barcode)
        self.entry.focus_set()

        # self.scan_status_label = tk.Label(self.root, text="Scan Status: Ready")
        # self.scan_status_label.pack()

        # 位置在右下角
        self.last_sync_label = tk.Label(self.root, text="Last Sync: Never")
        self.last_sync_label.pack()
        self.last_sync_label.place(relx=1.0, rely=1.0, anchor='se')
        self.last_sync_label.config(font=('Helvetica', 50))

    def adjust_column_widths(self, event=None):
        total_width = self.tree.winfo_width()
        col_widths = {
            'Time': 0.3,
            'Barcode': 0.5,
            'Status': 0.2
        }
        for col, percentage in col_widths.items():
            width = int(total_width * percentage)
            self.tree.column(col, width=width)

    def process_barcode(self, event):
        if event.keysym == 'Return':
            barcode = self.entry.get()
            if not barcode:
                self.scan_status_label.config(text="Scan Status: Scan Failed")
                self.play_error_audio()
            else:
                self.current_barcode = barcode
                self.scan_status_label.config(text=f"{barcode}", font=('Helvetica', 100))

                self.add_to_treeview(barcode)
                self.play_barcode_audio(barcode)
                self.write_to_cache(barcode)
                self.entry.delete(0, tk.END)
        else:
            if event.char:
                self.entry.insert(tk.END, event.char)

    def add_to_treeview(self, barcode):
        now = time.strftime('%H:%M:%S')
        self.tree.insert('', 'end', values=(now, barcode, 'Saved'))
        items = self.tree.get_children()
        if len(items) > 5:
            for item in items[-5:]:
                self.tree.item(item, tags='large')

        # self.tree.tag_configure('large', font=('Helvetica', 100))
        self.style.configure('Treeview', rowheight=120)  # 设置行高
        if len(self.tree.get_children()) > 5:
            self.tree.delete(self.tree.get_children()[0])

        self.tree.update_idletasks()

    # 播放条形码最后4位音频，数字和字母单独发音而不是整个单词或数值
    def play_barcode_audio(self, barcode):
        last_four_digits = barcode[-4:]
        # 间隔发音，避免数字和字母连在一起
        last_four_digits = ' '.join(list(last_four_digits))
        tts = gTTS(text=last_four_digits, lang='en')
        audio_file = 'barcode.mp3'
        tts.save(audio_file)
        os.system(f"mpg321 {audio_file}")
        os.remove(audio_file)

    def play_error_audio(self):
        tts = gTTS(text='Scan Failed', lang='en')
        audio_file = 'error.mp3'
        tts.save(audio_file)
        os.system(f"mpg321 {audio_file}")

    def write_to_cache(self, barcode):
        with open('cache.txt', 'a') as f:
            site_id = self.config.get('settings', 'site_id')
            record_id = str(uuid.uuid4())  # 生成唯一标识符
            f.write(f"{record_id},{barcode},{time.strftime('%Y-%m-%d %H:%M:%S')},{site_id}\n")


    def start_sync_thread(self):
        sync_thread = threading.Thread(target=self.sync_to_server, daemon=True)
        sync_thread.start()

    def sync_to_server(self):
        while True:
            time.sleep(int(self.config.get('settings', 'sync_interval')))
            # 如果本地缓存有内容则同步，否则不同步
            with open('cache.txt', 'r') as f:
                if f.read().strip():
                    self.sync_cache_to_server()
                    self.last_sync_time = time.time()
                    self.last_sync_label.config(text=f"Last Sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_sync_time))}")
                else:
                    print("No data to sync")
            # self.sync_cache_to_server()

    def sync_cache_to_server(self):
        server_url = self.config.get('settings', 'server_url')
        api_key = self.config.get('api', 'key')
        if server_url:
            with open('cache.txt', 'r') as f:
                lines = f.readlines()
            data = [{'id': line.split(',')[0], 'barcode': line.split(',')[1], 'timestamp': line.split(',')[2], 'site_id': line.split(',')[3].strip()} for line in lines]
            headers = {'X-API-KEY': api_key}
            try:
                response = requests.post(server_url, json=data, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    success_ids = result.get('success_ids', [])
                    failed_records = result.get('failed_records', [])
                    self.update_cache(success_ids, failed_records)
                else:
                    print(f"Failed to sync to server: {response.status_code}")
            except Exception as e:
                print(f"Error during sync: {e}")

    # 更新缓存文件，删除已成功上传的记录
    def update_cache(self, success_ids, failed_records):
        with open('cache.txt', 'r') as f:
            lines = f.readlines()

        new_cache = []
        for line in lines:
            record_id = line.split(',')[0]
            if record_id not in success_ids:
                new_cache.append(line)

        with open('cache.txt', 'w') as f:
            for line in new_cache:
                f.write(line)


    def check_network(self):
        try:
            socket.create_connection(('8.8.8.8', 53), timeout=5)
            self.network_status_label.config(text="Network Status: Online")
            print("Network Status: Online")
        except OSError:
            self.network_status_label.config(text="Network Status: Offline")
            print("Network Status: Offline")

if __name__ == "__main__":
    root = tk.Tk()
    app = BarcodeScannerApp(root)
    root.mainloop()
