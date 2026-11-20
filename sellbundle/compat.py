"""
Python 3.14 Compatibility Patch for Django's Template Context Engine.

In Python 3.14, `copy(super())` inside `django.template.context.BaseContext.__copy__`
raises:
    AttributeError: 'super' object has no attribute 'dicts' and no __dict__ for setting new attributes

This patch safely replaces `BaseContext.__copy__` with the standard copy mechanism
used in modern Django releases so that Django admin template rendering runs smoothly.
"""

from copy import copy
import django.template.context as context_mod


def patch_template_context():
    def _basecontext_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__ = copy(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    context_mod.BaseContext.__copy__ = _basecontext_copy


patch_template_context()
