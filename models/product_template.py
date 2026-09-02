from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sin_has_contract = fields.Boolean(
        string='Requiere contrato',
        help='Al vender este producto se generará un contrato automáticamente.',
    )
    sin_contract_template_id = fields.Many2one(
        'sin.document.template',
        string='Plantilla de contrato',
        domain="[('doc_type','=','contract')]",
    )

    sin_has_warranty = fields.Boolean(
        string='Certificado de garantía',
        help='Al vender este producto se generará un certificado de garantía automáticamente.',
    )
    sin_warranty_template_id = fields.Many2one(
        'sin.document.template',
        string='Plantilla de garantía',
        domain="[('doc_type','=','warranty')]",
    )

    sin_warranty_days = fields.Integer(
        string='Días de garantía',
        help='Vigencia de la garantía en días (sobreescribe la de la plantilla).',
    )
    sin_warranty_serial = fields.Boolean(
        string='Requiere nº de serie',
        help='Requerir número de serie al generar el certificado de garantía.',
    )
