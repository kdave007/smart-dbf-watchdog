

class WatchDog:
    def check_app():
        # 1. ¿app_principal.exe está corriendo?
        # 2. ¿app.lock es viejo (>30min)?
        # 3. Devuelve: "running", "hung", "not_running"
        pass

    def kill_app():
        # Mata app_principal.exe elegante -> forzado
        pass

    def start_app():
        # Ejecuta app_principal.exe
        pass