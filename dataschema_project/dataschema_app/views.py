from celery.result import AsyncResult

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import render, redirect, reverse
from django.views.generic import ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin

from dataschema_app.models import DataSchema, DataColumn, DataSet
from dataschema_app.forms import DataSchemaForm, DataColumnFormSet
from dataschema_app.mixins import IsOwnerTestMixin
from dataschema_app.tasks import generate_dataset_task

# Create your views here.


class DataSchemaListView(LoginRequiredMixin, ListView):
    model = DataSchema
    context_object_name = 'schemas_list'
    template_name = 'dataschema_app/schema_list.html'

    def get_queryset(self):
        return DataSchema.objects.filter(user=self.request.user).order_by('-created')


class DataSchemaCreateView(LoginRequiredMixin, CreateView):
    form_class = DataSchemaForm
    template_name = 'dataschema_app/schema_form.html'
    schema = None

    def form_valid(self, form):
        column_formset = DataColumnFormSet(self.request.POST)
        if column_formset.is_valid():
            self.schema = form.save(commit=False)
            self.schema.user = self.request.user
            self.schema.save()
            commit_column_formset = column_formset.save(commit=False)
            for form in commit_column_formset:
                form.user = self.request.user
                form.data_schema = self.schema
                form.save()
            return redirect(self.get_success_url())
        else:
            return render(self.request, template_name=self.template_name, context=self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['schema_form'] = DataSchemaForm(self.request.POST)
            context['column_formset'] = DataColumnFormSet(self.request.POST)
        else:
            context['schema_form'] = DataSchemaForm()
            context['column_formset'] = DataColumnFormSet()
        return context

    def get_success_url(self):
        return reverse('schema-dataset-list', kwargs={'schema_id': self.schema.id})


class DataSchemaUpdateView(LoginRequiredMixin, IsOwnerTestMixin, UpdateView):
    pass


class DataSchemaDeleteView(LoginRequiredMixin, IsOwnerTestMixin, DeleteView):
    pass


class DataSetListView(LoginRequiredMixin, ListView):
    model = DataSet
    context_object_name = 'dataset_list'
    template_name = 'dataschema_app/dataset_list.html'

    def get_queryset(self):
        return DataSet.objects.filter(data_schema__pk=self.kwargs['schema_id'], user=self.request.user)\
            .order_by('-created')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['schema_id'] = self.kwargs['schema_id']
        return context


@login_required
@csrf_protect
def generate_dataset(request):
    schema_id = request.POST.get('schema')
    rows = request.POST.get('rows')
    dataset = DataSet.objects.create(data_schema=DataSchema.objects.get(pk=schema_id), user=request.user)
    task = generate_dataset_task.delay(schema_id, rows, dataset.id)
    request.session['task_id'] = task.id
    request.session['dataset_id'] = dataset.id
    return redirect(reverse('schema-dataset-list', kwargs={'schema_id': schema_id}))


@login_required
@csrf_protect
def check_task_state(request):
    dataset_id = request.POST.get('dataset_id')
    task_id = request.POST.get('task_id')
    task = AsyncResult(task_id)
    if task.state == 'SUCCESS':
        dataset = DataSet.objects.get(pk=dataset_id)
        dataset.status = DataSet.READY
        dataset.save()
        del request.session['task_id']
        del request.session['dataset_id']
        return JsonResponse({'result': True})
    return JsonResponse({'result': False})

