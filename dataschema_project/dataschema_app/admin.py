from django.contrib import admin
from dataschema_app.models import DataSchema, DataColumn, DataSet

# Register your models here.

admin.site.register(DataSchema)
admin.site.register(DataColumn)
admin.site.register(DataSet)