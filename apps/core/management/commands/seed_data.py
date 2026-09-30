import hashlib
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Company, Membership, User
from apps.attendance.models import AttendanceRecord
from apps.automation.models import AutoTicketRule
from apps.dashboards.models import ActivityLog
from apps.dashboards.service import log_activity
from apps.feedback.models import Survey, SurveyResponse
from apps.ingestion.models import ErrorGroup, ErrorOccurrence, Feedback
from apps.products.models import APIKey, Product, ProductAccess, ProductVersion
from apps.tickets.models import Ticket, TicketComment

DEMO_EMAIL_SUFFIX = "@demo.local"

USERS = [
    ("owner", "Product Owner", Membership.Role.OWNER),
    ("admin", "Admin", Membership.Role.ADMIN),
    ("dev1", "Dev One", Membership.Role.DEVELOPER),
    ("dev2", "Dev Two", Membership.Role.DEVELOPER),
    ("support", "Support Agent", Membership.Role.SUPPORT),
    ("viewer", "Viewer", Membership.Role.VIEWER),
]

PRODUCTS = [
    ("Checkout API", "checkout-api", "production",
     "Payment processing service handling orders, refunds and webhooks."),
    ("Mobile App", "mobile-app", "staging",
     "iOS and Android client for browsing products and managing orders."),
    ("Billing Portal", "billing-portal", "production",
     "Customer-facing invoicing and subscription management."),
]

VERSIONS = {
    "checkout-api": ["1.4.0", "1.3.2", "1.3.1"],
    "mobile-app": ["2.1.0", "2.0.5"],
    "billing-portal": ["3.2.0", "3.1.4", "3.1.0"],
}

ERROR_TEMPLATES = {
    "checkout-api": [
        ("TypeError: Cannot read properties of undefined (reading 'items')", "TypeError", "high"),
        ("PaymentIntent requires_payment_method", "StripeError", "critical"),
        ("Timeout waiting for inventory service", "TimeoutError", "medium"),
        ("KeyError: 'currency' in pricing response", "KeyError", "low"),
        ("Connection reset by peer while fetching tax", "ConnectionError", "medium"),
    ],
    "mobile-app": [
        ("NSURLErrorDomain -1004 could not connect to server", "NSError", "high"),
        ("NullPointerException at CheckoutViewModel", "KotlinNullPointerException", "medium"),
        ("401 Unauthorized on refresh token", "AuthError", "critical"),
        ("LayoutInflater inflation failed on order screen", "InflateException", "low"),
    ],
    "billing-portal": [
        ("Segfault in invoice PDF renderer", "Segfault", "critical"),
        ("Deadlock on invoice update", "DatabaseError", "high"),
        ("500 on webhook delivery to billing", "WebhookError", "medium"),
        ("Invoice line items missing after tax recalculation", "DataError", "medium"),
    ],
}

TICKET_TITLES = {
    "checkout-api": [
        ("Confirmation page shows failure after a successful payment", "bug", "high"),
        ("Add support for Apple Pay", "feature", "medium"),
        ("Why was my order duplicated?", "question", "low"),
        ("Recurring 5xx on /api/v1/orders", "bug", "critical"),
        ("Refund flow missing email receipt", "bug", "medium"),
        ("Increase webhook retry timeout", "feature", "low"),
    ],
    "mobile-app": [
        ("App crashes when opening order history offline", "bug", "high"),
        ("Push notifications not delivered on iOS", "bug", "medium"),
        ("Dark mode toggle missing", "feature", "low"),
        ("Login screen keyboard covers submit button", "bug", "medium"),
        ("Support biometric login", "feature", "medium"),
    ],
    "billing-portal": [
        ("PDF invoices not generating for large accounts", "bug", "critical"),
        ("Subscription downgrade shows double charge", "bug", "high"),
        ("Add export to CSV", "feature", "low"),
        ("Invoice emails going to spam", "bug", "medium"),
    ],
}

COMMENTS = [
    "Reproduced locally, looking into a fix.",
    "Waiting on the third-party API team.",
    "Can we add a regression test for this?",
    "Customer reported this again today.",
    "Shipped a fix, monitoring it in production.",
    "Needs design input before implementation.",
]

