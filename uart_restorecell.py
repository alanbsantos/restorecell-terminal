import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial.tools.list_ports
from serial import Serial
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
import zipfile
import shutil
import tempfile
import sys
from pathlib import Path
import logging

class RestoreCellTerminal:
    def __init__(self, root):
        self.root = root
        
        # Verificar se o módulo serial está funcionando
        try:
            serial.tools.list_ports.comports()
        except Exception as e:
            messagebox.showerror(
                "Erro",
                "Erro ao inicializar módulo serial.\n"
                "Por favor, verifique se o PySerial está instalado corretamente.\n"
                f"Erro: {str(e)}"
            )
            root.destroy()
            return
            
        self.root.title("RESTORECELL Terminal - Software Gratuito")
        self.root.geometry("1000x700")
        
        # Configurações iniciais
        self.VERSION = "1.0.0"
        self.CONFIG_FILE = "restorecell_config.json"
        self.UPDATE_FOLDER = "update_temp"
        self.BACKUP_FOLDER = "backup_temp"
        self.PROTECTED_FILES = [
            "restorecell_config.json",
            "custom_profiles.json",
            "user_themes.json"
        ]
        
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
        
        # Dicionário de filtros UART
        self.uart_filters = {
            'vproc': tk.BooleanVar(value=False),
            'cpu': tk.BooleanVar(value=False),
            'pmic': tk.BooleanVar(value=False),
            'i2c': tk.BooleanVar(value=False),
            'clock': tk.BooleanVar(value=False),
            'rpmb': tk.BooleanVar(value=False),
            'ufs': tk.BooleanVar(value=False),
            'emmc': tk.BooleanVar(value=False),
            'ram': tk.BooleanVar(value=False),
            'outros': tk.BooleanVar(value=False)
        }
        
        # Criar interface de filtros
        self.create_filter_interface()
        
        # Adicionar variáveis para controle dos LEDs
        self.rx_active = False
        self.tx_active = False
        self.led_blink_duration = 100  # milissegundos

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
        """Cria as configurações de conexão com indicadores RX/TX"""
        # Frame para controles
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill=tk.X)
        
        # Frame para indicadores RX/TX
        indicators_frame = ttk.Frame(controls_frame)
        indicators_frame.pack(side=tk.LEFT, padx=5)
        
        # Criar indicadores RX/TX
        self.create_rx_tx_indicators(indicators_frame)
        
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
        
        # Frame para filtros
        filter_frame = ttk.Frame(controls_frame)
        filter_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(filter_frame, text="Filtro de Log:").pack(side=tk.LEFT, padx=5)
        
        # Lista atualizada de filtros
        self.filter_options = [
            'Bruto',
            'vproc',
            'cpu',
            'pmic',
            'i2c',
            'clock',
            'rpmb',
            'ufs',
            'emmc',
            'ram',
            'Outros'
        ]
        
        self.filter_combo = ttk.Combobox(
            filter_frame, 
            values=self.filter_options,
            textvariable=self.log_filter,
            width=15
        )
        self.filter_combo.set('Bruto')
        self.filter_combo.pack(side=tk.LEFT, padx=5)
        
        # Botão de busca
        self.search_btn = ttk.Button(
            filter_frame,
            text="Buscar",
            command=self.search_logs,
            style='Custom.TButton'
        )
        self.search_btn.pack(side=tk.LEFT, padx=5)

    def create_rx_tx_indicators(self, parent):
        """Cria os indicadores visuais de RX/TX"""
        # Frame para os LEDs
        led_frame = ttk.LabelFrame(parent, text="Serial Activity")
        led_frame.pack(side=tk.LEFT, padx=5)
        
        # Canvas para LED RX
        rx_frame = ttk.Frame(led_frame)
        rx_frame.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.rx_led = tk.Canvas(rx_frame, width=15, height=15)
        self.rx_led.pack(side=tk.LEFT)
        ttk.Label(rx_frame, text="RX").pack(side=tk.LEFT, padx=2)
        
        # Canvas para LED TX
        tx_frame = ttk.Frame(led_frame)
        tx_frame.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.tx_led = tk.Canvas(tx_frame, width=15, height=15)
        self.tx_led.pack(side=tk.LEFT)
        ttk.Label(tx_frame, text="TX").pack(side=tk.LEFT, padx=2)
        
        # Desenhar LEDs iniciais (apagados)
        self.draw_led(self.rx_led, 'off')
        self.draw_led(self.tx_led, 'off')

    def draw_led(self, canvas, state):
        """
        Desenha um LED no canvas especificado
        
        Args:
            canvas: Canvas do Tkinter
            state: 'on' ou 'off'
        """
        # Limpar canvas
        canvas.delete('all')
        
        # Cores do LED
        colors = {
            'rx': {'on': '#00ff00', 'off': '#004400'},  # Verde para RX
            'tx': {'on': '#ff0000', 'off': '#440000'}   # Vermelho para TX
        }
        
        # Identificar tipo de LED
        led_type = 'rx' if canvas == self.rx_led else 'tx'
        color = colors[led_type]['on' if state == 'on' else 'off']
        
        # Desenhar LED com borda
        canvas.create_oval(2, 2, 13, 13, 
                         fill=color,
                         outline='#333333',
                         width=1)
        
        # Adicionar brilho
        if state == 'on':
            canvas.create_oval(4, 4, 8, 8,
                             fill='#ffffff',
                             outline='')

    def blink_rx(self):
        """Pisca o LED RX"""
        if not self.rx_active:
            self.rx_active = True
            self.draw_led(self.rx_led, 'on')
            self.root.after(self.led_blink_duration, self.reset_rx)

    def blink_tx(self):
        """Pisca o LED TX"""
        if not self.tx_active:
            self.tx_active = True
            self.draw_led(self.tx_led, 'on')
            self.root.after(self.led_blink_duration, self.reset_tx)

    def reset_rx(self):
        """Reseta o LED RX"""
        self.rx_active = False
        self.draw_led(self.rx_led, 'off')

    def reset_tx(self):
        """Reseta o LED TX"""
        self.tx_active = False
        self.draw_led(self.tx_led, 'off')

    def read_serial(self):
        """Thread de leitura serial com indicador RX"""
        buffer = bytearray()
        while not self.stop_threads and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting:
                    # Piscar LED RX
                    self.root.after(0, self.blink_rx)
                    
                    # Ler dados
                    chunk = self.serial_port.read(self.serial_port.in_waiting)
                    buffer.extend(chunk)
                    
                    # Processar buffer
                    while b'\n' in buffer:
                        line_end = buffer.find(b'\n')
                        line = buffer[:line_end + 1]
                        buffer = buffer[line_end + 1:]
                        
                        if line:
                            processed_data = self.sanitize_log_data(line)
                            if processed_data:
                                if self.show_timestamps.get():
                                    timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S.%f]')
                                    processed_data = f"{timestamp} {processed_data}"
                                
                                self.root.after(0, self.append_to_log, processed_data)
                
            except Exception as e:
                logging.error(f"Erro na leitura serial: {str(e)}")
                self.root.after(0, self.handle_serial_error)
                break

    def write_serial(self, data):
        """
        Escreve dados na porta serial com indicador TX
        
        Args:
            data (str): Dados a serem enviados
        """
        try:
            if self.serial_port and self.serial_port.is_open:
                # Piscar LED TX
                self.root.after(0, self.blink_tx)
                
                # Enviar dados
                self.serial_port.write(data.encode())
                
        except Exception as e:
            logging.error(f"Erro ao enviar dados: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao enviar dados: {str(e)}")

    def sanitize_log_data(self, raw_data):
        """
        Sanitiza e formata os dados do log com tratamento robusto de caracteres
        
        Args:
            raw_data (bytes): Dados brutos do serial
            
        Returns:
            str: Dados sanitizados e formatados
        """
        try:
            # Tentar diferentes encodings
            for encoding in ['utf-8', 'ascii', 'latin1', 'cp1252']:
                try:
                    decoded = raw_data.decode(encoding, errors='ignore')
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Se nenhum encoding funcionar, usar ascii com replace
                decoded = raw_data.decode('ascii', errors='replace')
            
            # Remover caracteres de controle indesejados
            cleaned = ''
            for char in decoded:
                # Manter apenas caracteres printáveis e alguns especiais
                if char.isprintable() or char in '\n\r\t':
                    if ord(char) < 128 or char in 'áéíóúàèìòùâêîôûãõñäëïöüçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÑÄËÏÖÜÇ':
                        cleaned += char
                    else:
                        cleaned += ' '
            
            # Remover múltiplos espaços
            cleaned = ' '.join(cleaned.split())
            
            # Remover linhas vazias
            if not cleaned.strip():
                return None
                
            return cleaned.strip()
            
        except Exception as e:
            logging.error(f"Erro ao sanitizar dados: {str(e)}")
            return None

    def append_to_log(self, data):
        """Adiciona dados ao log com verificações robustas"""
        if not data or not isinstance(data, str):
            return
            
        try:
            # Verificar tamanho máximo
            MAX_LINE_LENGTH = 1000
            if len(data) > MAX_LINE_LENGTH:
                data = data[:MAX_LINE_LENGTH] + "... (truncado)"
            
            # Garantir que a string seja válida para Tcl/Tk
            safe_data = ''
            for char in data:
                if ord(char) < 128 or char in 'áéíóúàèìòùâêîôûãõñäëïöüçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÑÄËÏÖÜÇ':
                    safe_data += char
                else:
                    safe_data += '?'
            
            # Inserir no log
            self.log_area.insert(tk.END, safe_data + '\n')
            
            # Manter cópia para busca
            if not hasattr(self, 'original_log'):
                self.original_log = ''
            self.original_log += safe_data + '\n'
            
            # Gerenciar buffer
            self.manage_buffer_size()
            
            # Auto-scroll
            if self.auto_scroll:
                self.log_area.see(tk.END)
            
            # Atualizar interface
            self.root.update_idletasks()
            
        except tk.TclError as e:
            logging.error(f"Erro Tcl ao inserir log: {str(e)}")
        except Exception as e:
            logging.error(f"Erro ao adicionar log: {str(e)}")

    def manage_buffer_size(self):
        """Gerencia o tamanho do buffer de log"""
        try:
            if self.max_buffer_lines.get() > 0:
                # Contar linhas atuais
                total_lines = int(self.log_area.index('end-1c').split('.')[0])
                
                # Se exceder o limite, remover linhas antigas
                if total_lines > self.max_buffer_lines.get():
                    # Calcular quantas linhas remover
                    lines_to_remove = total_lines - self.max_buffer_lines.get()
                    
                    # Remover do início
                    self.log_area.delete('1.0', f'{lines_to_remove + 1}.0')
                    
                    # Atualizar log original também
                    self.original_log = '\n'.join(
                        self.original_log.splitlines()[lines_to_remove:]
                    )
                    
        except Exception as e:
            logging.error(f"Erro ao gerenciar buffer: {str(e)}")

    def handle_serial_error(self):
        """Trata erros de comunicação serial com retry"""
        try:
            self.disconnect()
            
            # Aguardar um pouco antes de tentar reconectar
            time.sleep(1)
            
            # Tentar reconectar algumas vezes
            for _ in range(3):
                try:
                    self.connect()
                    return
                except Exception:
                    time.sleep(1)
            
            # Se todas as tentativas falharem
            messagebox.showerror(
                "Erro de Comunicação",
                "Não foi possível restabelecer a conexão.\n"
                "Por favor, verifique o dispositivo e tente reconectar manualmente."
            )
            
        except Exception as e:
            logging.error(f"Erro ao tentar reconectar: {str(e)}")
            messagebox.showerror(
                "Erro",
                f"Erro ao tentar reconectar: {str(e)}\n"
                "Tente reiniciar o programa."
            )

    def should_display_log(self, data):
        """Verifica se o log deve ser exibido baseado nos filtros ativos"""
        data_lower = data.lower()
        current_filter = self.log_filter.get()
        
        # Modo bruto mostra tudo
        if current_filter == 'Bruto':
            return True
            
        # Verificar filtros específicos
        filter_patterns = {
            'vproc': ['vproc', 'voltage'],
            'cpu': ['cpu', 'processor'],
            'pmic': ['pmic', 'power'],
            'i2c': ['i2c', 'bus'],
            'clock': ['clock', 'freq'],
            'rpmb': ['rpmb', 'secure'],
            'ufs': ['ufs', 'storage'],
            'emmc': ['emmc', 'mmc'],
            'ram': ['ram', 'memory'],
            'outros': []  # Filtro especial tratado separadamente
        }
        
        # Se o filtro atual existe nos padrões
        if current_filter.lower() in filter_patterns:
            patterns = filter_patterns[current_filter.lower()]
            return any(pattern in data_lower for pattern in patterns)
        
        # Filtro "outros" captura logs que não se encaixam nos outros filtros
        if current_filter == 'Outros':
            return not any(
                pattern in data_lower 
                for patterns in filter_patterns.values() 
                for pattern in patterns
            )
        
        return False

    def filter_logs(self, data):
        """Filtra os logs de acordo com as configurações"""
        timestamp = datetime.now().strftime('[%Y-%m-%d %H:%M:%S.%f]') if self.show_timestamps.get() else ''
        
        # Armazenar log original
        if not hasattr(self, 'original_log'):
            self.original_log = ''
        self.original_log += f"{timestamp} {data}\n"
        
        # Aplicar filtros ativos
        self.apply_filters()

    def apply_filters(self):
        """Aplica os filtros selecionados ao log"""
        if not hasattr(self, 'original_log'):
            self.original_log = self.log_area.get(1.0, tk.END)

        # Limpar área de log
        self.log_area.delete(1.0, tk.END)

        # Obter filtros ativos
        active_filters = [
            name for name, var in self.uart_filters.items() 
            if var.get()
        ]

        # Obter texto de busca
        search_text = self.search_var.get().lower()

        # Processar cada linha do log original
        for line in self.original_log.splitlines():
            should_display = False
            
            # Se nenhum filtro está ativo, mostrar tudo
            if not active_filters and not search_text:
                should_display = True
            else:
                # Verificar filtros ativos
                for filter_name in active_filters:
                    if filter_name in line.lower():
                        should_display = True
                        break
                
                # Verificar texto de busca
                if search_text and search_text in line.lower():
                    should_display = True

            if should_display:
                self.log_area.insert(tk.END, line + '\n')

    def add_custom_filter(self):
        """Adiciona um filtro personalizado"""
        custom_filter = self.custom_filter_entry.get().strip()
        if custom_filter:
            # Adicionar novo filtro ao dicionário
            self.uart_filters[custom_filter] = tk.BooleanVar(value=True)
            # Recriar interface de filtros
            self.create_filter_interface()
            # Aplicar filtros
            self.apply_filters()

    def select_all_filters(self):
        """Seleciona todos os filtros"""
        for var in self.uart_filters.values():
            var.set(True)
        self.apply_filters()

    def clear_filters(self):
        """Limpa todos os filtros"""
        for var in self.uart_filters.values():
            var.set(False)
        self.search_var.set('')
        self.apply_filters()

    def highlight_filtered_text(self, text, filter_name):
        """Destaca o texto filtrado com cores diferentes"""
        start_idx = "1.0"
        while True:
            start_idx = self.log_area.search(
                filter_name, 
                start_idx, 
                tk.END, 
                nocase=True
            )
            if not start_idx:
                break
                
            end_idx = f"{start_idx}+{len(filter_name)}c"
            self.log_area.tag_add(filter_name, start_idx, end_idx)
            self.log_area.tag_config(
                filter_name, 
                foreground=self.get_filter_color(filter_name)
            )
            start_idx = end_idx

    def get_filter_color(self, filter_name):
        """Retorna uma cor específica para cada tipo de filtro"""
        colors = {
            'vproc': '#FF0000',  # Vermelho
            'cpu': '#00FF00',    # Verde
            'pmic': '#0000FF',   # Azul
            'i2c': '#FF00FF',    # Magenta
            'clock': '#00FFFF',  # Ciano
            'rpmb': '#FFFF00',   # Amarelo
            'ufs': '#FF8000',    # Laranja
            'emmc': '#8000FF',   # Roxo
            'ram': '#008000',    # Verde escuro
            'outros': '#808080'  # Cinza
        }
        return colors.get(filter_name, '#000000')  # Preto para filtros não mapeados

    def create_filter_interface(self):
        """Cria a interface para os filtros UART"""
        filter_frame = ttk.LabelFrame(self.root, text="Filtros UART")
        filter_frame.pack(fill=tk.X, padx=10, pady=5)

        # Frame para os checkboxes com scrollbar
        canvas = tk.Canvas(filter_frame)
        scrollbar = ttk.Scrollbar(filter_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Criar checkboxes para cada filtro
        for i, (filter_name, var) in enumerate(self.uart_filters.items()):
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            cb = ttk.Checkbutton(
                frame, 
                text=filter_name.upper(),
                variable=var,
                command=self.apply_filters
            )
            cb.pack(side=tk.LEFT)
            
            # Adicionar campo de entrada para filtros personalizados
            if filter_name == 'outros':
                self.custom_filter_entry = ttk.Entry(frame, width=20)
                self.custom_filter_entry.pack(side=tk.LEFT, padx=5)
                ttk.Button(
                    frame,
                    text="Adicionar",
                    command=self.add_custom_filter
                ).pack(side=tk.LEFT)

        # Botões de controle de filtro
        control_frame = ttk.Frame(filter_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Selecionar Todos",
            command=self.select_all_filters
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Limpar Filtros",
            command=self.clear_filters
        ).pack(side=tk.LEFT, padx=5)

        # Adicionar campo de busca
        ttk.Label(control_frame, text="Buscar:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.apply_filters())
        ttk.Entry(
            control_frame,
            textvariable=self.search_var,
            width=20
        ).pack(side=tk.LEFT, padx=5)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

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
        
        # Menu Ajuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        help_menu.add_command(label="Reportar Problema", command=self.open_github_issues)
        help_menu.add_command(label="Verificar Atualizações", command=self.check_for_updates)

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
        """Thread para monitorar mudanças nas portas seriais"""
        last_ports = set()
        
        while not self.stop_threads:
            try:
                # Obter portas atuais
                current_ports = set(port.device for port in serial.tools.list_ports.comports())
                
                # Verificar mudanças
                if current_ports != last_ports:
                    self.root.after(0, self.update_ports_list)
                    last_ports = current_ports
                
                # Aguardar antes da próxima verificação
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Erro no monitoramento de portas: {str(e)}")
                time.sleep(5)  # Aguardar mais tempo em caso de erro

    def verificar_disponibilidade_porta(self, port):
        """
        Verifica se uma porta está disponível para uso
        
        Args:
            port (str): Nome da porta a verificar
            
        Returns:
            bool: True se disponível, False caso contrário
        """
        try:
            # Verificar se a porta existe
            if port not in [p.device for p in serial.tools.list_ports.comports()]:
                return False
                
            # Tentar abrir a porta
            with serial.Serial(port, timeout=0.1) as test_port:
                return True
                
        except serial.SerialException:
            return False
        except Exception as e:
            logging.error(f"Erro ao verificar porta {port}: {str(e)}")
            return False

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
        """
        Verifica atualizações disponíveis no GitHub.
        Inclui tratamento de erros melhorado e verificação do repositório.
        """
        try:
            # Headers para API do GitHub
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'RestoreCell-Terminal'
            }

            # Primeiro, verifica se o repositório existe
            repo_url = "https://api.github.com/repos/alanbsantos/restorecell-terminal"
            repo_response = requests.get(repo_url, headers=headers)

            if repo_response.status_code == 404:
                self.log_area.insert(tk.END, "\nRepositório não encontrado. Verificando repositório alternativo...\n")
                # Tenta repositório alternativo
                repo_url = "https://api.github.com/repos/alanbsantos/restorecell"
                repo_response = requests.get(repo_url, headers=headers)

            if repo_response.status_code == 200:
                # Agora busca as releases
                releases_url = f"{repo_url}/releases/latest"
                releases_response = requests.get(releases_url, headers=headers)

                if releases_response.status_code == 200:
                    release_data = releases_response.json()
                    latest_version = release_data.get('tag_name', '').replace('v', '')

                    if not latest_version:
                        self.log_area.insert(tk.END, "\nNenhuma versão encontrada no repositório.\n")
                        return

                    if self.compare_versions(latest_version, self.VERSION):
                        update_msg = (
                            f"Nova versão {latest_version} disponível!\n\n"
                            f"Alterações:\n{release_data.get('body', 'Sem descrição disponível')}\n\n"
                            "Deseja baixar e instalar a atualização agora?"
                        )
                        
                        if messagebox.askyesno("Atualização Disponível", update_msg):
                            self.download_and_update(release_data)
                    else:
                        self.log_area.insert(tk.END, "\nSeu software está atualizado!\n")
                        messagebox.showinfo("Atualização", "O software está atualizado!")
                else:
                    if releases_response.status_code == 404:
                        self.log_area.insert(tk.END, "\nNenhuma release encontrada no repositório.\n")
                        messagebox.showinfo("Atualização", "Nenhuma atualização disponível no momento.")
                    else:
                        raise Exception(f"Erro ao buscar releases: {releases_response.status_code}")
            else:
                raise Exception(f"Erro ao verificar repositório: {repo_response.status_code}")

        except requests.exceptions.ConnectionError:
            error_msg = (
                "Não foi possível conectar ao servidor GitHub.\n"
                "Verifique sua conexão com a internet.\n\n"
                "Caso continue encontrando problemas, por favor nos informe no GitHub:\n"
                "https://github.com/alanbsantos/restorecell-terminal/issues"
            )
            self.log_area.insert(tk.END, f"\nErro de conexão: {error_msg}\n")
            messagebox.showerror("Erro de Conexão", error_msg)

        except Exception as e:
            error_msg = (
                f"Erro ao verificar atualizações: {str(e)}\n\n"
                "Caso tenha encontrado um bug, por favor, nos informe em nosso GitHub:\n"
                "https://github.com/alanbsantos/restorecell-terminal/issues"
            )
            self.log_area.insert(tk.END, f"\n{error_msg}\n")
            messagebox.showerror("Erro", error_msg)

        finally:
            # Adiciona um separador visual no log para melhor organização
            self.log_area.insert(tk.END, "\n" + "-"*50 + "\n")
            
            # Garante que o log seja visível
            self.log_area.see(tk.END)

    def compare_versions(self, latest, current):
        """
        Compara versões no formato x.y.z
        Retorna True se latest > current
        """
        try:
            if not latest or not current:
                return False
                
            latest_parts = [int(x) for x in latest.split('.')]
            current_parts = [int(x) for x in current.split('.')]
            
            # Garante que ambas as listas tenham o mesmo tamanho
            while len(latest_parts) < 3:
                latest_parts.append(0)
            while len(current_parts) < 3:
                current_parts.append(0)
            
            for l, c in zip(latest_parts, current_parts):
                if l > c:
                    return True
                elif l < c:
                    return False
            return False
            
        except (ValueError, AttributeError) as e:
            self.log_area.insert(tk.END, f"\nErro ao comparar versões: {str(e)}\n")
            return False

    def download_and_update(self, release_data):
        """
        Baixa e instala a atualização.
        
        Args:
            release_data (dict): Dados da release do GitHub
        """
        try:
            # Criar diretório temporário para download
            temp_dir = Path(tempfile.gettempdir()) / self.UPDATE_FOLDER
            temp_dir.mkdir(exist_ok=True)
            
            # Encontrar o arquivo .zip na release
            zip_asset = next(
                (asset for asset in release_data['assets'] 
                 if asset['name'].endswith('.zip')),
                None
            )
            
            if not zip_asset:
                raise Exception("Arquivo de atualização não encontrado")
            
            # Baixar arquivo
            self.download_update(zip_asset['browser_download_url'], temp_dir)
            
            # Preparar para atualização
            if messagebox.askyesno(
                "Atualização Pronta",
                "A atualização foi baixada. Deseja instalar agora?\n"
                "O programa será reiniciado após a instalação."
            ):
                self.install_update(temp_dir)
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao baixar atualização: {str(e)}")
            self.cleanup_update_files()

    def download_update(self, download_url, temp_dir):
        """
        Baixa o arquivo de atualização com barra de progresso.
        
        Args:
            download_url (str): URL para download
            temp_dir (Path): Diretório temporário
        """
        try:
            response = requests.get(download_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            # Criar janela de progresso
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Baixando Atualização")
            progress_window.geometry("300x150")
            
            progress_label = ttk.Label(progress_window, text="Baixando...")
            progress_label.pack(pady=10)
            
            progress_bar = ttk.Progressbar(
                progress_window, 
                length=200, 
                mode='determinate'
            )
            progress_bar.pack(pady=10)
            
            # Download com atualização da barra de progresso
            block_size = 1024
            downloaded = 0
            
            update_file = temp_dir / "update.zip"
            with open(update_file, 'wb') as f:
                for data in response.iter_content(block_size):
                    f.write(data)
                    downloaded += len(data)
                    progress = (downloaded / total_size) * 100
                    progress_bar['value'] = progress
                    progress_window.update()
            
            progress_window.destroy()
            
        except Exception as e:
            raise Exception(f"Erro ao baixar arquivo: {str(e)}")

    def install_update(self, temp_dir):
        """
        Instala a atualização baixada.
        
        Args:
            temp_dir (Path): Diretório com arquivos de atualização
        """
        try:
            # Criar backup
            self.create_backup()
            
            # Extrair arquivos
            update_zip = temp_dir / "update.zip"
            with zipfile.ZipFile(update_zip, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Copiar arquivos novos
            self.copy_update_files(temp_dir)
            
            # Limpar arquivos temporários
            self.cleanup_update_files()
            
            # Reiniciar aplicação
            if messagebox.askyesno(
                "Atualização Concluída",
                "Atualização instalada com sucesso!\n"
                "É necessário reiniciar o programa agora.\n\n"
                "Deseja reiniciar?"
            ):
                self.restart_application()
                
        except Exception as e:
            self.restore_backup()
            raise Exception(f"Erro ao instalar atualização: {str(e)}")

    def create_backup(self):
        """Cria backup dos arquivos atuais"""
        try:
            backup_dir = Path(self.BACKUP_FOLDER)
            backup_dir.mkdir(exist_ok=True)
            
            # Copiar arquivos atuais para backup
            current_dir = Path('.')
            for item in current_dir.glob('*'):
                if item.name not in [self.UPDATE_FOLDER, self.BACKUP_FOLDER]:
                    if item.is_file():
                        shutil.copy2(item, backup_dir)
                    elif item.is_dir():
                        shutil.copytree(
                            item, 
                            backup_dir / item.name,
                            dirs_exist_ok=True
                        )
                        
        except Exception as e:
            raise Exception(f"Erro ao criar backup: {str(e)}")

    def copy_update_files(self, temp_dir):
        """
        Copia arquivos da atualização para diretório principal.
        
        Args:
            temp_dir (Path): Diretório com arquivos novos
        """
        try:
            # Copiar arquivos novos, preservando arquivos protegidos
            for item in temp_dir.glob('*'):
                if item.name not in self.PROTECTED_FILES and item.name != "update.zip":
                    if item.is_file():
                        shutil.copy2(item, '.')
                    elif item.is_dir():
                        shutil.copytree(
                            item, 
                            Path('.') / item.name,
                            dirs_exist_ok=True
                        )
                        
        except Exception as e:
            raise Exception(f"Erro ao copiar arquivos: {str(e)}")

    def restore_backup(self):
        """Restaura backup em caso de falha na atualização"""
        try:
            backup_dir = Path(self.BACKUP_FOLDER)
            if backup_dir.exists():
                # Restaurar arquivos do backup
                for item in backup_dir.glob('*'):
                    if item.is_file():
                        shutil.copy2(item, '.')
                    elif item.is_dir():
                        shutil.copytree(
                            item, 
                            Path('.') / item.name,
                            dirs_exist_ok=True
                        )
                        
            messagebox.showinfo(
                "Restauração",
                "Backup restaurado com sucesso após falha na atualização."
            )
            
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Erro ao restaurar backup: {str(e)}\n"
                "Por favor, reinstale o programa manualmente."
            )

    def cleanup_update_files(self):
        """Remove arquivos temporários de atualização"""
        try:
            # Limpar diretório de atualização
            update_dir = Path(tempfile.gettempdir()) / self.UPDATE_FOLDER
            if update_dir.exists():
                shutil.rmtree(update_dir)
            
            # Limpar backup após atualização bem-sucedida
            backup_dir = Path(self.BACKUP_FOLDER)
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
                
        except Exception as e:
            print(f"Aviso: Erro ao limpar arquivos temporários: {str(e)}")

    def restart_application(self):
        """Reinicia a aplicação após atualização"""
        python = sys.executable
        script = Path(__file__).absolute()
        self.root.destroy()
        subprocess.Popen([python, script])
        sys.exit(0)

    def load_config(self):
        """
        Carrega configurações do arquivo JSON.
        Não cria arquivo padrão se não existir.
        """
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                    # Carregar configurações gerais
                    general = config.get('general', {})
                    self.dark_mode.set(general.get('dark_mode', False))
                    self.font_size.set(general.get('font_size', 10))
                    self.show_timestamps.set(general.get('show_timestamps', True))
                    self.max_buffer_lines.set(general.get('max_buffer', 1000))
                    
                    # Carregar temas personalizados
                    if 'custom_themes' in config:
                        self.themes.update(config['custom_themes'])
                    
                    # Carregar profiles
                    self.profiles = config.get('profiles', {})
                    
                    # Aplicar tema atual
                    self.apply_theme()
            else:
                messagebox.showinfo(
                    "Configurações",
                    "Arquivo de configurações não encontrado.\n" +
                    "As configurações serão salvas quando você personalizar as opções."
                )
        except Exception as e:
            messagebox.showwarning("Aviso", f"Erro ao carregar configurações: {str(e)}")

    def save_config(self):
        """
        Salva todas as configurações atuais em JSON
        """
        try:
            config = {
                'general': {
                    'dark_mode': self.dark_mode.get(),
                    'font_size': self.font_size.get(),
                    'show_timestamps': self.show_timestamps.get(),
                    'max_buffer': self.max_buffer_lines.get(),
                    'current_theme': 'dark' if self.dark_mode.get() else 'light',
                    'log_filter': self.log_filter.get()
                },
                'custom_themes': self.themes,
                'profiles': self.profiles,
                'window': {
                    'geometry': self.root.geometry()
                }
            }
            
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            messagebox.showwarning("Aviso", f"Erro ao salvar configuraçes: {str(e)}")

    def cleanup_and_exit(self):
        """Limpa recursos e fecha a aplicação com segurança"""
        try:
            # Parar todas as threads
            self.stop_threads = True
            
            # Aguardar threads terminarem
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            
            # Desconectar com retry
            if self.is_connected:
                for _ in range(3):
                    try:
                        self.disconnect()
                        break
                    except:
                        time.sleep(0.5)
            
            # Salvar configurações
            self.save_config()
            
            # Destruir a janela
            self.root.destroy()
            
        except Exception as e:
            print(f"Erro ao fechar aplicação: {str(e)}")
            self.root.destroy()

    def create_status_bar(self):
        """Cria a barra de status com indicadores"""
        # Frame para barra de status
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        # Separador acima da barra de status
        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X, side=tk.BOTTOM)
        
        # Indicador de conexão
        self.create_status_indicator(self.status_bar)
        
        # Informações adicionais
        info_frame = ttk.Frame(self.status_bar)
        info_frame.pack(side=tk.RIGHT, padx=5)
        
        # Versão do software
        version_label = ttk.Label(
            info_frame, 
            text=f"v{self.VERSION}",
            font=('Helvetica', 8)
        )
        version_label.pack(side=tk.RIGHT, padx=5)
        
        # Buffer size
        self.buffer_label = ttk.Label(
            info_frame,
            text="Buffer: 0/1000",
            font=('Helvetica', 8)
        )
        self.buffer_label.pack(side=tk.RIGHT, padx=5)
        
        # Baud rate atual
        self.baud_label = ttk.Label(
            info_frame,
            text="Baud: --",
            font=('Helvetica', 8)
        )
        self.baud_label.pack(side=tk.RIGHT, padx=5)
        
        # Porta atual
        self.port_label = ttk.Label(
            info_frame,
            text="Porta: --",
            font=('Helvetica', 8)
        )
        self.port_label.pack(side=tk.RIGHT, padx=5)

    def update_status_bar(self):
        """Atualiza as informações da barra de status"""
        try:
            # Atualizar informação de buffer
            total_lines = int(self.log_area.index('end-1c').split('.')[0])
            self.buffer_label.config(
                text=f"Buffer: {total_lines}/{self.max_buffer_lines.get()}"
            )
            
            # Atualizar informação de porta e baud rate
            if self.is_connected and self.serial_port:
                self.port_label.config(text=f"Porta: {self.serial_port.port}")
                self.baud_label.config(text=f"Baud: {self.serial_port.baudrate}")
            else:
                self.port_label.config(text="Porta: --")
                self.baud_label.config(text="Baud: --")
                
        except Exception as e:
            logging.error(f"Erro ao atualizar barra de status: {str(e)}")

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

    def open_github_issues(self):
        """Abre a página de issues do GitHub no navegador padrão"""
        issues_url = "https://github.com/alanbsantos/restorecell-terminal/issues"
        try:
            webbrowser.open(issues_url)
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Não foi possível abrir o navegador: {str(e)}\n\n"
                f"Por favor, acesse manualmente:\n{issues_url}"
            )

    def search_logs(self):
        """Busca avançada nos logs"""
        try:
            search_term = self.filter_combo.get()
            if not search_term or search_term == 'Bruto':
                self.restore_original_log()
                return
                
            # Salvar posição atual do scroll
            current_position = self.log_area.yview()
            
            # Limpar área de log
            self.log_area.delete('1.0', tk.END)
            
            # Filtrar e inserir linhas que contêm o termo
            count = 0
            for line in self.original_log.splitlines():
                if search_term.lower() in line.lower():
                    self.log_area.insert(tk.END, line + '\n')
                    count += 1
            
            # Destacar termos encontrados
            self.highlight_search_terms(search_term)
            
            # Restaurar posição do scroll
            self.log_area.yview_moveto(current_position[0])
            
            # Mostrar resultado
            messagebox.showinfo(
                "Resultado da Busca",
                f"Encontrados {count} resultados para '{search_term}'"
            )
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro na busca: {str(e)}")
            self.restore_original_log()

    def restore_original_log(self):
        """Restaura o log original"""
        if hasattr(self, 'original_log'):
            self.log_area.delete("1.0", tk.END)
            self.log_area.insert("1.0", self.original_log)

    def highlight_search_terms(self, search_term):
        """Destaca os termos encontrados no log"""
        if not search_term or search_term == 'Bruto':
            return
                
        start_pos = "1.0"
        while True:
            start_pos = self.log_area.search(
                search_term,
                start_pos,
                tk.END,
                nocase=True
            )
            if not start_pos:
                break
                
            end_pos = f"{start_pos}+{len(search_term)}c"
            self.log_area.tag_add("highlight", start_pos, end_pos)
            self.log_area.tag_config(
                "highlight",
                background="yellow",
                foreground="black"
            )
            start_pos = end_pos

    def clear_logs(self):
        """Limpa a área de logs com confirmação do usuário"""
        if messagebox.askyesno("Limpar Logs", "Deseja realmente limpar todos os logs?"):
            try:
                # Limpar área de texto
                self.log_area.delete("1.0", tk.END)
                
                # Resetar log original
                if hasattr(self, 'original_log'):
                    self.original_log = ''
                
                # Feedback visual
                self.status_label.configure(text="Logs limpos")
                
                # Registrar ação
                logging.info("Logs foram limpos pelo usuário")
                
            except Exception as e:
                messagebox.showerror(
                    "Erro",
                    f"Erro ao limpar logs: {str(e)}"
                )
                logging.error(f"Erro ao limpar logs: {str(e)}")

    def save_logs(self):
        """Salva os logs em um arquivo"""
        try:
            # Obter data e hora atual para o nome do arquivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"logs_restorecell_{timestamp}.txt"
            
            # Abrir diálogo para salvar arquivo
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                initialfile=default_filename,
                filetypes=[
                    ("Arquivos de texto", "*.txt"),
                    ("Todos os arquivos", "*.*")
                ]
            )
            
            if filename:
                # Obter conteúdo atual dos logs
                log_content = self.log_area.get("1.0", tk.END)
                
                # Salvar arquivo
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                
                # Feedback visual
                messagebox.showinfo(
                    "Sucesso",
                    f"Logs salvos com sucesso em:\n{filename}"
                )
                
                # Registrar ação
                logging.info(f"Logs salvos em: {filename}")
                
        except Exception as e:
            messagebox.showerror(
                "Erro",
                f"Erro ao salvar logs: {str(e)}"
            )
            logging.error(f"Erro ao salvar logs: {str(e)}")

    def toggle_connection(self):
        """Alterna entre conectar e desconectar da porta serial"""
        try:
            if not self.is_connected:
                self.connect()
            else:
                self.disconnect()
        except Exception as e:
            logging.error(f"Erro ao alternar conexão: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao alternar conexão: {str(e)}")

    def connect(self):
        """Estabelece conexão com a porta serial"""
        try:
            if not self.port_combo.get():
                messagebox.showerror("Erro", "Selecione uma porta COM")
                return
                
            # Verificar disponibilidade da porta
            if not self.verificar_disponibilidade_porta(self.port_combo.get()):
                messagebox.showerror(
                    "Erro",
                    "Porta não disponível.\nVerifique se ela não está sendo usada por outro programa."
                )
                return
            
            # Configurar e abrir porta serial
            self.serial_port = serial.Serial(
                port=self.port_combo.get(),
                baudrate=int(self.baud_combo.get()),
                timeout=0.1
            )
            
            # Atualizar estado
            self.is_connected = True
            self.connection_status.set("connected")
            self.connect_btn.configure(text="Desconectar")
            
            # Iniciar thread de leitura
            self.stop_threads = False
            read_thread = threading.Thread(target=self.read_serial, daemon=True)
            read_thread.start()
            self.threads.append(read_thread)
            
            # Atualizar interface
            self.update_status_indicator()
            logging.info(f"Conectado à porta {self.port_combo.get()}")
            
        except Exception as e:
            logging.error(f"Erro ao conectar: {str(e)}")
            messagebox.showerror("Erro de Conexão", f"Erro ao conectar: {str(e)}")
            self.disconnect()

    def disconnect(self):
        """Desconecta da porta serial"""
        try:
            # Parar threads
            self.stop_threads = True
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            self.threads.clear()
            
            # Fechar porta serial
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            # Atualizar estado
            self.is_connected = False
            self.connection_status.set("disconnected")
            self.connect_btn.configure(text="Conectar")
            
            # Atualizar interface
            self.update_status_indicator()
            logging.info("Desconectado da porta serial")
            
        except Exception as e:
            logging.error(f"Erro ao desconectar: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao desconectar: {str(e)}")
        finally:
            self.serial_port = None

    def create_log_area(self):
        """Cria a área de exibição de logs"""
        # Frame para área de log
        log_frame = ttk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Criar área de texto com scrollbar
        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=('Consolas', self.font_size.get()),
            background=self.current_theme['background'],
            foreground=self.current_theme['text']
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Configurar tags para highlight
        self.log_area.tag_configure(
            "highlight",
            background="yellow",
            foreground="black"
        )
        
        # Configurar menu de contexto
        self.create_context_menu()
        
        # Bind eventos
        self.log_area.bind('<Control-c>', self.copy_selection)
        self.log_area.bind('<Control-a>', self.select_all)
        self.log_area.bind('<Button-3>', self.show_context_menu)

    def create_context_menu(self):
        """Cria menu de contexto para a área de log"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copiar", command=self.copy_selection)
        self.context_menu.add_command(label="Selecionar Tudo", command=self.select_all)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Limpar Logs", command=self.clear_logs)
        self.context_menu.add_command(label="Salvar Logs...", command=self.save_logs)

    def show_context_menu(self, event):
        """Exibe o menu de contexto"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_selection(self, event=None):
        """Copia o texto selecionado para a área de transferência"""
        try:
            selected_text = self.log_area.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
        except tk.TclError:
            # Nenhuma seleção
            pass

    def select_all(self, event=None):
        """Seleciona todo o texto da área de log"""
        self.log_area.tag_add(tk.SEL, "1.0", tk.END)
        self.log_area.mark_set(tk.INSERT, "1.0")
        self.log_area.see(tk.INSERT)
        return 'break'

    def update_font_size(self):
        """Atualiza o tamanho da fonte da área de log"""
        current_font = font.Font(font=self.log_area['font'])
        self.log_area.configure(
            font=(current_font.actual()['family'], self.font_size.get())
        )

    def update_ports_list(self):
        """Atualiza a lista de portas seriais disponíveis"""
        try:
            # Obter lista de portas
            available_ports = [
                port.device
                for port in serial.tools.list_ports.comports()
            ]
            
            # Ordenar portas
            available_ports.sort()
            
            # Salvar seleção atual
            current_selection = self.port_combo.get() if hasattr(self, 'port_combo') else None
            
            # Atualizar combobox
            self.port_combo['values'] = available_ports
            
            # Restaurar seleção anterior se ainda disponível
            if current_selection and current_selection in available_ports:
                self.port_combo.set(current_selection)
            elif available_ports:
                self.port_combo.set(available_ports[0])
            else:
                self.port_combo.set('')
                
            # Atualizar status
            if hasattr(self, 'port_label'):
                if self.is_connected and self.serial_port:
                    self.port_label.config(text=f"Porta: {self.serial_port.port}")
                else:
                    self.port_label.config(text="Porta: --")
                    
        except Exception as e:
            logging.error(f"Erro ao atualizar lista de portas: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao atualizar lista de portas: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = RestoreCellTerminal(root)
    
    # Registrar função de limpeza ao fechar
    root.protocol("WM_DELETE_WINDOW", app.cleanup_and_exit)
    
    root.mainloop()
