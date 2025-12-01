"""
Schedule Manager - Decide cuándo ejecutar la app principal
Usa reloj.txt para recordar la última ejecución
"""
import os
from datetime import datetime, time
from pathlib import Path


class ScheduleManager:
    """
    Maneja la programación horaria (7AM a 9PM, cada hora)
    Simple pero resistente a cambios de hora y apagados
    """
    
    def __init__(self):
        self.clock_file = Path("reloj.txt")
        self.start_hour = 7    # 7:00 AM
        self.end_hour = 21     # 9:00 PM (21 en formato 24h)
        self.interval = 60     # minutos entre ejecuciones
        
    def _read_last_hour(self):
        """Lee la última hora ejecutada desde reloj.txt"""
        if not self.clock_file.exists():
            return None  # Primera ejecución
        
        try:
            with open(self.clock_file, 'r') as f:
                content = f.read().strip()
                if content.isdigit():
                    return int(content)
        except Exception:
            pass
        
        return None
    
    def _write_last_hour(self, hour):
        """Escribe la hora actual en reloj.txt"""
        try:
            with open(self.clock_file, 'w') as f:
                f.write(str(hour))
            return True
        except Exception:
            return False
    
    def is_within_schedule(self):
        """¿Estamos dentro del horario de 7AM a 9PM?"""
        now = datetime.now()
        current_hour = now.hour
        
        # Verificar si estamos en el rango
        if self.start_hour <= current_hour < self.end_hour:
            return True
        return False
    
    def should_run_now(self):
        """
        Verifica si es hora de ejecutar la app principal
        
        Lógica:
        1. ¿Estamos entre 7AM y 9PM?
        2. ¿La hora actual es DIFERENTE a la última ejecución?
        3. ¿Estamos en un múltiplo de la hora? (ej: 8:00, 9:00, etc.)
        """
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        # 1. Fuera de horario → no ejecutar
        if not self.is_within_schedule():
            return False, "Fuera de horario (7AM-9PM)"
        
        # 2. Leer última hora ejecutada
        last_hour = self._read_last_hour()
        
        # Si nunca hemos ejecutado (primera vez), ejecutar si es hora exacta
        if last_hour is None:
            if current_minute <= 5:  # Ejecutar en los primeros 5 minutos de la hora
                self._write_last_hour(current_hour)
                return True, f"Primera ejecución a las {current_hour}:00"
            return False, "Esperando hora exacta para primera ejecución"
        
        # 3. Si ya ejecutamos esta hora → esperar
        if current_hour == last_hour:
            return False, f"Ya se ejecutó esta hora ({current_hour}:00)"
        
        # 4. Ejecutar en los primeros 5 minutos de la nueva hora
        if current_minute <= 5:
            self._write_last_hour(current_hour)
            return True, f"Hora nueva: {current_hour}:00 (última: {last_hour}:00)"
        
        # 5. Si pasaron los primeros 5 minutos, esperar a la próxima hora
        return False, f"Pasó ventana de {current_hour}:00, esperando próxima hora"
    
    def get_next_execution(self):
        """Calcula cuándo será la próxima ejecución"""
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        
        if not self.is_within_schedule():
            # Si es después de las 9PM, mañana a las 7AM
            if current_hour >= self.end_hour:
                next_time = time(self.start_hour, 0)
                return "Mañana a las 07:00"
            # Si es antes de las 7AM, hoy a las 7AM
            else:
                next_time = time(self.start_hour, 0)
                return "Hoy a las 07:00"
        
        # Dentro del horario
        if current_minute <= 5:
            # Estamos en ventana de ejecución
            return f"Hoy a las {current_hour}:00 (en ventana)"
        else:
            # Próxima hora
            next_hour = current_hour + 1
            if next_hour < self.end_hour:
                return f"Hoy a las {next_hour}:00"
            else:
                return "Mañana a las 07:00"


# Instancia global para uso fácil
scheduler = ScheduleManager()