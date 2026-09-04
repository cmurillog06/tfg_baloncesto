# 🏀 Quinto Cuarto — Plataforma Integral de Baloncesto en Tiempo Real

> **Trabajo de Fin de Grado (TFG)**  
> Plataforma web para la gestión federativa, control arbitral de mesa, retransmisión interactiva mediante WebSockets y analítica avanzada de competiciones de baloncesto (Liga Endesa ACB y EuroLeague Basketball).

---

## 📋 Tabla de Contenidos
1. [Requisitos Previos](#-requisitos-previos)
2. [Guía de Instalación y Puesta en Marcha Paso a Paso](#-guía-de-instalación-y-puesta-en-marcha-paso-a-paso)
   - [Paso 1: Descargar / Clonar el proyecto](#paso-1-descargar--clonar-el-proyecto)
   - [Paso 2: Abrir la terminal en la carpeta](#paso-2-abrir-la-terminal-en-la-carpeta-del-proyecto)
   - [Paso 3: Crear el entorno virtual](#paso-3-crear-el-entorno-virtual-de-python)
   - [Paso 4: Activar el entorno virtual](#paso-4-activar-el-entorno-virtual)
   - [Paso 5: Instalar las dependencias](#paso-5-instalar-las-librerías-necesarias)
   - [Paso 6: Configurar las variables de entorno](#paso-6-crear-el-archivo-de-configuración-env)
   - [Paso 7: Inicializar la base de datos](#paso-7-crear-las-tablas-e-inicializar-los-datos-automáticamente)
   - [Paso 8: Iniciar el servidor web](#paso-8-iniciar-el-servidor-web-local)
   - [Paso 9: Ver la aplicación en el navegador](#paso-9-abrir-la-web-en-el-navegador)
3. [Credenciales y Cuentas de Acceso de Prueba](#-cuentas-y-credenciales-de-prueba-para-evaluación)
4. [Cómo Probar las Funcionalidades Clave en una Demostración](#-guía-de-demostración-de-funcionalidades)
5. [Estructura del Proyecto](#-estructura-del-código)
6. [Solución de Problemas Frecuentes](#-solución-de-problemas-frecuentes-faq)

---

## 💻 Requisitos Previos

Antes de empezar, asegúrate de tener instalado en tu ordenador:
- **Python 3.11 o superior** (Descargar desde [python.org](https://www.python.org/downloads/)).  
  *(En Windows, asegúrate de marcar la casilla **"Add Python to PATH"** durante la instalación).*
- **Git** (Descargar desde [git-scm.com](https://git-scm.com/)).
- Cualquier navegador web moderno (Google Chrome, Firefox, Edge, Safari, Brave).

---

## 🚀 Guía de Instalación y Puesta en Marcha Paso a Paso

Sigue estos pasos en orden para poner la aplicación en funcionamiento en menos de 3 minutos:

### Paso 1: Descargar / Clonar el proyecto
Si utilizas Git:
```bash
git clone https://github.com/cmurillog06/tfg_baloncesto.git
cd tfg_baloncesto
```
*(Si has recibido el proyecto en un archivo comprimido `.zip`, simplemente descomprímelo en tu carpeta de preferencia y entra en dicha carpeta).*

---

### Paso 2: Abrir la terminal en la carpeta del proyecto
- **En Windows:** Abre la carpeta descomprimida en el Explorador de Archivos, haz clic derecho y selecciona **"Abrir en Terminal"** (o escribe `powershell` o `cmd` en la barra de direcciones superior).
- **En macOS:** Abre la app **Terminal** y escribe `cd ` seguido de arrastrar la carpeta a la ventana del terminal.
- **En Linux:** Abre una terminal en el directorio del proyecto.

---

### Paso 3: Crear el entorno virtual de Python
El entorno virtual aísla las librerías del proyecto para que no interfieran con otros programas:

- **En Windows:**
  ```bash
  python -m venv venv
  ```
- **En macOS / Linux:**
  ```bash
  python3 -m venv venv
  ```

---

### Paso 4: Activar el entorno virtual

- **En Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  *(Nota: Si PowerShell te muestra un aviso de directiva de ejecución restringida, ejecuta primero `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` y vuelve a probar).*

- **En Windows (Símbolo del sistema / CMD):**
  ```cmd
  venv\Scripts\activate.bat
  ```

- **En macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

> 💡 **¿Cómo saber si está activo?** Verás el prefijo `(venv)` a la izquierda de la línea de comandos en tu terminal.

---

### Paso 5: Instalar las librerías necesarias
Con el entorno virtual activo `(venv)`, instala todas las dependencias del proyecto ejecutando:

```bash
pip install -r requirements.txt
```

---

### Paso 6: Crear el archivo de configuración `.env`
El proyecto incluye una plantilla lista para usar `.env.example`. Crea tu archivo `.env` copiándola:

- **En Windows (PowerShell / CMD):**
  ```bash
  copy .env.example .env
  ```
- **En macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

*(Por defecto, ya viene configurado con la clave secreta y SQLite para funcionar inmediatamente sin configurar bases de datos externas).*

---

### Paso 7: Crear las tablas e inicializar los datos automáticamente
Hemos creado un comando maestro (`seed_all`) que prepara toda la base de datos de una sola vez:

1. **Crear las tablas de la base de datos:**
   ```bash
   python manage.py migrate
   ```

2. **Cargar todos los datos demostrativos (clubes, ligas, 80 jugadores con fotos reales HD, escudos 1:1, partidos, actas y usuarios):**
   ```bash
   python manage.py seed_all
   ```

---

### Paso 8: Iniciar el servidor web local
Ejecuta el servidor de desarrollo:

```bash
python manage.py runserver
```

---

### Paso 9: Abrir la web en el navegador
Abre tu navegador de internet favorito y accede a la siguiente dirección:

👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** (o `http://localhost:8000/`)

¡Listo! Ya puedes navegar por toda la plataforma.

---

## 🔐 Cuentas y Credenciales de Prueba para Evaluación

El comando `seed_all` deja preconfigurados los siguientes usuarios listos para iniciar sesión desde el menú superior **"Iniciar Sesión"** (`/accounts/login/`):

| Rol | Usuario | Contraseña | ¿Qué permite hacer en la web? |
| :--- | :--- | :--- | :--- |
| **Mesa Arbitral** | `mesa` | `mesa1234` | **Control total del acta arbitral digital:** registrar canastas (1, 2, 3 pts), rebotes, asistencias, faltas y firmas de partidos en vivo. |
| **Administrador** | `admin` | `admin1234` | **Acceso total:** Panel de administración de Django (`/admin/`), gestión de competiciones, equipos y usuarios. |
| **Aficionado** | `aficionado` | `fan1234` | **Experiencia de espectador:** Seguimiento en directo de partidos, estadísticas individuales en tiempo real y clasificaciones. |
| **Entrenador** | `entrenador` | `coach1234` | **Gestión técnica:** Revisión de informes tácticos, box scores avanzados de plantilla y firma de acta. |

---

## 🎯 Guía de Demostración de Funcionalidades

Para evaluar la interactividad y arquitectura del proyecto de forma óptima:

### 1. Demostración de Retransmisión en Tiempo Real (WebSockets)
1. Abre **dos ventanas del navegador una al lado de la otra** (o una ventana normal y otra en modo incógnito).
2. En la **ventana izquierda**, entra como aficionado o invitado y abre el partido en directo:  
   👉 `http://127.0.0.1:8000/matches/3/live/` *(Real Madrid vs Unicaja)*.
3. En la **ventana derecha**, inicia sesión como **`mesa`** (clave `mesa1234`) y accede a la mesa arbitral del mismo partido:  
   👉 `http://127.0.0.1:8000/matches/3/scorekeeper/`.
4. Pulsa en cualquier jugador de la mesa arbitral para anotarle una canasta de 3 puntos o una falta.
5. **Comprueba el resultado:** Al instante, sin recargar la página, la ventana izquierda actualizará el marcador, el parcial, la jugada a jugada y la tabla de estadísticas con animaciones visuales fluidas.

### 2. Exploración de Competiciones y Clubes
- **Competiciones:** Accede a **Competiciones** en el menú para alternar entre **Liga Endesa ACB** y **EuroLeague Basketball**, visualizando clasificaciones calculadas automáticamente y calendarios por jornada.
- **Equipos y Plantillas:** Explora clubes como *Real Madrid, FC Barcelona, Panathinaikos, Olympiacos o AS Monaco*, con fichas técnicas completas de 80 jugadores y fotos reales HD oficiales.

### 3. Restablecer el Estado Inicial para otra Prueba
Si durante la evaluación has probado a registrar canastas o finalizar cuartos y quieres volver a dejar todos los partidos y clasificaciones en el estado limpio canónico:
- Puedes hacer clic en el botón **"Restablecer estado inicial"** situado arriba a la derecha en la lista de partidos (`/matches/`).
- O ejecutar en la terminal:
  ```bash
  python manage.py restore_canonical_data
  ```

---

## 📂 Estructura del Código

```text
tfg_baloncesto/
├── apps/
│   ├── accounts/     # Gestión de usuarios, roles (Admin, Mesa, Entrenador, Fan) y perfiles
│   ├── analytics/    # Algoritmos de valoración FIBA/ACB (PIR), estadísticas avanzadas y clasificaciones
│   ├── chat/         # Salas de debate en vivo y comunicación en tiempo real
│   ├── core/         # Landing page institucional, diseño base y navegación
│   ├── matches/      # Motor de partidos, mesa arbitral, acta digital oficial y WebSockets (Channels)
│   └── teams/        # Ligas (ACB/EuroLeague), clubes, plantillas, membresías e historial
├── config/           # Configuración centralizada de Django, rutas URL y enrutador ASGI
├── media/            # Escudos 1:1 oficiales, logotipos de ligas y fotografías HD de atletas
├── static/           # Hojas de estilo CSS3, diseño Glassmorphism, scripts JS y recursos visuales
├── templates/        # Plantillas HTML5 modulares y semánticas
├── requirements.txt  # Especificación de dependencias del proyecto
└── manage.py         # Punto de entrada de gestión de Django
```

---

## ❓ Solución de Problemas Frecuentes (FAQ)

- **¿Error `ExecutionPolicy` en PowerShell al activar el entorno?**  
  Abre PowerShell y ejecuta: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`. Luego vuelve a ejecutar `.\venv\Scripts\Activate.ps1`.
- **¿El puerto 8000 está ocupado por otro programa?**  
  Puedes iniciar el servidor en otro puerto (por ejemplo el 8080) ejecutando:  
  `python manage.py runserver 8080` y abrir `http://127.0.0.1:8080/`.
- **¿Cómo reiniciar la base de datos desde cero si toco algo por error?**  
  Borra el archivo `db.sqlite3` y vuelve a ejecutar:
  ```bash
  python manage.py migrate
  python manage.py seed_all
  ```