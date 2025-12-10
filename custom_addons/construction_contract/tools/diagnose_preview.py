#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostic Tool for Contract Preview Issues
Run this script to diagnose why preview is not working

Usage:
    odoo-bin shell -d DATABASE < tools/diagnose_preview.py
"""

import sys
import logging

_logger = logging.getLogger(__name__)


def diagnose_preview(env):
    """
    Run comprehensive diagnostics on preview functionality
    
    Args:
        env: Odoo environment
    """
    print("=" * 70)
    print("CONTRACT PREVIEW DIAGNOSTIC TOOL")
    print("=" * 70)
    
    issues = []
    warnings = []
    
    # 1. Check Jinja2
    print("\n[1/8] Checking Jinja2 installation...")
    try:
        import jinja2
        print(f"   ✓ Jinja2 {jinja2.__version__} installed")
    except ImportError:
        issues.append("Jinja2 not installed. Run: pip install jinja2")
        print("   ✗ Jinja2 NOT installed")
    
    # 2. Check WeasyPrint
    print("\n[2/8] Checking WeasyPrint installation...")
    try:
        import weasyprint
        print(f"   ✓ WeasyPrint {weasyprint.__version__} installed")
        
        # Test WeasyPrint
        pdf_service = env['construction.contract.pdf.generator']
        result = pdf_service.test_weasyprint_installation()
        if result.get('test_pdf_generation'):
            print("   ✓ WeasyPrint test PDF generation successful")
        else:
            warnings.append(f"WeasyPrint test failed: {result.get('error')}")
            print(f"   ⚠ WeasyPrint test failed: {result.get('error')}")
    except ImportError:
        issues.append("WeasyPrint not installed. Run: pip install WeasyPrint")
        print("   ✗ WeasyPrint NOT installed")
    
    # 3. Check PyPDF2
    print("\n[3/8] Checking PyPDF2 installation...")
    try:
        import PyPDF2
        print(f"   ✓ PyPDF2 {PyPDF2.__version__} installed")
    except ImportError:
        warnings.append("PyPDF2 not installed (optional). Run: pip install PyPDF2")
        print("   ⚠ PyPDF2 NOT installed (optional)")
    
    # 4. Check construction sites exist
    print("\n[4/8] Checking construction sites...")
    chantiers = env['construction.chantier'].search([])
    if chantiers:
        print(f"   ✓ Found {len(chantiers)} construction site(s)")
        for ch in chantiers[:3]:
            print(f"      - {ch.name} (ID: {ch.id})")
    else:
        issues.append("No construction sites found. Create at least one to test.")
        print("   ✗ No construction sites found")
    
    # 5. Check subcontractors exist
    print("\n[5/8] Checking subcontractors...")
    subcontractors = env['res.partner'].search([('is_subcontractor', '=', True)])
    if subcontractors:
        print(f"   ✓ Found {len(subcontractors)} subcontractor(s)")
        for sub in subcontractors[:3]:
            print(f"      - {sub.name} (ID: {sub.id})")
    else:
        issues.append("No subcontractors found. Create at least one to test.")
        print("   ✗ No subcontractors found")
    
    # 6. Check templates exist and have content
    print("\n[6/8] Checking contract templates...")
    templates = env['construction.contract.template'].search([])
    if templates:
        print(f"   ✓ Found {len(templates)} template(s)")
        for tpl in templates:
            has_html = bool(tpl.grapesjs_html and len(tpl.grapesjs_html.strip()) > 0)
            has_css = bool(tpl.grapesjs_css and len(tpl.grapesjs_css.strip()) > 0)
            status = "✓" if has_html else "✗"
            print(f"      {status} {tpl.name} (ID: {tpl.id})")
            print(f"         HTML: {len(tpl.grapesjs_html or '')} chars")
            print(f"         CSS: {len(tpl.grapesjs_css or '')} chars")
            
            if not has_html:
                warnings.append(f"Template '{tpl.name}' has no HTML content")
    else:
        issues.append("No contract templates found. Create at least one with content.")
        print("   ✗ No contract templates found")
    
    # 7. Check lots exist
    print("\n[7/8] Checking work packages (lots)...")
    lots = env['construction.lot'].search([])
    if lots:
        print(f"   ✓ Found {len(lots)} work package(s)")
        for lot in lots[:3]:
            print(f"      - {lot.name} (Chantier: {lot.chantier_id.name})")
    else:
        issues.append("No work packages found. Create at least one to test.")
        print("   ✗ No work packages found")
    
    # 8. Test preview generation
    print("\n[8/8] Testing preview generation...")
    if chantiers and subcontractors and templates and lots:
        try:
            # Create test wizard
            chantier = chantiers[0]
            subcontractor = subcontractors[0]
            template = templates[0]
            chantier_lots = lots.filtered(lambda l: l.chantier_id == chantier)
            
            if not chantier_lots:
                warnings.append(f"No lots found for chantier {chantier.name}")
                print(f"   ⚠ No lots found for selected chantier")
            else:
                wizard = env['contract.creation.wizard'].create({
                    'chantier_id': chantier.id,
                    'subcontractor_id': subcontractor.id,
                    'lot_ids': [(6, 0, [chantier_lots[0].id])],
                    'template_id': template.id,
                    'start_date': '2025-11-16',
                    'end_date': '2025-12-16',
                    'contract_date': '2025-11-16',
                })
                
                renderer = env['construction.contract.template.renderer']
                html = renderer.render_preview_from_wizard(wizard)
                
                if html and len(html) > 100:
                    print(f"   ✓ Preview generated successfully ({len(html)} chars)")
                    
                    # Check content
                    checks = [
                        (chantier.name in html, f"Chantier name '{chantier.name}'"),
                        (subcontractor.name in html, f"Subcontractor name '{subcontractor.name}'"),
                        ('<!DOCTYPE html>' in html, "DOCTYPE declaration"),
                        ('<html' in html, "HTML tag"),
                    ]
                    
                    for check, desc in checks:
                        status = "✓" if check else "✗"
                        print(f"      {status} Contains {desc}")
                        if not check:
                            warnings.append(f"Preview missing {desc}")
                else:
                    issues.append("Preview generated but HTML is too short or empty")
                    print(f"   ✗ Preview HTML too short ({len(html)} chars)")
                
                # Cleanup
                wizard.unlink()
                
        except Exception as e:
            issues.append(f"Preview generation failed: {str(e)}")
            print(f"   ✗ Preview generation failed: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("   ⊘ Skipped (missing prerequisites)")
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    if not issues and not warnings:
        print("\n✓✓✓ ALL CHECKS PASSED ✓✓✓")
        print("\nYour preview should work correctly.")
        print("\nIf preview still doesn't show:")
        print("  1. Clear browser cache (Ctrl+F5)")
        print("  2. Check browser console for JavaScript errors (F12)")
        print("  3. Restart Odoo server")
        print("  4. Check Odoo logs: tail -f /var/log/odoo/odoo.log")
    else:
        if issues:
            print(f"\n✗ FOUND {len(issues)} CRITICAL ISSUE(S):")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
        
        if warnings:
            print(f"\n⚠ FOUND {len(warnings)} WARNING(S):")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        
        print("\n" + "=" * 70)
        print("RECOMMENDED ACTIONS:")
        print("=" * 70)
        
        if any('WeasyPrint' in issue for issue in issues):
            print("\n1. Install WeasyPrint:")
            print("   pip3 install WeasyPrint")
        
        if any('Jinja2' in issue for issue in issues):
            print("\n2. Install Jinja2:")
            print("   pip3 install jinja2")
        
        if any('template' in issue.lower() for issue in issues):
            print("\n3. Create a contract template:")
            print("   - Go to Construction > Configuration > Contract Templates")
            print("   - Create a new template")
            print("   - Open the visual editor")
            print("   - Add some content with Jinja2 variables")
            print("   - Save the template")
        
        if any('chantier' in issue.lower() or 'site' in issue.lower() for issue in issues):
            print("\n4. Create a construction site:")
            print("   - Go to Construction > Construction Sites")
            print("   - Create a new construction site")
            print("   - Add at least one work package (lot)")
        
        print("\n5. Restart Odoo after installing packages:")
        print("   sudo systemctl restart odoo")
    
    print("\n" + "=" * 70)
    return {
        'issues': issues,
        'warnings': warnings,
        'passed': len(issues) == 0,
    }


# Main execution
if __name__ == '__main__' or 'env' in dir():
    try:
        # Get Odoo environment
        if 'env' not in dir():
            print("ERROR: This script must be run with odoo-bin shell")
            print("Usage: odoo-bin shell -d DATABASE < tools/diagnose_preview.py")
            sys.exit(1)
        
        result = diagnose_preview(env)
        
        if not result['passed']:
            sys.exit(1)
            
    except Exception as e:
        print(f"\n\n✗✗✗ DIAGNOSTIC FAILED ✗✗✗")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


