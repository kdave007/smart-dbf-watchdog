"""
Schedule Manager SIMPLIFICADO - Solo horario 7AM-9PM
"""
from datetime import datetime


class SimpleSchedule:
    """
    Solo verifica: ¿Estamos entre 7AM y 9PM?
    """
    
    def __init__(self):
        self.start_hour = 7    # 7:00 AM
        self.end_hour = 21     # 9:00 PM
    
    def is_within_hours(self):
        """¿Estamos entre 7AM y 9PM?"""
        now = datetime.now()
        return self.start_hour <= now.hour < self.end_hour
    
    def get_next_window(self):
        """Cuándo será el próximo período de ejecución"""
        now = datetime.now()
        current_hour = now.hour
        
        if current_hour < self.start_hour:
            return f"Hoy a las {self.start_hour}:00"
        elif current_hour >= self.end_hour:
            return f"Mañana a las {self.start_hour}:00"
        else:
            return f"Hasta las {self.end_hour}:00"


# Instancia global
scheduler = SimpleSchedule()