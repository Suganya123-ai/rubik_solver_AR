"""Which trained model each app uses: models/current.json, written by the self-improving loop
(autolearn/) when a retrained model beats the one in use. {"cube": "<file in models/>", "pyra": ...}.
An environment variable (RUBIK_MODEL, PYRA_MODEL) still overrides it; a missing or broken file
means the built-in default."""
import json
import os

MODELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
POINTER = os.path.join(MODELS, 'current.json')


def current_model(kind, default):
    """Path of the model in use for `kind` ('cube' or 'pyra'); `default` is a file name in models/."""
    try:
        with open(POINTER) as fh:
            name = json.load(fh).get(kind)
        if name and os.sep not in name and os.path.exists(os.path.join(MODELS, name)):
            return os.path.join(MODELS, name)
    except (OSError, ValueError, AttributeError):
        pass
    return os.path.join(MODELS, default)


def set_current_model(kind, name):
    """Points `kind` at models/<name> (written atomically: an app starting meanwhile reads old or new)."""
    try:
        with open(POINTER) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = {}
    data[kind] = name
    tmp = POINTER + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, POINTER)
