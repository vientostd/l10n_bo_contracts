from odoo import fields, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    sin_contract_ids = fields.One2many(
        'sin.contract', 'pos_order_id', string='Contratos',
    )
    sin_warranty_ids = fields.One2many(
        'sin.warranty', 'pos_order_id', string='Certificados de garantía',
    )

    def _sin_prepare_contract_vals(self, product, line):
        company = self.company_id or self.env.company
        template = product.sin_contract_template_id or (
            company.default_contract_template_id
            if company.default_contract_template_id and \
                company.default_contract_template_id.doc_type == 'contract'
            else False
        )
        if not template:
            raise UserError(
                _('El producto "%s" requiere contrato pero no tiene plantilla '
                  'de contrato asignada.') % product.display_name
            )
        desc = line.full_product_name if hasattr(line, 'full_product_name') else product.name
        return {
            'partner_id': self.partner_id.id if self.partner_id else False,
            'company_id': self.company_id.id,
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
        template = product.sin_warranty_template_id or (
            company.default_warranty_template_id
            if company.default_warranty_template_id and \
                company.default_warranty_template_id.doc_type == 'warranty'
            else False
        )
        if not template and not product.sin_warranty_template_id:
            raise UserError(
                _('El producto "%s" requiere certificado de garantía pero no tiene '
                  'plantilla de garantía asignada.') % product.display_name
            )
        desc = line.full_product_name if hasattr(line, 'full_product_name') else product.name
        return {
            'partner_id': self.partner_id.id if self.partner_id else False,
            'company_id': self.company_id.id,
            'pos_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id if template else False,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': desc,
                'quantity': line.qty,
                'price_unit': line.price_unit,
            })],
        }

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
                    contract = order.env['sin.contract'].create(vals)
                    contract.action_generate_document()
                if product.sin_has_warranty and company.auto_generate_warranties:
                    vals = order._sin_prepare_warranty_vals(product, line)
                    warranty = order.env['sin.warranty'].create(vals)
                    warranty.action_generate_document()

    def action_pos_order_paid(self):
        """Cuando el pedido POS queda pagado (venta concretada), se generan los
        contratos/certificados de los productos que los requieran."""
        res = super().action_pos_order_paid()
        self._sin_action_generate_documents()
        return res