# Usar una imagen oficial de Python como base
FROM python:3.9-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema operativo que PyMuPDF necesita
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos y luego instalarlos
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de tu aplicación al contenedor
COPY . .

# Indicar al contenedor que escuche en el puerto 8080
EXPOSE 8080

# El comando para correr tu aplicación usando Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "app:app"]