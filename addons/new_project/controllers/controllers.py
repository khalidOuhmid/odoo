# -*- coding: utf-8 -*-
# from odoo import http


# class NewProject(http.Controller):
#     @http.route('/new_project/new_project', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/new_project/new_project/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('new_project.listing', {
#             'root': '/new_project/new_project',
#             'objects': http.request.env['new_project.new_project'].search([]),
#         })

#     @http.route('/new_project/new_project/objects/<model("new_project.new_project"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('new_project.object', {
#             'object': obj
#         })

