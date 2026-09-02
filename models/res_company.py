from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sin_contract_representative = fields.Char(
        string='Representante legal (contratos)',
        help='Nombre del representante legal que firma los contratos/certificados.',
    )

    # Empresa por defecto para documentos generados
    default_contract_template_id = fields.Many2one(
        'sin.document.template',
        string='Plantilla de contrato por defecto',
        domain="[('doc_type','=','contract')]",
    )
    default_warranty_template_id = fields.Many2one(
        'sin.document.template',
        string='Plantilla de garantía por defecto',
        domain="[('doc_type','=','warranty')]",
    )

    # Configuración de generación automática
    auto_generate_contracts = fields.Boolean(
        string='Generar contratos automáticamente', default=True,
        help='Generar contratos automáticamente al confirmar ventas/POS de productos '
             'con contrato asignado.',
    )
    auto_generate_warranties = fields.Boolean(
        string='Generar certificados automáticamente', default=True,
        help='Generar certificados de garantía automáticamente al confirmar ventas/POS '
             'de productos con garantía asignada.',
    )
