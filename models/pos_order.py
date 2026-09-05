from odoo import fields, models, _

import logging
_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    sin_contract_ids = fields.One2many(
        'sin.contract', 'pos_order_id', string='Contratos',
    )
    sin_warranty_ids = fields.One2many(
        'sin.warranty', 'pos_order_id', string='Certificados de garantía',
    )

    def _sin_resolve_contract_template(self, product):
        company = self.company_id or self.env.company
        template = product.sin_contract_template_id
        if not template and company.default_contract_template_id.doc_type == 'contract':
            template = company.default_contract_template_id
        return template

    def _sin_resolve_warranty_template(self, product):
        company = self.company_id or self.env.company
        template = product.sin_warranty_template_id
        if not template and company.default_warranty_template_id.doc_type == 'warranty':
            template = company.default_warranty_template_id
        return template

    def _sin_prepare_contract_vals(self, product, line):
        company = self.company_id or self.env.company
        template = self._sin_resolve_contract_template(product)
        if not template:
            return None
        desc = line.full_product_name if hasattr(line, 'full_product_name') else product.name
        return {
            'partner_id': self.partner_id.id if self.partner_id else False,
            'company_id': company.id,
            'pos_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': desc,
                'quantity': line.qty,
                'price_unit': line.price_unit,
            })],
        }

    def _sin_prepare_warranty_vals(self, product, line):
        company = self.company_id or self.env.company
        template = self._sin_resolve_warranty_template(product)
        if not template:
            return None
        desc = line.full_product_name if hasattr(line, 'full_product_name') else product.name
        return {
            'partner_id': self.partner_id.id if self.partner_id else False,
            'company_id': company.id,
            'pos_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': desc,
                'quantity': line.qty,
                'price_unit': line.price_unit,
            })],
        }

    def _sin_missing_template_hint(self, product, doc_type):
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
        """Genera contratos y/o certificados de garantía a partir del pedido POS.
        Solo se invoca cuando el pedido está pagado (equivalente a venta confirmada)."""
        if not self:
            return
        for order in self:
            company = order.company_id or order.env.company
            if not (company.auto_generate_contracts or company.auto_generate_warranties):
                continue
            product_list = {}
            for line in order.lines:
                product = line.product_id
                if not product:
                    continue
                if not (product.sin_has_contract or product.sin_has_warranty):
                    continue
                if product.id not in product_list:
                    product_list[product.id] = {
                        'product': product,
                        'line': line,
                    }
            for info in product_list.values():
                product = info['product']
                line = info['line']
                if product.sin_has_contract and company.auto_generate_contracts:
                    vals = order._sin_prepare_contract_vals(product, line)
                    if vals is None:
                        order._sin_notify_missing_template(product, 'contract')
                    else:
                        contract = order.env['sin.contract'].create(vals)
                        contract.action_generate_document()
                if product.sin_has_warranty and company.auto_generate_warranties:
                    vals = order._sin_prepare_warranty_vals(product, line)
                    if vals is None:
                        order._sin_notify_missing_template(product, 'warranty')
                    else:
                        warranty = order.env['sin.warranty'].create(vals)
                        warranty.action_generate_document(skip_serial=True)

    def action_pos_order_paid(self):
        """Cuando el pedido POS queda pagado (venta concretada), se generan los
        contratos/certificados de los productos que los requieran."""
        res = super().action_pos_order_paid()
        self._sin_action_generate_documents()
        return res