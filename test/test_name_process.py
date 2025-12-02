# test_proceso_nombre.py
import subprocess
import os

def get_exact_process_name():
    """Obtiene el nombre EXACTO del proceso smart-dbf"""
    
    print("="*60)
    print("🔍 DETECTANDO NOMBRE EXACTO DEL PROCESO")
    print("="*60)
    
    # 1. Ejecuta tu app manualmente primero
    input("1. Ejecuta smart-dbf_local.exe manualmente y presiona Enter...")
    
    # 2. Buscar con tasklist
    print("\n2. Buscando con tasklist...")
    result = subprocess.run(['tasklist'], capture_output=True, text=True)
    
    found = False
    for line in result.stdout.split('\n'):
        if 'smart' in line.lower() or 'dbf' in line.lower():
            print(f"   📌 {line.strip()}")
            found = True
    
    if not found:
        print("   ❌ No se encontró 'smart' o 'dbf' en tasklist")
    
    # 3. Buscar con PowerShell
    print("\n3. Buscando con PowerShell...")
    ps_cmd = 'Get-Process | Where-Object {$_.ProcessName -like "*smart*" -or $_.ProcessName -like "*dbf*"} | Select-Object ProcessName, Id'
    
    try:
        result = subprocess.run(['powershell', '-Command', ps_cmd], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            print("   Procesos encontrados:")
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"   📌 {line.strip()}")
        else:
            print("   ❌ No se encontraron procesos con 'smart' o 'dbf'")
    except Exception as e:
        print(f"   ❌ Error con PowerShell: {e}")
    
    # 4. Buscar archivos .lock
    print("\n4. Buscando archivos .lock...")
    lock_files = [f for f in os.listdir('.') if f.endswith('.lock')]
    if lock_files:
        print(f"   🔒 Lock files encontrados: {lock_files}")
    else:
        print("   ❌ No hay archivos .lock")
    
    print("\n" + "="*60)
    print("🎯 INSTRUCCIONES:")
    print("1. Mira el nombre EXACTO que aparece en tasklist/PowerShell")
    print("2. Ese nombre debe ir en CONFIG['app_name']")
    print("3. Si hay lock file, ese nombre debe ir en CONFIG['lock_file']")
    print("="*60)

if __name__ == "__main__":
    get_exact_process_name()