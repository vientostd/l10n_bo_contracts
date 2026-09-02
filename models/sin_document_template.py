from odoo import fields, models


class SinDocumentTemplate(models.Model):
    _name = 'sin.document.template'
    _description = 'Plantilla de Contrato / Certificado de Garantía'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    doc_type = fields.Selection([
        ('contract', 'Contrato'),
        ('warranty', 'Certificado de Garantía'),
    ], string='Tipo de documento', required=True, default='contract', tracking=True)

    active = fields.Boolean(string='Activo', default=True)

    # Encabezado configurable
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        default=lambda self: self.env.company,
        required=True,
    )

    title = fields.Char(
        string='Título del documento',
        help='Ej.: "CONTRATO DE SERVICIO" o "CERTIFICADO DE GARANTÍA"',
    )

    intro_html = fields.Html(
        string='Introducción / preámbulo',
        help='Texto inicial del documento. Puede usar tokens como {company.name}, '
             '{partner.name}, {partner.vat}, {product.name}, etc.',
        default=lambda self: (
            '<p>Entre <b>{company.name}</b>, con NIT <b>{company.vat}</b>, '
            'representada legalmente por <b>{company.signature_representative}</b>, '
            'en adelante LA EMPRESA, y <b>{partner.name}</b>, '
            'con documento <b>{partner.vat}</b>, en adelante EL CLIENTE, '
            'se celebra el presente documento sujeto a las siguientes cláusulas:</p>'
        ),
    )

    body_html = fields.Html(
        string='Cuerpo / cláusulas',
        help='Cláusulas y contenido del documento. Use tokens según corresponda.',
        default=lambda self: (
            '<p><b>PRIMERA.-</b> Objeto. El presente documento regula la relación '
            'comercial entre las partes.</p>'
            '<p><b>SEGUNDA.-</b> Los productos adquiridos se detallan a continuación:'
            '<ul><li>{product_lines}</li></ul></p>'
            '<p><b>TERCERA.-</b> Aceptación. Ambas partes aceptan los términos '
            'descritos y firman en señal de conformidad.</p>'
        ),
    )

    closing_html = fields.Html(
        string='Cierre / lugar y fecha',
        help='Frase de cierre. Puede incluir {date_today}, {company.city}, etc.',
        default=lambda self: (
            '<p>Se firma en <b>{company.city}</b> a los {date_today} días del mes '
            'en curso, en dos ejemplares de igual tenor.</p>'
        ),
    )

    # Garantía (solo aplica a warranty)
    warranty_days = fields.Integer(
        string='Duración de garantía (días)',
        help='Vigencia de la garantía en días desde la fecha del documento.',
    )
    warranty_terms = fields.Html(
        string='Términos de garantía',
        help='Condiciones de cobertura de la garantía. Se incluyen en el certificado.',
        default=lambda self: (
            '<ul>'
            '<li>La garantía cubre defectos de fabricación por el periodo establecido.</li>'
            '<li>No cubre daños por mal uso, accidentes o modificaciones no autorizadas.</li>'
            '<li>La presente garantía es válida únicamente con la presentación de este '
            'certificado y la factura de compra.</li>'
            '</ul>'
        ),
    )

    # Integración con firma
    require_signature = fields.Boolean(
        string='Requiere firma electrónica', default=False,
        help='Si está activo, al generar el documento se podrá solicitar la firma '
             'del cliente mediante el panel de firma del contrato.',
    )
    sign_company = fields.Boolean(
        string='Firma de la empresa', default=True,
        help='Mostrar espacio de firma de la empresa.',
    )
    sign_client = fields.Boolean(
        string='Firma del cliente', default=True,
        help='Mostrar espacio de firma del cliente.',
    )
    sign_instruction = fields.Char(
        string='Instrucciones de firma',
        default='Firme aquí',
    )

    _sql_constraints = [
        ('name_type_uniq', 'UNIQUE(name, doc_type)',
         'Ya existe una plantilla con ese nombre para el mismo tipo de documento.'),
    ]

    def _get_available_tokens_domain(self):
        return [('doc_type', '=', self.doc_type)]
