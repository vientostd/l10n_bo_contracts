from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sin_contract_ids = fields.One2many(
        'sin.contract', 'sale_order_id', string='Contratos',
    )
    sin_warranty_ids = fields.One2many(
        'sin.warranty', 'sale_order_id', string='Certificados de garantía',
    )

    def _sin_prepare_contract_vals(self, product, line):
        company = self.env.company
        template = product.sin_contract_template_id or (
            company.default_contract_template_id
            if company.default_contract_template_id.doc_type == 'contract'
            else False
        )
        if not template:
            raise UserError(
                _('El producto "%s" requiere contrato pero no tiene plantilla '
                  'de contrato asignada.') % product.display_name
            )
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
        company = self.env.company
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
        return {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'sale_order_id': self.id,
            'date': self.date_order and self.date_order.date() or False,
            'template_id': template.id if template else False,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'description': line.name or product.name,
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
            })],
        }

    def _sin_action_generate_documents(self):
        """Genera contratos y/o certificados de garantía a partir de las líneas
        despedidas de la orden de venta. Se invoca al confirmar la venta."""
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
                contract = self.env['sin.contract'].create(vals)
                contract.action_generate_document()
            if product.sin_has_warranty and company.auto_generate_warranties:
                vals = self._sin_prepare_warranty_vals(product, line)
                warranty = self.env['sin.warranty'].create(vals)
                warranty.action_generate_document()

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            order._sin_action_generate_documents()
        return res
