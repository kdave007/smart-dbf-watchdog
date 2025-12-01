"""
Test SIMPLE para LockManager - Solo 3 casos básicos
"""
import os
import sys
import time
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent  # carpeta smart-dbf-watchdog
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import lock_manager

def test_1():
    """Caso 1: No hay lock, debe poder crear"""
    print("Test 1: Primer watchdog")
    
    # Limpiar
    lock_file = Path("watchdog.lock")
    if lock_file.exists():
        lock_file.unlink()
    
    lm = lock_manager.LockManager()
    
    # Debería poder adquirir
    if lm.check_and_acquire():
        lm.create_lock()
        print("  ✓ Lock creado")
        
        # Verificar que existe
        if lock_file.exists():
            print("  ✓ Lock file existe en disco")
        else:
            print("  ✗ ERROR: Lock file no creado")
        
        lm.remove_lock()
        return True
    else:
        print("  ✗ ERROR: No pudo adquirir lock (debería poder)")
        return False

def test_2():
    """Caso 2: Lock reciente, debe rechazar"""
    print("\nTest 2: Lock reciente (debe rechazar)")
    
    # Primero crear un lock
    lm1 = lock_manager.LockManager()
    lm1.check_and_acquire()
    lm1.create_lock()
    print("  Lock creado por 'proceso 1'")
    
    # Esperar 1 segundo (pero menos de 5 minutos)
    time.sleep(1)
    
    # Intentar otro lock
    lm2 = lock_manager.LockManager()
    result = lm2.check_and_acquire()
    
    if not result:
        print("  ✓ Correctamente rechazado (hay otro watchdog)")
    else:
        print("  ✗ ERROR: Debería haber rechazado")
    
    # Limpiar
    lm1.remove_lock()
    return not result  # Queremos que sea False

def test_3():
    """Caso 3: Salir y verificar que se limpia"""
    print("\nTest 3: Limpieza automática")
    
    # Crear lock
    lm = lock_manager.LockManager()
    lm.check_and_acquire()
    lm.create_lock()
    print("  Lock creado")
    
    # Remover (simula salida normal)
    lm.remove_lock()
    
    # Verificar que no existe
    lock_file = Path("watchdog.lock")
    if not lock_file.exists():
        print("  ✓ Lock removido correctamente")
        return True
    else:
        print("  ✗ ERROR: Lock no fue removido")
        return False

def main():
    """Ejecutar todos los tests"""
    print("="*50)
    print("TEST SIMPLE LOCK MANAGER")
    print("="*50)
    
    resultados = []
    
    # resultados.append(test_1())
    # time.sleep(1)  # Pequeña pausa
    
    resultados.append(test_2())
    time.sleep(1)
    
    resultados.append(test_3())
    
    # Resumen
    print("\n" + "="*50)
    print("RESULTADO FINAL:")
    print(f"Tests pasados: {sum(resultados)} de {len(resultados)}")
    
    if all(resultados):
        print("✅ TODOS LOS TESTS PASARON")
    else:
        print("❌ ALGUN TEST FALLÓ")
    
    print("="*50)

if __name__ == "__main__":
    main()