RESPONSE_COMMENTS = [
    "Really easy to use, keep it up!",
    "The loading times are a bit slow lately.",
    "Could not find the settings page.",
    "Love the new checkout flow.",
    "Billing is confusing, had to contact support.",
]

FEEDBACK_COMMENTS = [
    "Order took too long to confirm.",
    "Great experience overall.",
    "The app crashed during checkout.",
    "Support was very helpful.",
    "Wish there was an export option.",
]

# Days back from the 1st of the current month, so the history always lands
# inside the month being reported on rather than spilling into the next one.
# Offsets 0-27 cover the whole calendar month.
ATTENDANCE_PLAN = [
    ("owner", [1, 2, 4, 5, 7, 8, 11, 12, 14, 15, 18, 19, 21, 22]),
    ("admin", [1, 2, 3, 4, 7, 8, 9, 11, 12, 14, 15, 16, 18, 19, 21]),
    ("dev1", [1, 2, 3, 5, 7, 8, 11, 12, 13, 15, 18, 19, 21, 22]),
    ("dev2", [1, 3, 4, 7, 9, 11, 12, 14, 16, 18, 19, 22]),
    ("support", [1, 2, 4, 5, 8, 9, 11, 13, 15, 16, 18, 20, 21]),
    ("viewer", [2, 3, 7, 9, 12, 14, 18, 20]),
]

# Left deliberately open so the admin team view has a live "on the clock" list.
ATTENDANCE_OPEN = {"dev1", "support"}


