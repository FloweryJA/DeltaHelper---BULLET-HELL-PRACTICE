import os
import sys
import threading
import time
import winreg
import ctypes
import tkinter as tk
from tkinter import messagebox, ttk
import psutil
from pynput import keyboard


def resource_path(relative_path):
    """ Получает absolute путь к ресурсам (работает и при обычном запуске, и из PyInstaller) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_windows_theme():
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"


class ProcessSlowerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DeltaHelper - [[BULLET HELL PRACTICE]]")
        
        # Загрузка иконки окна
        icon_p = resource_path("app_icon.ico")
        if os.path.exists(icon_p):
            try:
                self.root.iconbitmap(icon_p)
            except Exception:
                pass

        self.root.geometry("850x640")
        self.root.minsize(750, 500)

        self.running = False
        self.target_proc = None
        self.suspended_pids = set()
        self.all_processes = []
        self.current_speed = 50

        self.current_lang = "en"
        self.theme_mode = "system"
        self.process_view_mode = "extended"

        self.hotkeys = {"start": "page_up", "stop": "end", "speed_up": "+", "speed_down": "-"}

        self.translations = {
            "ru": {
                "search_lbl": "Поиск процесса:", "btn_settings": "⚙ Настройки", "btn_refresh": "↻ Обновить",
                "col_name": "Название", "col_pid": "PID", "col_status": "Статус", "col_path": "Путь к файлу",
                "speed_lbl": "Скорость игры:", "hotkey_info": "(Клавиши настраиваются в меню)",
                "presets_lbl": "Пресеты:", "cb_children": "+ Дочерние процессы",
                "btn_start": "▶ Запустить замедление", "btn_stop": "⏹ Остановить",
                "status_ready": "Статус: Готов к работе", "status_active": "Замедление: {name} (PID: {pid})",
                "status_stopped": "Статус: Остановлено", "btn_back": "← Назад",
                "settings_title": "Настройки управления", "hk_start": "Запуск замедления:",
                "hk_stop": "Остановка замедления:", "hk_speed_up": "Увеличить скорость (+5%):",
                "hk_speed_down": "Уменьшить скорость (-5%):", "lang_lbl": "Язык / Language:",
                "theme_lbl": "Тема оформления:", "theme_system": "Системная (Windows)",
                "theme_dark": "Тёмная", "theme_light": "Светлая", "proc_mode_lbl": "Отображение процессов:",
                "proc_mode_extended": "Расширенный (Все)", "proc_mode_simple": "Простой (Панель задач)",
                "btn_save": "💾 Сохранить настройки", "press_key": "[ Нажмите клавишу... ]",
                "warn_title": "Внимание", "warn_empty_keys": "Поля клавиш не могут быть пустыми!",
                "warn_select_proc": "Выберите процесс из списка!", "success_title": "Успешно",
                "success_saved": "Настройки успешно сохранены!", "err_title": "Ошибка",
                "err_admin": "Запустите программу от имени Администратора!", "err_proc_closed": "Процесс уже завершен."
            },
            "en": {
                "search_lbl": "Search process:", "btn_settings": "⚙ Settings", "btn_refresh": "↻ Refresh",
                "col_name": "Name", "col_pid": "PID", "col_status": "Status", "col_path": "File Path",
                "speed_lbl": "Game Speed:", "hotkey_info": "(Hotkeys configured in settings)",
                "presets_lbl": "Presets:", "cb_children": "+ Child processes",
                "btn_start": "▶ Start Slowdown", "btn_stop": "⏹ Stop",
                "status_ready": "Status: Ready", "status_active": "Slowing down: {name} (PID: {pid})",
                "status_stopped": "Status: Stopped", "btn_back": "← Back",
                "settings_title": "Control Settings", "hk_start": "Start slowdown:",
                "hk_stop": "Stop slowdown:", "hk_speed_up": "Increase speed (+5%):",
                "hk_speed_down": "Decrease speed (-5%):", "lang_lbl": "Language / Язык:",
                "theme_lbl": "UI Theme:", "theme_system": "System (Windows)",
                "theme_dark": "Dark", "theme_light": "Light", "proc_mode_lbl": "Process View Mode:",
                "proc_mode_extended": "Extended (All)", "proc_mode_simple": "Simple (Taskbar)",
                "btn_save": "💾 Save Settings", "press_key": "[ Press any key... ]",
                "warn_title": "Warning", "warn_empty_keys": "Hotkey fields cannot be empty!",
                "warn_select_proc": "Select a process from the list!", "success_title": "Success",
                "success_saved": "Settings saved successfully!", "err_title": "Error",
                "err_admin": "Run the application as Administrator!", "err_proc_closed": "Process has already terminated."
            }
        }

        self.keyboard_listener = None
        self.setup_styles()

        self.container = tk.Frame(self.root, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True)

        self.main_view = tk.Frame(self.container, bg=self.colors["bg"])
        self.settings_view = tk.Frame(self.container, bg=self.colors["bg"])

        self.create_main_view()
        self.create_settings_view()

        self.update_ui_text()
        self.show_main_view()
        self.start_global_hotkeys()
        self.refresh_processes()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def t(self, key):
        return self.translations[self.current_lang].get(key, key)

    def setup_styles(self):
        effective_theme = self.theme_mode
        if effective_theme == "system":
            effective_theme = get_windows_theme()

        if effective_theme == "light":
            self.colors = {
                "bg": "#eff1f5", "fg": "#4c4f69", "panel": "#e6e9ef", "accent": "#1e66f5",
                "green": "#40a02b", "red": "#d20f39", "subtext": "#6c6f85", "btn_bg": "#ccd0da",
                "entry_bg": "#ffffff", "combo_bg": "#ffffff", "combo_fg": "#4c4f69"
            }
        else:
            self.colors = {
                "bg": "#1e1e2e", "fg": "#cdd6f4", "panel": "#181825", "accent": "#89b4fa",
                "green": "#a6e3a1", "red": "#f38ba8", "subtext": "#a6adc8", "btn_bg": "#313244",
                "entry_bg": "#181825", "combo_bg": "#313244", "combo_fg": "#cdd6f4"
            }

        self.root.configure(bg=self.colors["bg"])
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.style.configure(".", background=self.colors["bg"], foreground=self.colors["fg"], font=("Segoe UI", 10))
        self.style.configure("Treeview", background=self.colors["panel"], foreground=self.colors["fg"], fieldbackground=self.colors["panel"], rowheight=26, borderwidth=0)
        self.style.configure("Treeview.Heading", background=self.colors["bg"], foreground=self.colors["accent"], font=("Segoe UI", 10, "bold"))
        self.style.map("Treeview", background=[("selected", self.colors["accent"])], foreground=[("selected", "#ffffff" if effective_theme == "light" else "#11111b")])

        self.style.configure("TCombobox", fieldbackground=self.colors["combo_bg"], background=self.colors["btn_bg"], foreground=self.colors["combo_fg"], darkcolor=self.colors["bg"], lightcolor=self.colors["bg"], bordercolor=self.colors["accent"], arrowcolor=self.colors["combo_fg"])
        self.style.map("TCombobox", fieldbackground=[("readonly", self.colors["combo_bg"])], foreground=[("readonly", self.colors["combo_fg"])], background=[("readonly", self.colors["btn_bg"])])

    def apply_theme_to_widgets(self):
        self.setup_styles()
        self.root.option_add("*TCombobox*Listbox.background", self.colors["combo_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", self.colors["combo_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff" if self.colors["combo_bg"] == "#ffffff" else "#11111b")

        def update_widget(widget):
            cls = widget.winfo_class()
            if cls in ("Frame", "TLabelframe"):
                widget.config(bg=self.colors["bg"])
            elif cls == "Label":
                widget.config(bg=widget.master.cget("bg"), fg=self.colors["fg"])
            elif cls == "Entry":
                widget.config(bg=self.colors["entry_bg"], fg=self.colors["fg"], insertbackground=self.colors["fg"])
            elif cls == "Button":
                if widget not in [self.btn_start, self.btn_stop, self.btn_save]:
                    widget.config(bg=self.colors["btn_bg"], fg=self.colors["fg"])

            for child in widget.winfo_children():
                update_widget(child)

        update_widget(self.root)

        self.panel_settings.config(bg=self.colors["panel"])
        self.speed_header.config(bg=self.colors["panel"])
        self.presets_frame.config(bg=self.colors["panel"])
        self.lbl_speed_title.config(bg=self.colors["panel"])
        self.speed_label.config(bg=self.colors["panel"], fg=self.colors["accent"])
        self.lbl_hotkey_info.config(bg=self.colors["panel"], fg=self.colors["subtext"])
        self.lbl_presets.config(bg=self.colors["panel"], fg=self.colors["subtext"])
        self.cb_children.config(bg=self.colors["panel"], fg=self.colors["fg"], selectcolor=self.colors["bg"], activebackground=self.colors["panel"])
        self.speed_slider.config(bg=self.colors["panel"], troughcolor=self.colors["bg"])
        self.form_frame.config(bg=self.colors["panel"])

        for child in self.form_frame.winfo_children():
            if child.winfo_class() == "Label":
                child.config(bg=self.colors["panel"])

    def update_ui_text(self):
        self.lbl_search.config(text=self.t("search_lbl"))
        self.btn_settings.config(text=self.t("btn_settings"))
        self.btn_refresh.config(text=self.t("btn_refresh"))

        self.tree.heading("name", text=self.t("col_name"))
        self.tree.heading("pid", text=self.t("col_pid"))
        self.tree.heading("status", text=self.t("col_status"))
        self.tree.heading("path", text=self.t("col_path"))

        self.lbl_speed_title.config(text=self.t("speed_lbl"))
        self.lbl_hotkey_info.config(text=self.t("hotkey_info"))
        self.lbl_presets.config(text=self.t("presets_lbl"))
        self.cb_children.config(text=self.t("cb_children"))

        self.btn_start.config(text=self.t("btn_start"))
        self.btn_stop.config(text=self.t("btn_stop"))

        if not self.running:
            self.status_label.config(text=self.t("status_ready"))

        self.btn_back.config(text=self.t("btn_back"))
        self.settings_title_lbl.config(text=self.t("settings_title"))
        self.lbl_hk_start.config(text=self.t("hk_start"))
        self.lbl_hk_stop.config(text=self.t("hk_stop"))
        self.lbl_hk_speed_up.config(text=self.t("hk_speed_up"))
        self.lbl_hk_speed_down.config(text=self.t("hk_speed_down"))
        self.lbl_lang.config(text=self.t("lang_lbl"))
        self.lbl_theme.config(text=self.t("theme_lbl"))
        self.lbl_proc_mode.config(text=self.t("proc_mode_lbl"))
        self.btn_save.config(text=self.t("btn_save"))

    def show_main_view(self):
        self.settings_view.pack_forget()
        self.main_view.pack(fill="both", expand=True)

    def show_settings_view(self):
        for action, entry in self.hotkey_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, self.hotkeys[action])

        lang_map = {"en": "English", "ru": "Русский"}
        self.combo_lang.set(lang_map.get(self.current_lang, "English"))

        theme_map = {"system": self.t("theme_system"), "dark": self.t("theme_dark"), "light": self.t("theme_light")}
        self.combo_theme["values"] = [self.t("theme_system"), self.t("theme_dark"), self.t("theme_light")]
        self.combo_theme.set(theme_map.get(self.theme_mode, self.t("theme_system")))

        proc_map = {"extended": self.t("proc_mode_extended"), "simple": self.t("proc_mode_simple")}
        self.combo_proc_mode["values"] = [self.t("proc_mode_extended"), self.t("proc_mode_simple")]
        self.combo_proc_mode.set(proc_map.get(self.process_view_mode, self.t("proc_mode_extended")))

        self.main_view.pack_forget()
        self.settings_view.pack(fill="both", expand=True)

    def save_settings(self):
        new_hotkeys = {}
        for action, entry in self.hotkey_entries.items():
            val = entry.get().strip().lower()
            if not val or val in ["[ нажмите клавишу... ]", "[ press any key... ]"]:
                messagebox.showwarning(self.t("warn_title"), self.t("warn_empty_keys"), parent=self.root)
                return
            new_hotkeys[action] = val

        self.hotkeys = new_hotkeys
        self.current_lang = "ru" if self.combo_lang.get() == "Русский" else "en"

        sel_theme = self.combo_theme.get()
        if sel_theme in [self.translations["ru"]["theme_dark"], self.translations["en"]["theme_dark"]]:
            self.theme_mode = "dark"
        elif sel_theme in [self.translations["ru"]["theme_light"], self.translations["en"]["theme_light"]]:
            self.theme_mode = "light"
        else:
            self.theme_mode = "system"

        sel_proc = self.combo_proc_mode.get()
        if sel_proc in [self.translations["ru"]["proc_mode_simple"], self.translations["en"]["proc_mode_simple"]]:
            self.process_view_mode = "simple"
        else:
            self.process_view_mode = "extended"

        self.apply_theme_to_widgets()
        self.update_ui_text()
        self.refresh_processes()

        messagebox.showinfo(self.t("success_title"), self.t("success_saved"), parent=self.root)
        self.show_main_view()

    def create_main_view(self):
        search_frame = tk.Frame(self.main_view, bg=self.colors["bg"])
        search_frame.pack(fill="x", padx=15, pady=(15, 5))

        self.lbl_search = tk.Label(search_frame, bg=self.colors["bg"], fg=self.colors["fg"], font=("Segoe UI", 10, "bold"))
        self.lbl_search.pack(side="left", padx=(0, 10))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.filter_processes())

        search_entry = tk.Entry(search_frame, textvariable=self.search_var, bg=self.colors["entry_bg"], fg=self.colors["fg"], insertbackground=self.colors["fg"], bd=1, relief="solid")
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_settings = tk.Button(search_frame, command=self.show_settings_view, bg=self.colors["btn_bg"], fg=self.colors["fg"], activebackground=self.colors["accent"], bd=0, padx=12, pady=4, cursor="hand2")
        self.btn_settings.pack(side="right", padx=(5, 0))

        self.btn_refresh = tk.Button(search_frame, command=self.refresh_processes, bg=self.colors["btn_bg"], fg=self.colors["fg"], activebackground=self.colors["accent"], bd=0, padx=12, pady=4, cursor="hand2")
        self.btn_refresh.pack(side="right")

        tree_frame = tk.Frame(self.main_view, bg=self.colors["bg"])
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        columns = ("name", "pid", "status", "path")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.column("name", width=180, anchor="w")
        self.tree.column("pid", width=70, anchor="center")
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("path", width=400, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda event: self.start_slowdown())

        self.panel_settings = tk.Frame(self.main_view, bg=self.colors["panel"], padx=15, pady=10)
        self.panel_settings.pack(fill="x", padx=15, pady=5)

        self.speed_header = tk.Frame(self.panel_settings, bg=self.colors["panel"])
        self.speed_header.pack(fill="x")

        self.lbl_speed_title = tk.Label(self.speed_header, bg=self.colors["panel"], fg=self.colors["fg"], font=("Segoe UI", 10, "bold"))
        self.lbl_speed_title.pack(side="left")

        self.speed_label = tk.Label(self.speed_header, text="50%", bg=self.colors["panel"], fg=self.colors["accent"], font=("Segoe UI", 11, "bold"))
        self.speed_label.pack(side="left", padx=10)

        self.lbl_hotkey_info = tk.Label(self.speed_header, bg=self.colors["panel"], fg=self.colors["subtext"], font=("Segoe UI", 8))
        self.lbl_hotkey_info.pack(side="right")

        self.speed_var = tk.IntVar(value=50)
        self.speed_slider = tk.Scale(self.panel_settings, from_=1, to=100, orient="horizontal", variable=self.speed_var, bg=self.colors["panel"], fg=self.colors["fg"], highlightthickness=0, troughcolor=self.colors["bg"], command=self.update_speed_label)
        self.speed_slider.pack(fill="x", pady=5)

        self.presets_frame = tk.Frame(self.panel_settings, bg=self.colors["panel"])
        self.presets_frame.pack(fill="x", pady=(5, 0))

        self.lbl_presets = tk.Label(self.presets_frame, bg=self.colors["panel"], fg=self.colors["subtext"], font=("Segoe UI", 9))
        self.lbl_presets.pack(side="left", padx=(0, 5))

        for p_val in [1, 5, 10, 25, 50, 75, 100]:
            btn = tk.Button(self.presets_frame, text=f"{p_val}%", command=lambda v=p_val: self.set_preset_speed(v), bg=self.colors["btn_bg"], fg=self.colors["fg"], activebackground=self.colors["accent"], bd=0, padx=8, pady=2, font=("Segoe UI", 8), cursor="hand2")
            btn.pack(side="left", padx=2)

        self.include_children = tk.BooleanVar(value=False)
        self.cb_children = tk.Checkbutton(self.presets_frame, variable=self.include_children, bg=self.colors["panel"], fg=self.colors["fg"], selectcolor=self.colors["bg"], activebackground=self.colors["panel"], activeforeground=self.colors["fg"], font=("Segoe UI", 9))
        self.cb_children.pack(side="right")

        controls_frame = tk.Frame(self.main_view, bg=self.colors["bg"])
        controls_frame.pack(fill="x", padx=15, pady=10)

        self.btn_start = tk.Button(controls_frame, command=self.start_slowdown, bg=self.colors["green"], fg="#11111b", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=6, cursor="hand2")
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = tk.Button(controls_frame, command=self.stop_slowdown, bg=self.colors["red"], fg="#11111b", font=("Segoe UI", 10, "bold"), bd=0, padx=15, pady=6, state="disabled", cursor="hand2")
        self.btn_stop.pack(side="left")

        self.status_label = tk.Label(controls_frame, bg=self.colors["bg"], fg=self.colors["subtext"], font=("Segoe UI", 10))
        self.status_label.pack(side="right")

    def create_settings_view(self):
        top_frame = tk.Frame(self.settings_view, bg=self.colors["bg"])
        top_frame.pack(fill="x", padx=20, pady=20)

        self.btn_back = tk.Button(top_frame, command=self.show_main_view, bg=self.colors["btn_bg"], fg=self.colors["fg"], activebackground=self.colors["accent"], bd=0, padx=15, pady=6, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.btn_back.pack(side="left")

        self.settings_title_lbl = tk.Label(top_frame, bg=self.colors["bg"], fg=self.colors["accent"], font=("Segoe UI", 11, "bold"))
        self.settings_title_lbl.pack(side="left", padx=20)

        self.form_frame = tk.Frame(self.settings_view, bg=self.colors["panel"], padx=25, pady=20)
        self.form_frame.pack(fill="x", padx=20, pady=5)

        self.lbl_hk_start = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_hk_start.grid(row=0, column=0, sticky="w", pady=6)

        self.lbl_hk_stop = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_hk_stop.grid(row=1, column=0, sticky="w", pady=6)

        self.lbl_hk_speed_up = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_hk_speed_up.grid(row=2, column=0, sticky="w", pady=6)

        self.lbl_hk_speed_down = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["fg"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_hk_speed_down.grid(row=3, column=0, sticky="w", pady=6)

        self.hotkey_entries = {}
        for idx, action in enumerate(["start", "stop", "speed_up", "speed_down"]):
            entry = tk.Entry(self.form_frame, bg=self.colors["entry_bg"], fg=self.colors["accent"], insertbackground=self.colors["fg"], width=22, justify="center", font=("Segoe UI", 10, "bold"), bd=1, relief="solid")
            entry.grid(row=idx, column=1, padx=(20, 0), pady=6)
            entry.bind("<FocusIn>", lambda e, ent=entry: self.on_entry_focus_in(ent))
            entry.bind("<Key>", lambda e, ent=entry: self.on_entry_key_press(e, ent))
            self.hotkey_entries[action] = entry

        sep1 = ttk.Separator(self.form_frame, orient="horizontal")
        sep1.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)

        self.lbl_lang = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["accent"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_lang.grid(row=5, column=0, sticky="w", pady=6)

        self.combo_lang = ttk.Combobox(self.form_frame, values=["English", "Русский"], state="readonly", width=20, font=("Segoe UI", 10, "bold"), style="TCombobox")
        self.combo_lang.grid(row=5, column=1, padx=(20, 0), pady=6)

        self.lbl_theme = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["accent"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_theme.grid(row=6, column=0, sticky="w", pady=6)

        self.combo_theme = ttk.Combobox(self.form_frame, state="readonly", width=20, font=("Segoe UI", 10, "bold"), style="TCombobox")
        self.combo_theme.grid(row=6, column=1, padx=(20, 0), pady=6)

        self.lbl_proc_mode = tk.Label(self.form_frame, bg=self.colors["panel"], fg=self.colors["accent"], anchor="w", font=("Segoe UI", 10, "bold"))
        self.lbl_proc_mode.grid(row=7, column=0, sticky="w", pady=6)

        self.combo_proc_mode = ttk.Combobox(self.form_frame, state="readonly", width=20, font=("Segoe UI", 10, "bold"), style="TCombobox")
        self.combo_proc_mode.grid(row=7, column=1, padx=(20, 0), pady=6)

        self.btn_save = tk.Button(self.settings_view, command=self.save_settings, bg=self.colors["green"], fg="#11111b", font=("Segoe UI", 11, "bold"), bd=0, padx=20, pady=8, cursor="hand2")
        self.btn_save.pack(anchor="e", padx=20, pady=15)

    def on_entry_focus_in(self, entry):
        entry.delete(0, tk.END)
        entry.insert(0, self.t("press_key"))

    def on_entry_key_press(self, event, entry):
        key_name = event.keysym.lower()
        mapping = {"prior": "page_up", "next": "page_down", "plus": "+", "minus": "-", "equal": "=", "kp_add": "+", "kp_subtract": "-", "space": "space", "return": "enter", "backspace": "backspace", "escape": "esc"}
        final_key = mapping.get(key_name, key_name)

        if len(event.char) == 1 and event.char.isprintable() and not event.char.isspace():
            final_key = event.char.lower()

        entry.delete(0, tk.END)
        entry.insert(0, final_key)
        self.settings_view.focus_set()
        return "break"

    def start_global_hotkeys(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.keyboard_listener = keyboard.Listener(on_press=self.on_global_key_press)
        self.keyboard_listener.daemon = True
        self.keyboard_listener.start()

    def on_global_key_press(self, key):
        try:
            key_str = ""
            if isinstance(key, keyboard.Key):
                key_str = key.name.lower()
            elif isinstance(key, keyboard.KeyCode):
                if key.char:
                    key_str = key.char.lower()
                elif key.vk is not None:
                    if key.vk == 107: key_str = "+"
                    elif key.vk == 109: key_str = "-"

            target_up = self.hotkeys["speed_up"].lower()
            target_down = self.hotkeys["speed_down"].lower()

            if key_str == self.hotkeys["start"].lower():
                self.root.after_idle(self.start_slowdown)
            elif key_str == self.hotkeys["stop"].lower():
                self.root.after_idle(self.stop_slowdown)
            elif key_str == target_up or (target_up == "+" and key_str in ["+", "="]):
                self.root.after_idle(lambda: self.change_speed_step(5))
            elif key_str == target_down or (target_down == "-" and key_str in ["-"]):
                self.root.after_idle(lambda: self.change_speed_step(-5))
        except Exception:
            pass

    def change_speed_step(self, delta):
        new_val = max(1, min(100, self.speed_var.get() + delta))
        self.speed_var.set(new_val)
        self.update_speed_label(new_val)

    def set_preset_speed(self, val):
        self.speed_var.set(val)
        self.update_speed_label(val)

    def get_taskbar_pids(self):
        taskbar_pids = set()
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_windows_callback(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0 and user32.GetParent(hwnd) == 0:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    taskbar_pids.add(pid.value)
            return True

        cb = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb, 0)
        return taskbar_pids

    def refresh_processes(self):
        self.all_processes = []
        visible_pids = self.get_taskbar_pids() if self.process_view_mode == "simple" else None

        for p in psutil.process_iter(["pid", "name", "status", "exe"]):
            try:
                info = p.info
                if not info["name"]: continue
                pid = info["pid"]

                if self.process_view_mode == "simple" and pid not in visible_pids:
                    continue

                self.all_processes.append({"pid": pid, "name": info["name"], "status": info["status"] or "", "exe": info["exe"] or ""})
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self.all_processes.sort(key=lambda x: x["name"].lower())
        self.filter_processes()

    def filter_processes(self):
        search = self.search_var.get().lower().strip()
        self.tree.delete(*self.tree.get_children())

        for p in self.all_processes:
            if not search or search in p["name"].lower() or search in str(p["pid"]):
                self.tree.insert("", "end", iid=str(p["pid"]), values=(p["name"], p["pid"], p["status"], p["exe"]))

    def update_speed_label(self, val):
        val_int = int(val)
        self.speed_label.config(text=f"{val_int}%")
        self.current_speed = val_int

    def get_selected_process(self):
        selection = self.tree.selection()
        if not selection: return None
        try:
            return psutil.Process(int(selection[0]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def get_target_processes(self, root_proc):
        processes = [root_proc]
        if self.include_children.get():
            try:
                processes.extend([c for c in root_proc.children(recursive=True) if c.is_running()])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return list({p.pid: p for p in processes}.values())

    def precise_sleep(self, duration):
        if duration <= 0: return
        start = time.perf_counter()
        while (time.perf_counter() - start) < duration:
            if duration - (time.perf_counter() - start) > 0.002:
                time.sleep(0.001)

    def start_slowdown(self):
        if self.running: return

        proc = self.get_selected_process()
        if not proc:
            messagebox.showwarning(self.t("warn_title"), self.t("warn_select_proc"), parent=self.root)
            return

        try:
            name, pid = proc.name(), proc.pid
            proc.status()
        except psutil.AccessDenied:
            messagebox.showerror(self.t("err_title"), self.t("err_admin"), parent=self.root)
            return
        except psutil.NoSuchProcess:
            messagebox.showerror(self.t("err_title"), self.t("err_proc_closed"), parent=self.root)
            self.refresh_processes()
            return

        self.target_proc = proc
        self.running = True
        self.suspended_pids.clear()

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status_label.config(text=self.t("status_active").format(name=name, pid=pid), fg=self.colors["green"])

        threading.Thread(target=self.process_loop, daemon=True).start()

    def process_loop(self):
        try:
            while self.running:
                speed = self.current_speed
                if speed >= 100:
                    time.sleep(0.05)
                    continue

                if speed < 10: base_work_time = 0.002
                elif speed < 30: base_work_time = 0.005
                else: base_work_time = 0.015

                ratio = speed / 100.0
                work_time = base_work_time
                freeze_time = (work_time / ratio) - work_time

                self.precise_sleep(work_time)
                if not self.running: break

                procs = self.get_target_processes(self.target_proc)
                for proc in procs:
                    try:
                        if proc.is_running():
                            proc.suspend()
                            self.suspended_pids.add(proc.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                self.precise_sleep(freeze_time)

                for pid in list(self.suspended_pids):
                    try:
                        p = psutil.Process(pid)
                        if p.is_running(): p.resume()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    self.suspended_pids.discard(pid)
        except Exception as e:
            try:
                self.root.after_idle(lambda: messagebox.showerror(self.t("err_title"), f"Thread error: {e}", parent=self.root))
            except Exception:
                pass
        finally:
            self.resume_everything()

    def stop_slowdown(self):
        self.running = False
        self.resume_everything()
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status_label.config(text=self.t("status_stopped"), fg=self.colors["subtext"])

    def resume_everything(self):
        for pid in list(self.suspended_pids):
            try:
                proc = psutil.Process(pid)
                if proc.is_running(): proc.resume()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        self.suspended_pids.clear()

    def on_close(self):
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.stop_slowdown()
        self.root.destroy()


if __name__ == "__main__":
    try:
        myappid = "deltahelper.bullethell.slowdown.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    root = tk.Tk()
    app = ProcessSlowerApp(root)
    root.mainloop()
