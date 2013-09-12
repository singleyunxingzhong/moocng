# -*- coding: utf-8 -*-
from django.conf import settings
from django.utils import six


DEFAULT_NAMES = ('name', 'description', 'instances')


class ExternalAppOption(object):
    def __init__(self, meta):
        self.meta = meta

    def contribute_to_class(self, cls, name):
        cls._meta = self
        self.original_attrs = {}
        if self.meta:
            meta_attrs = self.meta.__dict__.copy()
            for name in self.meta.__dict__:
                # Ignore any private attributes that Django doesn't care about.
                # NOTE: We can't modify a dictionary's contents while looping
                # over it, so we loop over the *original* dictionary instead.
                if name.startswith('_'):
                    del meta_attrs[name]
            for attr_name in DEFAULT_NAMES:
                if attr_name in meta_attrs:
                    setattr(self, attr_name, meta_attrs.pop(attr_name))
                    self.original_attrs[attr_name] = getattr(self, attr_name)
                elif hasattr(self.meta, attr_name):
                    setattr(self, attr_name, getattr(self.meta, attr_name))
                    self.original_attrs[attr_name] = getattr(self, attr_name)

            # instances can be either a tuple of tuples, or a single
            # tuple of two strings. Normalize it to a tuple of tuples, so that
            # calling code can uniformly expect that.
            ins = meta_attrs.pop('instances', self.instances)
            if ins and not isinstance(ins[0], (tuple, list)):
                ins = (ins,)
            self.instances = ins

            # Any leftover attributes must be invalid.
            if meta_attrs != {}:
                raise TypeError("'class Meta' got invalid attribute(s): %s" % ','.join(meta_attrs.keys()))
        del self.meta


class ExternalAppBase(type):
    """
    Metaclass for all external apps.
    """
    def __new__(cls, name, bases, attrs):
        super_new = super(ExternalAppBase, cls).__new__

        if attrs == {}:
            return super_new(cls, name, bases, attrs)

        parents = [b for b in bases if isinstance(b, ExternalAppBase) and
                not (b.__mro__ == (b, object))]
        if not parents:
            return super_new(cls, name, bases, attrs)

        module = attrs.pop('__module__')
        new_class = super_new(cls, name, bases, {'__module__': module})
        attr_meta = attrs.pop('Meta', None)
        if not attr_meta:
            meta = getattr(new_class, 'Meta', None)
        else:
            meta = attr_meta
        kwargs = {}
        new_class.add_to_class('_meta', ExternalAppOption(meta, **kwargs))

        for obj_name, obj in attrs.items():
            new_class.add_to_class(obj_name, obj)

        return new_class

    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)

class ExternalApp(six.with_metaclass(ExternalAppBase)):

    def __init__(self, *args, **kwargs):
        if kwargs:
            for prop in list(kwargs):
                try:
                    if isinstance(getattr(self.__class__, prop), property):
                        setattr(self, prop, kwargs.pop(prop))
                except AttributeError:
                    pass
            if kwargs:
                raise TypeError("'%s' is an invalid keyword argument for this function" % list(kwargs)[0])
        super(ExternalApp, self).__init__()

    def render(self):
        raise NotImplementedError

    def create_remote_instance(self):
        raise NotImplementedError


class Askbot(ExternalApp):

    class Meta:
        name = 'askbot'
        description = 'askbot description'
        instances = settings.MOOCNG_EXTERNALAPPS['askbot']['instances']
