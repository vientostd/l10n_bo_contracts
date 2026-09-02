from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sin_signature = fields.Binary(
        string='Firma electrónica guardada', attachment=True,
        help='Firma o imagen de firma previamente guardada del cliente.',
    )
