from dataclasses import dataclass


@dataclass
class Product:
    codigo: str
    nombre: str
    categoria: str
    marca: str
    precio: float
    stock: int
    imagen: str = ""
    descripcion: str = ""
    