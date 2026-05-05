from django.urls import path

from . import views

app_name = "repository"

urlpatterns = [
    path("healthz/", views.healthcheck, name="healthcheck"),
    path("", views.project_list, name="project_list"),
    path("painel/", views.dashboard, name="dashboard"),
    path("usuario/recuperar/", views.username_reminder, name="username_reminder"),
    path("usuario/recuperar/enviado/", views.username_reminder_done, name="username_reminder_done"),
    path("projetos/novo/", views.project_create, name="project_create"),
    path("projetos/<slug:slug>/", views.project_detail, name="project_detail"),
    path("projetos/<slug:slug>/editar/", views.project_edit, name="project_edit"),
    path("projetos/<slug:slug>/arquivos/novo/", views.project_file_upload, name="project_file_upload"),
    path("projetos/<slug:slug>/equipe/novo/", views.project_member_add, name="project_member_add"),
    path("projetos/<slug:slug>/equipe/<int:pk>/remover/", views.project_member_delete, name="project_member_delete"),
    path("projetos/<slug:slug>/galeria/upload/", views.project_image_upload, name="project_image_upload"),
    path("projetos/<slug:slug>/galeria/<int:pk>/excluir/", views.project_image_delete, name="project_image_delete"),
    path("arquivos/<int:pk>/editar/", views.project_file_edit, name="project_file_edit"),
    path("arquivos/<int:pk>/excluir/", views.project_file_delete, name="project_file_delete"),
    path("arquivos/<int:pk>/baixar/", views.project_file_download, name="project_file_download"),
    path("opcoes/", views.options_list, name="options_list"),
    path("opcoes/<str:kind>/<int:pk>/editar/", views.option_edit, name="option_edit"),
    path("opcoes/<str:kind>/<int:pk>/excluir/", views.option_delete, name="option_delete"),
    path("pessoas/", views.people_list, name="people_list"),
    path("pessoas/nova/", views.person_create, name="person_create"),
    path("pessoas/<int:pk>/editar/", views.person_edit, name="person_edit"),
    path("usuarios/", views.users_list, name="users_list"),
    path("usuarios/novo/", views.user_create, name="user_create"),
    path("usuarios/ativar/<path:token>/", views.user_activate, name="user_activate"),
    path("usuarios/<int:pk>/", views.user_detail, name="user_detail"),
    path("usuarios/<int:pk>/editar/", views.user_edit, name="user_edit"),
    path("usuarios/<int:pk>/excluir/", views.user_delete, name="user_delete"),
]
