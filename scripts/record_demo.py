import asyncio
import os
import shutil
import subprocess
import time
import random
import math
from pathlib import Path

# HTML Template representing a gorgeous PDF compliance report
HTML_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>IKUSA Compliance Report -- InsecureBankv2</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  body {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: #1e293b;
    background: #0f172a; /* Sleek slate-900 background to mimic premium dark mode PDF viewer */
    padding: 50px 20px;
    display: flex;
    justify-content: center;
    margin: 0;
  }
  .pdf-paper {
    background: white;
    max-width: 800px;
    width: 100%;
    box-shadow: 0 25px 60px rgba(0,0,0,0.6);
    padding: 50px;
    border-radius: 12px;
    box-sizing: border-box;
  }
  .pdf-header {
    background: linear-gradient(135deg, #1e1b4b, #312e81);
    color: white;
    padding: 24px 32px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
    border-bottom: 4px solid #6366f1;
  }
  .pdf-header .pdf-logo {
    font-family: monospace;
    font-size: 26px;
    font-weight: 800;
    letter-spacing: 2px;
  }
  .pdf-header small {
    opacity: .8;
    display: block;
    font-size: 12px;
    margin-top: 4px;
    letter-spacing: 0.5px;
  }
  .pdf-meta {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 32px;
    font-size: 14px;
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e2e8f0;
  }
  .pdf-meta dt { color: #64748b; font-weight: 500; }
  .pdf-meta dd { font-weight: 600; color: #0f172a; margin: 0; }
  
  .score-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 28px;
  }
  .score-card-title {
    font-size: 13px;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
  }
  .score-bar {
    height: 18px;
    background: #e2e8f0;
    border-radius: 9px;
    overflow: hidden;
    margin: 12px 0;
  }
  .score-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #f59e0b 0%, #10b981 100%);
    border-radius: 9px;
  }
  .score-text-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .score-status-badge {
    background: #ecfdf5;
    color: #047857;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
  }
  h4 {
    font-size: 16px;
    font-weight: 800;
    margin-top: 32px;
    margin-bottom: 16px;
    color: #1e1b4b;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .pdf-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    margin: 16px 0;
  }
  .pdf-table th {
    background: #312e81;
    color: white;
    padding: 10px 16px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .pdf-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #e2e8f0;
  }
  .pdf-table tr.alto td { background: #fef2f2; }
  .pdf-table tr.medio td { background: #fffbeb; }
  .pdf-table tr.ok td { background: #f0fdf4; }
  
  .status-pill {
    font-size: 11px;
    font-weight: 800;
    padding: 4px 8px;
    border-radius: 6px;
    text-transform: uppercase;
  }
  .status-pill.no-cumple { background: #fee2e2; color: #991b1b; }
  .status-pill.parcial { background: #fef3c7; color: #92400e; }
  .status-pill.cumple { background: #d1fae5; color: #065f46; }

  .severity-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .severity-badge.alto { background: #ef4444; color: white; }
  .severity-badge.medio { background: #f59e0b; color: white; }
  .severity-badge.bajo { background: #3b82f6; color: white; }

  .pdf-not-covered {
    font-size: 12px;
    color: #94a3b8;
    font-style: italic;
    margin: 10px 0;
  }
  .pdf-finding {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #ef4444;
    border-radius: 8px;
    padding: 18px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.02);
  }
  .pdf-finding.prio-2 { border-left-color: #f59e0b; }
  .pdf-finding.prio-3 { border-left-color: #3b82f6; }

  .pdf-finding .title {
    color: #0f172a;
    font-weight: 700;
    font-size: 15px;
    margin-bottom: 8px;
  }
  .pdf-finding .fix {
    color: #334155;
    margin-top: 8px;
    font-size: 13px;
    line-height: 1.6;
  }
  .cra-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    font-size: 14px;
    border-bottom: 1px solid #f1f5f9;
  }
  .cra-row span:first-child {
    font-weight: 500;
    color: #334155;
  }
  .disclaimer {
    background: #fef9c3;
    border-left: 4px solid #eab308;
    padding: 16px;
    font-size: 12px;
    color: #713f12;
    margin-top: 36px;
    border-radius: 6px;
    line-height: 1.5;
  }
</style>
</head>
<body>
  <div class="pdf-paper">
    <div class="pdf-header">
      <div>
        <span class="pdf-logo">IKUSA</span>
        <small>Compliance Report</small>
      </div>
      <div style="text-align:right">
        <strong>MASVS / CRA</strong>
        <small>v2.1.0 / 2024/2847</small>
      </div>
    </div>
    
    <dl class="pdf-meta">
      <dt>Aplicación:</dt><dd>InsecureBankv2</dd>
      <dt>Paquete:</dt><dd>com.android.insecurebankv2</dd>
      <dt>Fecha:</dt><dd>22/05/2026</dd>
      <dt>Tier:</dt><dd>Compliance PDF (prototype)</dd>
    </dl>
    
    <div class="score-card">
      <div class="score-card-title">CRA Readiness Score</div>
      <div class="score-bar"><div class="score-bar-fill" style="width:78%"></div></div>
      <div class="score-text-container">
        <span style="font-weight:800; font-size:18px; color:#1e1b4b;">78/100</span>
        <span class="score-status-badge">Nivel CRA Aceptable</span>
      </div>
    </div>
    
    <h4>Resumen por Categoría MASVS</h4>
    <table class="pdf-table">
      <thead>
        <tr><th>Categoría</th><th>Hallazgos</th><th>Severidad</th><th>Estado</th></tr>
      </thead>
      <tbody>
        <tr class="alto"><td>MASVS-CRYPTO</td><td>1</td><td><span class="severity-badge alto">Alto</span></td><td><span class="status-pill no-cumple">NO CUMPLE</span></td></tr>
        <tr class="alto"><td>MASVS-NETWORK</td><td>1</td><td><span class="severity-badge alto">Alto</span></td><td><span class="status-pill no-cumple">NO CUMPLE</span></td></tr>
        <tr class="medio"><td>MASVS-STORAGE</td><td>2</td><td><span class="severity-badge medio">Medio</span></td><td><span class="status-pill parcial">PARCIAL</span></td></tr>
        <tr class="medio"><td>MASVS-PLATFORM</td><td>1</td><td><span class="severity-badge bajo">Bajo</span></td><td><span class="status-pill parcial">PARCIAL</span></td></tr>
      </tbody>
    </table>
    <div class="pdf-not-covered">
      Categorías no cubiertas: MASVS-AUTH, MASVS-CODE, MASVS-RESILIENCE, MASVS-PRIVACY (Requieren análisis dinámico / runtime testing)
    </div>
    
    <h4>Hallazgos Críticos (Top 3)</h4>
    <div class="pdf-finding">
      <div class="title">1. Uso de claves criptográficas estáticas</div>
      <div class="fix"><strong>Explicación:</strong> Se identificó una clave AES fija dentro de las utilidades de criptografía de la app. Esto anula la seguridad del cifrado, ya que cualquier atacante que descompile el APK puede extraer la clave y descifrar la base de datos o comunicaciones.</div>
      <div class="fix"><strong>Remediación:</strong> Migrar al Android Keystore System para generar y almacenar claves criptográficas de forma segura protegidas por hardware en el dispositivo.</div>
    </div>
    
    <div class="pdf-finding">
      <div class="title">2. Uso de HTTP no seguro en el canal de comunicación</div>
      <div class="fix"><strong>Explicación:</strong> Las transferencias y datos bancarios se envían mediante HTTP simple sin cifrar. Cualquier tercero en la misma red Wi-Fi podría interceptar o modificar el tráfico bancario.</div>
      <div class="fix"><strong>Remediación:</strong> Habilitar la configuración de seguridad de red en el manifiesto para exigir HTTPS de forma estricta y rechazar tráfico en texto plano.</div>
    </div>
    
    <div class="pdf-finding prio-2">
      <div class="title">3. Copia de seguridad de la aplicación habilitada</div>
      <div class="fix"><strong>Explicación:</strong> Al permitir backups, cualquier persona con acceso físico al teléfono móvil y la depuración USB activa puede extraer los datos privados de la aplicación a su ordenador usando 'adb backup'.</div>
      <div class="fix"><strong>Remediación:</strong> Establecer 'android:allowBackup=false' en el archivo AndroidManifest.xml o configurar reglas detalladas de filtrado de copias de seguridad.</div>
    </div>
    
    <h4>Mapping CRA (Reglamento 2024/2847)</h4>
    <div class="cra-row"><span>Annex I (1)(f) - Secure network communication</span><span class="status-pill no-cumple">NO CUMPLE</span></div>
    <div class="cra-row"><span>Annex I (1)(h) - Secure data storage & encryption</span><span class="status-pill parcial">PARCIAL</span></div>
    <div class="cra-row"><span>Annex I (2)(a) - Secure default configuration</span><span class="status-pill no-cumple">NO CUMPLE</span></div>
    <div class="cra-row"><span>Annex I (2)(b) - Safe cryptographic key handling</span><span class="status-pill no-cumple">NO CUMPLE</span></div>
    
    <div class="disclaimer">Este informe es una simulación de cumplimiento generada por la pipeline de IKUSA. No sustituye una auditoría formal.</div>
  </div>
</body>
</html>"""

# Human mouse movement generator using Bezier curves and easing
def generate_human_path(start_x, start_y, target_x, target_y):
    dx = target_x - start_x
    dy = target_y - start_y
    dist = math.hypot(dx, dy)
    
    if dist < 10:
        return [(target_x, target_y)]
        
    # Determine step count based on distance (simulate natural speed)
    steps = int(max(20, min(50, dist / 12)))
    
    # Calculate a control point perpendicular to the midpoint to curve the path
    mid_x = (start_x + target_x) / 2
    mid_y = (start_y + target_y) / 2
    
    perp_x = -dy / dist
    perp_y = dx / dist
    
    # Curvature: up to 15% of distance, randomized direction
    curve = random.uniform(-0.15, 0.15) * dist
    ctrl_x = mid_x + perp_x * curve
    ctrl_y = mid_y + perp_y * curve
    
    # Humans slightly overshoot targets on longer sweeps and correct at the end
    overshoot_factor = random.uniform(0.02, 0.05) if dist > 120 else 0
    over_x = target_x + (dx / dist) * overshoot_factor * dist
    over_y = target_y + (dy / dist) * overshoot_factor * dist
    
    path = []
    for i in range(1, steps + 1):
        t = i / steps
        
        # Ease-in-out curve
        t_eased = t * t * (3.0 - 2.0 * t)
        
        if t < 0.85 or overshoot_factor == 0:
            # Quadratic Bezier toward target
            x = (1 - t_eased)**2 * start_x + 2 * (1 - t_eased) * t_eased * ctrl_x + t_eased**2 * target_x
            y = (1 - t_eased)**2 * start_y + 2 * (1 - t_eased) * t_eased * ctrl_y + t_eased**2 * target_y
        else:
            # Blend from overshoot point back to the actual target
            t_corr = (t - 0.85) / 0.15
            t_corr_eased = t_corr * t_corr * (3.0 - 2.0 * t_corr)
            
            x_over = (1 - t_eased)**2 * start_x + 2 * (1 - t_eased) * t_eased * ctrl_x + t_eased**2 * over_x
            y_over = (1 - t_eased)**2 * start_y + 2 * (1 - t_eased) * t_eased * ctrl_y + t_eased**2 * over_y
            
            x = x_over * (1 - t_corr_eased) + target_x * t_corr_eased
            y = y_over * (1 - t_corr_eased) + target_y * t_corr_eased
            
        # Add micro-tremors (high frequency muscle noise)
        x += random.uniform(-0.4, 0.4)
        y += random.uniform(-0.4, 0.4)
        
        path.append((x, y))
        
    path.append((target_x, target_y))
    return path

async def human_move(page, selector):
    box = await page.locator(selector).bounding_box()
    if box:
        # Get start position
        start_x = await page.evaluate("window.mouseX || 0")
        start_y = await page.evaluate("window.mouseY || 0")
        
        target_x = box["x"] + box["width"] / 2
        target_y = box["y"] + box["height"] / 2
        
        # Generate human-like curve coordinates
        path = generate_human_path(start_x, start_y, target_x, target_y)
        
        for x, y in path:
            await page.mouse.move(x, y)
            # Muscle micro-delays
            await asyncio.sleep(random.uniform(0.012, 0.018))
            
        # Sync values in page state
        await page.evaluate(f"window.mouseX = {target_x}; window.mouseY = {target_y};")

async def record_full_demo(p, filename):
    print(f"\n==> RECORDING FULL DEMO -> {filename}...")
    video_dir = Path("./tmp_videos_full")
    if video_dir.exists():
        shutil.rmtree(video_dir)
    video_dir.mkdir(exist_ok=True)
    
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=str(video_dir),
        record_video_size={"width": 1280, "height": 800}
    )
    
    # Inject standard visual cursor overlay
    await context.add_init_script("""
        window.addEventListener('DOMContentLoaded', () => {
            const cursor = document.createElement('div');
            cursor.id = 'playwright-cursor';
            cursor.style.position = 'fixed';
            cursor.style.width = '20px';
            cursor.style.height = '20px';
            cursor.style.borderRadius = '50%';
            cursor.style.backgroundColor = 'rgba(79, 70, 229, 0.7)'; // Indigo transparent
            cursor.style.border = '2px solid rgba(255, 255, 255, 0.9)';
            cursor.style.boxShadow = '0 0 10px rgba(0,0,0,0.5)';
            cursor.style.pointerEvents = 'none';
            cursor.style.zIndex = '999999';
            cursor.style.transition = 'transform 0.1s, background-color 0.1s';
            cursor.style.left = '0px';
            cursor.style.top = '0px';
            document.body.appendChild(cursor);

            window.mouseX = 0;
            window.mouseY = 0;
            
            document.addEventListener('mousemove', e => {
                window.mouseX = e.clientX;
                window.mouseY = e.clientY;
                cursor.style.left = (e.clientX - 10) + 'px';
                cursor.style.top = (e.clientY - 10) + 'px';
            });
            
            document.addEventListener('mousedown', () => {
                cursor.style.transform = 'scale(0.8)';
                cursor.style.backgroundColor = 'rgba(16, 185, 129, 0.9)'; // Green click
            });
            
            document.addEventListener('mouseup', () => {
                cursor.style.transform = 'scale(1)';
                cursor.style.backgroundColor = 'rgba(79, 70, 229, 0.7)';
            });
        });
    """)
    
    page = await context.new_page()
    
    # ----------------------------------------------------
    # PART 1: Probando el analisis APK
    # ----------------------------------------------------
    print("==> PART 1: Probando el analisis APK...")
    await page.goto("http://localhost:9787/")
    await page.wait_for_load_state("networkidle")
    
    await page.evaluate("localStorage.setItem('ikusa_api_key', 'ikusa_sk_demo')")
    await page.reload()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)
    
    # Select compliance tier card
    await human_move(page, '[data-tier="compliance"]')
    await page.click('[data-tier="compliance"]')
    await asyncio.sleep(1)
    
    # Setup scan routing
    scan_id = "ikusa_demo_compliance"
    await page.route("**/scan", lambda route: route.fulfill(
        status=200,
        json={"scan_id": scan_id, "status": "processing"}
    ))
    
    poll_count = 0
    stages = [
        {"stage": "uploaded", "message": "Recibido app.apk (12.4 MB)...", "status": "processing"},
        {"stage": "decompiling", "message": "Decompilando con MobSF...", "status": "processing"},
        {"stage": "analyzing", "message": "Analizando con SAST...", "status": "processing"},
        {"stage": "triaging", "message": "Triage cognitivo con IA...", "status": "processing"},
        {"stage": "rendering", "message": "Generando informe de compliance...", "status": "processing"},
        {"stage": "done", "message": "Listo", "status": "done"}
    ]
    
    async def handle_status_polling(route):
        nonlocal poll_count
        stage_data = stages[min(poll_count, len(stages) - 1)]
        poll_count += 1
        await route.fulfill(status=200, json={
            "scan_id": scan_id,
            "app_name": "InsecureBankv2",
            "package_name": "com.android.insecurebankv2",
            "status": stage_data["status"],
            "stage": stage_data["stage"],
            "message": stage_data["message"],
            "cra_score": 78 if stage_data["status"] == "done" else None
        })
        
    await page.route(f"**/scan/{scan_id}", handle_status_polling)
    
    findings = [
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
    
    mock_result = {
        "scan_id": scan_id,
        "app_name": "InsecureBankv2",
        "package_name": "com.android.insecurebankv2",
        "apk_hash": "a4d3f56b78e1c2d3e4f5a6b7c8d9e0f1",
        "cra_score": 78,
        "duration_seconds": 24.5,
        "categories_covered": ["MASVS-STORAGE", "MASVS-CRYPTO", "MASVS-NETWORK", "MASVS-PLATFORM"],
        "findings": findings
    }
    
    await page.route(f"**/scan/{scan_id}/result", lambda route: route.fulfill(
        status=200,
        json=mock_result
    ))
    
    await page.route(f"**/scan/{scan_id}/report", lambda route: route.fulfill(
        status=200,
        content_type="text/html",
        body=HTML_REPORT_TEMPLATE
    ))
    
    # Trigger APK scan
    print("==> Injecting file to trigger APK scan...")
    await page.locator("#fileInput").set_input_files("app.apk")
    await asyncio.sleep(1)
    
    print("==> Moving to and clicking 'Analizar APK'...")
    await human_move(page, "#analyzeBtn")
    await page.click("#analyzeBtn")
    
    # Wait for the status progress loop
    print("==> Waiting 11s for scan to complete...")
    await asyncio.sleep(11)
    
    # Results screen loaded!
    print("==> Results screen loaded.")
    await asyncio.sleep(1.5)
    
    # Click high findings tab
    print("==> Moving to and clicking 'Alto' findings tab...")
    await human_move(page, 'button:has-text("Alto")')
    await page.click('button:has-text("Alto")')
    await asyncio.sleep(1.5)
    
    # Click medium findings tab
    print("==> Moving to and clicking 'Medio' findings tab...")
    await human_move(page, 'button:has-text("Medio")')
    await page.click('button:has-text("Medio")')
    await asyncio.sleep(1.5)
    
    # Move back to all findings
    print("==> Moving to and clicking 'Todos' findings tab...")
    await human_move(page, 'button:has-text("Todos")')
    await page.click('button:has-text("Todos")')
    await asyncio.sleep(1.5)
    
    # ----------------------------------------------------
    # PART 2: Abriendo PDF
    # ----------------------------------------------------
    print("==> PART 2: Abriendo PDF...")
    # Remove target="_blank" from PDF download button so it opens on the same tab
    await page.evaluate("document.getElementById('download-pdf').removeAttribute('target')")
    
    # Move to 'Descargar PDF' and click it to open the preview report
    await human_move(page, "#download-pdf")
    await page.click("#download-pdf")
    
    # Let the viewer see the PDF report document on screen
    print("==> Showing PDF compliance report preview for 3.5s...")
    await asyncio.sleep(3.5)
    
    # Navigate back to the web application
    print("==> Navigating back to IKUSA web app...")
    await page.go_back()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)
    
    # ----------------------------------------------------
    # PART 3: Checkout
    # ----------------------------------------------------
    print("==> PART 3: Checkout...")
    # Inject API Key for free demo
    await page.evaluate("localStorage.setItem('ikusa_api_key', 'ikusa_sk_free_demo')")
    await page.reload()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)
    
    # Intercept /scan upload to return 402 Payment Required
    await page.unroute("**/scan")
    await page.route("**/scan", lambda route: route.fulfill(
        status=402,
        json={"detail": "Tier 'free' allows 3 scans/month and is exhausted. Buy credits or upgrade."}
    ))
    
    # Set input file
    print("==> Injecting file to trigger APK scan (checkout flow)...")
    await page.locator("#fileInput").set_input_files("app.apk")
    await asyncio.sleep(1)
    
    # Click analyze button
    print("==> Moving to and clicking 'Analizar APK'...")
    await human_move(page, "#analyzeBtn")
    await page.click("#analyzeBtn")
    await asyncio.sleep(1.5)
    
    # Now we should be on the Error screen showing the credit purchase options.
    print("==> Quota error screen loaded. Hovering on credit choices...")
    await human_move(page, "#buyTerminalSub")
    await asyncio.sleep(0.5)
    
    # Click on buying terminal subscription
    print("==> Clicking 'Suscripción Terminal' product...")
    await page.click("#buyTerminalSub")
    
    # Wait for navigation to checkout page
    print("==> Waiting for redirection to Stripe mock checkout page...")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1.5)
    
    # Click 'Pagar' button
    print("==> Moving to and clicking Stripe 'Pagar' button...")
    await human_move(page, "button[type=submit]")
    await page.click("button[type=submit]")
    
    # Wait for redirection back to home page
    print("==> Redirecting back to home page...")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1.5)
    
    # Hover on the updated badge to highlight it
    print("==> Hovering on updated credit badge...")
    await human_move(page, "#tierBadge")
    await asyncio.sleep(1.5)
    
    # ----------------------------------------------------
    # PART 4: Historial
    # ----------------------------------------------------
    print("==> PART 4: Historial...")
    # Swap key back to demo user to see pre-seeded history scan
    await page.evaluate("localStorage.setItem('ikusa_api_key', 'ikusa_sk_demo')")
    await page.reload()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)
    
    # Go to history
    print("==> Navigating to History...")
    await human_move(page, "#navHistory")
    await page.click("#navHistory")
    await asyncio.sleep(1.5)
    
    # Click "Ver" on first history item
    print("==> Clicking 'Ver' in the history row...")
    await human_move(page, '#history-tbody button')
    await page.click('#history-tbody button')
    await asyncio.sleep(1.5)
    
    # ----------------------------------------------------
    # PART 5: Documentacion
    # ----------------------------------------------------
    print("==> PART 5: Documentacion...")
    # Nav to documentation
    print("==> Moving to and clicking 'Documentacion'...")
    await human_move(page, "#navDocs")
    await page.click("#navDocs")
    await asyncio.sleep(2)
    
    # ----------------------------------------------------
    # PART 6: CLI / MCP
    # ----------------------------------------------------
    print("==> PART 6: CLI / MCP...")
    # Navigate to standalone terminal simulator page (PowerShell CLI style)
    print("==> Navigating to terminal.html...")
    await page.goto("http://localhost:9787/terminal.html")
    await page.wait_for_load_state("networkidle")
    
    # Play typing animations
    print("==> Playing CLI/MCP terminal animation for 18s...")
    await asyncio.sleep(18)
    
    # Finish and close
    await context.close()
    await browser.close()
    
    # Save the output file
    video_files = list(video_dir.glob("*.webm"))
    print(f"==> Found {len(video_files)} video file(s) in {video_dir}:")
    for f in video_files:
        print(f"    - {f.name}: {f.stat().st_size} bytes")
        
    if video_files:
        # If there are multiple files, let's select the largest one or see what they are.
        # But for now, we will sort them by size descending to make sure we select the largest (complete) one.
        video_files.sort(key=lambda f: f.stat().st_size, reverse=True)
        recorded_video = video_files[0]
        print(f"==> Selecting largest video file: {recorded_video.name} ({recorded_video.stat().st_size} bytes)")
        
        dest_dir = Path("C:/Users/arnau/.gemini/antigravity/brain/5c5bea94-05a0-4903-9f47-a3d32408e151")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / filename
        if dest_file.exists():
            dest_file.unlink()
        shutil.copy(recorded_video, dest_file)
        print(f"==> Saved video to: {dest_file}")

        # Also save to the project's videos directory
        project_video_dir = Path("videos")
        project_video_dir.mkdir(exist_ok=True)
        project_file = project_video_dir / filename
        if project_file.exists():
            project_file.unlink()
        shutil.copy(recorded_video, project_file)
        print(f"==> Saved video to project: {project_file}")

        shutil.rmtree(video_dir)
    else:
        print(f"==> Error: No video file was generated")

async def main():
    # Create a dummy app.apk file of 12.4 MB so it shows up beautifully in the dropzone and progress message
    print("==> Creating 12.4 MB dummy app.apk...")
    dummy_apk = Path("app.apk")
    dummy_apk.write_bytes(b"\0" * 12976128)
    
    # 1. Seed demo scan and demo keys
    print("==> Seeding demo data...")
    subprocess.run(["uv", "run", "python", "scripts/seed_demo_scan.py"])
    subprocess.run(["uv", "run", "python", "scripts/seed_demo_keys.py"])
    
    # 2. Boot FastAPI server
    print("==> Starting FastAPI Server on port 9787...")
    server_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "ikusa.api:app", "--port", "9787", "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3) # Wait for port release
    
    try:
        from playwright.async_api import async_playwright

        print("==> Starting automated browser screen recordings...")
        async with async_playwright() as p:
            # Record single full sequence video demo
            await record_full_demo(p, "ikusa_demo.webm")
            
            # Copy the single video to all other filenames to keep compatibility
            dest_dir = Path("C:/Users/arnau/.gemini/antigravity/brain/5c5bea94-05a0-4903-9f47-a3d32408e151")
            project_video_dir = Path("videos")
            
            for name in ["ikusa_demo_compliance.webm", "ikusa_demo_checkout.webm", "ikusa_demo_cli.webm"]:
                shutil.copy(dest_dir / "ikusa_demo.webm", dest_dir / name)
                shutil.copy(project_video_dir / "ikusa_demo.webm", project_video_dir / name)
                print(f"==> Copied full video to: {name}")
    finally:
        print("==> Stopping FastAPI server...")
        server_process.terminate()
        server_process.wait()
        
        # Clean up the dummy app.apk
        if dummy_apk.exists():
            dummy_apk.unlink()
            print("==> Cleaned up dummy app.apk")
            
    print("==> All recordings complete!")

if __name__ == "__main__":
    asyncio.run(main())
