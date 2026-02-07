# gui_app.py
# -*- coding: utf-8 -*-

# 현재 filter_core_v2.py 모듈을 사용하는 GUI 애플리케이션

import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess

from filter_core_v2 import run_filter, load_min_wage, save_min_wage

def default_output_path():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(downloads, f"Filtered_list_{ts}.xlsx")

def open_folder(path):
    folder = os.path.dirname(path)
    subprocess.Popen(["explorer", folder])

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("求人審査ツール (Filtered Tool)")
        self.geometry("560x260")
        self.resizable(False, False)

        self.csv_path = tk.StringVar(value="")

        tk.Label(self, text="CSVファイルを選択してください:").pack(anchor="w", padx=12, pady=(12, 4))

        frame = tk.Frame(self)
        frame.pack(fill="x", padx=12)

        entry = tk.Entry(frame, textvariable=self.csv_path)
        entry.pack(side="left", fill="x", expand=True)

        tk.Button(frame, text="参照...", command=self.pick_csv).pack(side="left", padx=(8, 0))

        self.run_btn = tk.Button(self, text="実行", command=self.run, height=2)
        self.run_btn.pack(fill="x", padx=12, pady=(16, 6))

        self.setting_btn = tk.Button(self, text="設定(最低賃金)", command=self.open_min_wage_editor)
        self.setting_btn.pack(fill="x", padx=12, pady=(0, 6))

        self.status = tk.Label(self, text="待機中", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(4, 0))

    def pick_csv(self):
        path = filedialog.askopenfilename(
            title="CSVを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.csv_path.set(path)

    def run(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("エラー", "有効なCSVファイルを選択してください。")
            return

        out_xlsx = default_output_path()

        try:
            self.run_btn.config(state="disabled")
            self.status.config(text="処理中…")
            self.update_idletasks()

            result_path = run_filter(csv_path, out_xlsx)

            self.status.config(text=f"完了: {result_path}")
            if messagebox.askyesno("完了", "処理が完了しました。フォルダを開きますか？"):
                open_folder(result_path)

        except Exception as e:
            messagebox.showerror("エラー", str(e))
            self.status.config(text="エラー発生")

        finally:
            self.run_btn.config(state="normal")

    def open_min_wage_editor(self):
        data = load_min_wage()  # 현재 적용값(기본/저장값)

        win = tk.Toplevel(self)
        win.title("最低賃金 設定")
        win.geometry("420x520")

        tk.Label(win, text="各都道府県の最低賃金(円/時)を編集して、保存してください。").pack(anchor="w", padx=10, pady=(10, 6))
        tk.Label(win, text="形式: 都道府県=数字（例: 東京=1226）").pack(anchor="w", padx=10, pady=(0, 10))

        txt = tk.Text(win, height=25)
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        # 초기 텍스트 (pref=value)
        lines = [f"{k}={data[k]}" for k in data.keys()]
        txt.insert("1.0", "\n".join(lines))

        def on_save():
            raw_lines = txt.get("1.0", "end").strip().splitlines()
            new_map = dict(data)

            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                if "=" not in line:
                    messagebox.showerror("エラー", f"形式が不正です: {line}\n例: 東京=1226")
                    return
                pref, val = line.split("=", 1)
                pref = pref.strip()
                val = val.strip()

                if pref not in new_map:
                    messagebox.showerror("エラー", f"都道府県名が不正です: {pref}")
                    return
                try:
                    n = int(float(val))
                    if n <= 0:
                        raise ValueError
                    new_map[pref] = n
                except Exception:
                    messagebox.showerror("エラー", f"数値が不正です: {pref}={val}")
                    return

            path = save_min_wage(new_map)
            messagebox.showinfo("保存完了", f"保存しました。\n次回以降も反映されます。\n保存先: {path}")
            win.destroy()

        tk.Button(win, text="保存", command=on_save, height=2).pack(fill="x", padx=10, pady=(0, 10))

if __name__ == "__main__":
    App().mainloop()
