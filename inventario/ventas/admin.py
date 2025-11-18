from django.contrib import admin
from .models import Venta, ItemVenta

class ItemVentaInline(admin.TabularInline):
    model = ItemVenta
    extra = 0
    readonly_fields = ['precio_unitario', 'subtotal']
    can_delete = False

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ['codigo_venta', 'cliente', 'fecha', 'total']
    list_filter = ['fecha', 'cliente']
    readonly_fields = ['codigo_venta', 'total']
    inlines = [ItemVentaInline]

@admin.register(ItemVenta)
class ItemVentaAdmin(admin.ModelAdmin):
    list_display = ['venta', 'producto', 'cantidad', 'precio_unitario', 'subtotal']
    list_filter = ['venta', 'producto']
    readonly_fields = ['subtotal']