from django.db import migrations


def clear_admin_avatar(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    # Limpiar avatar de usuarios admin o con rutas inválidas
    Profile.objects.filter(user__username="admin").update(avatar="")


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_customuser_role"),
    ]

    operations = [
        migrations.RunPython(clear_admin_avatar, reverse_func),
    ]
