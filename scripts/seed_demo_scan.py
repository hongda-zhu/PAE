import os
import json
from pathlib import Path
from datetime import datetime, timezone

# PDF template content (valid minimal 1-page PDF)
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 90 >>
stream
BT
/F1 24 Tf
100 700 Td
(IKUSA Compliance Report - INSECUREBANK V2) Tj
0 -40 Td
/F1 14 Tf
(CRA Readiness Score: 78 / 100) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f \r
0000000009 00000 n \r
0000000056 00000 n \r
0000000111 00000 n \r
0000000259 00000 n \r
trailer
<< /Size 5 /Root 1 0 R >>
startxref
400
%%EOF
"""

def main():
    # Resolve scan storage directory from environment or default
    from ikusa.config import get_settings
    try:
        settings = get_settings()
        storage = settings.scan_storage
    except Exception:
        storage = Path("/tmp/ikusa-scans")
    
    scan_id = "ikusa_demo_01"
    scan_dir = storage / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating mock scan in: {scan_dir.resolve()}")
    
    # 1. State JSON
    state = {
        "scan_id": scan_id,
        "status": "done",
        "stage": "done",
        "message": "Scan complete",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "user_id": "demo",
        "app_name": "InsecureBankv2",
        "package_name": "com.android.insecurebankv2",
        "cra_score": 78,
        "findings_count": 5,
        "duration_seconds": 45.3,
        "error": None
    }
    with open(scan_dir / "state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
        
    # 2. Result JSON
    result = {
        "scan_id": scan_id,
        "app_name": "InsecureBankv2",
        "package_name": "com.android.insecurebankv2",
        "apk_hash": "a4d3f56bc78de90f01a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4",
        "cra_score": 78,
        "categories_covered": ["MASVS-STORAGE", "MASVS-CRYPTO", "MASVS-NETWORK", "MASVS-PLATFORM"],
        "duration_seconds": 45.3,
        "findings": [
            {
                "id": "CRYPTO-0",
                "title": "Uso de claves criptográficas estáticas",
                "severity": "high",
                "masvs_category": "MASVS-CRYPTO",
                "description": "La aplicación utiliza una clave AES estática codificada de forma rígida en el código fuente para cifrar los datos del usuario.",
                "file_path": "com/android/insecurebankv2/CryptoUtility.java",
                "cwe": "CWE-321",
                "raw_mobsf_key": "hardcoded_aes_key",
                "priority": 1,
                "explanation": "Se identificó una clave AES fija dentro de las utilidades de criptografía de la app. Esto anula la seguridad del cifrado, ya que cualquier atacante que descompile el APK puede extraer la clave y descifrar la base de datos o comunicaciones.",
                "remediation": "Migrar al Android Keystore System para generar y almacenar claves criptográficas de forma segura protegidas por hardware en el dispositivo.",
                "cra_articles": ["Annex I (1)(h)", "Annex I (2)(b)"]
            },
            {
                "id": "NETWORK-0",
                "title": "Uso de HTTP no seguro en el canal de comunicación",
                "severity": "high",
                "masvs_category": "MASVS-NETWORK",
                "description": "La aplicación realiza conexiones HTTP en texto plano a su servidor backend, lo que facilita ataques de tipo Man-in-the-Middle (MitM).",
                "file_path": "com/android/insecurebankv2/DoTransfer.java",
                "cwe": "CWE-319",
                "raw_mobsf_key": "cleartext_traffic_allowed",
                "priority": 1,
                "explanation": "Las transferencias y datos bancarios se envían mediante HTTP simple sin cifrar. Cualquier tercero en la misma red Wi-Fi podría interceptar o modificar el tráfico bancario.",
                "remediation": "Habilitar la configuración de seguridad de red en el manifiesto para exigir HTTPS de forma estricta y rechazar tráfico en texto plano.",
                "cra_articles": ["Annex I (1)(f)", "Annex I (2)(a)"]
            },
            {
                "id": "STORAGE-0",
                "title": "Copia de seguridad de la aplicación habilitada",
                "severity": "medium",
                "masvs_category": "MASVS-STORAGE",
                "description": "La bandera 'android:allowBackup' está establecida en 'true' en el archivo AndroidManifest.xml, lo que permite realizar copias de seguridad de los datos de la aplicación mediante comandos ADB.",
                "file_path": "AndroidManifest.xml",
                "cwe": "CWE-921",
                "raw_mobsf_key": "allow_backup_enabled",
                "priority": 2,
                "explanation": "Al permitir backups, cualquier persona con acceso físico al teléfono móvil y la depuración USB activa puede extraer los datos privados de la aplicación a su ordenador usando 'adb backup'.",
                "remediation": "Establecer 'android:allowBackup=false' en el archivo AndroidManifest.xml o configurar reglas detalladas de filtrado de copias de seguridad.",
                "cra_articles": ["Annex I (1)(h)"]
            },
            {
                "id": "STORAGE-1",
                "title": "Almacenamiento de datos sensibles en la base de datos local sin cifrar",
                "severity": "medium",
                "masvs_category": "MASVS-STORAGE",
                "description": "La aplicación almacena registros de transacciones bancarias en una base de datos SQLite estándar sin cifrado adicional.",
                "file_path": "com/android/insecurebankv2/DatabaseHelper.java",
                "cwe": "CWE-311",
                "raw_mobsf_key": "sqlite_db_plain",
                "priority": 2,
                "explanation": "La base de datos del historial de transacciones se guarda sin cifrar. Si el dispositivo sufre de rooting o vulnerabilidad del sistema operativo, otras aplicaciones o atacantes físicos podrían leer las transacciones bancarias directamente.",
                "remediation": "Migrar a SQLCipher o cifrar las columnas con información sensible antes de insertarlas en la base de datos local.",
                "cra_articles": ["Annex I (1)(h)"]
            },
            {
                "id": "PLATFORM-0",
                "title": "Depuración habilitada en producción",
                "severity": "low",
                "masvs_category": "MASVS-PLATFORM",
                "description": "El atributo 'android:debuggable' está habilitado en el manifiesto, facilitando la conexión de depuradores externos.",
                "file_path": "AndroidManifest.xml",
                "cwe": "CWE-215",
                "raw_mobsf_key": "debuggable_enabled",
                "priority": 3,
                "explanation": "El APK se compiló en modo depuración. Esto permite a los atacantes acoplar un depurador en tiempo de ejecución, volcar la memoria y saltarse controles de seguridad importantes.",
                "remediation": "Asegurarse de que 'android:debuggable' esté en 'false' en el archivo AndroidManifest.xml para todas las compilaciones de producción.",
                "cra_articles": ["Annex I (1)(h)"]
            }
        ]
    }
    with open(scan_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        
    # 3. PDF file
    with open(scan_dir / "report.pdf", "wb") as f:
        f.write(MINIMAL_PDF)
        
    print("Mock scan seeded successfully! Check the app dashboard or history.")

if __name__ == "__main__":
    main()
