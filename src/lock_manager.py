

class LockManager:
    def create_lock(pid):
        # Escribe watchdog.lock con PID y timestamp
        pass
        
    def check_other_instance():
        # Lee watchdog.lock
        # Si existe y PID diferente está corriendo → return True
        # Si no existe o PID muerto → return False
        pass