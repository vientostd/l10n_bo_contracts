import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sin_contract_ids = fields.One2many(
        'sin.contract', 'sale_order_id', string='Contratos',
    )
    sin_warranty_ids = fields.One2many(
        'sin.warranty', 'sale_order_id', string='Certificados de garantía',
    )

    def _sin_resolve_contract_template(self, product):
        """Resuelve la plantilla de contrato (producto o por defecto de empresa).
        Devuelve la plantilla o un recordset vacío si no hay ninguna."""
        company = self.env.company
        template = product.sin_contract_template_id
        if not template and company.default_contract_template_id.doc_type == 'contract':
            template = company.default_contract_template_id
        return template

    def _sin_resolve_warranty_template(self, product):
        """Resuelve la plantilla de certificado de garantía (producto o por
        defecto de empresa). Devuelve la plantilla o un recordset vacío."""
        company = self.env.company
        template = product.sin_warranty_template_id
        if not template and company.default_warranty_template_id.doc_type == 'warranty':
            template = company.default_warranty_template_id
        return template

    def _sin_prepare_contract_vals(self, product, line):
        template = self._sin_resolve_contract_template(product)
        if not template:
            return None
        return {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'sale_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': line.name or product.name,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
            })],
        }

    def _sin_prepare_warranty_vals(self, product, line):
        template = self._sin_resolve_warranty_template(product)
        if not template:
            return None
        qty = line.product_uom_qty if hasattr(line, 'product_uom_qty') else getattr(line, 'qty', 1.0)
        return {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'sale_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': line.name or product.name,
                'quantity': qty,
                'price_unit': line.price_unit,
            })],
        }

    def _sin_missing_template_hint(self, product, doc_type):
        """Devuelve el texto de aviso (producto sin plantilla) para dejar una
        nota en la orden sin abortar la venta."""
        label = 'contrato' if doc_type == 'contract' else 'certificado de garantía'
        return _(
            'El producto "%s" requiere %s pero no tiene plantilla asignada. '
            'El documento no se generó automáticamente.'
        ) % (product.display_name, label)

    def _sin_notify_missing_template(self, product, doc_type):
        """Deja la nota de plantilla faltante sin abortar la venta."""
        hint = self._sin_missing_template_hint(product, doc_type)
        _logger.warning(hint)
        self.message_post(body=hint, subtype_xmlid='mail.mt_note')

    def _sin_action_generate_documents(self):
        """Genera contratos y/o certificados de garantía a partir de las líneas
        de la orden de venta. Se invoca al confirmar la venta.

        Si un producto requiere un documento pero no se encuentra plantilla, NO
        se aborta la venta: se omite la generación y se deja una nota en la orden.
        """
        company = self.company_id or self.env.company
        product_list = {}
        for line in self.order_line:
            product = line.product_id
            if not product:
                continue
            if not (product.sin_has_contract or product.sin_has_warranty):
                continue
            key = product.id
            if key not in product_list:
                product_list[key] = {
                    'product': product,
                    'line': line,
                }
        # Por producto único deseamos un solo contrato/garantía por orden.
        for info in product_list.values():
            product = info['product']
            line = info['line']
            if product.sin_has_contract and company.auto_generate_contracts:
                vals = self._sin_prepare_contract_vals(product, line)
                if vals is None:
                    self._sin_notify_missing_template(product, 'contract')
                else:
                    contract = self.env['sin.contract'].create(vals)
                    contract.action_generate_document()
            if product.sin_has_warranty and company.auto_generate_warranties:
                vals = self._sin_prepare_warranty_vals(product, line)
                if vals is None:
                    self._sin_notify_missing_template(product, 'warranty')
                else:
                    warranty = self.env['sin.warranty'].create(vals)
                    warranty.action_generate_document(skip_serial=True)

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order._sin_action_generate_documents()
        return res
