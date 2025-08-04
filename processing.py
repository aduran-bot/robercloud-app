import os
import io
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import logging
import fitz  # PyMuPDF
import base64
import requests
from datetime import datetime
import glob

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

BASE_DPI = 300

COORDINATE_MODES = {
    "negocio": {
        "Fachada del negocio": (38, 148, 300, 319),
        "Ubicación del negocio": (309, 148, 567, 319),
        "Panorámica": (38, 345, 300, 515),
        "Rótulo": (308, 346, 567, 515)
    },
    "publicidad": {
        "Foto Panorámica": (50, 148, 308, 292),
        "Ubicación de la Publicidad": (323, 148, 567, 292),
        "Foto de la Estructura": (50, 318, 308, 463),
        "Otra cara de la Publicidad": (323, 318, 567, 463)
    },
    "ambulantes": {
        "Foto de la actividad": (50, 148, 308, 292),
        "Ubicación de la Actividad": (323, 148, 567, 292)
    },
    "mupa": {
        "Fachada": (37, 190, 300, 382),
        "Rótulo": (307, 190, 570, 383)
    },
    "mercado": {
        "Fachada del módulo": (34, 152, 306, 304),
        "Lateral del módulo": (319, 152, 583, 304)
    },
    "mucho": {
        "Fachada del módulo": (37, 181, 299, 373),
        "Lateral del módulo": (307, 181, 567, 373)
    }
}

# La clase MUSAConnector y AdvancedImageProcessor no necesitan cambios, se dejan igual.
class MUSAConnector:
    # ... (Tu código de MUSAConnector aquí, no se modifica) ...
    def __init__(self):
        self.credentials = {"mupa": {"username": "snavarrosig", "password": "Entrar01"},"default": {"username": "ycardenassig", "password": "Entrar01"}}
    def set_mode(self, mode):
        pass
    def get_credentials(self):
        return "", ""
    def download_image(self, url):
        return None

class AdvancedImageProcessor:
    # ... (Tu código de AdvancedImageProcessor aquí, no se modifica) ...
    @staticmethod
    def points_to_pixels(points, dpi=BASE_DPI):
        return int(points * dpi / 72.0)
    @staticmethod
    def smart_resize_with_crop(image, target_width, target_height):
        if not image: return None
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P': image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB': image = image.convert('RGB')
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    @staticmethod
    def enhance_image_quality(image):
        return image
    @staticmethod
    def optimize_image_for_pdf(image):
        if not image: return None
        if image.mode != 'RGB': optimized = image.convert('RGB')
        else: optimized = image.copy()
        try:
            optimized = optimized.filter(ImageFilter.UnsharpMask(radius=0.5, percent=150, threshold=2))
            optimized = optimized.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(optimized)
            optimized = enhancer.enhance(1.15)
            enhancer = ImageEnhance.Brightness(optimized)
            optimized = enhancer.enhance(1.03)
            enhancer = ImageEnhance.Color(optimized)
            optimized = enhancer.enhance(1.05)
        except Exception as e:
            logging.warning(f"Error aplicando mejoras: {e}")
            optimized = image.copy() if image.mode == 'RGB' else image.convert('RGB')
        return optimized

class PDFImageExtractor:
    """Clase para extraer imágenes de PDFs renderizando la página."""

    # CORRECTO: La función ahora acepta 'stream' y 'pdf_path' opcionales.
    def _extract_images_by_coordinates(self, coords, pdf_path=None, stream=None):
        """Extrae imágenes por coordenadas desde una ruta de archivo o un stream de bytes."""
        extracted_images = []

        if not pdf_path and not stream:
            logging.error("Se debe proporcionar una ruta (pdf_path) o un stream de bytes (stream).")
            return [], False
        
        try:
            # CORRECTO: Abrimos el PDF desde el stream si existe, si no, desde la ruta.
            doc = fitz.open(stream=stream, filetype="pdf") if stream else fitz.open(pdf_path)

            if len(doc) == 0:
                logging.warning("PDF vacío")
                doc.close()
                return [], False
            
            page = doc[0]  # Primera página
            
            # Renderizar la página a imagen con alta resolución
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            width, height = img.size
            
            # Extraer cada área según las coordenadas
            for title, coord in coords.items():
                scale_factor = 2
                scaled_coord = (
                    max(0, coord[0] * scale_factor),
                    max(0, coord[1] * scale_factor),
                    min(width, coord[2] * scale_factor),
                    min(height, coord[3] * scale_factor)
                )
                
                if (scaled_coord[2] > scaled_coord[0] and scaled_coord[3] > scaled_coord[1]):
                    area_img = img.crop(scaled_coord)
                    extracted_images.append(area_img)
                else:
                    area_width = int((coord[2] - coord[0]) * scale_factor)
                    area_height = int((coord[3] - coord[1]) * scale_factor)
                    blank_img = Image.new('RGB', (area_width, area_height), color='white')
                    extracted_images.append(blank_img)
            
            logging.info(f"Extraídas {len(extracted_images)} imágenes por coordenadas")
            return extracted_images, True
            
        except Exception as e:
            logging.error(f"Error extrayendo por coordenadas: {e}")
            return [], False