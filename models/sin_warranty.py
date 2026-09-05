from markupsafe import escape
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import timedelta
from .sin_docx_mixin import SinDocxMixin


class SinWarranty(SinDocxMixin, models.Model):
    _name = 'sin.warranty'
    _description = 'Certificado de Garantía'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Nº Garantía', required=True, readonly=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('sin.warranty'),
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
    date_expiry = fields.Date(string='Vence', readonly=True, tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )

    partner_id = fields.Many2one(
        'res.partner', string='Cliente',
        tracking=True,
        help='Cliente del certificado. Puede quedar vacío en ventas de mostrador '
             '(POS) y completarse después.',
    )
    partner_document = fields.Char(
        string='Documento del cliente', compute='_compute_partner_fields', store=True,
    )

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta', readonly=True)
    pos_order_id = fields.Many2one('pos.order', string='Pedido POS', readonly=True)

    template_id = fields.Many2one(
        'sin.document.template', string='Plantilla', required=True,
        domain="[('doc_type','=','warranty')]",
    )
    document_title = fields.Char(string='Título del documento', readonly=True)
    intro_html = fields.Html(string='Introducción', readonly=True)
    body_html = fields.Html(string='Cuerpo', readonly=True)
    closing_html = fields.Html(string='Cierre', readonly=True)
    warranty_terms = fields.Html(string='Términos de garantía', readonly=True)

    # Líneas (productos en garantía)
    line_ids = fields.One2many(
        'sin.warranty.line', 'warranty_id', string='Productos', readonly=True,
    )

    # Firma
    require_signature = fields.Boolean(
        string='Requiere firma', related='template_id.require_signature', readonly=True,
    )
    client_signature = fields.Binary(string='Firma del cliente', attachment=True)
    client_signature_name = fields.Char(string='Nombre del firmante', tracking=True)
    client_signature_date = fields.Datetime(string='Fecha firma cliente', readonly=True)

    note = fields.Text(string='Notas')

    # Datos técnicos del equipo amparado (paquete tecnológico)
    equipment_brand = fields.Char(string='Marca del equipo')
    equipment_model = fields.Char(string='Modelo del equipo')
    equipment_serial = fields.Char(string='Nº de serie del equipo')
    equipment_processor = fields.Char(string='Procesador')
    equipment_ram = fields.Char(string='Memoria RAM (GB)')
    equipment_storage = fields.Char(string='Almacenamiento (GB / tipo)')
    equipment_os_version = fields.Char(string='Versión del sistema operativo')
    equipment_omv_version = fields.Char(string='Versión OpenMediaVault')
    equipment_odoo_edition = fields.Selection([
        ('community', 'Community'),
        ('enterprise', 'Enterprise'),
    ], string='Edición de Odoo')

    document_pdf = fields.Binary(
        string='PDF del certificado', attachment=True, readonly=True,
    )
    document_pdf_name = fields.Char(string='Nombre del PDF', readonly=True)

    @api.depends('partner_id')
    def _compute_partner_fields(self):
        for rec in self:
            partner = rec.partner_id
            sin_doc = getattr(partner, 'sin_document_number', '') or ''
            rec.partner_document = partner.vat or sin_doc or ''

    def action_generate_document(self, skip_serial=False):
        for rec in self:
            rec._generate_document_content(skip_serial=skip_serial)
            rec.state = 'generated'

    def _get_effective_warranty_days(self):
        """Devuelve los días de garantía efectivos: los del producto (primera
        línea) si están definidos, si no los de la plantilla."""
        product = False
        for line in self.line_ids:
            product = line.product_id
            if product:
                break
        if product and product.product_tmpl_id.sin_warranty_days:
            return product.product_tmpl_id.sin_warranty_days
        return self.template_id.warranty_days or 0

    def _generate_document_content(self, skip_serial=False):
        self.ensure_one()
        if not self.template_id:
            raise UserError('Debe seleccionar una plantilla para el certificado de garantía.')
        days = self._get_effective_warranty_days()
        if days and self.date:
            self.date_expiry = self.date + timedelta(days=days)
        # Si algún producto requiere nº de serie, validarlo (solo para generación
        # manual del documento; el flujo automático de venta lo omite si falta).
        need_serial = any(
            line.product_id.product_tmpl_id.sin_warranty_serial
            for line in self.line_ids
        )
        if need_serial and not skip_serial:
            missing = [
                line.description or line.product_id.name
                for line in self.line_ids if not line.serial_number
            ]
            if missing:
                raise UserError(
                    _('El certificado de garantía requiere número de serie para: %s') %
                    ', '.join(missing)
                )
        line_info = self.line_ids._format_lines_for_template()
        ctx = self._build_token_context(line_info)
        self.document_title = self.template_id.title or self.template_id.doc_type
        self.intro_html = self._render_tokens(self.template_id.intro_html or '', ctx)
        self.body_html = self._render_tokens(self.template_id.body_html or '', ctx)
        self.closing_html = self._render_tokens(self.template_id.closing_html or '', ctx)
        self.warranty_terms = self._render_tokens(self.template_id.warranty_terms or '', ctx)
        self.document_pdf_name = '%s.pdf' % (self.name or 'garantia')
        # Si la plantilla trae un .docx, generar el PDF desde Word (prioridad)
        if self.template_id.template_file:
            docx_ctx = self._build_token_context(self.line_ids._format_lines_for_docx())
            self.document_pdf = self._render_docx_pdf(
                self.template_id.template_file, docx_ctx,
                out_name=self.name or 'garantia',
            )

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
            'company.signature_representative': representative or '',
            'partner.name': partner.name or '',
            'partner.vat': partner.vat or sin_doc or '',
            'partner.street': partner.street or '',
            'partner.city': partner.city or '',
            'product_lines': line_info or '',
            'date': self.date.strftime('%d/%m/%Y') if self.date else '',
            'date_day': self.date.strftime('%d') if self.date else '',
            'date_month': self.date.strftime('%m') if self.date else '',
            'date_year': self.date.strftime('%Y') if self.date else '',
            'date_expiry': self.date_expiry.strftime('%d/%m/%Y') if self.date_expiry else '-',
            'warranty.days': self._get_effective_warranty_days(),
            'warranty.name': self.name or '',
            # Datos técnicos del equipo amparado
            'warranty.brand': self.equipment_brand or '',
            'warranty.model': self.equipment_model or '',
            'warranty.serial': self.equipment_serial or '',
            'warranty.processor': self.equipment_processor or '',
            'warranty.ram': self.equipment_ram or '',
            'warranty.storage': self.equipment_storage or '',
            'warranty.os_version': self.equipment_os_version or '',
            'warranty.omv_version': self.equipment_omv_version or '',
            'warranty.odoo_edition': self.equipment_odoo_edition or '',
        }

    @staticmethod
    def _render_tokens(html, ctx):
        import re
        def _sub(m):
            key = m.group(1)
            return str(ctx.get(key, m.group(0)))
        return re.sub(r'\{([a-zA-Z0-9_.]+)\}', _sub, html)

    def action_sign_client(self):
        """Confirma la firma del cliente. La imagen se guarda previamente por el
        widget OWL en `client_signature`."""
        self.ensure_one()
        if not self.client_signature:
            raise UserError('La firma del cliente está vacía. Dibuje o suba la firma antes de confirmar.')
        if not self.client_signature_name:
            self.client_signature_name = self.partner_id.name
        if not self.client_signature_date:
            self.client_signature_date = fields.Datetime.now()
        self.state = 'signed'

    def action_open_report(self):
        if self.template_id.template_file:
            return self._open_generated_pdf()
        return self.env.ref(
            'l10n_bo_contracts.report_sin_warranty'
        ).report_action(self)

    def _open_generated_pdf(self):
        """Abre el PDF generado (plantilla Word) como descarga/visualización."""
        self.ensure_one()
        if not self.document_pdf:
            # Regenera el contenido sin cambiar el estado (no usar action_generate_document).
            self._generate_document_content()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'document_pdf'),
        ], limit=1)
        if attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'new',
            }
        return self.env.ref(
            'l10n_bo_contracts.report_sin_warranty'
        ).report_action(self)

    def action_cancel(self):
        self.state = 'cancelled'

    def action_draft(self):
        self.state = 'draft'


class SinWarrantyLine(models.Model):
    _name = 'sin.warranty.line'
    _description = 'Línea de certificado de garantía'
    _order = 'sequence, id'

    warranty_id = fields.Many2one('sin.warranty', string='Garantía', ondelete='cascade', required=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    description = fields.Text(string='Descripción')
    quantity = fields.Float(string='Cantidad', default=1.0)
    serial_number = fields.Char(string='Nº de serie')
    price_unit = fields.Float(string='Precio unitario')

    def _format_lines_for_template(self):
        lines = []
        for line in self:
            desc = escape(line.description or (line.product_id.name if line.product_id else ''))
            serial = escape(' (Serie: %s)' % line.serial_number) if line.serial_number else ''
            lines.append('<li>%s%s — Cantidad: %s</li>' % (desc, serial, line.quantity))
        return ''.join(lines) or '—'

    def _format_lines_for_docx(self):
        """Versión texto plano (con saltos de línea) para plantillas Word."""
        lines = []
        for line in self:
            desc = line.description or (line.product_id.name if line.product_id else '')
            serial = ' (Serie: %s)' % line.serial_number if line.serial_number else ''
            lines.append('%s%s — Cantidad: %s' % (desc, serial, line.quantity))
        return '\n'.join(lines) or '—'
