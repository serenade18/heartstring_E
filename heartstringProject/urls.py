"""
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

from heartstringApp import views
from heartstringApp.views import SuperUserRegistrationView, UserAccountUpdateView, UserAccountDeleteView, \
    MyPlayListView, MyStreamListView

# from heartstringProject import settings

router = routers.DefaultRouter()
router.register("tickets", views.TicketViewSet, basename="tickets")
router.register("payments", views.PaymentViewSet, basename="payments")
router.register("plays", views.PlayViewSet, basename="plays")
router.register("videos", views.VideoViewSet, basename="videos")
router.register("play_casts", views.PlayCastViewSet, basename="play_casts")
router.register("offers", views.OffersVIewSet, basename="offers")
router.register("home_api", views.HomeApiViewSet, basename="home_api")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('auth/', include('djoser.urls.authtoken')),
    path('auth/', include('djoser.social.urls')),
    path('auth/superuser/', SuperUserRegistrationView.as_view({'post': 'create_superuser'}), name='superuser-registration'),
    path('api/update-user/', UserAccountUpdateView.as_view(), name='update-user'),
    path('api/delete-user/<int:pk>/', UserAccountDeleteView.as_view(), name='user-delete'),
    path('api/my-plays/', MyPlayListView.as_view(), name='my-plays'),
    path('api/my-stream/', MyStreamListView.as_view(), name='my-stream'),
    path('api/', include(router.urls)),
    path('api/gettoken/', TokenObtainPairView.as_view(), name="gettoken"),
    path('api/refresh_token/', TokenRefreshView.as_view(), name="refresh_token"),
]
# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
