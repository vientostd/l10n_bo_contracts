{
    'name': 'Contratos y Certificados de Garantía',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Gestión de contratos y certificados de garantía por producto, con firma electrónica',
    'description': """
Contratos y Certificados de Garantía
=====================================

Módulo para gestionar contratos y certificados de garantía vinculados a productos.

Características:
- Asignación de plantilla de contrato y/o garantía a cada producto.
- Generación automática del contrato/certificado al confirmar una orden de venta
  o un pedido del Punto de Venta (POS).
- Documentos QWeb en PDF rellenados con los datos de la empresa, del cliente y
  de los productos vendidos.
- Plantillas de documento editables (configurador visual de campos) Sin_*.
- Firma electrónica OWL integrada (dibujo, subida de archivo o nombre escrito),
  al estilo del módulo Sign de Odoo.
- Historial y estados de cada contrato/certificado.
""",
    'author': 'Desarrollo propio',
    'website': '',
    'depends': ['base', 'sale', 'point_of_sale', 'account', 'product', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/sin_contract_sequence.xml',
        'views/sin_document_template_views.xml',
        'views/sin_contract_views.xml',
        'views/sin_warranty_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/sin_menus.xml',
        'reports/sin_contract_reports.xml',
    ],
    'assets': {
        'web.assets_frontend': [],
        'web.assets_backend': [
            'l10n_bo_contracts/static/src/scss/sin_signature.scss',
            'l10n_bo_contracts/static/src/js/sin_signature.js',
            'l10n_bo_contracts/static/src/xml/sin_signature.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
