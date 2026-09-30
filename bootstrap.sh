#!/usr/bin/env bash
#
# Bootstrap the local dev environment end to end:
#   1. apply migrations
#   2. create (or promote) a Django superuser
#   3. push demo data via the seed_data management command
#
# Usage:
#   ./bootstrap.sh                 # migrate + superuser + reseed demo workspace
#   ./bootstrap.sh --keep          # same, but keep existing demo data if present
#   ./bootstrap.sh --no-seed       # migrate + superuser only
#   ./bootstrap.sh --rules         # also run the auto-ticket rule engine (evaluate_rules)
#
# Override any default with env vars, e.g. SUPERUSER_PASSWORD=hunter2 ./bootstrap.sh

set -euo pipefail

cd "$(dirname "$0")"

# --- interpreter -------------------------------------------------------------
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "venv/bin/python" ]; then
  PY="venv/bin/python"
elif [ -x "../venv/bin/python" ]; then
  PY="../venv/bin/python"
else
  PY="python3"
fi

# Neither the name nor the email collides with the seeder: seed_data creates a
# demo user called "admin" and wipes every @demo.local account on --reset, so a
# superuser using either would be deleted or have its role rewritten on reseed.
SUPERUSER_USERNAME="${SUPERUSER_USERNAME:-root}"
SUPERUSER_EMAIL="${SUPERUSER_EMAIL:-root@localhost}"
SUPERUSER_PASSWORD="${SUPERUSER_PASSWORD:-testpass123}"
DEMO_COMPANY="${DEMO_COMPANY:-Acme Corp}"
DEMO_PASSWORD="${DEMO_PASSWORD:-testpass123}"

RESET_FLAG="--reset"
RUN_SEED=1
RUN_RULES=0

for arg in "$@"; do
  case "$arg" in
    --keep)     RESET_FLAG="" ;;
    --no-seed)  RUN_SEED=0 ;;
    --rules)    RUN_RULES=1 ;;
    -h|--help)  sed -n '2,15p' "$0" | sed 's/^#\{1,\} \{0,1\}//'; exit 0 ;;
    *)          echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

export BOOTSTRAP_USERNAME="$SUPERUSER_USERNAME"
export BOOTSTRAP_EMAIL="$SUPERUSER_EMAIL"
export BOOTSTRAP_PASSWORD="$SUPERUSER_PASSWORD"
export BOOTSTRAP_COMPANY="$DEMO_COMPANY"

echo "==> Interpreter: $($PY -c 'import sys; print(sys.executable)')"

# --- 1. migrations -----------------------------------------------------------
echo "==> Applying migrations"
"$PY" manage.py migrate --noinput

# --- 2. demo data ------------------------------------------------------------
if [ "$RUN_SEED" -eq 1 ]; then
  echo "==> Seeding demo workspace"
  # shellcheck disable=SC2086
  "$PY" manage.py seed_data $RESET_FLAG --company "$DEMO_COMPANY" --password "$DEMO_PASSWORD"
else
  echo "==> Skipping demo data (--no-seed)"
fi

# --- 3. superuser ------------------------------------------------------------
# Runs after seeding so the superuser can be attached to the demo company.
# get_or_create keeps an existing account; the owner membership matters because
# a user with no Membership is redirected to accounts:company_setup on every view.
"$PY" manage.py shell -c "
import os
from apps.accounts.models import Company, Membership, User

username = os.environ['BOOTSTRAP_USERNAME']
email = os.environ['BOOTSTRAP_EMAIL']
password = os.environ['BOOTSTRAP_PASSWORD']
company_name = os.environ['BOOTSTRAP_COMPANY']

user, created = User.objects.get_or_create(
    username=username,
    defaults={'email': email},
)
changed = []
if created:
    user.set_password(password)
    changed.append('created')
else:
    if not user.is_superuser or not user.is_staff:
        changed.append('promoted')
    if not user.check_password(password):
        user.set_password(password)
        changed.append('password reset')

user.email = email
user.is_superuser = True
user.is_staff = True
user.save()

company = Company.objects.filter(name=company_name).first()
role = None
if company is not None:
    membership, m_created = Membership.objects.get_or_create(
        user=user, company=company, defaults={'role': Membership.Role.OWNER},
    )
    if m_created:
        changed.append('owner membership created')
    elif membership.role != Membership.Role.OWNER:
        membership.role = Membership.Role.OWNER
        membership.save()
        changed.append('owner membership upgraded')
    role = membership.role

print('SUPERUSER_RESULT=' + (', '.join(changed) if changed else 'unchanged'))
print('SUPERUSER_ROLE=' + (role or 'no-company'))
"

# --- 4. automation rules (optional) ------------------------------------------
if [ "$RUN_RULES" -eq 1 ]; then
  echo "==> Evaluating auto-ticket rules"
  "$PY" manage.py evaluate_rules
fi

# --- summary -----------------------------------------------------------------
"$PY" manage.py shell -c "
import os
from django.contrib.auth import get_user_model
from apps.accounts.models import Company, Membership
from apps.attendance.models import AttendanceRecord
from apps.leave.models import LeavePolicy, LeaveRequest
from apps.automation.models import AutoTicketRule
from apps.payroll.models import Holiday, PayrollProfile, PayrollRun, Payslip
from apps.dashboards.models import ActivityLog
from apps.feedback.models import Survey, SurveyResponse
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback
from apps.products.models import APIKey, Product, ProductVersion
from apps.tickets.models import Ticket, TicketComment

User = get_user_model()
print('--- bootstrap summary ---')
print('companies: %d  users: %d  memberships: %d  superusers: %d' % (
    Company.objects.count(), User.objects.count(), Membership.objects.count(),
    User.objects.filter(is_superuser=True).count()))
print('products: %d  versions: %d  api keys: %d' % (
    Product.objects.count(), ProductVersion.objects.count(), APIKey.objects.count()))
print('error groups: %d  occurrences: %d' % (
    ErrorGroup.objects.count(), ErrorOccurrence.objects.count()))
print('tickets: %d  comments: %d' % (Ticket.objects.count(), TicketComment.objects.count()))
print('surveys: %d  responses: %d  feedback: %d' % (
    Survey.objects.count(), SurveyResponse.objects.count(), Feedback.objects.count()))
print('rules: %d  activity: %d' % (AutoTicketRule.objects.count(), ActivityLog.objects.count()))
print('attendance records: %d  open right now: %d' % (
    AttendanceRecord.objects.count(),
    AttendanceRecord.objects.filter(check_in__isnull=False, check_out__isnull=True).count()))
print('leave policies: %d  requests: %d  pending: %d' % (
    LeavePolicy.objects.count(),
    LeaveRequest.objects.count(),
    LeaveRequest.objects.filter(status='pending').count()))
print('payroll: %d holidays  %d rates (%d on payroll)  %d runs  %d payslips' % (
    Holiday.objects.count(), PayrollProfile.objects.count(),
    PayrollProfile.objects.filter(is_on_payroll=True).count(),
    PayrollRun.objects.count(), Payslip.objects.count()))
print('admin login: %s / %s' % (os.environ['BOOTSTRAP_USERNAME'], os.environ['BOOTSTRAP_PASSWORD']))
print('demo login:  owner|admin|dev1|dev2|support|viewer / ' + os.environ['BOOTSTRAP_PASSWORD'])
"

echo
echo "==> Start the dev server with: $PY manage.py runserver 8010"
