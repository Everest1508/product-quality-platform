import type { RouteObject } from 'react-router-dom';
import { ErrorDetailPage } from '@/pages/errors/ErrorDetailPage';
import { ErrorFormPage } from '@/pages/errors/ErrorFormPage';
import { ErrorsPage } from '@/pages/errors/ErrorsPage';
import { ProductApiDocsPage } from '@/pages/products/ProductApiDocsPage';
import { ProductDetailPage } from '@/pages/products/ProductDetailPage';
import { ProductFormPage } from '@/pages/products/ProductFormPage';
import { ProductsPage } from '@/pages/products/ProductsPage';
import { RuleFormPage } from '@/pages/automation/RuleFormPage';
import { RulesPage } from '@/pages/automation/RulesPage';
import { CsHubPage } from '@/pages/feedback/CsHubPage';
import { PublicSurveyPage } from '@/pages/feedback/PublicSurveyPage';
import { SurveyDetailPage } from '@/pages/feedback/SurveyDetailPage';
import { SurveyFormPage } from '@/pages/feedback/SurveyFormPage';
import { SurveysPage } from '@/pages/feedback/SurveysPage';
import { AuditLogPage } from '@/pages/dashboards/AuditLogPage';
import { ProductDashboardPage } from '@/pages/dashboards/ProductDashboardPage';
import { ReportsPage } from '@/pages/dashboards/ReportsPage';
import { HomePage } from '@/pages/home/HomePage';
import { DsrPage } from '@/pages/dsr/DsrPage';
import { CompanySetupPage } from '@/pages/auth/CompanySetupPage';
import { LoginPage } from '@/pages/auth/LoginPage';
import { OAuthPage } from '@/pages/auth/OAuthPage';
import { ProfilePage } from '@/pages/profile/ProfilePage';
import { TeamPage } from '@/pages/team/TeamPage';
import { ApplyPage } from '@/pages/leave/ApplyPage';
import { ApprovalsPage } from '@/pages/leave/ApprovalsPage';
import { CalendarPage } from '@/pages/leave/CalendarPage';
import { MyLeavePage } from '@/pages/leave/MyLeavePage';
import { PoliciesPage } from '@/pages/leave/PoliciesPage';
import { MyPayslipsPage, PayslipPage } from '@/pages/payroll/SlipPages';
import { PreviewPage, RunDetailPage, RunListPage } from '@/pages/payroll/RunPages';
import { HolidaysPage, ProfilesPage } from '@/pages/payroll/SetupPages';
import { AttendancePage } from '@/pages/attendance/AttendancePage';
import { CorrectionQueuePage, CorrectionRequestPage, RecordEditPage } from '@/pages/attendance/CorrectionPages';
import { TeamAttendancePage } from '@/pages/attendance/TeamPage';
import { TimesheetDetailPage, TimesheetPage } from '@/pages/attendance/TimesheetPages';
import { Notifications } from '@/pages/Notifications';
import { TicketDetailPage } from '@/pages/ticket/TicketDetailPage';
import { TicketFormPage } from '@/pages/ticket/TicketFormPage';
import { TicketsPage } from '@/pages/tickets/TicketsPage';

