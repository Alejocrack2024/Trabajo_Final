from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db.models import ProtectedError
from .models import Cliente
from .forms import ClienteForm

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

class ClienteList(LoginRequiredMixin, VendedorPermissionMixin, ListView):
    model = Cliente
    template_name = 'clientes/cliente_list.html'
    permission_required = 'clientes.view_cliente'
    paginate_by = 10

class ClienteCreate(LoginRequiredMixin, VendedorPermissionMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:cliente_list')
    permission_required = 'clientes.add_cliente'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Cliente '{self.object}' creado con éxito.")
        return response

class ClienteUpdate(LoginRequiredMixin, VendedorPermissionMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    success_url = reverse_lazy('clientes:cliente_list')
    permission_required = 'clientes.change_cliente'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Cliente '{self.object}' actualizado con éxito.")
        return response

class ClienteDelete(LoginRequiredMixin, VendedorPermissionMixin, DeleteView):
    model = Cliente
    template_name = 'clientes/cliente_confirm_delete.html'
    success_url = reverse_lazy('clientes:cliente_list')
    permission_required = 'clientes.delete_cliente'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f"Cliente '{self.object}' eliminado con éxito.")
            return response

        except ProtectedError:
            messages.error(
                request, 
                f"No se puede borrar el cliente '{self.object}' porque tiene "
                f"una o más ventas asociadas."
            )
            return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'eliminar'
        return context

class ClienteDetail(LoginRequiredMixin, VendedorPermissionMixin, DetailView):
    model = Cliente
    template_name = 'clientes/cliente_detail.html'
    permission_required = 'clientes.view_cliente'