from django.urls import path

from individual.views import import_individuals

urlpatterns = [
    path('import_individuals/', import_individuals),
]