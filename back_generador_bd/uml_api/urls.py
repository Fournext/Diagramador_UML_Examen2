from django.urls import path
from .views import GenerateUMLView, set_backupUML, get_backupUML


urlpatterns = [
    path('chatbot/', GenerateUMLView.as_view(), name='generate-uml'),
    path("set_backup_uml/<uuid:room_id>/", set_backupUML, name="backup_uml-id"),
    path("get_backup_uml/<uuid:room_id>/", get_backupUML, name="backup_uml-id"),
]
