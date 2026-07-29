import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django
django.setup()
from apps.ingestion.models import IngestedTicket

tickets = IngestedTicket.objects.all().order_by('-id')[:10]
for t in tickets:
    print(f'id={t.id} title="{t.title}" ticket_type="{t.ticket_type}" desc="{t.description}"')
