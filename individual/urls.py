from django.urls import path

from .views import (
    import_individuals,
    download_invalid_items
)

urlpatterns = [
    path('import_individuals/', import_individuals),
    path('download_invalid_items/', download_invalid_items),
]