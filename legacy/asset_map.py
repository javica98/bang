import os
from typing import Dict

# Ruta al folder de imágenes del paquete descargado (no copiado):
DEFAULT_IMG_DIR = r"C:\Users\Asus\Downloads\pygame_cards-0.1\pygame_cards-0.1\pygame_cards\img"


def _img(path):
    p = os.path.join(DEFAULT_IMG_DIR, path)
    return p if os.path.isfile(p) else None


BACK_IMAGE = _img("back-side.png")


def get_image_for_clase(id_clase: int) -> str:
    """Devuelve la ruta a la imagen asociada a la clase de carta.

    Actualmente devuelve la imagen de respaldo si existe, o None.
    Puedes editar este mapeo para usar imágenes específicas por clase.
    """
    # Mapeo por defecto: todas las cartas usan la misma imagen de reverso (si está disponible)
    if BACK_IMAGE:
        return BACK_IMAGE
    return None


def map_all_from_csv(csv_path: str) -> Dict[int, str]:
    """Lee `cartas.csv` y devuelve un dict {id_clase: imagen_path_or_None}.
    """
    mapping = {}
    if not os.path.isfile(csv_path):
        return mapping
    with open(csv_path, newline='', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(';')
            try:
                id_clase = int(parts[0])
            except Exception:
                continue
            mapping[id_clase] = get_image_for_clase(id_clase)
    return mapping
