from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.urls import reverse

class Venta(models.Model):
    CODIGO_PREFIJO = "VNT-"
    
    codigo_venta = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    
    def __str__(self):
        return f"{self.codigo_venta} - {self.cliente.nombre}"
    
    def get_absolute_url(self):
        return reverse('ventas:venta_detail', kwargs={'pk': self.pk})
    
    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha']

class ItemVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey('productos.Producto', on_delete=models.PROTECT)
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"
    
    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Item de Venta"
        verbose_name_plural = "Items de Venta"