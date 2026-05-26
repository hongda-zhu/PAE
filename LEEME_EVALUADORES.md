# Guía de Evaluación del Prototipo IKUSA -- Compliance Scanner

Este documento está diseñado para los evaluadores del proyecto **IKUSA**. Dado que el prototipo requiere una infraestructura técnica local compleja (Docker, Ollama con modelos de IA de 5 GB, base de datos local y dependencias de análisis estático SAST), hemos preparado esta guía visual interactiva para facilitar la evaluación rápida de la aplicación.

---

## 📂 Contenido de la Entrega

Para evaluar el proyecto sin necesidad de instalar dependencias, por favor revise los siguientes recursos incluidos en esta carpeta:

1. **🌐 Demostración Web Interactiva (`demostracion_interactiva.html`)**: Una recreación 100% funcional y cliente-side de la aplicación web que corre **directamente en cualquier navegador sin necesidad de levantar ningún servidor**. Permite arrastrar un APK de prueba, hacer clic en "Analizar APK", ver la animación del pipeline de análisis y explorar los resultados dinámicos e historial.
2. **📱 APK de Prueba (`InsecureBankv2_prueba.apk`)**: Una aplicación Android real y vulnerable de código abierto (InsecureBankv2). Se proporciona para que los evaluadores puedan arrastrarla y soltarla directamente en el dropzone de la demostración interactiva (o subirla en la ejecución Docker real).
3. **🎥 Video Demostrativo (`videos/ikusa_demo.webm`)**: Un walkthrough continuo que muestra la interfaz real de la aplicación web, el proceso de carga de un APK, el progreso de análisis, el reporte de hallazgos interactivo, el flujo de Stripe Checkout simulado y el historial.
4. **📄 Reporte de Cumplimiento de Ejemplo (`reporte_ejemplo_compliance.html`)**: El archivo de reporte final interactivo que genera IKUSA para los APKs analizados (puede abrirse haciendo doble clic en cualquier navegador).
5. **📊 Código Fuente (`src/` / `Makefile` / `README.md`)**: El código fuente completo para inspección técnica.

---

## 🎥 Resumen del Video Demostrativo (`ikusa_demo.webm`)

El video de demostración interactivo dura aproximadamente 55 segundos y muestra:

* **0:00 - 0:08**: Carga de la aplicación web principal y selección del plan de cumplimiento **"Compliance PDF"**.
* **0:08 - 0:25**: Subida mediante *drag-and-drop* del archivo APK (`InsecureBankv2.apk`) y visualización del pipeline de progreso real (Decompilación con MobSF, Análisis SAST, Triage mediante Inteligencia Artificial local, Generación de PDF).
* **0:25 - 0:40**: Carga interactiva de la pantalla de **Resultados**:
  * Puntuación **CRA Readiness Score** (`78/100`).
  * Desglose por categorías OWASP MASVS (Criptografía, Red, Almacenamiento, Plataforma).
  * Filtrado dinámico de hallazgos por severidad (**Alto**, **Medio** y **Todos**).
* **0:40 - 0:48**: Consulta e inspección del **Historial** de análisis anteriores.
* **0:48 - 0:52**: Visualización del panel de **Documentación** técnica para la integración web, CLI y MCP (Model Context Protocol para asistentes de IA).
* **0:52 - 0:55**: Simulación interactiva de comandos en terminal mediante `ikusa-cli` y arranque del servidor de herramientas.

---

## 📄 El Reporte de Cumplimiento (MASVS / CRA)

El valor principal de IKUSA es traducir vulnerabilidades técnicas de seguridad móvil (OWASP MASVS) en artículos legales de cumplimiento para la nueva normativa europea **Cyber Resilience Act (CRA - Reglamento 2024/2847)** de forma automatizada mediante LLMs.

En el archivo adjunto `reporte_ejemplo_compliance.html` se puede observar cómo se estructura el informe entregado al cliente:
* **Mapeo Regulatorio**: Relación directa entre vulnerabilidades técnicas (por ejemplo, *uso de HTTP no seguro*) y los artículos legales infringidos (*Annex I (1)(f) - Secure network communication*).
* **Guías de Mitigación**: Explicaciones sencillas de los riesgos y cómo remediarlos a nivel de código para personal no técnico.

---

## 🚀 Ejecución Completa con Docker (Opcional)

Si desea probar el prototipo real ejecutándolo de forma local en su ordenador, ahora todo el stack tecnológico está unificado mediante Docker. Solo se requiere tener instalado **Docker** (con Docker Compose):

**Forma rápida (un solo comando):**

```bash
make demo
```

Esto copia `.env.demo` a `.env` (si no existe), construye la imagen,
arranca los tres servicios con healthchecks (MobSF + Ollama + app),
descarga el modelo LLM en su primer arranque y deja la app en
[http://localhost:9787](http://localhost:9787). Para parar: `make demo-down`.

**Forma manual (equivalente, paso a paso):**

1. **Configurar variables de entorno** (el `.env.demo` trae un
   `MOBSF_API_KEY` fijo que MobSF inyecta como env, evitando el típico
   error 401 tras reiniciar el contenedor):
   ```bash
   cp .env.demo .env
   ```
2. **Iniciar todo el sistema**:
   ```bash
   docker compose up --build -d
   ```
   *Esto compilará y levantará la aplicación web de IKUSA (puerto `9787`), MobSF (puerto `8000`) y Ollama (puerto `11434`).*
3. **Descargar el modelo LLM local** (necesario en el primer arranque para el análisis de IA):
   ```bash
   docker exec ikusa-ollama ollama pull qwen2.5:7b
   ```
4. **Acceder a la aplicación**: Abra [http://localhost:9787](http://localhost:9787) en su navegador.

