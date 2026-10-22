"""Root URL configuration - mounts all API, admin, CMS, and docs routes."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Django Admin (unfold-themed)
    path('admin/', admin.site.urls),

    # Wagtail CMS admin
    path('cms/', include('wagtail.admin.urls')),
    path('documents/', include('wagtail.documents.urls')),
    path('pages/', include('wagtail.urls')),

    # API v1
    path('api/v1/', include('pepoltek.api_router')),

    # OpenAPI schema & Swagger (staff-only, enforced in spectacular settings)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Allauth (OAuth callbacks)
    path('accounts/', include('allauth.urls')),
]

# Serve static/media in development
if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
