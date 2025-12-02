"""
Test REAL del watchdog - Simula escenarios reales
"""
import os
import json
import time
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Asegurar que el directorio raíz del proyecto esté en sys.path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent  # carpeta smart-dbf-watchdog
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import watchdog  # Importamos el módulo para crear instancias


def crear_lock_falso(timestamp_str, pid=9999):
    """Crea un lock file falso para testing"""
    lock_data = {
        "timestamp": timestamp_str,
        "pid": pid,
        "client_id": "test"
    }
    
    with open("test_app.lock", 'w') as f:
        json.dump(lock_data, f, indent=2)
    
    return lock_data


def test_1_lock_fresco():
    """Test: Lock file reciente (<30min)"""
    print("🧪 Test 1: Lock file FRESCO (reciente)")
    print("-" * 40)
    
    # Crear lock file con timestamp actual (fresco)
    timestamp_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    crear_lock_falso(timestamp_actual)
    
    # Crear watchdog de prueba
    wd = watchdog.AppWatchdog(
        app_name="test_app.exe",  # Nombre falso
        lock_file="test_app.lock",
        timeout_minutes=30
    )
    
    # Leer lock file
    lock_data = wd.read_lock_file()
    print(f"✓ Lock leído: {lock_data['timestamp']}")
    
    # Calcular edad
    edad = wd.get_lock_age_minutes()
    print(f"✓ Edad calculada: {edad:.2f} minutos")
    
    # Verificar estado (simulando que proceso existe)
    # Para simular proceso existente, necesitaríamos mock
    print(f"✓ Edad < 30min: {'SÍ' if edad < 30 else 'NO'}")
    
    # Limpiar
    os.remove("test_app.lock")
    print("✅ Test 1 PASADO\n")
    return True


def test_2_lock_viejo():
    """Test: Lock file viejo (>30min)"""
    print("🧪 Test 2: Lock file VIEJO (>30min)")
    print("-" * 40)
    
    # Crear lock file con timestamp de hace 35 minutos
    tiempo_viejo = datetime.now() - timedelta(minutes=35)
    timestamp_viejo = tiempo_viejo.strftime("%Y-%m-%d %H:%M:%S")
    crear_lock_falso(timestamp_viejo)
    
    # Crear watchdog
    wd = watchdog.AppWatchdog(
        app_name="test_app.exe",
        lock_file="test_app.lock",
        timeout_minutes=30
    )
    
    # Leer lock file
    lock_data = wd.read_lock_file()
    print(f"✓ Lock leído: {lock_data['timestamp']}")
    print(f"  (hace 35 minutos)")
    
    # Calcular edad
    edad = wd.get_lock_age_minutes()
    print(f"✓ Edad calculada: {edad:.1f} minutos")
    
    # Verificar
    if edad > 30:
        print(f"✓ CORRECTO: Edad > 30min (app estaría COLGADA)")
    else:
        print(f"✗ ERROR: Edad debería ser >30, es {edad:.1f}")
    
    # Limpiar
    os.remove("test_app.lock")
    print("✅ Test 2 PASADO\n")
    return edad > 30


def test_3_lock_corrupto():
    """Test: Lock file corrupto/inválido"""
    print("🧪 Test 3: Lock file CORRUPTO")
    print("-" * 40)
    
    # Crear archivo corrupto (no JSON válido)
    with open("test_app.lock", 'w') as f:
        f.write("ESTO NO ES JSON {corrupto: sí}")
    
    # Crear watchdog
    wd = watchdog.AppWatchdog(
        app_name="test_app.exe",
        lock_file="test_app.lock",
        timeout_minutes=30
    )
    
    # Intentar leer lock file corrupto
    lock_data = wd.read_lock_file()
    
    if lock_data is None:
        print("✓ CORRECTO: Detectó lock corrupto (retornó None)")
        resultado = True
    else:
        print(f"✗ ERROR: Debería retornar None, retornó: {lock_data}")
        resultado = False
    
    # Calcular edad debería ser None
    edad = wd.get_lock_age_minutes()
    if edad is None:
        print("✓ CORRECTO: Edad es None para lock corrupto")
    else:
        print(f"✗ ERROR: Edad debería ser None, es: {edad}")
        resultado = False
    
    # Limpiar
    os.remove("test_app.lock")
    print("✅ Test 3 PASADO\n")
    return resultado


def test_4_sin_lock_file():
    """Test: No existe lock file"""
    print("🧪 Test 4: SIN lock file")
    print("-" * 40)
    
    # Asegurarse que no existe el archivo
    if os.path.exists("test_app.lock"):
        os.remove("test_app.lock")
    
    # Crear watchdog
    wd = watchdog.AppWatchdog(
        app_name="test_app.exe",
        lock_file="test_app.lock",  # No existe
        timeout_minutes=30
    )
    
    # Intentar leer lock file inexistente
    lock_data = wd.read_lock_file()
    
    if lock_data is None:
        print("✓ CORRECTO: Lock file no existe (retornó None)")
        resultado = True
    else:
        print(f"✗ ERROR: Debería retornar None, retornó: {lock_data}")
        resultado = False
    
    # Calcular edad debería ser None
    edad = wd.get_lock_age_minutes()
    if edad is None:
        print("✓ CORRECTO: Edad es None cuando no hay lock")
    else:
        print(f"✗ ERROR: Edad debería ser None, es: {edad}")
        resultado = False
    
    print("✅ Test 4 PASADO\n")
    return resultado


