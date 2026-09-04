# 🏀 Quinto Cuarto — Plataforma Web de Baloncesto en Tiempo Real

> **Trabajo de Fin de Grado (TFG)**  
> Plataforma web para el control arbitral de mesa, retransmisión interactiva en tiempo real (WebSockets), actas digitales oficiales y analítica avanzada de competiciones de baloncesto.

---

## 💻 Requisito Único Previo
Tener instalado **Python 3.11 o superior** en el ordenador (Descargar gratis desde [python.org](https://www.python.org/downloads/)).  
*(En Windows, es importante marcar la casilla **"Add Python to PATH"** durante el instalador).*

---

## 🚀 Guía Rápida de Puesta en Marcha (Menos de 2 minutos)

Abre la terminal en la carpeta principal del proyecto y ejecuta estos comandos en orden:

### 🪟 Si usas Windows (PowerShell / Símbolo del Sistema):
```bash
# 1. Crear el entorno virtual
python -m venv venv

# 2. Activar el entorno virtual
.\venv\Scripts\activate

# 3. Instalar las librerías necesarias
pip install -r requirements.txt

# 4. Crear el archivo de configuración
copy .env.example .env

# 5. Inicializar la base de datos con todos los equipos, 80 jugadores y partidos
python manage.py migrate
python manage.py seed_all

# 6. Encender el servidor web
python manage.py runserver
```

---

### 🍏 Si usas macOS / Linux:
```bash
# 1. Crear el entorno virtual
python3 -m venv venv

# 2. Activar el entorno virtual
source venv/bin/activate

# 3. Instalar las librerías necesarias
pip install -r requirements.txt

# 4. Crear el archivo de configuración
cp .env.example .env

# 5. Inicializar la base de datos con todos los equipos, 80 jugadores y partidos
python manage.py migrate
python manage.py seed_all

# 6. Encender el servidor web
python manage.py runserver
```

---

## 🌐 Ver la Web en el Navegador

Una vez que el servidor esté encendido, abre tu navegador web y entra en:

👉 **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🔑 Cuentas y Credenciales de Acceso

En la pantalla de inicio de sesión (`/accounts/login/`) dispones de **botones de un clic** que rellenan automáticamente los datos de prueba. Si prefieres escribirlos manualmente:

| Rol | Usuario | Contraseña | Funcionalidad principal |
| :--- | :--- | :--- | :--- |
| **Mesa Arbitral** | `oficial_mesa` | `Basket2026!` | Control del acta digital: registrar puntos, faltas, cambios y firmas. |
| **Administrador** | `admin` | `Basket2026!` | Acceso al panel de administración y control total. |
| **Entrenador** | `coach_madrid` | `Basket2026!` | Informes tácticos, estadísticas avanzadas y firma de acta. |
| **Aficionado** | `aficionado_basket` | `Basket2026!` | Seguimiento en vivo del marcador, jugada a jugada y clasificaciones. |

---

## 🎯 Cómo Probar la Retransmisión en Vivo (WebSockets)

1. Abre **dos ventanas del navegador** (una normal y otra en modo incógnito).
2. En la **primera ventana**, entra como espectador al partido en directo:  
   👉 `http://127.0.0.1:8000/matches/3/live/`
3. En la **segunda ventana**, inicia sesión como `oficial_mesa` y accede a la mesa arbitral:  
   👉 `http://127.0.0.1:8000/matches/3/scorekeeper/`
4. Pulsa en cualquier jugador desde la mesa para sumar 3 puntos o una falta:  
   *Verás cómo la primera ventana se actualiza inmediatamente en tiempo real sin recargar la página.*

---

## 🔄 Reiniciar los Datos de Demostración
Si durante las pruebas quieres volver a dejar todos los marcadores y clasificaciones en su estado inicial limpio:
- Pulsa el botón **"Restablecer estado inicial"** en la lista de partidos (`/matches/`).
- O ejecuta en la terminal: `python manage.py restore_canonical_data`
