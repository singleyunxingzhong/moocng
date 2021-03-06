# -*- coding: utf-8 -*-
from django import forms
from django.forms import ValidationError
from django.utils.translation import ugettext_lazy as _

from moocng.externalapps.models import ExternalApp
from moocng.forms import BootstrapMixin


class ExternalAppForm(forms.ModelForm, BootstrapMixin):

    error_messages = {
        'slug_edit': _("Once the slug has been set, you must contact an administrator to change it"),
        'instance_type_edit': _("Once the instance type has been set, you must contact an administrator to change it"),
        'status_in_progress': _("The external application creation task is being processed. Saving is not allowed in this status."),
        'status_tampering': _("Oops! It might seem you have tried tampering the object status..."),
    }

    status = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = ExternalApp
        fields = ('app_name', 'slug', 'visibility', 'status', 'instance_type')

    def clean_instance_type(self):
        instance_type = self.cleaned_data['instance_type']
        if self.instance.id:
            externalapp = ExternalApp.objects.get(pk=self.instance.id)
            if instance_type and externalapp.instance_type != instance_type:
                raise ValidationError(self.error_messages['instance_type_edit'])
        return instance_type

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if self.instance.id:
            externalapp = ExternalApp.objects.get(pk=self.instance.id)
            if slug and externalapp.slug != slug:
                raise ValidationError(self.error_messages['slug_edit'])
        return slug

    def clean(self):
        cleaned_data = super(ExternalAppForm, self).clean()
        status = int(cleaned_data.get('status'))
        if self.instance.id:
            externalapp = ExternalApp.objects.get(pk=self.instance.id)
            if status == externalapp.status:
                if status == ExternalApp.IN_PROGRESS:
                    raise ValidationError(self.error_messages['status_in_progress'])
            else:
                raise ValidationError(self.error_messages['status_tampering'])
        return self.cleaned_data
