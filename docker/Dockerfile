FROM odoo:18.0
USER root
RUN pip3 install pandas openpyxl --break-system-packages
USER odoo
EXPOSE 8069
CMD ["odoo"]
