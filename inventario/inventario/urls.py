from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.contrib.auth import logout

def custom_logout(request):
    """Logout personalizado que no va al admin"""
    logout(request)
    return redirect('productos:producto_list')  # Asegúrate de que este nombre exista

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("productos.urls")),
    path('clientes/', include("clientes.urls")),
    # CORRECCIÓN: Cambia 'producto_list' por 'productos.urls'
    # Si quitas la siguiente línea, las URLs de productos no estarán en la raíz
    # path("", include("productos.urls")),
    path('ventas/', include("ventas.urls")),
    path('accounts/', include('allauth.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    path('accounts/logout/', custom_logout, name='custom_logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)