import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class Command(BaseCommand):
    help = "Comando maestro de inicialización: Puebla y armoniza toda la base de datos (equipos, ligas, plantillas, escudos, fotos reales, partidos, actas, clasificaciones y usuarios de prueba)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("🏀 INICIALIZANDO BASE DE DATOS DE QUINTO CUARTO"))
        self.stdout.write("=" * 70)

        # 1. Asegurar directorios multimedia necesarios
        for sub in ["teams", "leagues", "players", "avatars"]:
            d = os.path.join(settings.MEDIA_ROOT, sub)
            os.makedirs(d, exist_ok=True)

        # 2. Crear Usuarios de Prueba para la demostración (coincidentes con el acceso rápido de la web)
        self.stdout.write("\n👤 [1/7] Configurando usuarios y credenciales de prueba...")
        demo_users = [
            ("admin", "admin@quintocuarto.es", "Basket2026!", User.Role.ADMIN, True, True, "Carlos", "Administrador"),
            ("oficial_mesa", "mesa@quintocuarto.es", "Basket2026!", User.Role.TABLE_OFFICIAL, False, False, "Carlos", "Murillo"),
            ("coach_madrid", "coach@quintocuarto.es", "Basket2026!", User.Role.COACH, False, False, "Chus", "Mateo"),
            ("aficionado_basket", "fan@quintocuarto.es", "Basket2026!", User.Role.FAN, False, False, "Aficionado", "Basket"),
        ]

        # Limpiar usuarios temporales que no sean los oficiales de demostración
        canonical_usernames = [u[0] for u in demo_users]
        User.objects.exclude(username__in=canonical_usernames).delete()

        for username, email, password, role, is_staff, is_superuser, first_name, last_name in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "role": role,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                    "first_name": first_name,
                    "last_name": last_name,
                }
            )
            user.role = role
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.first_name = first_name
            user.last_name = last_name
            user.set_password(password)
            user.save()
            action = "creado" if created else "actualizado"
            self.stdout.write(f"   ✓ Usuario '{username}' ({user.get_role_display()} - {user.get_full_name()}) {action} - Contraseña: {password}")

        # 3. Poblar EuroLeague
        self.stdout.write("\n🌍 [2/7] Poblando Liga EuroLeague y clubes europeos...")
        call_command("seed_euroleague")

        # 4. Poblar Plantillas Oficiales (80 jugadores) y estadísticas canónicas
        self.stdout.write("\n👥 [3/7] Generando plantillas completas de 80 jugadores y estadísticas canónicas...")
        call_command("seed_full_rosters")

        # 5. Asignar Escudos Oficiales 1:1
        self.stdout.write("\n🛡️ [4/7] Asignando escudos oficiales 1:1 a todos los clubes...")
        call_command("seed_team_logos")

        # 6. Asignar Logotipos de Ligas
        self.stdout.write("\n🏆 [5/7] Asignando logotipos y emblemas de competición...")
        call_command("seed_league_logos")

        # 7. Sincronizar Partidos de Liga Endesa ACB
        self.stdout.write("\n🇪🇸 [6/7] Sincronizando partidos de Liga Endesa ACB...")
        call_command("seed_acb_matches")

        # 8. Membresías Históricas
        self.stdout.write("\n📜 [7/7] Registrando historial deportivo pasado de jugadores...")
        call_command("seed_history")

        # 9. Restaurar y verificar estado canónico final de partidos y clasificaciones
        call_command("restore_canonical_data")

        # 10. Restaurar mensajes oficiales del chat en vivo
        self.stdout.write("\n💬 Restaurando mensajes canónicos del chat en vivo...")
        from apps.chat.models import ChatMessage
        from apps.matches.models import Match
        
        ChatMessage.objects.all().delete()
        live_match = Match.objects.filter(home_team__acronym="RMB", away_team__acronym="UNI").first()
        if live_match:
            coach = User.objects.filter(username="coach_madrid").first()
            admin_u = User.objects.filter(username="admin").first()
            fan = User.objects.filter(username="aficionado_basket").first()
            mesa = User.objects.filter(username="oficial_mesa").first()
            
            if coach:
                ChatMessage.objects.create(match=live_match, user=coach, message="¡Vamos equipo!")
            if admin_u:
                ChatMessage.objects.create(match=live_match, user=admin_u, message="¡Gran defensa!")
            if fan:
                ChatMessage.objects.create(match=live_match, user=fan, message="¡Gran defensa! ¡Increíble jugada!")
            if mesa:
                ChatMessage.objects.create(match=live_match, user=mesa, message="¡Gran defensa!")
            if coach:
                ChatMessage.objects.create(match=live_match, user=coach, message="¡Vamos equipo!")
            self.stdout.write("   ✓ Mensajes de chat canónicos restaurados con éxito.")

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS(
                "🎉 ¡TODO EL SISTEMA HA SIDO INICIALIZADO Y SINCRONIZADO CON ÉXITO!\n"
                "Todos los datos son 100% portables y accesibles desde cualquier ordenador."
            )
        )
        self.stdout.write("=" * 70)
