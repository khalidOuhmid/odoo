FROM odoo:18.0

USER root

# ============= SYSTEM DEPENDENCIES =============
# WeasyPrint requires these system libraries for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    # WeasyPrint core dependencies
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    # Font support
    fonts-liberation \
    fonts-dejavu-core \
    # PDF manipulation
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# ============= PYTHON PACKAGES =============
# Install Python dependencies for construction modules
RUN pip3 install --no-cache-dir --break-system-packages \
    # Data processing
    pandas \
    openpyxl \
    # PDF generation (construction_contract)
    weasyprint \
    PyPDF2 \
    # Templating
    Jinja2 \
    # Image processing
    Pillow

USER odoo
EXPOSE 8069
CMD ["odoo"]