class Command(BaseCommand):
    help = (
        "Seed a full demo workspace: company, users, products, versions, API keys, "
        "errors, tickets, surveys, feedback, automation rules and activity. "
        "Run with --reset to wipe an existing demo company first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the existing demo company (and all of its data) before seeding.",
        )
        parser.add_argument(
            "--company",
            default="Acme Corp",
            help="Name of the demo company (default: Acme Corp).",
        )
        parser.add_argument(
            "--password",
            default="testpass123",
            help="Password for every seeded user (default: testpass123).",
        )

    def handle(self, *args, **options):
        random.seed(42)
        self.company_name = options["company"]
        self.password = options["password"]
        self.now = timezone.now()

        if options["reset"]:
            self._reset()

        if Company.objects.filter(name=self.company_name).exists():
            self.stdout.write(self.style.ERROR(
                f"Company '{self.company_name}' already exists. "
                "Re-run with --reset to wipe it and re-seed."
            ))
            return

        self.stdout.write("Seeding demo workspace...")

        company = self._create_company()
        users = self._create_users(company)
        self._create_products(company, users)

        products = list(Product.objects.filter(company=company))
        self._create_access(company, users, products)

        for product in products:
            self._create_versions(company, product)
            self._create_api_keys(company, product, users)
            self._create_error_groups(company, product, users)
            self._create_tickets(company, product, users)
            self._create_surveys(company, product, users)
            self._create_feedback(company, product)
            self._create_rules(company, product, users)

        self._backfill_activity(company)
        self._create_attendance(company, users)
        self._create_leave(company, users)
        self._create_payroll(company, users)

        usernames = ", ".join(u[0] for u in USERS)
        self.stdout.write(self.style.SUCCESS(
            "\nDone. Demo data seeded.\n"
            f"  Company: {company.name}\n"
            f"  Users:   {usernames}\n"
            f"  Login:   admin / {self.password}   (any user listed above)\n"
            f"  Leave:   approver can approve at /leave/approvals/\n"
            f"  Payroll: on payroll at /payroll/, salaries at /payroll/profiles/\n"
        ))

    def _reset(self):
        deleted, by_model = Company.objects.filter(name=self.company_name).delete()
        users, _ = User.objects.filter(email__endswith=DEMO_EMAIL_SUFFIX).delete()
        company_count = by_model.get("accounts.Company", 0)
        self.stdout.write(
            f"Removed previous demo data: {company_count} company(ies), "
            f"{deleted} related object(s), {users} demo user(s)."
        )

    def _create_company(self):
        company = Company.objects.create(name=self.company_name)
        log_activity(
            company, "member_joined",
            f"Company '{company.name}' created",
        )
        return company

    def _create_users(self, company):
        users = {}
        reused = []
        for username, full_name, role in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}{DEMO_EMAIL_SUFFIX}"},
            )
            if created or user.email.endswith(DEMO_EMAIL_SUFFIX):
                user.set_password(self.password)
                user.save()
            elif not created:
                reused.append(username)
            Membership.objects.get_or_create(
                user=user,
                company=company,
                defaults={"role": role},
            )
            users[username] = user
            log_activity(
                company, "member_joined",
                f"{full_name} joined the workspace",
                actor=user,
                target_content_type="membership",
                target_object_id=user.pk,
            )
        if reused:
            self.stdout.write(self.style.WARNING(
                "Reused existing account(s) without changing their password: "
                + ", ".join(reused)
            ))
        return users

    def _create_products(self, company, users):
        owner = users["owner"]
        for name, slug, env, description in PRODUCTS:
            product = Product.objects.create(
                company=company,
                name=name,
                slug=slug,
                default_environment=env,
                description=description,
            )
            log_activity(
                company, "product_created",
                f"Product '{name}' created",
                description=description[:200],
                actor=owner,
                target_content_type="product",
                target_object_id=product.pk,
                metadata={"product_id": product.pk},
            )

    def _create_access(self, company, users, products):
        owner, admin = users["owner"], users["admin"]
        dev1, dev2, support = users["dev1"], users["dev2"], users["support"]
        access_map = {
            "checkout-api": [dev1, dev2, support],
            "mobile-app": [dev1],
            "billing-portal": [dev2, support],
        }
        for product in products:
            for user in access_map.get(product.slug, []):
                record, created = ProductAccess.objects.get_or_create(
                    product=product,
                    user=user,
                    company=company,
                )
                if created:
                    log_activity(
                        company, "access_granted",
                        f"{user.username} granted access to {product.name}",
                        actor=owner,
                        target_content_type="product_access",
                        target_object_id=record.pk,
                        metadata={"product_id": product.pk, "user_id": user.pk},
                    )
        # Owners/admins implicitly have access to everything.
        _ = (owner, admin)

    def _create_versions(self, company, product):
        versions = VERSIONS.get(product.slug, ["1.0.0"])
        for index, version_string in enumerate(versions):
            version = ProductVersion.objects.create(
                company=company,
                product=product,
                version_string=version_string,
                is_current=(index == 0),
            )
            ProductVersion.objects.filter(pk=version.pk).update(
                released_at=self.now - timedelta(days=random.randint(10, 180))
            )

    def _create_api_keys(self, company, product, users):
        key, _ = APIKey.create_key(product=product, name="default")
        log_activity(
            company, "api_key_created",
            f"API key created for {product.name}",
            actor=users["owner"],
            target_content_type="api_key",
            target_object_id=key.pk,
            metadata={"product_id": product.pk},
        )

    def _create_error_groups(self, company, product, users):
        templates = ERROR_TEMPLATES.get(product.slug, ERROR_TEMPLATES["checkout-api"])
        for title, error_type, severity in templates:
            fingerprint = hashlib.sha256(
                f"{product.slug}:{title}".encode()
            ).hexdigest()[:32]
            status = random.choices(
                ["open", "investigating", "resolved", "ignored"],
                weights=[45, 25, 20, 10],
            )[0]
            first_seen = self.now - timedelta(
                days=random.randint(0, 29), hours=random.randint(0, 23)
            )
            last_seen = min(
                self.now, first_seen + timedelta(hours=random.randint(4, 240))
            )
            count = random.randint(5, 40)

            group = ErrorGroup.objects.create(
                company=company,
                product=product,
                fingerprint=fingerprint,
                title=title,
                error_type=error_type,
                severity=severity,
                status=status,
                occurrence_count=count,
                affected_user_count=random.randint(0, 200),
            )
            ErrorGroup.objects.filter(pk=group.pk).update(
                first_seen=first_seen,
                last_seen=last_seen,
            )

            for _ in range(random.randint(2, 8)):
                occurrence = ErrorOccurrence.objects.create(
                    company=company,
                    error_group=group,
                    environment=product.default_environment,
                    stacktrace=(
                        f'  at {title.split(":")[0].strip()} '
                        f"({title.lower().replace(' ', '_')}.py:{random.randint(10, 400)})"
                    ),
                    page=random.choice(
                        ["/checkout", "/pricing", "/api/v1/orders", "/billing", "/settings"]
                    ),
                    device=random.choice(["desktop", "mobile", "tablet"]),
                    os=random.choice(["Windows", "macOS", "Linux", "Android", "iOS"]),
                    browser=random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
                    user_ref=f"user_{random.randint(1000, 9999)}",
                )
                ErrorOccurrence.objects.filter(pk=occurrence.pk).update(
                    created_at=first_seen + timedelta(minutes=random.randint(0, 2000))
                )

            log_activity(
                company, "error_captured",
                f"[{severity}] {title}",
                description=f"{count} occurrences",
                actor=users["owner"],
                target_content_type="error_group",
                target_object_id=group.pk,
                metadata={"product_id": product.pk, "severity": severity},
            )

    def _create_tickets(self, company, product, users):
        titles = TICKET_TITLES.get(product.slug, TICKET_TITLES["checkout-api"])
        pool = [users["dev1"], users["dev2"], users["support"]]
        for title, ticket_type, priority in titles:
            status = random.choices(
                ["open", "assigned", "in_progress", "testing", "resolved", "closed"],
                weights=[25, 15, 20, 10, 20, 10],
            )[0]
            created_at = self.now - timedelta(
                days=random.randint(0, 29), hours=random.randint(0, 23)
            )
            roll = random.random()
            deadline = None
            if roll < 0.4:
                deadline = created_at + timedelta(days=random.randint(1, 14))
            elif roll < 0.55:
                deadline = self.now - timedelta(days=random.randint(1, 5))

            ticket = Ticket.objects.create(
                company=company,
                product=product,
                title=title,
                description=f"Seeded demo ticket for {product.name}.",
                ticket_type=ticket_type,
                priority=priority,
                status=status,
                source="manual",
                created_by=users["owner"],
                deadline=deadline,
            )

            if status not in ("resolved", "closed") and random.random() < 0.7:
                ticket.set_assignees([random.choice(pool)])

            Ticket.objects.filter(pk=ticket.pk).update(
                created_at=created_at,
                updated_at=created_at + timedelta(hours=random.randint(1, 120)),
            )

            if random.random() < 0.5:
                TicketComment.objects.create(
                    company=company,
                    ticket=ticket,
                    author=random.choice(pool),
                    body=random.choice(COMMENTS),
                )

            log_activity(
                company, "ticket_created",
                f"Ticket #{ticket.pk} created",
                description=title,
                actor=users["owner"],
                target_content_type="ticket",
                target_object_id=ticket.pk,
                metadata={"product_id": product.pk},
            )

    def _create_surveys(self, company, product, users):
        specs = [
            ("Checkout Experience", "csat", "active", 1, 5),
            ("Overall Product NPS", "nps", "active", 0, 10),
            ("Support Resolution CES", "ces", "closed", 1, 7),
        ]
        for name, survey_type, status, low, high in specs:
            survey, _ = Survey.objects.get_or_create(
                company=company,
                product=product,
                name=name,
                defaults={
                    "survey_type": survey_type,
                    "status": status,
                    "created_by": users["owner"],
                },
            )
            for _ in range(random.randint(8, 20)):
                response = SurveyResponse.objects.create(
                    company=company,
                    survey=survey,
                    score=random.randint(low, high),
                    comment=random.choice(RESPONSE_COMMENTS) if random.random() < 0.3 else "",
                )
                SurveyResponse.objects.filter(pk=response.pk).update(
                    created_at=self.now - timedelta(
                        days=random.randint(0, 29), hours=random.randint(0, 23)
                    )
                )
            log_activity(
                company, "survey_created",
                f"Survey '{name}' created for {product.name}",
                actor=users["owner"],
                target_content_type="survey",
                target_object_id=survey.pk,
                metadata={"product_id": product.pk},
            )

    def _create_feedback(self, company, product):
        for _ in range(random.randint(2, 6)):
            feedback = Feedback.objects.create(
                company=company,
                product=product,
                rating=random.randint(1, 5),
                comment=random.choice(FEEDBACK_COMMENTS),
                user_ref=f"user_{random.randint(1000, 9999)}",
            )
            Feedback.objects.filter(pk=feedback.pk).update(
                created_at=self.now - timedelta(
                    days=random.randint(0, 29), hours=random.randint(0, 23)
                )
            )

    def _create_rules(self, company, product, users):
        AutoTicketRule.objects.create(
            company=company,
            product=product,
            name="Critical errors auto-ticket",
            trigger_type="error_threshold",
            severity="critical",
            threshold_count=10,
            window_minutes=60,
            action="create_ticket",
            assign_to=users["dev1"],
        )
        AutoTicketRule.objects.create(
            company=company,
            product=product,
            name="High-severity spike alert",
            trigger_type="error_threshold",
            severity="high",
            threshold_count=25,
            window_minutes=120,
            action="notify_only",
        )

    def _create_attendance(self, company, users):
        """Seed this month's punch history plus today's live state.

        Offsets are counted back from the 1st of the current month, so the
        records always sit inside the month the timesheet defaults to even
        when the command runs late in a month.
        """
        from datetime import datetime, time

        today = timezone.localdate()
        month_start = today.replace(day=1)

        for username, offsets in ATTENDANCE_PLAN:
            user = users[username]
            for offset in offsets:
                day = month_start + timedelta(days=offset - 1)
                if day > today:
                    continue  # don't seed the future
                if day.weekday() >= 5 and random.random() < 0.7:
                    continue  # mostly weekends off

                check_in = timezone.make_aware(
                    datetime.combine(day, time(hour=9, minute=random.randint(0, 45)))
                )
                hours = random.choices(
                    [6, 7, 7.5, 8, 8.5, 9], weights=[1, 2, 2, 4, 2, 1]
                )[0]

                record = AttendanceRecord.objects.create(
                    company=company,
                    user=user,
                    date=day,
                    check_in=check_in,
                    check_out=check_in + timedelta(hours=hours),
                )
                if random.random() < 0.08:
                    record.is_edited = True
                    record.notes = "Corrected by admin"
                    record.save()

        # Today: two are still on the clock, the rest are done for the day.
        #
        # The arrival times are derived from the *shift start*, not from
        # `now - N hours`. Counting back from the clock made the demo data
        # depend on the hour the seed happened to run: at 14:25 a punch 7 hours
        # ago lands at 07:25, but at 09:00 the same code lands at 02:00, and
        # anything past the shift start manufactured a real late penalty out of
        # demo data. Timesheet history above is `time(hour=9, ...)` for the same
        # reason.
        from apps.attendance.service import shift_for

        shift = shift_for(company)
        shift_start = timezone.make_aware(
            datetime.combine(today, shift.start_time)
        )
        # Never seed an arrival in the future if the command runs before the
        # shift does; fall back to `now - 1h` in that case.
        latest_arrival = shift_start + timedelta(minutes=random.randint(0, 10))
        if self.now <= latest_arrival:
            latest_arrival = self.now - timedelta(hours=1)

        for username, user in users.items():
            if username in ATTENDANCE_OPEN:
                AttendanceRecord.objects.create(
                    company=company,
                    user=user,
                    date=today,
                    check_in=latest_arrival
                    - timedelta(minutes=random.randint(20, 240)),
                    check_out=None,
                )
            elif random.random() < 0.85:
                check_out = self.now - timedelta(minutes=random.randint(5, 90))
                arrival = latest_arrival - timedelta(minutes=random.randint(20, 240))
                AttendanceRecord.objects.create(
                    company=company,
                    user=user,
                    date=today,
                    check_in=arrival,
                    check_out=check_out if check_out > arrival else None,
                )

    def _create_leave(self, company, users):
        """Seed leave policies, an approver, and a few requests.

        Dates are built from working days so the seeded requests always sit
        inside this calendar year and respect the per-policy caps.
        """
        from apps.leave.models import LeavePolicy, LeaveRequest

        policies = {
            "Casual": LeavePolicy.objects.create(
                company=company,
                name="Casual",
                icon="coffee",
                color="green",
                max_days_per_year=Decimal("12.0"),
                max_consecutive_days=Decimal("3.0"),
                is_paid=True,
            ),
            "Sick": LeavePolicy.objects.create(
                company=company,
                name="Sick",
                icon="stethoscope",
                color="amber",
                max_days_per_year=Decimal("5.0"),
                max_consecutive_days=Decimal("3.0"),
                is_paid=True,
            ),
            "Unpaid": LeavePolicy.objects.create(
                company=company,
                name="Unpaid",
                icon="wallet",
                color="red",
                max_days_per_year=None,
                max_consecutive_days=None,
                is_paid=False,
            ),
        }

        # Give one developer the approver flag so the queue is not admin-only.
        Membership.objects.filter(
            user=users["admin"], company=company
        ).update(is_leave_approver=True)

        today = timezone.localdate()

        def next_working_day(offset):
            """The `offset`-th working day from today, at least a week out."""
            day = today + timedelta(days=7)
            while day.weekday() >= 5:
                day += timedelta(days=1)
            count = 1
            while count < offset:
                day += timedelta(days=1)
                if day.weekday() < 5:
                    count += 1
            return day

        plan = [
            ("dev1", "Casual", "approved", "Family wedding", False, 2),
            ("dev1", "Sick", "pending", "Dental surgery follow-up", False, 1),
            ("dev2", "Casual", "pending", "Long weekend trip", False, 3),
            ("admin", "Unpaid", "rejected", "Extended personal trip", False, 5),
            ("support", "Sick", "approved", "Flu, advised to rest", True, 1),
        ]

        for username, policy_name, status, reason, half, days in plan:
            policy = policies[policy_name]
            start = next_working_day(random.randint(1, 6))
            charged = Decimal("0.5") if half else Decimal(days)
            # Walk forward over working days so the stored charge always
            # matches working_days(start, end) and no weekend days sneak in.
            end = start
            if not half:
                for _ in range(days - 1):
                    end += timedelta(days=1)
                    # Saturday needs two steps to reach Monday.
                    while end.weekday() >= 5:
                        end += timedelta(days=1)
            LeaveRequest.objects.create(
                company=company,
                user=users[username],
                policy=policy,
                start_date=start,
                end_date=end,
                is_half_day=half,
                days=charged,
                status=status,
                reason=reason,
                decided_by=users["admin"] if status != "pending" else None,
                decided_at=None if status == "pending" else self.now,
                decision_note="Not enough cover that week" if status == "rejected" else "",
            )

        self.stdout.write(
            f"  Leave:   {LeavePolicy.objects.filter(company=company).count()} policies, "
            f"{LeaveRequest.objects.filter(company=company).count()} requests\n"
        )

    def _create_payroll(self, company, users):
        """Seed holidays and a daily rate for part of the team.

        Rates are backdated to the start of the year so every pay cycle,
        past or future, resolves to one. `viewer` is deliberately left off
        payroll so the "nobody to pay" case stays reachable in the demo.
        """
        from apps.payroll.models import Holiday, PayrollProfile

        for month, day, name in ((1, 26, "Republic Day"), (8, 15, "Independence Day")):
            Holiday.objects.get_or_create(
                company=company, date=date(self.now.year, month, day), defaults={"name": name}
            )

        # Monthly gross, the way pay is actually quoted. The daily rate is
        # derived per cycle from the real working-day count.
        salaries = {"owner": None, "admin": "90000.00", "dev1": "42000.00",
                    "dev2": "42000.00", "support": "24000.00"}
        on_payroll = {"admin", "dev1", "dev2", "support"}
        for username, salary in salaries.items():
            user = users.get(username)
            if user is None:
                continue
            PayrollProfile.objects.create(
                company=company,
                user=user,
                monthly_salary=Decimal(salary) if salary else None,
                currency="INR",
                is_on_payroll=username in on_payroll,
                effective_from=date(self.now.year, 1, 1),
            )

        self.stdout.write(
            f"  Payroll: {Holiday.objects.filter(company=company).count()} holidays, "
            f"{PayrollProfile.objects.filter(company=company, is_on_payroll=True).count()} "
            f"on payroll\n"
        )

    def _backfill_activity(self, company):
        entries = list(ActivityLog.objects.filter(company=company).order_by("created_at"))
        recent = entries[:8]
        for entry in entries[len(recent):]:
            ActivityLog.objects.filter(pk=entry.pk).update(
                created_at=self.now - timedelta(
                    days=random.randint(1, 29), hours=random.randint(0, 23)
                )
            )
