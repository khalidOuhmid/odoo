# -*- coding: utf-8 -*-
# from odoo import http


# class ProjectTest(http.Controller):
#     @http.route('/project_test/project_test', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project_test/project_test/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('project_test.listing', {
#             'root': '/project_test/project_test',
#             'objects': http.request.env['project_test.project_test'].search([]),
#         })

#     @http.route('/project_test/project_test/objects/<model("project_test.project_test"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project_test.object', {
#             'object': obj
#         })

