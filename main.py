"""
Watchdog Principal - Con recuperación robusta de errores
"""
import os
import sys
import time
import atexit
import traceback
from datetime import datetime

from src.lock_manager import LockManager
from src.logger import logger
from src.schedule_manager import scheduler
from src.watchdog import AppWatchdog


# ============================================
# CONFIGURACIÓN
# ============================================
CONFIG = {
    #"app_name": "smart-dbf_local.exe",
     "app_name": "smart-dbf_v2.1_32b.exe",
    "lock_file": "smart_dbf.lock",
    "timeout_minutes": 70,
    "check_interval_minutes": 15,  # Cambia a 15 para producción
    "wait_after_action_minutes": 2,
    "start_hour": 9,
    "end_hour": 23,
}

# Calcular segundos
CONFIG["check_interval"] = CONFIG["check_interval_minutes"] * 60
CONFIG["wait_after_action"] = CONFIG["wait_after_action_minutes"] * 60


def interruptible_sleep(seconds):
    """
    Duerme en chunks de 10 segundos, verificando stop.txt cada vez.
    Retorna True si se detectó stop.txt, False si completó el sleep normal.
    """
    elapsed = 0
    chunk = 10  # Verificar cada 10 segundos
    
    # Obtener directorio del script/exe
    if getattr(sys, 'frozen', False):
        # Running as exe
        script_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        script_dir = os.path.dirname(os.path.abspath(__file__))
    
    stop_file = os.path.join(script_dir, "stop.txt")
    
    while elapsed < seconds:
        if os.path.exists(stop_file):
            return True  # Señal de stop detectada
        
        # Dormir el menor entre: tiempo restante o chunk
        sleep_time = min(chunk, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time
    
    return False  # Sleep completado sin interrupción


def main():
    """Función principal - ROBUSTA contra errores"""
    
    try:
        # Mostrar banner
        logger.info("=" * 60)
        logger.info("🛡️  WATCHDOG 1.6")
        logger.info(f"📅 Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📌 CWD: {os.getcwd()}")
        logger.info(f"📌 Frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"📌 sys.executable: {sys.executable}")
        logger.info(f"📌 __file__: {__file__}")
        logger.info("=" * 60)
        
        # Mostrar configuración
        logger.info(f"⚙️  CONFIGURACIÓN:")
        logger.info(f"   📱 App: {CONFIG['app_name']}")
        logger.info(f"   🔒 Lock: {CONFIG['lock_file']}")
        logger.info(f"   ⏱️  Timeout: {CONFIG['timeout_minutes']} min")
        logger.info(f"   🔄 Revisión: cada {CONFIG['check_interval_minutes']} min")
        logger.info(f"   🕐 Horario: {CONFIG['start_hour']}:00-{CONFIG['end_hour']}:00")
        logger.info("=" * 60)
        
        # 1. INICIALIZAR WATCHDOG
        app_watchdog = AppWatchdog(
            app_name=CONFIG["app_name"],
            lock_file=CONFIG["lock_file"],
            timeout_minutes=CONFIG["timeout_minutes"],
            lock_time_format="%Y-%m-%d %H:%M:%S"
        )
        
        # 2. VERIFICAR QUE NO HAY OTRO WATCHDOG Y ADQUIRIR LOCK
        lock_manager = LockManager()

        logger.info(f"🔒 Watchdog lock file: {lock_manager.lock_path}")
        
        if not lock_manager.check_and_acquire():
            logger.error("❌ Ya hay otro watchdog corriendo. Saliendo.")
            logger.status("❌ ERROR: Otro watchdog activo")
            return 1
        
        # Lock ya fue creado por check_and_acquire()
        logger.info(f"🔒 Watchdog registrado (PID {os.getpid()})")
        
        # 3. CONFIGURAR CLEANUP (se ejecuta incluso si crashea)
        atexit.register(lambda: lock_manager.remove_lock())
        atexit.register(lambda: logger.info("👋 Watchdog finalizado"))
        atexit.register(lambda: logger.status("💤 Watchdog detenido"))
        
        # 4. REGISTRAR HANDLER PARA SEÑALES DE CRASH
        def handle_crash(signum=None, frame=None):
            """Maneja crashes inesperados"""
            logger.error("💥 CRASH DETECTADO - Limpiando...")
            lock_manager.remove_lock()
            logger.status("💥 Watchdog crasheó")
            sys.exit(1)
        
        # En Windows no hay señales UNIX, pero podemos registrar con atexit
        atexit.register(handle_crash)
        
        logger.status(f"✅ Activo | Robustez: ALTA | Revisión: {CONFIG['check_interval_minutes']}min")
        
    except Exception as e:
        # ERROR EN INICIALIZACIÓN - NO PODEMOS CONTINUAR
        logger.error(f"💥 ERROR CRÍTICO en inicialización: {e}")
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        logger.status(f"❌ ERROR INICIAL: {str(e)[:40]}...")
        
        # Registrar para diagnóstico
        try:
            with open("watchdog_crash_init.log", "a") as f:
                f.write(f"[{datetime.now()}] INIT CRASH: {str(e)}\n")
                f.write(traceback.format_exc() + "\n")
        except:
            pass
        
        return 1
    
    # 5. LOOP PRINCIPAL CON RECUPERACIÓN POR CICLO
    ciclo = 0
    ejecuciones = 0
    reinicios = 0
    errores_recientes = 0
    
    # Refrescar watchdog.lock antes de que expire (LOCK_TIMEOUT_MINUTES=5)
    last_lock_refresh = datetime.now()
    lock_refresh_interval_seconds = 10  # Refrescar cada 10 segundos
    
    logger.info("🔁 Iniciando loop principal con recuperación...")
    
    # Determinar ruta del stop.txt una vez
    if getattr(sys, 'frozen', False):
        script_dir = os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    stop_file = os.path.join(script_dir, "stop.txt")
    
    while True:
        try:
            # Mantener vivo el watchdog.lock para evitar que otro scheduler lo tome como huérfano
            now = datetime.now()
            if (now - last_lock_refresh).total_seconds() >= lock_refresh_interval_seconds:
                lock_manager.refresh_lock()
                last_lock_refresh = now

            # Chequear archivo de stop para finalizar el watchdog
            if os.path.exists(stop_file):
                logger.info("[STOP] 🛑 stop.txt encontrado. Saliendo del watchdog...")
                logger.status("🛑 Detenido por stop.txt")
                break

            ciclo += 1
            hora_actual = datetime.now().strftime('%H:%M')
            
            logger.info(f"🔄 Ciclo #{ciclo} - {hora_actual}")
            
            # Verificar si estamos en horario
            if CONFIG["start_hour"] <= datetime.now().hour < CONFIG["end_hour"]:
                logger.info(f"✅ En horario ({CONFIG['start_hour']}:00-{CONFIG['end_hour']}:00)")
                
                # Verificar estado de la app
                estado = app_watchdog.check_app_status()
                logger.info(f"📊 Estado: {estado}")
                
                if estado == "not_running":
                    logger.info(f"🚀 Ejecutando {CONFIG['app_name']}...")
                    logger.status(f"🚀 Ejecutando {CONFIG['app_name']}...")
                    
                    if app_watchdog.start_app():
                        ejecuciones += 1
                        logger.info(f"✅ App iniciada (total: {ejecuciones})")
                        logger.status("✅ App en ejecución")
                        if interruptible_sleep(CONFIG["wait_after_action"]):
                            logger.info("[STOP] stop.txt detectado durante espera")
                            break
                    else:
                        logger.error("❌ Error al iniciar app")
                        logger.status("❌ Error al iniciar")
                        errores_recientes += 1
                
                elif estado == "hung":
                    logger.warning(f"⚠️ App colgada (> {CONFIG['timeout_minutes']}min)")
                    logger.status("⚠️ App colgada, reiniciando...")
                    
                    if app_watchdog.kill_app():
                        reinicios += 1
                        logger.info(f"♻️ App terminada (reinicios: {reinicios})")
                        if interruptible_sleep(10):
                            logger.info("[STOP] stop.txt detectado durante espera")
                            break
                        
                        if app_watchdog.start_app():
                            ejecuciones += 1
                            logger.info("✅ App reiniciada")
                            logger.status("✅ App reiniciada")
                            if interruptible_sleep(CONFIG["wait_after_action"]):
                                logger.info("[STOP] stop.txt detectado durante espera")
                                break
                        else:
                            logger.error("❌ Error al reiniciar")
                            logger.status("❌ Error al reiniciar")
                            errores_recientes += 1
                    else:
                        logger.error("❌ No se pudo recuperar app")
                        logger.status("❌ App colgada sin recuperación")
                        errores_recientes += 1
                
                elif estado == "running_ok":
                    logger.info("👍 App ejecutándose normalmente")
                    logger.status("👍 App OK")
                    errores_recientes = 0  # Resetear contador si todo va bien
            else:
                logger.info(f"😴 Fuera de horario")
                logger.status(f"💤 Durmiendo hasta {CONFIG['start_hour']}:00")
            
            # Esperar para próxima revisión
            minutos = CONFIG["check_interval_minutes"]
            logger.info(f"💤 Durmiendo {minutos} minutos...")
            if interruptible_sleep(CONFIG["check_interval"]):
                logger.info("[STOP] stop.txt detectado durante sleep")
                logger.status("🛑 Detenido por stop.txt")
                break
            
        except KeyboardInterrupt:
            logger.info("🛑 Detenido por usuario")
            logger.status("🛑 Detenido por usuario")
            break
            
        except OSError as e:
            # ERROR DE SISTEMA OPERATIVO (incluyendo WinError 233 - broken pipe)
            if hasattr(e, 'winerror') and e.winerror == 233:
                logger.warning(f"⚠️  Broken pipe detectado en ciclo #{ciclo} (proceso terminado inesperadamente)")
                logger.info("🔄 Continuando con el siguiente ciclo...")
                errores_recientes = 0  # No contar como error grave
            else:
                errores_recientes += 1
                logger.error(f"⚠️  Error OS en ciclo #{ciclo}: {e}")
                logger.error(f"📋 Traceback parcial: {traceback.format_exc()[:500]}...")
                logger.status(f"⚠️  Error temporal, continuando...")
            
        except Exception as e:
            # ERROR EN CICLO - NO DETENER EL WATCHDOG
            errores_recientes += 1
            logger.error(f"⚠️  Error en ciclo #{ciclo}: {e}")
            logger.error(f"📋 Traceback parcial: {traceback.format_exc()[:500]}...")
            logger.status(f"⚠️  Error temporal, continuando...")
            
            # Registrar error
            try:
                with open("watchdog_errors.log", "a") as f:
                    f.write(f"[{datetime.now()}] CYCLE {ciclo} ERROR: {str(e)}\n")
                    f.write(traceback.format_exc() + "\n")
            except:
                pass
            
            # Si hay muchos errores seguidos, esperar más
            if errores_recientes >= 3:
                wait_time = 300  # 5 minutos
                logger.warning(f"⚠️  Muchos errores seguidos ({errores_recientes}), esperando {wait_time//60} min...")
                if interruptible_sleep(wait_time):
                    logger.info("[STOP] stop.txt detectado durante espera de error")
                    logger.status("🛑 Detenido por stop.txt")
                    break
            else:
                # Esperar tiempo normal
                if interruptible_sleep(CONFIG["check_interval"]):
                    logger.info("[STOP] stop.txt detectado durante espera de error")
                    logger.status("🛑 Detenido por stop.txt")
                    break
    
    # 6. FINALIZACIÓN NORMAL
    logger.info("=" * 60)
    logger.info(f"📊 RESUMEN FINAL:")
    logger.info(f"   Ciclos completados: {ciclo}")
    logger.info(f"   Ejecuciones de app: {ejecuciones}")
    logger.info(f"   Reinicios por colgadas: {reinicios}")
    logger.info(f"   Errores capturados: {errores_recientes}")
    logger.info("=" * 60)
    logger.info("👋 Watchdog finalizado correctamente")
    
    return 0


if __name__ == "__main__":
    # Cambiar al directorio del script
    try:
        if getattr(sys, 'frozen', False):
            os.chdir(os.path.dirname(sys.executable))
        else:
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        print(f"❌ ERROR cambiando directorio: {e}")
        sys.exit(1)
    
    # Ejecutar con captura de errores final
    try:
        exit_code = main()
    except Exception as e:
        print(f"💥 ERROR NO CAPTURADO: {e}")
        print(traceback.format_exc())
        exit_code = 1
    
    sys.exit(exit_code)