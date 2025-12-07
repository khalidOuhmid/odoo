# -*- coding: utf-8 -*-
"""
Template Variables
Defines all Jinja2 variables available in contract templates
Used for both template editing (GrapesJS) and rendering
"""

# Available variables with descriptions
TEMPLATE_VARIABLES = {
    'contract': {
        'name': 'Contract Reference',
        'date': 'Contract Date',
        'start_date': 'Work Start Date',
        'end_date': 'Work End Date',
        'total_amount_ht': 'Amount Excluding VAT',
        'total_amount_tva': 'VAT Amount',
        'total_amount_ttc': 'Amount Including VAT',
        'retention_amount': 'Retention Amount (garantie)',
        'retention_rate': 'Retention Rate Percentage',
    },
    'chantier': {
        'name': 'Construction Site Name',
        'reference': 'Site Reference',
        'client': 'Client Name',
        'address': 'Site Address',
        'city': 'City',
        'postal_code': 'Postal Code',
    },
    'subcontractor': {
        'name': 'Subcontractor Company Name',
        'siret': 'SIRET Number',
        'email': 'Email Address',
        'phone': 'Phone Number',
        'mobile': 'Mobile Number',
        'address': 'Company Address',
        'urssaf_code': 'URSSAF Activity Code',
    },
    'lots': {
        'description': 'List of Lots (Table)',
        'is_table': True,
        'fields': {
            'name': 'Lot Name',
            'description': 'Lot Description',
            'amount': 'Lot Amount',
        }
    },
    'purchase_orders': {
        'description': 'Purchase Orders (Table)',
        'is_table': True,
        'fields': {
            'name': 'PO Reference',
            'date': 'PO Date',
            'amount': 'PO Amount',
        }
    },
    'deliverables': {
        'description': 'Contract Deliverables (Table)',
        'is_table': True,
        'fields': {
            'name': 'Deliverable Name',
            'type': 'Deliverable Type',
            'description': 'Description',
        }
    },
}


def get_variable_blocks_for_grapesjs():
    """
    Generate GrapesJS blocks definition from template variables

    Returns:
        list: List of block definitions for GrapesJS editor
    """
    blocks = []

    for category, variables in TEMPLATE_VARIABLES.items():
        # Handle table-type variables differently
        if isinstance(variables, dict) and variables.get('is_table'):
            # Create a table block
            fields_html = ''
            for field_name, field_desc in variables.get('fields', {}).items():
                fields_html += f'<th>{field_desc}</th>'

            table_html = f'''
            <table class="table table-bordered contract-table">
                <thead>
                    <tr>{fields_html}</tr>
                </thead>
                <tbody>
                    {{% for item in {category} %}}
                    <tr>
                        {' '.join([f'<td>{{{{ item.{field} }}}}</td>' for field in variables.get('fields', {}).keys()])}
                    </tr>
                    {{% endfor %}}
                </tbody>
            </table>
            '''

            blocks.append({
                'id': f'table_{category}',
                'label': variables['description'],
                'category': 'Contract Tables',
                'content': table_html,
            })
        else:
            # Create individual variable blocks
            for var_name, description in variables.items():
                blocks.append({
                    'id': f'{category}_{var_name}',
                    'label': f'{category.title()}: {description}',
                    'category': 'Contract Variables',
                    'content': f'<span class="contract-var" data-variable="{category}.{var_name}">{{{{ {category}.{var_name} }}}}</span>',
                    'attributes': {
                        'class': 'contract-variable',
                        'data-type': 'variable',
                    }
                })

    return blocks


def get_context_example():
    """
    Generate example context for template preview

    Returns:
        dict: Example data structure for template rendering
    """
    return {
        'contract': {
            'name': 'CONT/00001',
            'date': '15/11/2025',
            'start_date': '01/12/2025',
            'end_date': '31/03/2026',
            'total_amount_ht': '50,000.00 €',
            'total_amount_tva': '10,000.00 €',
            'total_amount_ttc': '60,000.00 €',
            'retention_amount': '3,000.00 €',
            'retention_rate': '5.0',
        },
        'chantier': {
            'name': 'Résidence Les Fleurs',
            'reference': 'CHANT/2025/001',
            'client': 'SCI Les Jardins',
            'address': '12 Avenue de la République',
            'city': 'Bordeaux',
            'postal_code': '33000',
        },
        'subcontractor': {
            'name': 'Entreprise Dupont SARL',
            'siret': '123 456 789 00012',
            'email': 'contact@dupont-btp.fr',
            'phone': '05 56 12 34 56',
            'mobile': '06 12 34 56 78',
            'address': '45 Rue du Commerce, 33000 Bordeaux',
            'urssaf_code': '43.34Z',
        },
        'lots': [
            {
                'name': 'Gros Œuvre',
                'description': 'Fondations et structure béton',
                'amount': '25,000.00 €',
            },
            {
                'name': 'Charpente',
                'description': 'Charpente traditionnelle en bois',
                'amount': '15,000.00 €',
            },
        ],
        'purchase_orders': [
            {
                'name': 'PO/2025/001',
                'date': '10/11/2025',
                'amount': '25,000.00 €',
            },
            {
                'name': 'PO/2025/002',
                'date': '12/11/2025',
                'amount': '15,000.00 €',
            },
        ],
    }
