import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django
django.setup()

from apps.ingestion.serializers import TicketIngestSerializer

s = TicketIngestSerializer(data={})
s.is_valid()
print(f'Errors: {s.errors}')
print(f'Validated data: {s.validated_data}')

# Check field properties
for field_name, field in s.fields.items():
    print(f'{field_name}: required={field.required}, default={field.default!r}, allow_null={field.allow_null}, allow_blank={getattr(field, "allow_blank", "N/A")}')
