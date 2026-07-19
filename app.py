from __future__ import annotations

import argparse
import logging
import random
import shutil
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from urllib.parse import urlparse

from autofire import APP_NAME, APP_VERSION
from autofire.logging_setup import configure_logging
from autofire.paths import app_data_dir, database_path
from autofire.scheduler import configure_daily_reminder, remove_daily_reminder
from autofire.storage import Contact, Store


EMOJIS = ("😀", "😃", "😄", "😁", "😊", "😉", "😂", "🤗", "🙂", "😎")


def find_edge() -> str | None:
    found = shutil.which("msedge")
    if found:
        return found
    candidates = (
        Path.home() / "AppData/Local/Microsoft/Edge/Application/msedge.exe",
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    )
    return next((str(path) for path in candidates if path.exists()), None)


class AutoFireApp:
    def __init__(self, root: tk.Tk, store: Store, logger: logging.Logger):
        self.root = root
        self.store = store
        self.logger = logger
        self.plan: list[tuple[Contact, str]] = []

        self.url_var = tk.StringVar(value=self.store.get_setting("url", "https://www.douyin.com/"))
        self.time_var = tk.StringVar(value=self.store.get_setting("reminder_time", "20:00"))
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="准备就绪")

        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("920x650")
        self.root.minsize(800, 560)
        self._build_ui()
        self.refresh_contacts()

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(container, text="AutoFire", font=("Microsoft YaHei UI", 20, "bold"))
        title.pack(anchor=tk.W)
        ttk.Label(
            container,
            text="每日互动提醒与联系人偏好管理 · 登录和最终发送均由用户在官方网页手动完成",
        ).pack(anchor=tk.W, pady=(0, 12))

        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.home_tab = ttk.Frame(self.notebook, padding=12)
        self.contacts_tab = ttk.Frame(self.notebook, padding=12)
        self.preview_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.home_tab, text="启动与提醒")
        self.notebook.add(self.contacts_tab, text="联系人")
        self.notebook.add(self.preview_tab, text="本次预览")

        self._build_home_tab()
        self._build_contacts_tab()
        self._build_preview_tab()
        ttk.Separator(container).pack(fill=tk.X, pady=(10, 6))
        ttk.Label(container, textvariable=self.status_var).pack(anchor=tk.W)

    def _build_home_tab(self) -> None:
        frame = self.home_tab
        ttk.Label(frame, text="抖音网页版地址").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Entry(frame, textvariable=self.url_var, width=70).grid(row=0, column=1, sticky=tk.EW, padx=8)
        ttk.Button(frame, text="保存并用 Edge 打开", command=self.open_douyin).grid(row=0, column=2, sticky=tk.E)

        ttk.Separator(frame).grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=18)
        ttk.Label(frame, text="每日提醒时间（24 小时制）").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Entry(frame, textvariable=self.time_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=8)
        ttk.Button(frame, text="自动配置提醒", command=self.configure_reminder).grid(row=2, column=2, sticky=tk.E)
        ttk.Button(frame, text="移除提醒", command=self.remove_reminder).grid(row=3, column=2, sticky=tk.E, pady=6)

        note = (
            "环境检查：AutoFire 仅需 Windows、已安装的 Microsoft Edge 与可写入的本地数据目录。\n"
            "自动配置会创建当前 Windows 用户的每日提醒任务；它只显示提醒，不会在后台发送消息。"
        )
        ttk.Label(frame, text=note, justify=tk.LEFT).grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(24, 8))
        ttk.Button(frame, text="检查环境", command=self.check_environment).grid(row=5, column=0, sticky=tk.W)
        ttk.Button(frame, text="生成本次表情预览", command=self.generate_plan).grid(row=5, column=1, sticky=tk.W, padx=8)
        ttk.Separator(frame).grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=18)
        ttk.Label(frame, text="网页打开后的操作", font=("Microsoft YaHei UI", 11, "bold")).grid(
            row=7, column=0, columnspan=3, sticky=tk.W
        )
        ttk.Label(
            frame,
            text="1. 在 Edge 中自行登录并点击“消息”；2. 回到此处点击“我已登录，管理联系人”；"
            "3. 录入/导入可私信好友后生成表情预览。",
            justify=tk.LEFT,
            wraplength=720,
        ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(6, 10))
        ttk.Button(frame, text="我已登录，管理联系人", command=self.start_after_login).grid(
            row=8, column=2, sticky=tk.E
        )
        frame.columnconfigure(1, weight=1)

    def _build_contacts_tab(self) -> None:
        toolbar = ttk.Frame(self.contacts_tab)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(toolbar, text="搜索").pack(side=tk.LEFT)
        search = ttk.Entry(toolbar, textvariable=self.search_var, width=28)
        search.pack(side=tk.LEFT, padx=6)
        search.bind("<KeyRelease>", lambda _event: self.refresh_contacts())
        ttk.Button(toolbar, text="新增", command=self.add_contact_dialog).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="从剪贴板导入", command=self.import_clipboard).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="全选", command=lambda: self.set_visible_selected(True)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="取消全选", command=lambda: self.set_visible_selected(False)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="下一步：生成预览", command=self.generate_plan).pack(side=tk.LEFT, padx=12)
        ttk.Button(toolbar, text="编辑", command=self.edit_contact_dialog).pack(side=tk.RIGHT, padx=3)
        ttk.Button(toolbar, text="🗑", width=3, command=self.delete_contact).pack(side=tk.RIGHT, padx=3)

        columns = ("selected", "nickname", "remark", "updated")
        self.contact_tree = ttk.Treeview(self.contacts_tab, columns=columns, show="headings", selectmode="extended")
        self.contact_tree.heading("selected", text="选择")
        self.contact_tree.heading("nickname", text="昵称")
        self.contact_tree.heading("remark", text="备注（优先显示）")
        self.contact_tree.heading("updated", text="最近修改")
        self.contact_tree.column("selected", width=70, anchor=tk.CENTER, stretch=False)
        self.contact_tree.column("nickname", width=180)
        self.contact_tree.column("remark", width=220)
        self.contact_tree.column("updated", width=190)
        self.contact_tree.pack(fill=tk.BOTH, expand=True)
        self.contact_tree.bind("<Double-1>", self.toggle_clicked_contact)
        ttk.Label(
            self.contacts_tab,
            text="双击联系人行可切换勾选。导入格式：每行“昵称”或“昵称|备注”。联系人由用户自行从可私信好友列表录入。",
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_preview_tab(self) -> None:
        ttk.Label(self.preview_tab, text="本次互动预览", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            self.preview_tab,
            text="每次生成均从常用笑脸中随机挑选。请在网页内逐一打开会话并由你本人完成最终发送。",
        ).pack(anchor=tk.W, pady=(2, 10))
        self.preview_tree = ttk.Treeview(self.preview_tab, columns=("contact", "emoji"), show="headings")
        self.preview_tree.heading("contact", text="联系人")
        self.preview_tree.heading("emoji", text="建议表情")
        self.preview_tree.column("contact", width=420)
        self.preview_tree.column("emoji", width=140, anchor=tk.CENTER)
        self.preview_tree.pack(fill=tk.BOTH, expand=True)
        buttons = ttk.Frame(self.preview_tab)
        buttons.pack(fill=tk.X, pady=10)
        ttk.Button(buttons, text="重新随机", command=self.generate_plan).pack(side=tk.LEFT)
        ttk.Button(buttons, text="复制表情清单", command=self.copy_plan).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="确认联系人清单", command=self.confirm_selection).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="记录本次已手动处理", command=self.record_manual_completion).pack(side=tk.RIGHT)

    def _save_url(self) -> str | None:
        value = self.url_var.get().strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            messagebox.showerror(APP_NAME, "请输入有效的 http 或 https 网页地址。")
            return None
        self.store.set_setting("url", value)
        return value

    def open_douyin(self) -> None:
        url = self._save_url()
        if not url:
            return
        edge = find_edge()
        try:
            if edge:
                subprocess.Popen([edge, url])
            else:
                webbrowser.open(url)
                messagebox.showwarning(APP_NAME, "未找到 Edge，已使用系统默认浏览器打开。")
        except OSError as error:
            messagebox.showerror(APP_NAME, f"无法打开浏览器：{error}")
            return
        self.logger.info("Opened user-selected website: %s", url)
        self.status_var.set("已打开网页：请自行登录、点击“消息”，完成后回到本程序点击“我已登录，管理联系人”。")

    def start_after_login(self) -> None:
        self.notebook.select(self.contacts_tab)
        self.status_var.set("请录入或从剪贴板导入可私信好友，勾选后点击“下一步：生成预览”。")

    def check_environment(self) -> None:
        checks = [
            ("本地数据目录", str(app_data_dir())),
            ("Microsoft Edge", find_edge() or "未找到（将使用默认浏览器）"),
            ("Python 运行环境", sys.executable),
        ]
        messagebox.showinfo(APP_NAME, "环境检查完成：\n\n" + "\n".join(f"{name}：{value}" for name, value in checks))
        self.status_var.set("环境检查完成。")

    def configure_reminder(self) -> None:
        time_value = self.time_var.get().strip()
        try:
            hour, minute = (int(piece) for piece in time_value.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_NAME, "时间格式应为 HH:MM，例如 20:00。")
            return
        normalized = f"{hour:02d}:{minute:02d}"
        if not messagebox.askyesno(APP_NAME, f"将在每天 {normalized} 显示提醒。是否继续？"):
            return
        ok, detail = configure_daily_reminder(normalized)
        if not ok:
            self.logger.error("Could not configure reminder: %s", detail)
            messagebox.showerror(APP_NAME, f"配置提醒失败：{detail}")
            return
        self.time_var.set(normalized)
        self.store.set_setting("reminder_time", normalized)
        self.logger.info("Configured daily reminder at %s", normalized)
        messagebox.showinfo(APP_NAME, detail)
        self.status_var.set(f"每日 {normalized} 的后台提醒已配置。")

    def remove_reminder(self) -> None:
        if not messagebox.askyesno(APP_NAME, "确定要移除 Windows 每日提醒吗？"):
            return
        ok, detail = remove_daily_reminder()
        if ok:
            self.logger.info("Removed daily reminder")
            messagebox.showinfo(APP_NAME, detail)
            self.status_var.set("每日提醒已移除。")
        else:
            messagebox.showerror(APP_NAME, f"移除提醒失败：{detail}")

    def refresh_contacts(self) -> None:
        for item in self.contact_tree.get_children():
            self.contact_tree.delete(item)
        for contact in self.store.list_contacts(self.search_var.get()):
            marker = "✓" if contact.selected else ""
            self.contact_tree.insert(
                "",
                tk.END,
                iid=str(contact.id),
                values=(marker, contact.nickname, contact.remark, contact.updated_at.replace("T", " ")),
            )

    def selected_tree_ids(self) -> list[int]:
        return [int(item) for item in self.contact_tree.selection()]

    def toggle_clicked_contact(self, event: tk.Event) -> None:
        item = self.contact_tree.identify_row(event.y)
        if not item:
            return
        current = self.store.list_contacts()
        target = next((contact for contact in current if contact.id == int(item)), None)
        if target:
            self.store.set_selected([target.id], not target.selected)
            self.refresh_contacts()

    def set_visible_selected(self, selected: bool) -> None:
        ids = [contact.id for contact in self.store.list_contacts(self.search_var.get())]
        self.store.set_selected(ids, selected)
        self.refresh_contacts()
        self.status_var.set("已更新当前筛选结果的勾选状态。")

    def add_contact_dialog(self) -> None:
        self.contact_dialog(None)

    def edit_contact_dialog(self) -> None:
        ids = self.selected_tree_ids()
        if len(ids) != 1:
            messagebox.showinfo(APP_NAME, "请先选择一个联系人进行编辑。")
            return
        contact = next(item for item in self.store.list_contacts() if item.id == ids[0])
        self.contact_dialog(contact)

    def contact_dialog(self, existing: Contact | None) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑联系人" if existing else "新增联系人")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        nickname = tk.StringVar(value=existing.nickname if existing else "")
        remark = tk.StringVar(value=existing.remark if existing else "")
        ttk.Label(dialog, text="昵称").grid(row=0, column=0, padx=12, pady=10, sticky=tk.W)
        ttk.Entry(dialog, textvariable=nickname, width=35).grid(row=0, column=1, padx=12, pady=10)
        ttk.Label(dialog, text="备注").grid(row=1, column=0, padx=12, pady=10, sticky=tk.W)
        ttk.Entry(dialog, textvariable=remark, width=35).grid(row=1, column=1, padx=12, pady=10)

        def save() -> None:
            try:
                if existing:
                    self.store.update_contact(existing.id, nickname.get(), remark.get())
                else:
                    self.store.add_contact(nickname.get(), remark.get())
            except ValueError as error:
                messagebox.showerror(APP_NAME, str(error), parent=dialog)
                return
            self.logger.info("Saved contact preference")
            dialog.destroy()
            self.refresh_contacts()

        ttk.Button(dialog, text="保存", command=save).grid(row=2, column=1, padx=12, pady=(4, 12), sticky=tk.E)

    def delete_contact(self) -> None:
        ids = self.selected_tree_ids()
        if not ids:
            messagebox.showinfo(APP_NAME, "请先选择要删除的联系人。")
            return
        if not messagebox.askyesno(APP_NAME, f"确定删除选中的 {len(ids)} 位联系人吗？"):
            return
        for contact_id in ids:
            self.store.delete_contact(contact_id)
        self.logger.info("Deleted %d local contact preference(s)", len(ids))
        self.refresh_contacts()

    def import_clipboard(self) -> None:
        try:
            raw = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(APP_NAME, "剪贴板中没有可导入的文本。")
            return
        added = 0
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            nickname, separator, remark = line.partition("|")
            try:
                self.store.add_contact(nickname, remark if separator else "")
                added += 1
            except ValueError:
                continue
        self.refresh_contacts()
        self.logger.info("Imported %d local contact preference(s)", added)
        messagebox.showinfo(APP_NAME, f"已导入 {added} 位联系人。")

    def generate_plan(self) -> None:
        contacts = self.store.selected_contacts()
        if not contacts:
            messagebox.showinfo(APP_NAME, "请先在“联系人”页至少勾选一位联系人。")
            return
        self.plan = [(contact, random.choice(EMOJIS)) for contact in contacts]
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        for contact, emoji in self.plan:
            self.preview_tree.insert("", tk.END, values=(contact.label, emoji))
        self.notebook.select(self.preview_tab)
        self.status_var.set(f"已生成 {len(self.plan)} 位联系人的表情预览。")
        if self.store.needs_selection_confirmation():
            summary = "\n".join(f"• {contact.label}：{emoji}" for contact, emoji in self.plan)
            if messagebox.askyesno(APP_NAME, "联系人清单首次使用或已变更，请确认：\n\n" + summary):
                self.store.confirm_current_selection()
                self.logger.info("Confirmed selected contact list (%d contacts)", len(self.plan))
                self.status_var.set("联系人清单已确认。")

    def confirm_selection(self) -> None:
        if not self.plan:
            self.generate_plan()
            if not self.plan:
                return
        summary = "\n".join(f"• {contact.label}：{emoji}" for contact, emoji in self.plan)
        if messagebox.askyesno(APP_NAME, "请确认当前联系人清单：\n\n" + summary):
            self.store.confirm_current_selection()
            self.logger.info("Manually confirmed selected contact list (%d contacts)", len(self.plan))
            self.status_var.set("联系人清单已确认。")

    def copy_plan(self) -> None:
        if not self.plan:
            messagebox.showinfo(APP_NAME, "请先生成本次预览。")
            return
        lines = [f"{contact.label}：{emoji}" for contact, emoji in self.plan]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.status_var.set("本次表情清单已复制到剪贴板。")

    def record_manual_completion(self) -> None:
        if not self.plan:
            messagebox.showinfo(APP_NAME, "请先生成本次预览。")
            return
        if not messagebox.askyesno(APP_NAME, "确认已在网页内自行完成本次互动并记录吗？"):
            return
        details = "; ".join(f"{contact.label}:{emoji}" for contact, emoji in self.plan)
        self.store.record_run(len(self.plan), "manual_completion", details)
        self.logger.info("Recorded manual completion for %d contact(s): %s", len(self.plan), details)
        self.status_var.set("已记录本次手动处理结果。")
        messagebox.showinfo(APP_NAME, "已写入本地执行记录。")


def show_reminder() -> bool:
    root = tk.Tk()
    root.withdraw()
    start = messagebox.askyesno(APP_NAME, "到设定时间了。是否现在打开 AutoFire？", parent=root)
    root.destroy()
    return start


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--reminder", action="store_true")
    args, _ = parser.parse_known_args()
    if args.reminder and not show_reminder():
        return

    logger = configure_logging()
    logger.info("Starting AutoFire")
    root = tk.Tk()
    AutoFireApp(root, Store(database_path()), logger)
    root.mainloop()


if __name__ == "__main__":
    main()
