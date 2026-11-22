#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import subprocess


def ensure_local_venv():
    """
    If run outside the project virtualenv (e.g. from global Python or another env),
    automatically re-executes with the project's dedicated .venv interpreter.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    win_python = os.path.join(base_dir, '.venv', 'Scripts', 'python.exe')
    posix_python = os.path.join(base_dir, '.venv', 'bin', 'python')

    target_python = None
    if os.path.isfile(win_python):
        target_python = win_python
    elif os.path.isfile(posix_python):
        target_python = posix_python

    if target_python and os.path.normcase(sys.executable) != os.path.normcase(target_python):
        # Prevent re-exec loop
        if os.environ.get('SELLBUNDLE_VENV_ACTIVE') != '1':
            env = os.environ.copy()
            env['SELLBUNDLE_VENV_ACTIVE'] = '1'
            try:
                result = subprocess.call([target_python, os.path.abspath(__file__)] + sys.argv[1:], env=env)
                sys.exit(result)
            except Exception:
                pass


def main():
    """Run administrative tasks."""
    ensure_local_venv()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sellbundle.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
