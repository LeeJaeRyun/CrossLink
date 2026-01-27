# gui_app.py
# -*- coding: utf-8 -*-
import os
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess

from filter_core import run_filter

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
        self.geometry("560x220")
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

if __name__ == "__main__":
    App().mainloop()
