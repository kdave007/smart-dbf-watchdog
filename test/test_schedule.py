# test_schedule.py
import sys
from pathlib import Path
from datetime import datetime

# Asegurar que el directorio raíz del proyecto esté en sys.path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent  # carpeta smart-dbf-watchdog
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.schedule_manager import ScheduleManager

def test_schedule():
    print("Probando Schedule Manager...")
    print(f"Hora actual: {datetime.now().strftime('%H:%M')}")
    print()
    
    scheduler = ScheduleManager()
    
    # Test 1: ¿Dentro de horario?
    within = scheduler.is_within_schedule()
    print(f"1. ¿Dentro de horario (7AM-9PM)?: {'✅ Sí' if within else '❌ No'}")
    
    # Test 2: ¿Debe ejecutar ahora?
    should_run, reason = scheduler.should_run_now()
    print(f"2. ¿Debe ejecutar ahora?: {'✅ Sí' if should_run else '❌ No'}")
    print(f"   Razón: {reason}")
    
    # Test 3: Próxima ejecución
    next_exec = scheduler.get_next_execution()
    print(f"3. Próxima ejecución: {next_exec}")
    
    # Test 4: Mostrar contenido de reloj.txt
    import os
    if os.path.exists("reloj.txt"):
        with open("reloj.txt", "r") as f:
            print(f"4. reloj.txt: {f.read().strip()} (última hora ejecutada)")
    else:
        print("4. reloj.txt: (no existe aún)")

if __name__ == "__main__":
    test_schedule()