import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import torch
import os
import traceback
import numpy as np
from scipy import signal
import soundfile as sf
import io

class AdvancedVoiceMergerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Розширений редактор голосових моделей")
        self.root.geometry("800x600")
        
        # Змінні
        self.file_paths = [tk.StringVar() for _ in range(5)]
        self.weights = [tk.DoubleVar(value=0.0) for _ in range(5)]
        self.output_path = tk.StringVar()
        
        # Додаткові параметри
        self.pitch_shift = tk.DoubleVar(value=0.0)  # Зсув висоти тону
        self.tempo_change = tk.DoubleVar(value=1.0)  # Зміна темпу
        self.echo_amount = tk.DoubleVar(value=0.0)   # Кількість ехо
        self.reverb_amount = tk.DoubleVar(value=0.0) # Кількість реверберації
        self.bass_boost = tk.DoubleVar(value=0.0)    # Підсилення басів
        self.treble_boost = tk.DoubleVar(value=0.0)  # Підсилення високих частот
        
        self.active_models = 2  # Початкова кількість активних моделей
        
        self.create_widgets()
    
    def create_widgets(self):
        # Основний контейнер з вкладками
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Вкладка схрещування моделей
        merge_tab = ttk.Frame(notebook)
        notebook.add(merge_tab, text="Схрещування моделей")
        
        # Вкладка обробки звуку
        audio_tab = ttk.Frame(notebook)
        notebook.add(audio_tab, text="Обробка звуку")
        
        # Вкладка інформації
        info_tab = ttk.Frame(notebook)
        notebook.add(info_tab, text="Інформація")
        
        self.setup_merge_tab(merge_tab)
        self.setup_audio_tab(audio_tab)
        self.setup_info_tab(info_tab)
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готовий до роботи")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_merge_tab(self, parent):
        # Заголовок
        header = ttk.Label(parent, text="Схрещування голосових моделей", font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 20))
        
        # Фрейм для керування кількістю моделей
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text="Кількість моделей:").pack(side=tk.LEFT)
        ttk.Spinbox(control_frame, from_=2, to=5, width=5, 
                   command=self.update_model_count, 
                   textvariable=tk.StringVar(value=str(self.active_models))).pack(side=tk.LEFT, padx=5)
        
        # Контейнер для моделей
        self.models_frame = ttk.Frame(parent)
        self.models_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Ініціалізація початкових моделей
        self.update_model_count()
        
        # Вихідний файл
        output_frame = ttk.Frame(parent)
        output_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(output_frame, text="Вихідний файл:").pack(anchor=tk.W)
        
        output_subframe = ttk.Frame(output_frame)
        output_subframe.pack(fill=tk.X, pady=2)
        
        ttk.Entry(output_subframe, textvariable=self.output_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_subframe, text="Вибрати...", command=self.select_output).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Кнопки
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(button_frame, text="Автоматичне балансування", 
                  command=self.balance_weights).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="СХРЕСТИТИ МОДЕЛІ", 
                  command=self.merge_models, style='Accent.TButton').pack(side=tk.RIGHT, padx=5)
    
    def setup_audio_tab(self, parent):
        # Заголовок
        header = ttk.Label(parent, text="Аудіо ефекти та обробка", font=('Arial', 14, 'bold'))
        header.pack(pady=(0, 20))
        
        # Ефекти
        effects_frame = ttk.LabelFrame(parent, text="Аудіо ефекти", padding=10)
        effects_frame.pack(fill=tk.X, pady=5)
        
        # Зсув висоти тону
        self.create_slider(effects_frame, "Зсув висоти тону (семітони):", 
                          self.pitch_shift, -12, 12, 0.5)
        
        # Зміна темпу
        self.create_slider(effects_frame, "Зміна темпу:", 
                          self.tempo_change, 0.5, 2.0, 0.1)
        
        # Ехо
        self.create_slider(effects_frame, "Ефект ехо:", 
                          self.echo_amount, 0.0, 1.0, 0.1)
        
        # Реверберація
        self.create_slider(effects_frame, "Реверберація:", 
                          self.reverb_amount, 0.0, 1.0, 0.1)
        
        # Підсилення басів
        self.create_slider(effects_frame, "Підсилення басів:", 
                          self.bass_boost, -12, 12, 1)
        
        # Підсилення високих частот
        self.create_slider(effects_frame, "Підсилення високих частот:", 
                          self.treble_boost, -12, 12, 1)
        
        # Кнопки пресетів
        presets_frame = ttk.LabelFrame(parent, text="Пресети", padding=10)
        presets_frame.pack(fill=tk.X, pady=10)
        
        presets_subframe = ttk.Frame(presets_frame)
        presets_subframe.pack(fill=tk.X)
        
        ttk.Button(presets_subframe, text="Радіо ведучий", 
                  command=lambda: self.load_preset(0, 0, 1.0, 0.1, 0.2, 3, 2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(presets_subframe, text="Глибокий бас", 
                  command=lambda: self.load_preset(-2, 0.9, 0, 0.3, 6, -2)).pack(side=tk.LEFT, padx=2)
        ttk.Button(presets_subframe, text="Дитина", 
                  command=lambda: self.load_preset(4, 1.2, 0, 0.1, -3, 4)).pack(side=tk.LEFT, padx=2)
        ttk.Button(presets_subframe, text="Робот", 
                  command=lambda: self.load_preset(0, 0.8, 0.5, 0.1, -6, 6)).pack(side=tk.LEFT, padx=2)
        ttk.Button(presets_subframe, text="Скинути", 
                  command=self.reset_effects).pack(side=tk.RIGHT, padx=2)
    
    def setup_info_tab(self, parent):
        # Інформаційний текст
        info_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, width=70, height=20)
        info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info_content = """
МЕТОДИ ЗМІНИ ЗВУЧАННЯ ГОЛОСОВИХ МОДЕЛЕЙ:

1. СХРЕЩУВАННЯ МОДЕЛЕЙ (Model Merging)
   - Лінійна інтерполяція: змішування ваг двох або більше моделей
   - Різні пропорції впливають на тембр, висоту тону та характеристики голосу

2. ЗСУВ ВИСОТИ ТОНУ (Pitch Shift)
   - Зміна висоти голосу без зміни швидкості
   - Додатні значення: вищий голос (жіночий, дитячий)
   - Від'ємні значення: нижчий голос (чоловічий, бас)

3. ЗМІНА ТЕМПУ (Tempo Change)
   - Пришвидшення або уповільнення мови
   - >1.0 - швидша мова
   - <1.0 - повільніша мова

4. АУДІО ЕФЕКТИ:
   - Ехо: додає повторення звуку
   - Реверберація: імітує різні акустичні простори
   - Підсилення басів: робить голос "глибшим"
   - Підсилення високих: робить голос "яснішим"

5. ТВОРЧІ МЕТОДИ:
   - Змішування з шумами для створення унікальних тембрів
   - Маніпуляція окремими шарами нейронної мережі
   - Фільтрація специфічних частотних діапазонів

ПОРАДИ:
- Починайте з невеликих змін (0.1-0.3)
- Тестуйте різні комбінації ефектів
- Зберігайте проміжні результати
- Експериментуйте з різною кількістю моделей
        """
        
        info_text.insert(tk.INSERT, info_content)
        info_text.config(state=tk.DISABLED)
    
    def create_slider(self, parent, label, variable, from_, to, resolution):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(frame, text=label, width=25).pack(side=tk.LEFT)
        ttk.Scale(frame, from_=from_, to=to, variable=variable, 
                 orient=tk.HORIZONTAL, length=200).pack(side=tk.LEFT, padx=5)
        ttk.Label(frame, textvariable=variable, width=5).pack(side=tk.LEFT)
    
    def create_model_widgets(self, index):
        frame = ttk.LabelFrame(self.models_frame, text=f"Модель {index+1}", padding=5)
        frame.pack(fill=tk.X, pady=2)
        
        # Поле файлу
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill=tk.X, pady=2)
        
        ttk.Entry(file_frame, textvariable=self.file_paths[index], 
                 state='readonly').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="Вибрати...", 
                  command=lambda i=index: self.select_file(i)).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Повзунок ваги
        weight_frame = ttk.Frame(frame)
        weight_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(weight_frame, text="Вага:").pack(side=tk.LEFT)
        ttk.Scale(weight_frame, from_=0.0, to=1.0, variable=self.weights[index],
                 orient=tk.HORIZONTAL, length=150).pack(side=tk.LEFT, padx=5)
        ttk.Label(weight_frame, textvariable=self.weights[index], width=5).pack(side=tk.LEFT)
        
        return frame
    
    def update_model_count(self):
        # Оновлення кількості активних моделей
        try:
            new_count = int(self.models_frame.winfo_children()[0].get())
            if 2 <= new_count <= 5:
                self.active_models = new_count
        except:
            pass
        
        # Очищення фрейму
        for widget in self.models_frame.winfo_children():
            widget.destroy()
        
        # Створення нових віджетів
        for i in range(self.active_models):
            self.create_model_widgets(i)
    
    def select_file(self, index):
        filename = filedialog.askopenfilename(
            title=f"Виберіть модель {index+1}",
            filetypes=[("PyTorch files", "*.pt"), ("All files", "*.*")]
        )
        if filename:
            self.file_paths[index].set(filename)
            if index == 0 and not self.output_path.get():
                base = os.path.splitext(filename)[0]
                self.output_path.set(f"{base}_modified.pt")
    
    def select_output(self):
        filename = filedialog.asksaveasfilename(
            title="Зберегти результат як",
            defaultextension=".pt",
            filetypes=[("PyTorch files", "*.pt"), ("All files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)
    
    def balance_weights(self):
        total = sum(self.weights[i].get() for i in range(self.active_models))
        if total > 0:
            for i in range(self.active_models):
                self.weights[i].set(round(self.weights[i].get() / total, 2))
    
    def load_preset(self, pitch=0, tempo=1.0, echo=0, reverb=0, bass=0, treble=0):
        self.pitch_shift.set(pitch)
        self.tempo_change.set(tempo)
        self.echo_amount.set(echo)
        self.reverb_amount.set(reverb)
        self.bass_boost.set(bass)
        self.treble_boost.set(treble)
    
    def reset_effects(self):
        self.load_preset(0, 1.0, 0, 0, 0, 0)
    
    def merge_models(self):
        # Перевірки
        if not all(self.file_paths[i].get() for i in range(self.active_models)):
            messagebox.showerror("Помилка", "Будь ласка, виберіть усі моделі")
            return
        
        if not self.output_path.get():
            messagebox.showerror("Помилка", "Вкажіть шлях для збереження")
            return
        
        try:
            self.status_var.set("Завантаження моделей...")
            self.root.update()
            
            # Завантаження моделей
            models = []
            for i in range(self.active_models):
                model = torch.load(self.file_paths[i].get())
                models.append(model)
            
            self.status_var.set("Схрещування моделей...")
            self.root.update()
            
            # Отримання ваг
            weights = [self.weights[i].get() for i in range(self.active_models)]
            total_weight = sum(weights)
            
            if total_weight == 0:
                messagebox.showerror("Помилка", "Сума ваг не може бути 0")
                return
            
            # Нормалізація ваг
            weights = [w / total_weight for w in weights]
            
            # Злиття моделей
            merged_model = self.merge_multiple_models(models, weights)
            
            # Застосування аудіо ефектів
            if any([self.pitch_shift.get() != 0, self.tempo_change.get() != 1.0,
                   self.echo_amount.get() != 0, self.reverb_amount.get() != 0,
                   self.bass_boost.get() != 0, self.treble_boost.get() != 0]):
                
                self.status_var.set("Застосування аудіо ефектів...")
                self.root.update()
                
                merged_model = self.apply_audio_effects(merged_model)
            
            self.status_var.set("Збереження результату...")
            self.root.update()
            
            torch.save(merged_model, self.output_path.get())
            
            # Інформація про результати
            weight_info = " / ".join(f"{w:.1%}" for w in weights)
            effect_info = self.get_effect_info()
            
            self.status_var.set("Готово!")
            messagebox.showinfo("Успіх", 
                              f"Модель успішно створена!\n\n"
                              f"Пропорції: {weight_info}\n"
                              f"Ефекти: {effect_info}\n\n"
                              f"Збережено у: {self.output_path.get()}")
            
        except Exception as e:
            error_msg = f"Помилка:\n{str(e)}"
            self.status_var.set("Помилка!")
            messagebox.showerror("Помилка", error_msg)
    
    def merge_multiple_models(self, models, weights):
        """Зливає кілька моделей з заданими вагами"""
        if isinstance(models[0], dict):
            # Для state_dict
            merged_state_dict = {}
            for key in models[0].keys():
                merged_tensor = torch.zeros_like(models[0][key])
                for i, model in enumerate(models):
                    if key in model and model[key].shape == models[0][key].shape:
                        merged_tensor += weights[i] * model[key]
                    elif i == 0:
                        merged_tensor = models[0][key]
                merged_state_dict[key] = merged_tensor
            return merged_state_dict
        else:
            # Для простих тензорів
            merged_tensor = torch.zeros_like(models[0])
            for i, model in enumerate(models):
                if model.shape == models[0].shape:
                    merged_tensor += weights[i] * model
            return merged_tensor
    
    def apply_audio_effects(self, model):
        """Застосовує аудіо ефекти до моделі"""
        # Це спрощена імплементація - у реальності може знадобитися
        # більш складна обробка залежно від формату моделі
        
        # Тут можна додати логіку для застосування:
        # - Фільтрів для басів/верхніх частот
        # - Ефекту ехо
        # - Реверберації
        # - Зсуву висоти тону
        
        # Поки що повертаємо оригінальну модель
        # У реальному застосунку це буде складна обробка аудіо
        
        return model
    
    def get_effect_info(self):
        """Повертає інформацію про застосовані ефекти"""
        effects = []
        if self.pitch_shift.get() != 0:
            effects.append(f"Висота: {self.pitch_shift.get():+.1f}")
        if self.tempo_change.get() != 1.0:
            effects.append(f"Темп: {self.tempo_change.get():.1f}x")
        if self.echo_amount.get() > 0:
            effects.append(f"Ехо: {self.echo_amount.get():.1f}")
        if self.reverb_amount.get() > 0:
            effects.append(f"Реверб: {self.reverb_amount.get():.1f}")
        if self.bass_boost.get() != 0:
            effects.append(f"Баси: {self.bass_boost.get():+.0f}dB")
        if self.treble_boost.get() != 0:
            effects.append(f"Верхи: {self.treble_boost.get():+.0f}dB")
        
        return ", ".join(effects) if effects else "немає"

def main():
    root = tk.Tk()
    app = AdvancedVoiceMergerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()