import os
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, StringVar, IntVar, messagebox
from tkinter import scrolledtext

from cache_manager import load_cache, save_cache, clear_cache, cache_size_bytes
from translator import translate_srt_files


class TranslatorGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("SRT/VTT Translator — by LTN")
        self.minsize(960, 850)  
        self.resizable(True, True)
        self.configure(padx=6, pady=6) 

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  
        # state
        self.files = []
        self.output_folder = None
        self.cache = load_cache()

        # control flags
        self._stop_flag = False
        self._pause_event = threading.Event()

        # UI vars
        self.encoding_var = StringVar(value="utf-8")
        self.dest_lang = StringVar(value="vi — Vietnamese (vi)")
        self.output_mode = StringVar(value="bilingual")
        self.service_var = StringVar(value="google")

        self.chunk_size = IntVar(value=20)
        self.max_workers = IntVar(value=4)
        self.sleep_min = IntVar(value=1)
        self.sleep_max = IntVar(value=3)

        self._build_ui()
        self._update_cache_label()

    # ---------------- UI ----------------
    def _build_ui(self):
        PADX, PADY = 8, 4

        # 1) Files / Folder
        file_frame = tb.Labelframe(self, text="1) Files / Folder", padding=8)
        file_frame.grid(row=0, column=0, sticky="nsew", padx=PADX, pady=(PADY, 4))
        file_frame.columnconfigure(2, weight=1)

        tb.Button(file_frame, text="📂 Chọn file SRT/VTT", bootstyle="primary",
                  command=self.choose_files).grid(row=0, column=0, padx=6, pady=6, sticky="w")
        tb.Button(file_frame, text="📁 Chọn folder (quét đệ quy)", bootstyle="info",
                  command=self.choose_folder).grid(row=0, column=1, padx=6, pady=6, sticky="w")
        self.files_label = tb.Label(file_frame, text="Chưa chọn file", bootstyle="secondary")
        self.files_label.grid(row=0, column=2, padx=8, sticky="w")

        # 2) Output & Language
        out_frame = tb.Labelframe(self, text="2) Output & Language", padding=8)
        out_frame.grid(row=1, column=0, sticky="ew", padx=PADX, pady=4)
        out_frame.columnconfigure(1, weight=1)

        tb.Label(out_frame, text="Dịch sang:").grid(row=0, column=0, sticky=W, padx=6, pady=6)
        tb.Combobox(out_frame, textvariable=self.dest_lang,
                    values=[
                        "vi — Vietnamese (vi)", "en — English (en)",
                        "fr — French (fr)", "es — Spanish (es)",
                        "de — German (de)", "pt — Portuguese (pt)"
                    ],
                    width=32, state="readonly").grid(row=0, column=1, padx=6, pady=6, sticky="w")

        tb.Label(out_frame, text="Encoding:").grid(row=0, column=2, sticky=W, padx=6, pady=6)
        tb.Combobox(out_frame, textvariable=self.encoding_var,
                    values=["utf-8", "utf-16", "utf-8-sig"],
                    width=14, state="readonly").grid(row=0, column=3, padx=6, pady=6, sticky="w")

        tb.Label(out_frame, text="Output mode:").grid(row=1, column=0, sticky=W, padx=6, pady=4)
        tb.Radiobutton(out_frame, text="Bilingual (EN + dest)", variable=self.output_mode,
                       value="bilingual").grid(row=1, column=1, sticky=W, padx=6)
        tb.Radiobutton(out_frame, text="Destination only", variable=self.output_mode,
                       value="dest_only").grid(row=1, column=2, sticky=W, padx=6)

        tb.Label(out_frame, text="Dịch vụ:").grid(row=2, column=0, sticky=W, padx=6, pady=4)
        tb.Combobox(out_frame, textvariable=self.service_var,
                    values=["google", "mymemory"],
                    width=20, state="readonly").grid(row=2, column=1, padx=6, pady=6, sticky="w")

        # 3) Performance
        perf_frame = tb.Labelframe(self, text="3) Performance tuning", padding=8)
        perf_frame.grid(row=2, column=0, sticky="ew", padx=PADX, pady=4)

        tb.Label(perf_frame, text="Chunk size:").grid(row=0, column=0, sticky=W, padx=6, pady=3)
        tb.Entry(perf_frame, textvariable=self.chunk_size, width=8).grid(row=0, column=1, padx=6, pady=3)
        tb.Label(perf_frame, text="Max workers:").grid(row=0, column=2, sticky=W, padx=6, pady=3)
        tb.Entry(perf_frame, textvariable=self.max_workers, width=8).grid(row=0, column=3, padx=6, pady=3)

        tb.Label(perf_frame, text="Sleep min (s):").grid(row=1, column=0, sticky=W, padx=6, pady=3)
        tb.Entry(perf_frame, textvariable=self.sleep_min, width=8).grid(row=1, column=1, padx=6, pady=3)
        tb.Label(perf_frame, text="Sleep max (s):").grid(row=1, column=2, sticky=W, padx=6, pady=3)
        tb.Entry(perf_frame, textvariable=self.sleep_max, width=8).grid(row=1, column=3, padx=6, pady=3)

        # 4) Buttons
        btn_frame = tb.Frame(self)
        btn_frame.grid(row=3, column=0, sticky="ew", padx=PADX, pady=(6, 4))
        btn_frame.columnconfigure(4, weight=1)

        self.start_btn = tb.Button(btn_frame, text="▶ Bắt đầu", bootstyle="success",
                                   command=self.start_translation)
        self.start_btn.grid(row=0, column=0, padx=4, pady=2, sticky="w")

        self.pause_btn = tb.Button(btn_frame, text="⏸ Pause", bootstyle="warning-outline",
                                   command=self.pause_resume, state="disabled")
        self.pause_btn.grid(row=0, column=1, padx=4, pady=2, sticky="w")

        self.stop_btn = tb.Button(btn_frame, text="⏹ Dừng", bootstyle="danger",
                                  command=self.stop_translation, state="disabled")
        self.stop_btn.grid(row=0, column=2, padx=4, pady=2, sticky="w")

        tb.Button(btn_frame, text="💾 Chọn thư mục lưu...", bootstyle="info",
                  command=self.choose_output_folder).grid(row=0, column=3, padx=8, pady=2, sticky="w")

        tb.Button(btn_frame, text="🧹 Clear Cache", bootstyle="danger-outline",
                  command=self._clear_cache).grid(row=0, column=5, padx=4, pady=2, sticky="e")

        # 5) Progress + Log
        prog_frame = tb.Labelframe(self, text="Progress", padding=8)
        prog_frame.grid(row=4, column=0, sticky="nsew", padx=PADX, pady=(4, 6))
        prog_frame.columnconfigure(0, weight=1)
        prog_frame.rowconfigure(5, weight=1)

        self.current_file_label = tb.Label(prog_frame, text="File hiện tại: —")
        self.current_file_label.grid(row=0, column=0, sticky="w", padx=4, pady=(2, 6))

        self.file_progress = tb.Progressbar(prog_frame, maximum=100, bootstyle="info-striped")
        self.file_progress.grid(row=1, column=0, sticky="ew", padx=4, pady=3)

        self.total_label = tb.Label(prog_frame, text="Tổng tiến độ: 0/0 file (0%)")
        self.total_label.grid(row=2, column=0, sticky="w", padx=4, pady=(6, 3))

        self.total_progress = tb.Progressbar(prog_frame, maximum=100, bootstyle="success-striped")
        self.total_progress.grid(row=3, column=0, sticky="ew", padx=4, pady=3)

        tb.Label(prog_frame, text="Log:").grid(row=4, column=0, sticky="nw", padx=4, pady=(6, 2))
        self.log_box = scrolledtext.ScrolledText(prog_frame, height=10, wrap="word", font=("Consolas", 9))
        self.log_box.grid(row=5, column=0, sticky="nsew", padx=4, pady=(2, 4))

        # 6) Footer
        footer_frame = tb.Frame(self)
        footer_frame.grid(row=5, column=0, sticky="ew", padx=PADX, pady=(2, 8))
        tb.Separator(footer_frame, orient=HORIZONTAL).pack(fill="x", pady=(0, 4))
        tb.Label(footer_frame,
                 text="By Designer & Developer: LTN — nhanlt.dev",
                 font=("Segoe UI", 9, "italic"),
                 anchor=CENTER,
                 bootstyle="secondary").pack(fill="x")

        self.cache_label = tb.Label(footer_frame, text="Cache size: 0.00 MB",
                                    font=("Segoe UI", 9), bootstyle="secondary")
        self.cache_label.pack(fill="x")

        self._log("Ứng dụng sẵn sàng. Chọn file hoặc folder để bắt đầu.")

    # ---------------- Cache ----------------
    def _update_cache_label(self):
        size_mb = cache_size_bytes() / 1024.0
        self.cache_label.configure(text=f"Cache size: {size_mb:.2f} MB")

    def _clear_cache(self):
        if messagebox.askyesno("Xóa cache", "Bạn có chắc muốn xóa toàn bộ cache dịch?"):
            clear_cache()
            self.cache = {}
            save_cache(self.cache)
            self._log("🧹 Cache đã được xóa.")
            self._update_cache_label()

    # ---------------- File handlers ----------------
    def choose_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn file subtitle",
            filetypes=[("Subtitle files", "*.srt *.vtt"), ("All files", "*.*")]
        )
        if files:
            self.files = list(files)
            self.files_label.configure(text=f"{len(self.files)} file đã chọn")
            self._log(f"Đã chọn {len(self.files)} file.")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder chứa .srt/.vtt")
        if folder:
            files = []
            for root, _, fnames in os.walk(folder):
                for fn in fnames:
                    if fn.lower().endswith((".srt", ".vtt")):
                        files.append(os.path.join(root, fn))
            self.files = sorted(files)
            self.files_label.configure(text=f"{len(self.files)} file (bao gồm subfolder)")
            self._log(f"Đã lấy {len(self.files)} file từ folder (bao gồm subfolder).")

    def choose_output_folder(self):
        folder = filedialog.askdirectory(title="Chọn nơi lưu file đã dịch")
        if folder:
            self.output_folder = folder
            self._log(f"Chọn thư mục lưu: {folder}")

    # ---------------- Controls ----------------
    def start_translation(self):
        if not self.files:
            messagebox.showwarning("Chưa chọn file", "Bạn chưa chọn file hoặc folder chứa file .srt/.vtt")
            return
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸ Pause")
        self.stop_btn.configure(state="normal")
        self._stop_flag = False
        self._pause_event.clear()
        threading.Thread(target=self._run_translation, daemon=True).start()

    def pause_resume(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_btn.configure(text="⏸ Pause")
            self._log("▶ Resume")
        else:
            self._pause_event.set()
            self.pause_btn.configure(text="▶ Resume")
            self._log("⏸ Paused — sẽ tạm dừng sau chunk hiện tại...")

    def stop_translation(self):
        self._stop_flag = True
        self._pause_event.clear()
        self._log("⛔ Stop requested — sẽ dừng sau chunk hiện tại...")

    def _run_translation(self):
        total_files = len(self.files)
        done_files = 0
        dest_lang_code = self.dest_lang.get().split(" — ")[0]
        encoding = self.encoding_var.get()
        output_mode = self.output_mode.get()
        service = self.service_var.get()
        chunk_size = max(1, int(self.chunk_size.get()))
        max_workers = max(1, int(self.max_workers.get()))
        min_sleep = float(self.sleep_min.get())
        max_sleep = float(self.sleep_max.get())

        for fpath in self.files:
            if self._stop_flag:
                self._log("⛔ Đã dừng bởi user.")
                break

            filename = os.path.basename(fpath)
            self._set_current_file(filename)
            self._update_file_progress(0, 0, 1, filename)
            self._log(f"🔄 Bắt đầu dịch: {fpath}")

            try:
                outputs = translate_srt_files(
                    files=[fpath],
                    cache=self.cache,
                    dest_lang=dest_lang_code,
                    output_mode=output_mode,
                    save_choice=(2 if self.output_folder else 1),
                    output_folder=self.output_folder,
                    stop_event=lambda: self._stop_flag,
                    pause_event=self._pause_event,
                    progress_callback=lambda cur, tot, fname=filename: self._on_chunk_progress(cur, tot, fname),
                    chunk_size=chunk_size,
                    max_workers=max_workers,
                    min_sleep=min_sleep,
                    max_sleep=max_sleep,
                    encoding=encoding,
                    retries=4,
                )
                if outputs and not self._stop_flag:
                    self._on_chunk_progress(1, 1, filename)
                    self._log(f"✅ Hoàn thành: {outputs[0]}")
                elif self._stop_flag:
                    self._log("⛔ Đã dừng khi đang xử lý file.")
                else:
                    self._log("⚠️ Không có file đầu ra.")
            except Exception as e:
                self._log(f"❌ Lỗi khi dịch {fpath}: {e}")

            done_files += 1
            self._update_total_progress(done_files, total_files)

        save_cache(self.cache)
        self._update_cache_label()
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="⏸ Pause")
        self.stop_btn.configure(state="disabled")
        if not self._stop_flag:
            self._log("🎉 Hoàn thành tất cả file.")
        else:
            self._log("⛔ Đã dừng.")

    # ---------------- UI updates ----------------
    def _on_chunk_progress(self, current, total, filename):
        percent = (current / total) * 100 if total else 0
        self.after(0, self._update_file_progress, percent, current, total, filename)

    def _update_file_progress(self, percent, current, total, filename):
        self.file_progress.configure(value=percent)
        self.current_file_label.configure(
            text=f"File hiện tại: {filename} — {current}/{total} chunk ({percent:.1f}%)")
        self.update_idletasks()

    def _update_total_progress(self, done, total):
        percent = (done / total) * 100 if total else 0
        self.after(0, lambda: (
            self.total_progress.configure(value=percent),
            self.total_label.configure(
                text=f"Tổng tiến độ: {done}/{total} file ({percent:.1f}%)"),
            self.update_idletasks()
        ))

    def _set_current_file(self, filename):
        self.after(0, lambda: self.current_file_label.configure(text=f"File hiện tại: {filename}"))

    def _log(self, text):
        self.after(0, self._append_log, text)

    def _append_log(self, text):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        # giữ log không quá dài
        if int(self.log_box.index("end-1c").split(".")[0]) > 500:
            self.log_box.delete("1.0", "2.0")