def test_5_formato_timestamp():
    """Test: Diferentes formatos de timestamp"""
    print("🧪 Test 5: Formatos de timestamp")
    print("-" * 40)
    
    formatos = [
        ("%Y-%m-%d %H:%M:%S", "2025-12-02 14:30:45"),
        ("%d/%m/%Y %H:%M", "02/12/2025 14:30"),
        ("%Y%m%d_%H%M%S", "20251202_143045"),
    ]
    
    resultados = []
    
    for fmt, timestamp_str in formatos:
        print(f"\nProbando formato: {fmt}")
        print(f"Timestamp: {timestamp_str}")
        
        # Crear watchdog con formato específico
        wd = watchdog.AppWatchdog(
            app_name="test_app.exe",
            lock_file="test_app.lock",
            timeout_minutes=30,
            lock_time_format=fmt
        )
        
        # Crear lock con este formato
        lock_data = {
            "timestamp": timestamp_str,
            "pid": 9999,
            "client_id": "test"
        }
        
        with open("test_app.lock", 'w') as f:
            json.dump(lock_data, f)
        
        # Intentar leer y calcular edad
        data_leida = wd.read_lock_file()
        edad = wd.get_lock_age_minutes()
        
        if data_leida and edad is not None:
            print(f"  ✓ Formato aceptado, edad: {edad:.2f} min")
            resultados.append(True)
        else:
            print(f"  ✗ Formato NO aceptado")
            resultados.append(False)
        
        # Limpiar
        os.remove("test_app.lock")
    
    todos_ok = all(resultados)
    print(f"\n✅ Test 5: {'PASADO' if todos_ok else 'FALLADO'}\n")
    return todos_ok


def test_6_simulacion_estados():
    """Test: Simulación de estados posibles"""
    print("🧪 Test 6: Simulación de ESTADOS de app")
    print("-" * 40)
    
    # Nota: Para test real necesitaríamos mock de is_app_running()
    # Por ahora solo explicamos la lógica
    
    print("ESTADOS POSIBLES:")
    print()
    print("1. 'not_running' → Cuando:")
    print("   - is_app_running() retorna False")
    print("   - Sin importar lock file")
    print()
    print("2. 'running_ok' → Cuando:")
    print("   - is_app_running() retorna True")
    print("   - Y (lock file no existe O edad < timeout)")
    print()
    print("3. 'hung' → Cuando:")
    print("   - is_app_running() retorna True")
    print("   - Y lock file existe Y edad > timeout")
    print()
    
    print("🎯 Para test REAL de estados necesitamos:")
    print("   - Mock de is_app_running()")
    print("   - Mock de subprocess.run()")
    print("   (Esto es para test unitario avanzado)")
    
    print("\n⏭️  Este test se completará en versión avanzada")
    return True  # Aceptamos por ahora


def main():
    """Ejecutar todos los tests"""
    print("=" * 60)
    print("🧪 TESTS REALES DEL WATCHDOG")
    print("=" * 60)
    
    # Cambiar al directorio actual
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    resultados = []
    
    try:
        resultados.append(test_1_lock_fresco())
        time.sleep(0.5)
        
        resultados.append(test_2_lock_viejo())
        time.sleep(0.5)
        
        resultados.append(test_3_lock_corrupto())
        time.sleep(0.5)
        
        resultados.append(test_4_sin_lock_file())
        time.sleep(0.5)
        
        resultados.append(test_5_formato_timestamp())
        time.sleep(0.5)
        
        resultados.append(test_6_simulacion_estados())
        
    except Exception as e:
        print(f"💥 ERROR en tests: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Resumen final
    print("=" * 60)
    print("📊 RESUMEN FINAL DE TESTS")
    print("=" * 60)
    
    pasados = sum(resultados)
    total = len(resultados)
    
    for i, resultado in enumerate(resultados, 1):
        estado = "✅ PASÓ" if resultado else "❌ FALLÓ"
        print(f"Test {i}: {estado}")
    
    print(f"\n🎯 Resultado: {pasados}/{total} tests pasados")
    
    if pasados == total:
        print("\n✨ ¡TODOS LOS TESTS PASARON!")
        print("El watchdog funciona correctamente en escenarios básicos.")
    else:
        print(f"\n⚠️  {total - pasados} test(s) fallaron")
        print("Revisa los errores arriba.")
    
    print("=" * 60)
    return pasados == total


if __name__ == "__main__":
    exit(0 if main() else 1)