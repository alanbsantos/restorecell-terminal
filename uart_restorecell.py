import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import datetime
import os
import subprocess
import webbrowser
from tkinter import font
import time
import json
import requests
from datetime import datetime
from tkinter import colorchooser
import re

class RestoreCellTerminal:
    def __init__(self, root):
        self.root = root
        self.root.title("RESTORECELL Terminal - Software Gratuito")
        self.root.geometry("1000x700")
        
        # Configurações iniciais
        self.VERSION = "1.0.0"
        self.CONFIG_FILE = "restorecell_config.json"
        
        # Variáveis de controle
        self.is_connected = False
        self.auto_scroll = True
        self.current_mode = tk.StringVar(value="UART")
        self.log_filter = tk.StringVar(value="Bruto")
        self.auto_baud_detection = tk.BooleanVar(value=False)
        self.font_size = tk.IntVar(value=10)
        self.max_buffer_lines = tk.IntVar(value=1000)
        self.show_timestamps = tk.BooleanVar(value=True)
        self.dark_mode = tk.BooleanVar(value=False)
        self.current_profile = tk.StringVar(value="Default")
        self.connection_status = tk.StringVar(value="disconnected")
        
        # Controle de threads
        self.stop_threads = False
        self.threads = []
        
        # Inicializar profiles
        self.profiles = {}
        
        # Configurar temas
        self.setup_styles()
        
        # Criar interface
        self.create_main_layout()
        
        # Aplicar tema após criar a interface
        self.apply_theme()
        
        # Criar menu
        self.create_menu()
        
        # Configurações de porta serial
        self.serial_port = None
        self.update_ports_list()
        
        # Iniciar thread de monitoramento
        self.port_monitor_thread = threading.Thread(target=self.monitor_ports, daemon=True)
        self.port_monitor_thread.start()
        
        # Carregar configurações
        self.load_config()
        
        # Verificar atualizações
        self.check_for_updates()

    def setup_styles(self):
        """Configura os temas disponíveis"""
        self.themes = {
            'light': {
                'primary': '#2C3E50',
                'secondary': '#3498DB',
                'accent': '#E74C3C',
                'background': '#ECF0F1',
                'text': '#2C3E50'
            },
            'dark': {
                'primary': '#1a1a1a',
                'secondary': '#2980b9',
                'accent': '#c0392b',
                'background': '#2c2c2c',
                'text': '#ecf0f1'
            }
        }
        
        self.current_theme = self.themes['light' if not self.dark_mode.get() else 'dark']
        
        # Configurar estilo dos widgets
        style = ttk.Style()
        style.configure('Custom.TButton',
                       background=self.current_theme['secondary'],
                       foreground=self.current_theme['text'])

    def apply_theme(self):
        """Aplica o tema atual aos widgets"""
        theme = self.current_theme
        
        # Configurar cores do tema
        self.root.configure(bg=theme['background'])
        
        # Configurar área de log (agora já criada)
        if hasattr(self, 'log_area'):
            self.log_area.configure(
                bg=theme['background'],
                fg=theme['text'],
                insertbackground=theme['text']
            )
        
        # Atualizar estilo dos botões e widgets
        style = ttk.Style()
        style.configure('Custom.TButton',
                       background=theme['secondary'],
                       foreground=theme['text'])

    def create_main_layout(self):
        """Cria o layout principal da aplicação"""
        # Frame superior
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Configurações de conexão
        self.create_connection_settings(top_frame)
        
        # Área de log
        self.create_log_area()
        
        # Barra de status
        self.create_status_bar()
        
        # Notebook para abas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Aba principal
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text="Terminal")
        
        # Aba de diagnóstico ADB
        self.adb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.adb_frame, text="Diagnóstico ADB")
        self.create_adb_diagnostics()

    def create_connection_settings(self, parent):
        """Cria as configurações de conexão"""
        # Frame para controles
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill=tk.X)
        
        # Indicador de status
        self.create_status_indicator(controls_frame)
        
        # Porta COM
        ttk.Label(controls_frame, text="Porta:").pack(side=tk.LEFT, padx=5)
        self.port_combo = ttk.Combobox(controls_frame, width=10)
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        # Baud Rate com várias opções
        ttk.Label(controls_frame, text="Baud Rate:").pack(side=tk.LEFT, padx=5)
        self.baud_combo = ttk.Combobox(controls_frame, 
                                     values=['9600', '19200', '38400', '57600', '115200', '230400', '460800', '921600'],
                                     width=10)
        self.baud_combo.set('115200')
        self.baud_combo.pack(side=tk.LEFT, padx=5)
        
        # Botões de controle
        self.connect_btn = ttk.Button(controls_frame, 
                                    text="Conectar",
                                    command=self.toggle_connection,
                                    style='Custom.TButton')
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        # Modo de comunicação
        ttk.Radiobutton(controls_frame, 
                       text="UART",
                       variable=self.current_mode,
                       value="UART").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(controls_frame,
                       text="ADB",
                       variable=self.current_mode,
                       value="ADB").pack(side=tk.LEFT, padx=5)
        
        # Filtros de log
        ttk.Label(controls_frame, text="Filtro de Log:").pack(side=tk.LEFT, padx=5)
        self.filter_combo = ttk.Combobox(controls_frame, 
                                         values=['Bruto', 'Erro', 'Diagnóstico'],
                                         textvariable=self.log_filter,
                                         width=15)
        self.filter_combo.set('Bruto')
        self.filter_combo.pack(side=tk.LEFT, padx=5)
        
    def create_log_area(self):
        # Frame para logs
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Área de texto para logs
        self.log_area = scrolledtext.ScrolledText(log_frame,
                                                wrap=tk.WORD,
                                                font=('Consolas', 10))
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Botões de controle de log
        control_frame = ttk.Frame(log_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(control_frame,
                  text="Limpar Logs",
                  command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame,
                  text="Salvar Logs",
                  command=self.save_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame,
                  text="Executar Diagnóstico ADB",
                  command=self.run_adb_diagnostics).pack(side=tk.LEFT, padx=5)
        
    def create_status_bar(self):
        """Cria a barra de status na parte inferior da janela"""
        self.status_bar = ttk.Label(self.root,
                                  text="Desconectado",
                                  background=self.current_theme['accent'])
        self.status_bar.pack(fill=tk.X, pady=5)
        
    def update_ports_list(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
            
    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()
            
    def connect(self):
        """Conecta ao dispositivo"""
        try:
            self.connection_status.set('connecting')
            self.update_status_indicator()
            
            if self.auto_baud_detection.get():
                baud = self.detect_baud_rate()
                if baud:
                    self.baud_combo.set(str(baud))
                else:
                    raise Exception("Não foi possível detectar o baud rate")
            
            port = self.port_combo.get()
            baud = int(self.baud_combo.get())
            
            self.serial_port = serial.Serial(port, baud, timeout=1)
            self.is_connected = True
            
            # Iniciar thread de leitura
            read_thread = threading.Thread(target=self.read_serial)
            read_thread.daemon = True
            self.threads.append(read_thread)
            read_thread.start()
            
            self.connection_status.set('connected')
            self.update_status_indicator()
            self.connect_btn.configure(text="Desconectar")
            
        except Exception as e:
            self.connection_status.set('error')
            self.update_status_indicator()
            messagebox.showerror("Erro", f"Erro ao conectar: {str(e)}")

    def disconnect(self):
        """Desconecta do dispositivo"""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.is_connected = False
            self.connection_status.set('disconnected')
            self.update_status_indicator()
            self.connect_btn.configure(text="Conectar")
        except Exception as e:
            self.connection_status.set('error')
            self.update_status_indicator()
            messagebox.showerror("Erro", f"Erro ao desconectar: {str(e)}")

    def read_serial(self):
        """Thread de leitura serial"""
        while not self.stop_threads and self.is_connected:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode('utf-8')
                    self.root.after(0, self.log_area.insert, tk.END, data)
                    if self.auto_scroll:
                        self.root.after(0, self.log_area.see, tk.END)
            except:
                self.root.after(0, self.disconnect)
                break

    def filter_logs(self, data):
        timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S.%f]') if self.show_timestamps.get() else ''
        
        # Aplicar filtros existentes
        if self.log_filter.get() == "Bruto":
            self.add_to_log(f"{timestamp} {data}")
        elif self.log_filter.get() == "Erro" and "Erro" in data:
            self.add_to_log(f"{timestamp} {data}")
        elif self.log_filter.get() == "Diagnóstico" and "Diagnóstico" in data:
            self.add_to_log(f"{timestamp} {data}")

    def add_to_log(self, data):
        # Controle de buffer
        if self.get_log_lines_count() >= self.max_buffer_lines.get():
            # Remover primeiras linhas
            self.log_area.delete('1.0', '2.0')
        
        self.log_area.insert(tk.END, data)
        
        if self.auto_scroll:
            self.log_area.see(tk.END)

    def get_log_lines_count(self):
        return int(self.log_area.index('end-1c').split('.')[0])

    def clear_logs(self):
        self.log_area.delete(1.0, tk.END)
        
    def save_logs(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"restorecell_log_{timestamp}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            with open(filename, 'w') as f:
                f.write(self.log_area.get(1.0, tk.END))
            messagebox.showinfo("Sucesso", "Log salvo com sucesso!")
    
    def run_adb_diagnostics(self):
        if self.current_mode.get() == "ADB":
            try:
                output = subprocess.check_output("adb devices", shell=True).decode('utf-8')
                self.log_area.insert(tk.END, "=== Diagnóstico ADB ===\n")
                self.log_area.insert(tk.END, output)
                self.log_area.insert(tk.END, "=== Fim do Diagnóstico ADB ===\n\n")
            except Exception as e:
                messagebox.showerror("Erro ADB", f"Erro ao executar diagnóstico ADB: {str(e)}")

    def create_menu(self):
        """Cria a barra de menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Arquivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Arquivo", menu=file_menu)
        file_menu.add_command(label="Salvar Logs", command=self.save_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.quit)
        
        # Menu Configurações
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configurações", menu=settings_menu)
        settings_menu.add_checkbutton(label="Modo Escuro",
                                    variable=self.dark_mode,
                                    command=self.apply_theme)
        settings_menu.add_checkbutton(label="Mostrar Timestamps",
                                    variable=self.show_timestamps)
        settings_menu.add_checkbutton(label="Detecção Automática de Baud Rate",
                                    variable=self.auto_baud_detection)
        
        # Menu Perfis
        profile_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Perfis", menu=profile_menu)
        profile_menu.add_command(label="Salvar Perfil Atual",
                               command=self.save_profile)
        
        # Menu Sobre
        about_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Sobre", menu=about_menu)
        about_menu.add_command(label="Instagram @restorecell10",
                             command=lambda: webbrowser.open('https://instagram.com/restorecell10'))
        about_menu.add_command(label="Verificar Atualizações",
                             command=self.check_for_updates)

    def create_adb_diagnostics(self):
        buttons_frame = ttk.Frame(self.adb_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        adb_commands = {
            "Verificar Dispositivos": "adb devices",
            "Status da Bateria": "adb shell dumpsys battery",
            "Status do Sistema": "adb shell dumpsys activity",
            "Teste de Rede": "adb shell ping -c 4 google.com",
            "Reiniciar Device": "adb reboot"
        }
        
        for label, command in adb_commands.items():
            btn = ttk.Button(buttons_frame,
                           text=label,
                           command=lambda cmd=command: self.execute_adb_command(cmd))
            btn.pack(side=tk.LEFT, padx=5)

    def execute_adb_command(self, command):
        if self.current_mode.get() != "ADB":
            messagebox.showwarning("Aviso", "Ative o modo ADB primeiro!")
            return
            
        try:
            output = subprocess.check_output(command, shell=True).decode('utf-8')
            self.log_area.insert(tk.END, f"\n=== {command} ===\n{output}\n")
            self.log_area.see(tk.END)
        except Exception as e:
            messagebox.showerror("Erro ADB", f"Erro ao executar comando: {str(e)}")

    def monitor_ports(self):
        """Thread de monitoramento de portas"""
        while not self.stop_threads:
            try:
                current_ports = set([port.device for port in serial.tools.list_ports.comports()])
                if set(self.port_combo['values']) != current_ports:
                    self.root.after(0, self.update_ports_list)
                time.sleep(1)
            except:
                continue

    def detect_baud_rate(self):
        """Detecta automaticamente o baud rate"""
        common_rates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        
        for rate in common_rates:
            try:
                with serial.Serial(self.port_combo.get(), rate, timeout=0.5) as ser:
                    # Tenta ler dados
                    ser.read(100)
                    return rate
            except:
                continue
        return None

    def update_font_size(self):
        """Atualiza o tamanho da fonte na área de log"""
        current_font = font.Font(font=self.log_area['font'])
        self.log_area.configure(font=(current_font.actual()['family'], 
                                    self.font_size.get()))

    def save_profile(self):
        profile_name = self.current_profile.get()
        profile = {
            'baud_rate': self.baud_combo.get(),
            'auto_baud': self.auto_baud_detection.get(),
            'font_size': self.font_size.get(),
            'dark_mode': self.dark_mode.get(),
            'show_timestamps': self.show_timestamps.get(),
            'max_buffer': self.max_buffer_lines.get()
        }
        
        self.profiles[profile_name] = profile
        self.save_config()

    def load_profile(self, profile_name):
        if profile_name in self.profiles:
            profile = self.profiles[profile_name]
            self.baud_combo.set(profile['baud_rate'])
            self.auto_baud_detection.set(profile['auto_baud'])
            self.font_size.set(profile['font_size'])
            self.dark_mode.set(profile['dark_mode'])
            self.show_timestamps.set(profile['show_timestamps'])
            self.max_buffer_lines.set(profile['max_buffer'])
            self.apply_theme()
            self.update_font_size()

    def check_for_updates(self):
        try:
            # Simular verificação de versão (substitua pela sua lógica real)
            latest_version = "1.0.1"
            if latest_version > self.VERSION:
                if messagebox.askyesno("Atualização Disponível",
                                     f"Nova versão {latest_version} disponível. Deseja baixar?"):
                    webbrowser.open("https://github.com/seu-repo/restorecell-terminal/releases")
        except:
            pass  # Silenciosamente ignora erros de verificação

    def load_config(self):
        """Carrega as configurações salvas do arquivo JSON"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    
                    # Carregar profiles
                    self.profiles = config.get('profiles', {})
                    
                    # Carregar configurações gerais
                    if 'current_profile' in config:
                        self.load_profile(config['current_profile'])
            else:
                # Criar configuração padrão
                self.save_config()
        except Exception as e:
            messagebox.showwarning("Aviso", f"Erro ao carregar configurações: {str(e)}")
            self.save_config()  # Criar novo arquivo de configuração

    def save_config(self):
        """Salva as configurações atuais em arquivo JSON"""
        try:
            config = {
                'profiles': self.profiles,
                'current_profile': self.current_profile.get(),
                'general': {
                    'dark_mode': self.dark_mode.get(),
                    'font_size': self.font_size.get(),
                    'show_timestamps': self.show_timestamps.get(),
                    'max_buffer': self.max_buffer_lines.get()
                }
            }
            
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            messagebox.showwarning("Aviso", f"Erro ao salvar configurações: {str(e)}")

    def cleanup_and_exit(self):
        """Limpa recursos e fecha a aplicação"""
        try:
            # Parar todas as threads
            self.stop_threads = True
            
            # Aguardar threads terminarem
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            
            # Desconectar se necessário
            if self.is_connected:
                self.disconnect()
            
            # Salvar configurações
            self.save_config()
            
            # Destruir a janela
            self.root.destroy()
            
        except Exception as e:
            print(f"Erro ao fechar aplicação: {str(e)}")
            self.root.destroy()

    def create_status_indicator(self, parent):
        """Cria o indicador visual de status"""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(side=tk.LEFT, padx=5)
        
        # Canvas para o indicador LED
        self.status_led = tk.Canvas(self.status_frame, width=15, height=15)
        self.status_led.pack(side=tk.LEFT)
        
        # Label para texto do status
        self.status_label = ttk.Label(self.status_frame, textvariable=self.connection_status)
        self.status_label.pack(side=tk.LEFT, padx=2)
        
        # Desenhar LED inicial
        self.update_status_indicator()

    def update_status_indicator(self):
        """Atualiza o indicador visual de status"""
        status_colors = {
            'connected': '#2ecc71',    # Verde
            'disconnected': '#e74c3c', # Vermelho
            'connecting': '#f1c40f',   # Amarelo
            'error': '#95a5a6'         # Cinza
        }
        
        status = self.connection_status.get()
        color = status_colors.get(status, status_colors['error'])
        
        # Limpar canvas
        self.status_led.delete('all')
        
        # Desenhar círculo com borda
        self.status_led.create_oval(2, 2, 13, 13, 
                                   fill=color,
                                   outline='#2c3e50',
                                   width=1)

if __name__ == "__main__":
    root = tk.Tk()
    app = RestoreCellTerminal(root)
    
    # Registrar função de limpeza ao fechar
    root.protocol("WM_DELETE_WINDOW", app.cleanup_and_exit)
    
    root.mainloop()
