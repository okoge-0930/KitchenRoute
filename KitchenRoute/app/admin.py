from django.contrib import admin
from .models import Organization, User, Recipe, Step, Progress


admin.site.register(Organization)
admin.site.register(User)
admin.site.register(Recipe)
admin.site.register(Step)
admin.site.register(Progress)