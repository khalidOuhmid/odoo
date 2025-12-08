print("CHECKING FIELDS...")
fields = env['construction.chantier'].fields_get(['margin_rate', 'gross_margin', 'days_remaining', 'deadline_status', 'priority'])
valid_fields = list(fields.keys())
print(f"FOUND FIELDS: {valid_fields}")
if 'margin_rate' not in valid_fields:
    print("FATAL: margin_rate MISSING")
else:
    print("margin_rate EXISTS")
