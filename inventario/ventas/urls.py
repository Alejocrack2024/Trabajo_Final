from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    # Vistas principales
    path('', views.VentaListView.as_view(), name='venta_list'),
    path('nueva/', views.VentaCreateView.as_view(), name='venta_create'),
    path('<int:pk>/', views.VentaDetailView.as_view(), name='venta_detail'),
    path('<int:pk>/eliminar/', views.VentaDeleteView.as_view(), name='venta_delete'),
    
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Reportes y estadísticas
    path('reportes/', views.VentaReportesView.as_view(), name='venta_reportes'),
    path('estadisticas/', views.ventas_estadisticas_api, name='venta_estadisticas'),
    path('datos-filtrados/', views.ventas_datos_filtrados, name='venta_datos_filtrados'),
    
    # PDF y facturas
    path('<int:pk>/pdf/', views.generar_pdf_factura, name='venta_pdf'),
    path('<int:pk>/factura/', views.factura_html, name='venta_factura_html'),
]