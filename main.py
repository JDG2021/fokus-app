import sqlite3
from datetime import date, timedelta, datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.animation import Animation

import matplotlib.pyplot as plt

try:
    from plyer import notification
except ImportError:
    notification = None


# ------------------ THEME ------------------
PRIMARY = (0.18, 0.55, 0.95, 1)
SUCCESS = (0.25, 0.75, 0.45, 1)
DANGER = (0.85, 0.25, 0.25, 1)
BG = (0.96, 0.97, 0.98, 1)
CARD = (1, 1, 1, 1)
TEXT = (0.1, 0.1, 0.1, 1)
MUTED = (0.6, 0.6, 0.6, 1)

DB_NAME = "habits.db"
Window.size = (360, 640)


# ------------------ HABIT CARD ------------------
class HabitCard(BoxLayout):
    def __init__(self, habit_id, name, streak, done_today, callback, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.habit_id = habit_id
        self.callback = callback

        self.size_hint_y = None
        self.height = 84
        self.padding = 16
        self.spacing = 12

        with self.canvas.before:
            Color(*CARD)
            self.rect = RoundedRectangle(radius=[20])
        self.bind(pos=self.update_rect, size=self.update_rect)

        self.label = Button(
            text=f"[b]{name}[/b]\n[color=777777]{streak} dagar i rad[/color]",
            markup=True,
            halign="left",
            valign="middle",
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT
        )
        self.label.bind(
            size=lambda i, v: setattr(i, "text_size", (i.width, None))
        )
        self.label.bind(on_press=lambda x: callback(self, edit=True))

        self.button = Button(
            text="✓ Klar" if done_today else "Klar",
            size_hint_x=None,
            width=88,
            background_normal="",
            background_color=SUCCESS if done_today else PRIMARY,
            color=(1, 1, 1, 1)
        )
        self.button.disabled = done_today
        self.button.scale = 1
        self.button.bind(on_press=self.on_press)

        self.add_widget(self.label)
        self.add_widget(self.button)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_press(self, instance):
        anim = Animation(scale=0.95, duration=0.05) + Animation(scale=1, duration=0.05)
        anim.start(instance)
        self.callback(self, edit=False)


# ------------------ MAIN LAYOUT ------------------
class FokusLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=16, padding=16, **kwargs)

        self.db = sqlite3.connect(DB_NAME)
        self.today = date.today()
        self.yesterday = self.today - timedelta(days=1)

        self.create_tables()

        self.add_widget(Label(
            text="Fokus",
            font_size=32,
            bold=True,
            size_hint_y=None,
            height=64,
            color=TEXT
        ))

        self.add_widget(Label(
            text="Created by R.H.",
            font_size=11,
            size_hint_y=None,
            height=16,
            color=MUTED
        ))

        self.add_widget(self.action_button("Statistik", self.show_graph))
        self.add_widget(self.action_button("Påminnelse", self.reminder_popup))

        self.scroll = ScrollView()
        self.list_layout = BoxLayout(
            orientation="vertical",
            spacing=14,
            size_hint_y=None
        )
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        self.scroll.add_widget(self.list_layout)
        self.add_widget(self.scroll)

        add_btn = Button(
            text="+ Ny vana",
            size_hint_y=None,
            height=60,
            font_size=18,
            background_normal="",
            background_color=PRIMARY,
            color=(1, 1, 1, 1)
        )
        add_btn.bind(on_press=self.add_habit_popup)
        self.add_widget(add_btn)

        self.load_habits()
        Clock.schedule_interval(self.check_reminder, 60)

        self.opacity = 0
        Animation(opacity=1, duration=0.3).start(self)

    def action_button(self, text, callback):
        btn = Button(
            text=text,
            size_hint_y=None,
            height=52,
            background_normal="",
            background_color=(0.88, 0.92, 0.97, 1),
            color=TEXT
        )
        btn.bind(on_press=lambda x: callback())
        return btn

    # ------------------ DATABASE ------------------
    def create_tables(self):
        cur = self.db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                last_done TEXT,
                streak INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS history (
                day TEXT PRIMARY KEY,
                done INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.db.commit()

    def load_habits(self):
        self.list_layout.clear_widgets()
        for hid, name, last_done, streak in self.db.execute(
            "SELECT id, name, last_done, streak FROM habits"
        ):
            self.list_layout.add_widget(
                HabitCard(
                    hid,
                    name,
                    streak or 0,
                    last_done == self.today.isoformat(),
                    self.handle_action
                )
            )

    # ------------------ LOGIK ------------------
    def handle_action(self, card, edit=False):
        if edit:
            self.delete_popup(card)
            return

        cur = self.db.cursor()
        cur.execute("SELECT last_done, streak FROM habits WHERE id=?", (card.habit_id,))
        last_done, streak = cur.fetchone()

        if last_done == self.today.isoformat():
            return

        streak = streak + 1 if last_done == self.yesterday.isoformat() else 1

        Animation(opacity=0.3, duration=0.1).start(card)

        self.db.execute(
            "UPDATE habits SET last_done=?, streak=? WHERE id=?",
            (self.today.isoformat(), streak, card.habit_id)
        )
        self.db.commit()

        self.update_history()
        Clock.schedule_once(lambda dt: self.load_habits(), 0.12)

    def update_history(self):
        cur = self.db.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM habits WHERE last_done=?",
            (self.today.isoformat(),)
        )
        done = cur.fetchone()[0]
        cur.execute(
            "INSERT OR REPLACE INTO history (day, done) VALUES (?,?)",
            (self.today.isoformat(), done)
        )
        self.db.commit()

    # ------------------ POPUPS ------------------
    def add_habit_popup(self, _):
        box = BoxLayout(orientation="vertical", spacing=12, padding=12)
        field = TextInput(hint_text="Ny vana", multiline=False)
        save = Button(text="Spara", size_hint_y=None, height=50, background_color=PRIMARY)

        box.add_widget(field)
        box.add_widget(save)

        popup = Popup(title="Ny vana", content=box, size_hint=(0.85, 0.4))

        save.bind(on_press=lambda x: (
            self.db.execute(
                "INSERT INTO habits (name, last_done, streak) VALUES (?, ?, 0)",
                (field.text.strip(), None)
            ),
            self.db.commit(),
            self.load_habits(),
            popup.dismiss()
        ) if field.text.strip() else None)

        popup.open()

    def delete_popup(self, card):
        box = BoxLayout(orientation="vertical", spacing=12, padding=12)
        del_btn = Button(text="Ta bort vana", background_color=DANGER, size_hint_y=None, height=50)
        cancel = Button(text="Avbryt", size_hint_y=None, height=50)

        box.add_widget(del_btn)
        box.add_widget(cancel)

        popup = Popup(title="Alternativ", content=box, size_hint=(0.8, 0.35))

        del_btn.bind(on_press=lambda x: (
            self.db.execute("DELETE FROM habits WHERE id=?", (card.habit_id,)),
            self.db.commit(),
            self.load_habits(),
            popup.dismiss()
        ))
        cancel.bind(on_press=popup.dismiss)

        popup.open()

    # ------------------ STATISTIK ------------------
    def show_graph(self):
        cur = self.db.cursor()
        days, values = [], []

        for i in range(6, -1, -1):
            d = (self.today - timedelta(days=i)).isoformat()
            cur.execute("SELECT done FROM history WHERE day=?", (d,))
            r = cur.fetchone()
            days.append(d[-5:])
            values.append(r[0] if r else 0)

        plt.figure(figsize=(4.5, 2.8))
        plt.bar(days, values)
        plt.title("Senaste 7 dagarna", fontsize=12)
        plt.tight_layout()
        plt.savefig("stats.png")
        plt.close()

        Popup(
            title="Statistik",
            content=Image(source="stats.png"),
            size_hint=(0.9, 0.6)
        ).open()

    # ------------------ PÅMINNELSE ------------------
    def reminder_popup(self):
        box = BoxLayout(orientation="vertical", spacing=12, padding=12)
        field = TextInput(hint_text="HH:MM", multiline=False)
        save = Button(text="Spara", size_hint_y=None, height=50, background_color=PRIMARY)

        box.add_widget(field)
        box.add_widget(save)

        popup = Popup(title="Daglig påminnelse", content=box, size_hint=(0.8, 0.4))

        save.bind(on_press=lambda x: (
            self.db.execute(
                "INSERT OR REPLACE INTO settings (key,value) VALUES ('reminder_time',?)",
                (field.text,)
            ),
            self.db.commit(),
            popup.dismiss()
        ))

        popup.open()

    def check_reminder(self, dt):
        if not notification:
            return

        cur = self.db.cursor()
        cur.execute("SELECT value FROM settings WHERE key='reminder_time'")
        row = cur.fetchone()

        if row and datetime.now().strftime("%H:%M") == row[0]:
            notification.notify(
                title="Fokus",
                message="Dags att fokusera på dina vanor.",
                timeout=10
            )


class FokusApp(App):
    def build(self):
        Window.clearcolor = BG
        return FokusLayout()


FokusApp().run()
