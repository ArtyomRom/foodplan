from django.contrib import admin
from django.urls import path
from bot import views as bot_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', bot_views.health, name='health'),
    path('webhook/<str:token>/', bot_views.telegram_webhook, name='telegram-webhook'),
]

# Маршруты для медиа-файлов при DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    