# -----------------------------------------------------------------------------
# productos/views.py
# -----------------------------------------------------------------------------
from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q, F
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import Producto, MovimientoStock
from .forms import ProductoForm, MovimientoStockForm, AjusteStockForm

# Mixin para permisos de Stock
class StockPermissionMixin(PermissionRequiredMixin):
    """
    Mixin que permite el acceso si el usuario tiene los permisos requeridos
    O si pertenece al grupo 'stock de productos'.
    """
    def has_permission(self):
        base_permission = super().has_permission()
        es_de_stock = self.request.user.groups.filter(name='stock de productos').exists()
        return base_permission or es_de_stock

# VISTAS PÚBLICAS (todos los usuarios autenticados pueden ver)
class ProductoListView(LoginRequiredMixin, ListView):
    """Muestra una lista de todos los productos."""
    model = Producto
    template_name = "productos/producto_list.html"
    context_object_name = "productos"
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        stock_bajo = self.request.GET.get('stock_bajo')
        if stock_bajo:
            queryset = queryset.filter(stock__lt=F("stock_minimo"))
        return queryset.order_by("nombre")

class ProductoDetailView(LoginRequiredMixin, DetailView):
    """Muestra los detalles de un producto específico."""
    model = Producto
    template_name = "productos/producto_detail.html"
    context_object_name = "producto"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["movimientos"] = self.object.movimientos.all()[:10]
        context["form_ajuste"] = AjusteStockForm
        return context

class StockBajoListView(LoginRequiredMixin, ListView):
    """Muestra una lista filtrada solo para productos con stock bajo."""
    model = Producto
    template_name = "productos/stock_bajo_list.html"
    context_object_name = "productos"

    def get_queryset(self):
        return Producto.objects.filter(stock__lt=F("stock_minimo")).order_by("nombre")

# VISTAS RESTRINGIDAS (solo stock de productos y Administradores)
class ProductoCreateView(LoginRequiredMixin, StockPermissionMixin, CreateView):
    """Vista para crear un nuevo producto."""
    model = Producto
    form_class = ProductoForm
    template_name = "productos/producto_form.html"
    success_url = reverse_lazy("productos:producto_list")
    permission_required = "productos.add_producto"

    def form_valid(self, form):
        response = super().form_valid(form)
        if form.cleaned_data["stock"] > 0:
            MovimientoStock.objects.create(
                producto=self.object,
                tipo="entrada",
                cantidad=form.cleaned_data["stock"],
                motivo="Stock inicial",
                fecha=timezone.now(),
                usuario=self.request.user.username if self.request.user.is_authenticated else "Sistema"
            )
        messages.success(self.request, "Producto creado exitosamente")
        return response

class ProductoUpdateView(LoginRequiredMixin, StockPermissionMixin, UpdateView):
    """Vista para actualizar un producto existente."""
    model = Producto
    template_name = "productos/producto_form.html"
    form_class = ProductoForm
    success_url = reverse_lazy("productos:producto_list")
    permission_required = "productos.change_producto"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Producto actualizado exitosamente")
        return response

class ProductoDeleteView(LoginRequiredMixin, StockPermissionMixin, DeleteView):
    """Vista para eliminar un producto."""
    model = Producto
    template_name = "productos/producto_confirm_delete.html"
    success_url = reverse_lazy("productos:producto_list")
    permission_required = "productos.delete_producto"

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Producto eliminado exitosamente")
        return super().delete(request, *args, **kwargs)

class MovimientoStockCreateView(LoginRequiredMixin, StockPermissionMixin, CreateView):
    """Vista para registrar un nuevo movimiento de stock."""
    model = MovimientoStock
    template_name = "productos/movimiento_form.html"
    form_class = MovimientoStockForm
    permission_required = "productos.add_movimientostock"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["producto"] = get_object_or_404(Producto, pk=self.kwargs["pk"])
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["producto"] = get_object_or_404(Producto, pk=self.kwargs["pk"])
        return context

    def form_valid(self, form):
        movimiento = form.save(commit=False)
        movimiento.producto = get_object_or_404(Producto, pk=self.kwargs["pk"])
        movimiento.usuario = self.request.user.username if self.request.user.is_authenticated else "Sistema"

        if movimiento.tipo == "entrada":
            movimiento.producto.stock += movimiento.cantidad
        elif movimiento.tipo == "salida":
            if movimiento.producto.stock >= movimiento.cantidad:
                movimiento.producto.stock -= movimiento.cantidad
            else:
                form.add_error("cantidad", "No hay stock suficiente")
                return self.form_invalid(form)
        
        movimiento.producto.save()
        movimiento.save()

        messages.success(self.request, f"Movimiento de stock registrado exitosamente")
        return redirect("productos:producto_detail", pk=movimiento.producto.pk)

class AjusteStockView(LoginRequiredMixin, StockPermissionMixin, FormView):
    """Vista para ajustar el stock de un producto a un valor específico."""
    form_class = AjusteStockForm
    template_name = "productos/ajuste_stock_form.html"
    permission_required = "productos.change_producto"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["producto"] = get_object_or_404(Producto, pk=self.kwargs["pk"])
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["producto"] = get_object_or_404(Producto, pk=self.kwargs["pk"])
        return context

    def form_valid(self, form):
        producto = get_object_or_404(Producto, pk=self.kwargs["pk"])
        nueva_cantidad = form.cleaned_data["cantidad"]
        motivo = form.cleaned_data["motivo"] or "Ajuste de stock"

        diferencia = nueva_cantidad - producto.stock

        if diferencia != 0:
            tipo = "entrada" if diferencia > 0 else "salida" 
            MovimientoStock.objects.create(
                producto=producto,
                tipo=tipo,
                cantidad=abs(diferencia),
                motivo=motivo,
                fecha=timezone.now(),
                usuario=self.request.user.username if self.request.user.is_authenticated else "Sistema"
            )

            producto.stock = nueva_cantidad
            producto.save()

            messages.success(self.request, f"Stock actualizado exitosamente")
        else:
            messages.info(self.request, f"El stock no ha cambiado")

        return redirect("productos:producto_detail", pk=producto.pk)