export const shellRoutes: RouteObject[] = [
  { path: '/notifications/', element: <Notifications /> },
  ...[
    '/tickets/',
    '/tickets/kanban/',
    '/tickets/list/',
    '/products/:pk/tickets/',
    '/products/:pk/tickets/kanban/',
    '/products/:pk/tickets/list/',
  ].map((path) => ({ path, element: <TicketsPage /> })),
  { path: '/tickets/create/', element: <TicketFormPage /> },
  { path: '/products/:pk/tickets/create/', element: <TicketFormPage /> },
  { path: '/tickets/:id/edit/', element: <TicketFormPage /> },
  { path: '/tickets/:id/', element: <TicketDetailPage /> },
  { path: '/products/:pk/tickets/:id/', element: <TicketDetailPage /> },
  { path: '/errors/', element: <ErrorsPage /> },
  { path: '/products/:pk/errors/', element: <ErrorsPage /> },
  { path: '/errors/create/', element: <ErrorFormPage /> },
  { path: '/products/:pk/errors/create/', element: <ErrorFormPage /> },
  { path: '/errors/:id/', element: <ErrorDetailPage /> },
  { path: '/products/:pk/errors/:error_pk/', element: <ErrorDetailPage /> },
  { path: '/products/', element: <ProductsPage /> },
  { path: '/products/create/', element: <ProductFormPage /> },
  { path: '/products/:pk/', element: <ProductDetailPage /> },
  { path: '/products/:pk/edit/', element: <ProductFormPage /> },
  { path: '/products/:pk/api/', element: <ProductApiDocsPage /> },
  { path: '/leave/', element: <MyLeavePage /> },
  { path: '/leave/apply/', element: <ApplyPage /> },
  { path: '/leave/calendar/', element: <CalendarPage /> },
  { path: '/leave/approvals/', element: <ApprovalsPage /> },
  { path: '/leave/policies/', element: <PoliciesPage /> },
  { path: '/payroll/', element: <RunListPage /> },
  { path: '/payroll/preview/', element: <PreviewPage /> },
  { path: '/payroll/runs/:id/', element: <RunDetailPage /> },
  { path: '/payroll/payslips/:id/', element: <PayslipPage /> },
  { path: '/payroll/me/', element: <MyPayslipsPage /> },
  { path: '/payroll/me/:id/', element: <PayslipPage mine /> },
  { path: '/payroll/holidays/', element: <HolidaysPage /> },
  { path: '/payroll/profiles/', element: <ProfilesPage /> },
  { path: '/attendance/', element: <AttendancePage /> },
  { path: '/attendance/team/', element: <TeamAttendancePage /> },
  { path: '/attendance/timesheet/', element: <TimesheetPage /> },
  { path: '/attendance/timesheet/:user_id/', element: <TimesheetDetailPage /> },
  { path: '/attendance/corrections/', element: <CorrectionQueuePage /> },
  { path: '/attendance/corrections/request/', element: <CorrectionRequestPage /> },
  { path: '/attendance/:id/edit/', element: <RecordEditPage /> },
  { path: '/team/', element: <TeamPage /> },
  { path: '/profile/', element: <ProfilePage /> },
  { path: '/dsr/', element: <DsrPage /> },
  { path: '/dashboards/', element: <HomePage /> },
  { path: '/dashboards/reports/', element: <ReportsPage /> },
  { path: '/dashboards/audit/', element: <AuditLogPage /> },
  { path: '/dashboards/product/:product_pk/', element: <ProductDashboardPage /> },
  { path: '/feedback/', element: <SurveysPage /> },
  { path: '/products/:pk/surveys/', element: <SurveysPage /> },
  { path: '/feedback/create/', element: <SurveyFormPage /> },
  { path: '/products/:pk/surveys/create/', element: <SurveyFormPage /> },
  { path: '/feedback/cs-hub/', element: <CsHubPage /> },
  { path: '/feedback/:id/', element: <SurveyDetailPage /> },
  { path: '/automation/', element: <RulesPage /> },
  { path: '/products/:pk/rules/', element: <RulesPage /> },
  { path: '/automation/create/', element: <RuleFormPage /> },
  { path: '/products/:pk/rules/create/', element: <RuleFormPage /> },
  { path: '/automation/:id/edit/', element: <RuleFormPage /> },
];

// Pages that need no login: no sidebar, no bootstrap.
export const publicRoutes: RouteObject[] = [
  { path: '/feedback/respond/:id/', element: <PublicSurveyPage /> },
  { path: '/login/', element: <LoginPage /> },
  { path: '/company/setup/', element: <CompanySetupPage /> },
  { path: '/oauth/authorize/', element: <OAuthPage /> },
];
