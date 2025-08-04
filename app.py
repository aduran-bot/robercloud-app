import os
import io
from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
import logging
import fitz  # PyMuPDF

# Importar la lógica principal de tu aplicación.
from core_logic.processing import PDFImageExtractor, AdvancedImageProcessor, COORDINATE_MODES

# Configuración de la aplicación Flask
app = Flask(__name__)
# Ya no necesitamos la carpeta de subidas, la quitamos
# app.config['UPLOAD_FOLDER'] = 'uploads' 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max

# Instancias de las clases de procesamiento
pdf_extractor = PDFImageExtractor()
processor = AdvancedImageProcessor()

# Ruta para la página principal (formulario de subida)
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para manejar el procesamiento del PDF
@app.route('/process', methods=['POST'])
def process_pdf():
    # 1. Obtener el archivo subido
    if 'pdf_file' not in request.files:
        return "No se encontró el archivo PDF", 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return "No se seleccionó ningún archivo", 400
    
    if file:
        filename_safe = secure_filename(file.filename)
        try:
            # CORRECTO: Leemos el archivo directamente en memoria, no lo guardamos en disco.
            pdf_in_memory = file.read()

            # 2. Obtener el modo y el municipio del formulario
            municipio = request.form.get('municipio', 'MUSA')
            mode_key = request.form.get('mode', 'negocio')
            
            # Lógica para mapear modo y municipio a la clave de coordenadas
            current_mode = mode_key
            if municipio == "MUPA":
                current_mode = "mercado" if mode_key == "mercado" else "mupa"
            elif municipio == "MUCHO":
                current_mode = "mucho"

            logging.info(f"Processing '{filename_safe}' in mode '{current_mode}'")

            # 3. Extraer imágenes del PDF desde la memoria
            coords = COORDINATE_MODES.get(current_mode, COORDINATE_MODES["negocio"])
            # CORRECTO: Pasamos el 'stream' de bytes a la función
            extracted_images, success = pdf_extractor._extract_images_by_coordinates(coords=coords, stream=pdf_in_memory)

            if not success or not extracted_images:
                return "Error: no se pudieron extraer imágenes del PDF. Por favor, asegúrese de que el PDF contiene imágenes válidas en las posiciones esperadas.", 400

            # 4. Crear un nuevo PDF en memoria
            output_pdf_stream = io.BytesIO()
            new_doc = fitz.open()
            new_doc_page = new_doc.new_page(width=fitz.paper_size("A4")[0], height=fitz.paper_size("A4")[1])

            # 5. Insertar imágenes procesadas
            for title, img in zip(coords.keys(), extracted_images):
                if img:
                    coord = coords[title]
                    # Aquí el código de procesamiento de imágenes sigue igual
                    target_width = processor.points_to_pixels(coord[2] - coord[0])
                    target_height = processor.points_to_pixels(coord[3] - coord[1])
                    processed_image = processor.smart_resize_with_crop(img, target_width, target_height)
                    processed_image = processor.optimize_image_for_pdf(processed_image)
                    img_bytes = io.BytesIO()
                    processed_image.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    img_rect = fitz.Rect(coord[0], coord[1], coord[2], coord[3])
                    new_doc_page.insert_image(img_rect, stream=img_bytes.getvalue())
            
            # 6. Guardar el nuevo PDF en el stream y enviarlo al usuario
            new_doc.save(output_pdf_stream)
            new_doc.close()
            output_pdf_stream.seek(0)

            # CORRECTO: Ya no hay que borrar ningún archivo con os.remove()
            
            return send_file(
                output_pdf_stream,
                as_attachment=True,
                download_name=f'processed_{filename_safe}',
                mimetype='application/pdf'
            )
        
        except fitz.FileDataError:
            logging.error(f"Error: Archivo PDF corrupto o no válido: {filename_safe}")
            return "Error: El archivo subido no es un PDF válido o está corrupto. Por favor, suba otro archivo.", 400
        except Exception as e:
            logging.error(f"Error durante el procesamiento: {e}")
            return f"Error interno del servidor. Por favor, inténtelo de nuevo.", 500