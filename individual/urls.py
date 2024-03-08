from django.urls import path

from .views import (
    import_individuals,
    download_invalid_items,
    download_individual_upload
)

urlpatterns = [
    path('import_individuals/', import_individuals),
    path('download_invalid_items/', download_invalid_items),
    path('download_individual_upload_file/', download_individual_upload),
]
