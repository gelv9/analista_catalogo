# Imagen base de Python
FROM python:3.11-slim

# Instalar dependencias del sistema (Poppler para pdf2image)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiar e instalar dependencias Python primero (aprovecha caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Puerto de Streamlit
EXPOSE 8501

# Comando para arrancar la app
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
