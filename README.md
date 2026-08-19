# Plataforma Web para la Gestión y Seguimiento en Tiempo Real de Ligas de Baloncesto

Trabajo de Fin de Grado (TFG).

---

## 🛠️ Stack Tecnológico
- **Backend:** Django 5.1 (Python) con arquitectura modular.
- **Tiempo Real:** Django Channels + Daphne (WebSockets).
- **Frontend:** HTML5 semántico, CSS3 moderno responsive y Vanilla JS modular.
- **Base de Datos:** SQLite (desarrollo local) / PostgreSQL (producción).
- **Testing:** Pytest, Pytest-Django, Coverage.
- **Despliegue:** Render (ASGI).

---

## 🚀 Guía de Inicio Rápido en Local

### 1. Clonar el repositorio y acceder
```bash
git clone <url-del-repositorio>
cd tfg_baloncesto
```

### 2. Crear y activar el entorno virtual
```bash
# En Windows:
python -m venv venv
.\venv\Scripts\activate

# En Linux/macOS:
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements-dev.txt
```

### 4. Configurar variables de entorno
Copiar el archivo `.env.example` a `.env`:
```bash
cp .env.example .env
```

---

## 🌿 Flujo de Trabajo en Git (GitFlow)
- `main`: Versiones estables y de producción.
- `develop`: Rama central de integración.
- `feature/<nombre>`: Ramas de funcionalidades específicas.
- Formato de commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).