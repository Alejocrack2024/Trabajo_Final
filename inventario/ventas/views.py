from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, DeleteView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.forms import inlineformset_factory
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncMonth, TruncDay, TruncYear
from datetime import datetime, timedelta
from weasyprint import HTML
import tempfile
import os

from .models import Venta, ItemVenta
from .forms import VentaForm, ItemVentaForm
from productos.models import Producto
from clientes.models import Cliente

# Mixin para permisos de Vendedor
class VendedorPermissionMixin(PermissionRequiredMixin):
    """
    Mixin que permite el acceso si el usuario tiene los permisos requeridos
    O si pertenece al grupo 'vendedor'.
    """
    def has_permission(self):
        base_permission = super().has_permission()
        es_vendedor = self.request.user.groups.filter(name='vendedor').exists()
        return base_permission or es_vendedor

# Crear el formset para los items de venta
ItemVentaFormSet = inlineformset_factory(
    Venta,
    ItemVenta,
    form=ItemVentaForm,
    extra=5,
    can_delete=True,
    fields=['producto', 'cantidad']
)

# ========== VISTAS PRINCIPALES DE VENTAS ========== #

class VentaCreateView(LoginRequiredMixin, VendedorPermissionMixin, View):
    template_name = 'ventas/venta_form.html'
    permission_required = 'ventas.add_venta'
    
    def get(self, request, *args, **kwargs):
        form = VentaForm()
        formset = ItemVentaFormSet(prefix='items')
        
        context = {
            'form': form,
            'formset': formset,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = VentaForm(request.POST)
        formset = ItemVentaFormSet(request.POST, prefix='items')

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Crear la venta
                    venta = form.save(commit=False)
                    
                    # Generar código de venta único
                    if Venta.objects.exists():
                        last_id = Venta.objects.latest('pk').pk
                    else:
                        last_id = 0
                    
                    venta.codigo_venta = f"{Venta.CODIGO_PREFIJO}{(last_id + 1):06d}"
                    venta.save()
                    
                    total_venta = 0
                    items_procesados = 0
                    
                    # Procesar cada item del formset
                    for form_item in formset:
                        if form_item.cleaned_data.get('DELETE', False):
                            continue
                            
                        producto = form_item.cleaned_data.get('producto')
                        cantidad = form_item.cleaned_data.get('cantidad')
                        
                        if not producto or not cantidad:
                            continue
                            
                        items_procesados += 1
                        
                        # Validar stock
                        if producto.stock < cantidad:
                            raise Exception(
                                f"Stock insuficiente para {producto.nombre}. "
                                f"Disponible: {producto.stock}, Solicitado: {cantidad}."
                            )
                        
                        # Calcular precios
                        precio_unitario = producto.precio
                        subtotal = precio_unitario * cantidad
                        
                        # Descontar stock del producto
                        producto.stock -= cantidad
                        producto.save()
                        
                        # Crear item de venta
                        item_venta = form_item.save(commit=False)
                        item_venta.venta = venta
                        item_venta.precio_unitario = precio_unitario
                        item_venta.subtotal = subtotal
                        item_venta.save()
                        
                        total_venta += subtotal

                    # Validar que haya al menos un item
                    if items_procesados == 0:
                        venta.delete()
                        messages.warning(request, "La venta debe contener al menos un producto.")
                        return render(request, self.template_name, {
                            'form': form, 
                            'formset': formset
                        })
                    
                    # Actualizar total de la venta
                    venta.total = total_venta
                    venta.save()
                    
                    messages.success(
                        request, 
                        f"Venta {venta.codigo_venta} registrada exitosamente. Total: ${total_venta:,.2f}"
                    )
                    return redirect('ventas:venta_list')

            except Exception as e:
                messages.error(request, f"Error al procesar la venta: {str(e)}")
        
        # Si hay errores de validación
        return render(request, self.template_name, {
            'form': form, 
            'formset': formset
        })

class VentaListView(LoginRequiredMixin, VendedorPermissionMixin, ListView):
    model = Venta
    template_name = 'ventas/venta_list.html'
    context_object_name = 'ventas'
    paginate_by = 10
    permission_required = 'ventas.view_venta'
    
    def get_queryset(self):
        queryset = Venta.objects.select_related('cliente').prefetch_related('items')
        
        # Filtro por fecha si se proporciona
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        
        if fecha_inicio:
            queryset = queryset.filter(fecha__date__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__date__lte=fecha_fin)
            
        return queryset.order_by('-fecha')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fecha_inicio'] = self.request.GET.get('fecha_inicio', '')
        context['fecha_fin'] = self.request.GET.get('fecha_fin', '')
        return context

class VentaDetailView(LoginRequiredMixin, VendedorPermissionMixin, DetailView):
    model = Venta
    template_name = 'ventas/venta_detail.html'
    context_object_name = 'venta'
    permission_required = 'ventas.view_venta'
    
    def get_queryset(self):
        return Venta.objects.select_related('cliente').prefetch_related('items__producto')

class VentaDeleteView(LoginRequiredMixin, VendedorPermissionMixin, DeleteView):
    model = Venta
    template_name = 'ventas/venta_confirm_delete.html'
    success_url = reverse_lazy('ventas:venta_list')
    permission_required = 'ventas.delete_venta'

    def form_valid(self, form):
        # Antes de eliminar, restaurar el stock de productos
        with transaction.atomic():
            venta = self.get_object()
            for item in venta.items.all():
                producto = item.producto
                producto.stock += item.cantidad
                producto.save()
            
            messages.success(self.request, f"Venta {venta.codigo_venta} eliminada y stock restaurado.")
            return super().form_valid(form)

# ========== VISTAS DE REPORTES Y ESTADÍSTICAS ========== #

class VentaReportesView(LoginRequiredMixin, VendedorPermissionMixin, TemplateView):
    """Vista para reportes y estadísticas"""
    template_name = 'ventas/venta_reportes.html'
    permission_required = 'ventas.view_venta'

def ventas_estadisticas_api(request):
    """API para obtener estadísticas de ventas"""
    if request.method == 'GET':
        try:
            # Parámetros de filtro
            dias = int(request.GET.get('dias', 30))
            fecha_limite = datetime.now() - timedelta(days=dias)
            
            # Ventas por día
            ventas_por_dia = Venta.objects.filter(
                fecha__gte=fecha_limite
            ).annotate(
                dia=TruncDay('fecha')
            ).values('dia').annotate(
                total=Sum('total'),
                cantidad=Count('id')
            ).order_by('dia')
            
            # Productos más vendidos
            productos_mas_vendidos = ItemVenta.objects.filter(
                venta__fecha__gte=fecha_limite
            ).values(
                'producto__nombre'
            ).annotate(
                total_vendido=Sum('cantidad'),
                total_ingresos=Sum('subtotal')
            ).order_by('-total_vendido')[:10]
            
            # Ventas por mes
            ventas_por_mes = Venta.objects.filter(
                fecha__gte=fecha_limite
            ).annotate(
                mes=TruncMonth('fecha')
            ).values('mes').annotate(
                total=Sum('total'),
                cantidad=Count('id')
            ).order_by('mes')
            
            # Clientes que más compran
            clientes_top = Venta.objects.filter(
                fecha__gte=fecha_limite
            ).values(
                'cliente__nombre', 'cliente__apellido'
            ).annotate(
                total_compras=Sum('total'),
                cantidad_compras=Count('id')
            ).order_by('-total_compras')[:10]
            
            # Estadísticas generales
            total_ventas = Venta.objects.aggregate(total=Sum('total'))['total'] or 0
            cantidad_ventas = Venta.objects.count()
            venta_promedio = total_ventas / cantidad_ventas if cantidad_ventas > 0 else 0
            
            # Estadísticas del período
            ventas_periodo = Venta.objects.filter(fecha__gte=fecha_limite)
            total_periodo = ventas_periodo.aggregate(total=Sum('total'))['total'] or 0
            cantidad_periodo = ventas_periodo.count()
            promedio_periodo = total_periodo / cantidad_periodo if cantidad_periodo > 0 else 0
            
            data = {
                'ventas_por_dia': list(ventas_por_dia),
                'productos_mas_vendidos': list(productos_mas_vendidos),
                'ventas_por_mes': list(ventas_por_mes),
                'clientes_top': list(clientes_top),
                'estadisticas_generales': {
                    'total_ventas': float(total_ventas),
                    'cantidad_ventas': cantidad_ventas,
                    'venta_promedio': float(venta_promedio),
                },
                'estadisticas_periodo': {
                    'total_periodo': float(total_periodo),
                    'cantidad_periodo': cantidad_periodo,
                    'promedio_periodo': float(promedio_periodo),
                }
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

def ventas_datos_filtrados(request):
    """API para datos filtrados por fecha"""
    if request.method == 'GET':
        try:
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')
            
            ventas = Venta.objects.all()
            
            if fecha_inicio:
                ventas = ventas.filter(fecha__date__gte=fecha_inicio)
            if fecha_fin:
                ventas = ventas.filter(fecha__date__lte=fecha_fin)
            
            # Calcular estadísticas filtradas
            total_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
            cantidad_ventas = ventas.count()
            venta_promedio = total_ventas / cantidad_ventas if cantidad_ventas > 0 else 0
            
            # Ventas por día filtradas
            ventas_por_dia = ventas.annotate(
                dia=TruncDay('fecha')
            ).values('dia').annotate(
                total=Sum('total'),
                cantidad=Count('id')
            ).order_by('dia')
            
            # Productos más vendidos en el período
            productos_periodo = ItemVenta.objects.filter(
                venta__in=ventas
            ).values(
                'producto__nombre'
            ).annotate(
                total_vendido=Sum('cantidad'),
                total_ingresos=Sum('subtotal')
            ).order_by('-total_vendido')[:10]
            
            data = {
                'estadisticas_generales': {
                    'total_ventas': float(total_ventas),
                    'cantidad_ventas': cantidad_ventas,
                    'venta_promedio': float(venta_promedio),
                },
                'ventas_por_dia': list(ventas_por_dia),
                'productos_periodo': list(productos_periodo),
            }
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# ========== VISTAS DE PDF Y FACTURAS CON WEASYPRINT ========== #

def generar_pdf_factura(request, pk):
    """Generar PDF de factura para una venta usando WeasyPrint"""
    try:
        venta = get_object_or_404(
            Venta.objects.select_related('cliente').prefetch_related('items__producto'), 
            pk=pk
        )
        
        # Datos de empresa (personalizables)
        empresa = {
            'nombre': 'Mi Empresa S.A.',
            'direccion': 'Calle Principal 123, Ciudad',
            'telefono': '+54 11 1234-5678',
            'email': 'info@miempresa.com',
            'cuit': '30-12345678-9',
            'iva': 'Responsable Inscripto',
        }
        
        context = {
            'venta': venta,
            'empresa': empresa,
        }
        
        # Renderizar template HTML
        html_string = render_to_string('ventas/factura_pdf.html', context, request=request)
        
        # Generar PDF con WeasyPrint
        html = HTML(string=html_string, base_url=request.build_absolute_uri())
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            html.write_pdf(tmp_file.name)
            
            # Leer el archivo PDF generado
            with open(tmp_file.name, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Eliminar el archivo temporal
            os.unlink(tmp_file.name)
        
        # Crear respuesta HTTP
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"factura_{venta.codigo_venta}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f"Error al generar PDF: {str(e)}")
        return redirect('ventas:venta_detail', pk=pk)

def factura_html(request, pk):
    """Vista para previsualizar la factura en HTML"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente').prefetch_related('items__producto'), 
        pk=pk
    )
    
    # Datos de empresa (personalizables)
    empresa = {
        'nombre': 'Mi Empresa S.A.',
        'direccion': 'Calle Principal 123, Ciudad',
        'telefono': '+54 11 1234-5678',
        'email': 'info@miempresa.com',
        'cuit': '30-12345678-9',
        'iva': 'Responsable Inscripto',
    }
    
    context = {
        'venta': venta,
        'empresa': empresa,
    }
    
    return render(request, 'ventas/factura_pdf.html', context)

# ========== VISTAS ADICIONALES ========== #

class DashboardView(LoginRequiredMixin, VendedorPermissionMixin, TemplateView):
    """Vista del dashboard principal"""
    template_name = 'ventas/dashboard.html'
    permission_required = 'ventas.view_venta'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas rápidas
        hoy = datetime.now().date()
        inicio_mes = hoy.replace(day=1)
        
        # Ventas del día
        ventas_hoy = Venta.objects.filter(fecha__date=hoy)
        context['ventas_hoy_count'] = ventas_hoy.count()
        context['ventas_hoy_total'] = ventas_hoy.aggregate(total=Sum('total'))['total'] or 0
        
        # Ventas del mes
        ventas_mes = Venta.objects.filter(fecha__date__gte=inicio_mes)
        context['ventas_mes_count'] = ventas_mes.count()
        context['ventas_mes_total'] = ventas_mes.aggregate(total=Sum('total'))['total'] or 0
        
        # Productos con stock bajo
        context['stock_bajo'] = Producto.objects.filter(stock__lt=10)[:5]
        
        # Últimas ventas
        context['ultimas_ventas'] = Venta.objects.select_related('cliente').order_by('-fecha')[:5]
        
        return context