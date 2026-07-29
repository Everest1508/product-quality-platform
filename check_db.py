import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django
django.setup()
from apps.ingestion.models import IngestedTicket

t = IngestedTicket.objects.last()
if t:
    print(f'ticket_type: "{t.ticket_type}"')
    print(f'title: "{t.title}"')
    print(f'description: "{t.description}"')
    print(f'metadata: {t.metadata}')
else:
    print('No tickets found')
