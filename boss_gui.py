# -*- coding: utf-8 -*-
"""BOSS直聘岗位采集工具 - 图形界面版
参照小红书爬虫结构：输入关键词/城市/数量，一键采集，设置自动保存
"""
import os, sys, threading, queue, math, json, io
import tkinter as tk
from tkinter import ttk, messagebox

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import boss_spider as bs


class TextRedirector(io.StringIO):
    def __init__(self, q):
        self.q = q
    def write(self, s):
        if s.strip():
            self.q.put(s)
    def flush(self):
        pass


class BossGUI:
    def __init__(self, root):
        self.root = root
        root.title("BOSS直聘岗位采集工具 v2.3（latin-1修复版）")
        root.geometry("780x580")
        root.minsize(700, 480)
        self.log_queue = queue.Queue()
        self.spider = None
        self.worker = None
        self.settings = self.load_settings()
        self.build_ui()
        self.root.after(100, self.poll_log)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log("欢迎使用 BOSS直聘岗位采集工具\n")
        self.log("使用方法：填好关键词/城市/数量 → 点「打开登录页」扫码 → 点「开始采集」\n")

    # ---------- 设置持久化 ----------
    def load_settings(self):
        try:
            with open(os.path.join(BASE, 'data', 'settings.json'), encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_settings(self):
        try:
            d = os.path.join(BASE, 'data')
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'settings.json'), 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 界面 ----------
    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill='x')
        ttk.Label(top, text="关键词:").grid(row=0, column=0, sticky='e', padx=2)
        self.kw_var = tk.StringVar(value=self.settings.get('keyword', '皮具'))
        ttk.Entry(top, textvariable=self.kw_var, width=16).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="城市:").grid(row=0, column=2, sticky='e', padx=2)
        self.city_var = tk.StringVar(value=self.settings.get('city', '广州'))
        ttk.Entry(top, textvariable=self.city_var, width=10).grid(row=0, column=3, padx=4)
        ttk.Label(top, text="数量:").grid(row=0, column=4, sticky='e', padx=2)
        self.num_var = tk.StringVar(value=str(self.settings.get('count', 100)))
        ttk.Entry(top, textvariable=self.num_var, width=7).grid(row=0, column=5, padx=4)

        self.btn_open = ttk.Button(top, text="① 打开登录页", command=self.open_browser)
        self.btn_open.grid(row=0, column=6, padx=4)
        self.btn_start = ttk.Button(top, text="② 开始采集", command=self.start, state='disabled')
        self.btn_start.grid(row=0, column=7, padx=4)
        self.btn_stop = ttk.Button(top, text="停止", command=self.stop, state='disabled')
        self.btn_stop.grid(row=0, column=8)

        self.dedup_var = tk.BooleanVar(value=self.settings.get('dedup', True))
        ttk.Checkbutton(top, text="跳过已采集过的岗位(去重)", variable=self.dedup_var).grid(
            row=1, column=0, columnspan=4, sticky='w', pady=6)
        ttk.Button(top, text="打开导出文件夹", command=self.open_export).grid(
            row=1, column=6, columnspan=3, sticky='e')

        mid = ttk.Frame(self.root)
        mid.pack(fill='both', expand=True, padx=10, pady=(0, 6))
        self.log_box = tk.Text(mid, height=22, wrap='word', state='disabled', font=('Microsoft YaHei', 9))
        sb = ttk.Scrollbar(mid, command=self.log_box.yview)
        self.log_box.config(yscrollcommand=sb.set)
        self.log_box.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        self.status = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status, relief='sunken', anchor='w', padding=4).pack(fill='x', side='bottom')

    # ---------- 日志 ----------
    def log(self, msg):
        self.log_queue.put(msg)

    def poll_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_box.config(state='normal')
                self.log_box.insert('end', msg)
                self.log_box.see('end')
                self.log_box.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.poll_log)

    def set_busy(self, busy):
        self.btn_open.config(state='disabled' if busy else 'normal')
        self.btn_start.config(state='disabled' if busy else 'normal')
        self.btn_stop.config(state='normal' if busy else 'disabled')

    # ---------- 动作 ----------
    def save_config_txt(self, kw, city):
        with open(os.path.join(BASE, 'config.txt'), 'w', encoding='utf-8') as f:
            f.write(f"keyword={kw}\ncity={city}\n")

    def open_browser(self):
        kw = self.kw_var.get().strip() or '皮具'
        city = self.city_var.get().strip() or '广州'
        self.settings.update({'keyword': kw, 'city': city})
        self.save_settings()
        self.save_config_txt(kw, city)
        # 刷新采集配置（不用 reload，直接更新模块全局 Config）
        bs.Config = bs.load_config()
        if self.spider:
            messagebox.showinfo("提示", "浏览器已打开，配置已刷新（新关键词会生效），可直接点「② 开始采集」")
            return
        self.set_busy(True)
        self.status.set("正在打开浏览器...")
        self.worker = threading.Thread(target=self._open_worker, daemon=True)
        self.worker.start()

    def _open_worker(self):
        redirect = TextRedirector(self.log_queue)
        old = sys.stdout
        sys.stdout = redirect
        try:
            self.log("[配置] 正在启动浏览器...\n")
            self.spider = bs.BossDP()
            self.spider._stop_flag = False
            self.spider.page.get(bs.Config['start_url'])
            self.log(f"[配置] 关键词: {bs.Config.get('keyword_raw','')} | 城市: {bs.Config.get('city','')}\n")
            self.log("浏览器已打开。\n")
            self.log("→ 若未登录：请扫码登录 BOSS直聘\n")
            self.log("→ 登录完成后，点击「② 开始采集」\n")
        except Exception as e:
            import traceback
            self.log(f"打开浏览器失败: {e}\n")
            self.log(traceback.format_exc())
        finally:
            sys.stdout = old
            self.root.after(0, lambda: self.set_busy(False))

    def start(self):
        if not self.spider:
            messagebox.showinfo("提示", "请先点「① 打开登录页」")
            return
        if self.worker and self.worker.is_alive() and self.btn_start['state'] == 'disabled':
            messagebox.showinfo("提示", "正在采集中")
            return
        try:
            count = int(self.num_var.get().strip())
        except Exception:
            count = 100
        count = max(10, min(count, 3000))
        # 每次开始采集前都刷新配置（改关键词/城市立即生效）
        kw = self.kw_var.get().strip() or '皮具'
        city = self.city_var.get().strip() or '广州'
        self.settings.update({'keyword': kw, 'city': city, 'count': count, 'dedup': self.dedup_var.get()})
        self.save_settings()
        self.save_config_txt(kw, city)
        bs.Config = bs.load_config()
        self.set_busy(True)
        self.status.set(f"采集中：{kw} / {city} / 目标 {count} 条")
        # 自动打开导出文件夹，便于实时查看结果
        try:
            exp_dir = os.path.join(BASE, '导出结果')
            os.makedirs(exp_dir, exist_ok=True)
            os.startfile(exp_dir)
        except Exception:
            pass
        self.worker = threading.Thread(target=self._crawl_worker, args=(count,), daemon=True)
        self.worker.start()

    def _crawl_worker(self, count):
        redirect = TextRedirector(self.log_queue)
        old = sys.stdout
        sys.stdout = redirect
        try:
            self.log("等待登录态确认（3秒）...\n")
            import time
            time.sleep(3)
            self.spider.get_cookie_headers()
            max_pages = max(5, math.ceil(count / 8) + 2)
            self.log(f"开始采集，目标 {count} 条（不足将自动翻页直到采满或100页）\n")
            # 显式传最新关键词，避免默认参数绑定旧值
            self.spider.crawl(max_pages=max_pages, target=count, keyword=bs.Config['keyword'])
            self.spider.save_to_csv()
            out = os.path.join(BASE, '导出结果', 'boss_jobs.csv')
            self.log(f"\n===== 采集完成 =====\n")
            self.log(f"结果文件: {out}\n")
            self.log("可在「导出结果」文件夹中查看 CSV\n")
        except Exception as e:
            import traceback
            self.log(f"采集异常: {e}\n")
            self.log(traceback.format_exc())
        finally:
            sys.stdout = old
            self.root.after(0, self._crawl_done)

    def _crawl_done(self):
        self.set_busy(False)
        self.status.set("完成")

    def stop(self):
        if self.spider:
            self.spider._stop_flag = True
            self.log("正在停止采集（当前页处理完即停）...\n")
            self.status.set("正在停止...")

    def open_export(self):
        p = os.path.join(BASE, '导出结果')
        try:
            os.makedirs(p, exist_ok=True)
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def on_close(self):
        self.save_settings()
        if self.spider:
            try:
                self.spider._stop_flag = True
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = BossGUI(root)
    root.mainloop()
