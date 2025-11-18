# clientes/models.py
from django.db import models
from django.db import models
from django.urls import reverse

class Cliente(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    numero_documento = models.CharField(max_length=9, unique=True, verbose_name='Numero_Documento')
    e_mail = models.EmailField(verbose_name='E-mail', blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)


    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    
    def get_absolute_url(self):
        # URL para ver el detalle de este cliente
        return reverse('clientes:cliente_detail', kwargs={'pk': self.pk})
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"
