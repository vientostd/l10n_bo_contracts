from odoo import fields, models, api
from odoo.exceptions import UserError


class SinContract(models.Model):
    _name = 'sin.contract'
    _description = 'Contrato'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Nº Contrato', required=True, readonly=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('sin.contract'),
    )
    active = fields.Boolean(string='Activo', default=True)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('generated', 'Generado'),
        ('sent', 'Enviado'),
        ('signed', 'Firmado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', tracking=True, required=True)

    date = fields.Date(
        string='Fecha', default=fields.Date.context_today, required=True, tracking=True,
    )
    date_signature = fields.Datetime(string='Fecha de firma', readonly=True)

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )

    # Datos del cliente
    partner_id = fields.Many2one(
        'res.partner', string='Cliente',
        tracking=True,
        help='Cliente del contrato. Puede quedar vacío en ventas de mostrador '
             '(POS) y completarse después.',
    )
    partner_document = fields.Char(
        string='Documento del cliente',
        compute='_compute_partner_fields', store=True,
    )
    partner_address = fields.Text(
        string='Dirección del cliente',
        compute='_compute_partner_fields', store=True,
    )

    # Origen
    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', readonly=True)
    pos_order_id = fields.Many2one('pos.order', string='Pedido POS', readonly=True)

    # Plantilla y contenido
    template_id = fields.Many2one(
        'sin.document.template', string='Plantilla', required=True, tracking=True,
        domain="[('doc_type','=','contract')]",
    )
    document_title = fields.Char(string='Título del documento', readonly=True)
    intro_html = fields.Html(string='Introducción', readonly=True)
    body_html = fields.Html(string='Cuerpo', readonly=True)
    closing_html = fields.Html(string='Cierre', readonly=True)

    # Líneas de producto del contrato
    line_ids = fields.One2many(
        'sin.contract.line', 'contract_id', string='Productos', readonly=True,
    )

    # Firma
    require_signature = fields.Boolean(
        string='Requiere firma', related='template_id.require_signature', readonly=True,
    )
    sign_company = fields.Boolean(
        string='Firma empresa', related='template_id.sign_company', readonly=True,
    )
    sign_client = fields.Boolean(
        string='Firma cliente', related='template_id.sign_client', readonly=True,
    )
    sign_instruction = fields.Char(
        string='Instrucciones de firma', related='template_id.sign_instruction', readonly=True,
    )
    # true client signature image (base64)
    client_signature = fields.Binary(string='Firma del cliente', attachment=True)
    client_signature_name = fields.Char(string='Nombre del firmante', tracking=True)
    client_signature_date = fields.Datetime(string='Fecha firma cliente', readonly=True)
    # true company signature image
    company_signature = fields.Binary(string='Firma de la empresa', attachment=True)
    company_signature_name = fields.Char(string='Firmante de la empresa')
    company_signature_date = fields.Datetime(string='Fecha firma empresa', readonly=True)

    note = fields.Text(string='Notas')

    # Almacena el PDF generado (report) para adjuntarlo automáticamente
    document_pdf = fields.Binary(
        string='PDF del contrato', attachment=True, readonly=True,
        help='Documento PDF generado para el contrato.',
    )
    document_pdf_name = fields.Char(string='Nombre del PDF', readonly=True)

    @api.depends('partner_id')
    def _compute_partner_fields(self):
        for rec in self:
            partner = rec.partner_id
            sin_doc = getattr(partner, 'sin_document_number', '') or ''
            rec.partner_document = partner.vat or sin_doc or ''
            addr = partner.street or ''
            if partner.city:
                addr += (', ' if addr else '') + partner.city
            rec.partner_address = addr

    def action_generate_document(self):
        """Genera el HTML final del contrato reemplazando los tokens y guarda el PDF."""
        for rec in self:
            rec._generate_document_content()
            rec.state = 'generated'

    def _generate_document_content(self):
        self.ensure_one()
        if not self.template_id:
            raise UserError('Debe seleccionar una plantilla para el contrato.')
        line_info = self.line_ids._format_lines_for_template()
        ctx = self._build_token_context(line_info)
        self.document_title = self.template_id.title or self.template_id.doc_type
        self.intro_html = self._render_tokens(self.template_id.intro_html or '', ctx)
        self.body_html = self._render_tokens(self.template_id.body_html or '', ctx)
        self.closing_html = self._render_tokens(self.template_id.closing_html or '', ctx)
        self.document_pdf_name = '%s.pdf' % (self.name or 'contrato')

    def _build_token_context(self, line_info):
        company = self.company_id
        partner = self.partner_id
        representative = company.sin_contract_representative \
            if hasattr(company, 'sin_contract_representative') else ''
        sin_doc = partner.sin_document_number \
            if hasattr(partner, 'sin_document_number') else ''
        return {
            'company.name': company.name or '',
            'company.vat': company.vat or '',
            'company.city': company.city or '',
            'company.street': company.street or '',
            'company.phone': company.phone or '',
            'company.email': company.email or '',
            'company.signature_representative': representative or '',
            'partner.name': partner.name or '',
            'partner.vat': partner.vat or sin_doc or '',
            'partner.street': partner.street or '',
            'partner.city': partner.city or '',
            'partner.phone': partner.phone or '',
            'partner.email': partner.email or '',
            'partner_address': self.partner_address or '',
            'product_lines': line_info or '',
            'date': self.date.strftime('%d/%m/%Y') if self.date else '',
            'date_today': fields.Date.context_today(self).strftime('%d de %B de %Y'),
            'contract.name': self.name or '',
        }

    @staticmethod
    def _render_tokens(html, ctx):
        import re
        def _sub(m):
            key = m.group(1)
            return str(ctx.get(key, m.group(0)))
        return re.sub(r'\{([a-zA-Z0-9_.]+)\}', _sub, html)

    def action_send(self):
        """Marca el contrato como enviado (permite luego solicitar la firma)."""
        self.state = 'sent'

    def action_sign_client(self):
        """Confirma la firma del cliente. La imagen se guarda previamente por el
        widget OWL en `client_signature`; aquí se valida y se finaliza el estado."""
        self.ensure_one()
        if not self.client_signature:
            raise UserError('La firma del cliente está vacía. Dibuje o suba la firma antes de confirmar.')
        if not self.client_signature_name:
            self.client_signature_name = self.partner_id.name
        if not self.client_signature_date:
            self.client_signature_date = fields.Datetime.now()
        if self.sign_company:
            if self.company_signature and not self.state == 'signed':
                self.state = 'signed'
        else:
            self.state = 'signed'

    def action_sign_company(self):
        """Confirma la firma de la empresa. La imagen se guarda previamente por el
        widget OWL en `company_signature`."""
        self.ensure_one()
        if not self.company_signature:
            raise UserError('La firma de la empresa está vacía. Dibuje o suba la firma antes de confirmar.')
        if not self.company_signature_name:
            self.company_signature_name = self.company_id.sin_contract_representative \
                if hasattr(self.company_id, 'sin_contract_representative') else self.company_id.name
        if not self.company_signature_date:
            self.company_signature_date = fields.Datetime.now()
        if self.sign_client:
            if self.client_signature and not self.state == 'signed':
                self.state = 'signed'
        else:
            self.state = 'signed'

    def action_cancel(self):
        self.state = 'cancelled'

    def action_draft(self):
        self.state = 'draft'

    def action_open_report(self):
        return self.env.ref(
            'l10n_bo_contracts.report_sin_contract'
        ).report_action(self)


class SinContractLine(models.Model):
    _name = 'sin.contract.line'
    _description = 'Línea de contrato'
    _order = 'sequence, id'

    contract_id = fields.Many2one('sin.contract', string='Contrato', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    description = fields.Text(string='Descripción')
    quantity = fields.Float(string='Cantidad', default=1.0)
    price_unit = fields.Float(string='Precio unitario')
    price_subtotal = fields.Monetary(
        string='Subtotal', currency_field='currency_id', compute='_compute_amount',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', related='contract_id.company_id.currency_id',
    )

    @api.depends('quantity', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    def _format_lines_for_template(self):
        lines = []
        for line in self:
            desc = line.description or (line.product_id.name if line.product_id else '')
            lines.append(
                '<li>%s — Cantidad: %s — Precio: %s</li>' % (
                    desc,
                    line.quantity,
                    ('%0.2f' % line.price_unit) if line.price_unit else '-',
                )
            )
        return ''.join(lines) or '—'
