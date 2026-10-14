import { lazy } from 'react';
import type { RouteObject } from 'react-router-dom';

// Each page is its own file that loads when the page is first opened, so the first load downloads the shell, not the whole app.
const ErrorDetailPage = lazy(() => import('@/pages/errors/ErrorDetailPage').then((m) => ({ default: m.ErrorDetailPage })));
const ErrorFormPage = lazy(() => import('@/pages/errors/ErrorFormPage').then((m) => ({ default: m.ErrorFormPage })));
const ErrorsPage = lazy(() => import('@/pages/errors/ErrorsPage').then((m) => ({ default: m.ErrorsPage })));
const ProductApiDocsPage = lazy(() => import('@/pages/products/ProductApiDocsPage').then((m) => ({ default: m.ProductApiDocsPage })));
const ProductDetailPage = lazy(() => import('@/pages/products/ProductDetailPage').then((m) => ({ default: m.ProductDetailPage })));
const ProductFormPage = lazy(() => import('@/pages/products/ProductFormPage').then((m) => ({ default: m.ProductFormPage })));
const ProductsPage = lazy(() => import('@/pages/products/ProductsPage').then((m) => ({ default: m.ProductsPage })));
const RuleFormPage = lazy(() => import('@/pages/automation/RuleFormPage').then((m) => ({ default: m.RuleFormPage })));
const RulesPage = lazy(() => import('@/pages/automation/RulesPage').then((m) => ({ default: m.RulesPage })));
const CsHubPage = lazy(() => import('@/pages/feedback/CsHubPage').then((m) => ({ default: m.CsHubPage })));
const PublicSurveyPage = lazy(() => import('@/pages/feedback/PublicSurveyPage').then((m) => ({ default: m.PublicSurveyPage })));
const SurveyDetailPage = lazy(() => import('@/pages/feedback/SurveyDetailPage').then((m) => ({ default: m.SurveyDetailPage })));
const SurveyFormPage = lazy(() => import('@/pages/feedback/SurveyFormPage').then((m) => ({ default: m.SurveyFormPage })));
const SurveysPage = lazy(() => import('@/pages/feedback/SurveysPage').then((m) => ({ default: m.SurveysPage })));
const AuditLogPage = lazy(() => import('@/pages/dashboards/AuditLogPage').then((m) => ({ default: m.AuditLogPage })));
const ProductDashboardPage = lazy(() => import('@/pages/dashboards/ProductDashboardPage').then((m) => ({ default: m.ProductDashboardPage })));
const ReportsPage = lazy(() => import('@/pages/dashboards/ReportsPage').then((m) => ({ default: m.ReportsPage })));
const HomePage = lazy(() => import('@/pages/home/HomePage').then((m) => ({ default: m.HomePage })));
const DsrPage = lazy(() => import('@/pages/dsr/DsrPage').then((m) => ({ default: m.DsrPage })));
const CompanySetupPage = lazy(() => import('@/pages/auth/CompanySetupPage').then((m) => ({ default: m.CompanySetupPage })));
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const OAuthPage = lazy(() => import('@/pages/auth/OAuthPage').then((m) => ({ default: m.OAuthPage })));
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage').then((m) => ({ default: m.ProfilePage })));
const TeamPage = lazy(() => import('@/pages/team/TeamPage').then((m) => ({ default: m.TeamPage })));
const MemberPage = lazy(() => import('@/pages/team/MemberPage').then((m) => ({ default: m.MemberPage })));
const ApplyPage = lazy(() => import('@/pages/leave/ApplyPage').then((m) => ({ default: m.ApplyPage })));
const ApprovalsPage = lazy(() => import('@/pages/leave/ApprovalsPage').then((m) => ({ default: m.ApprovalsPage })));
const CalendarPage = lazy(() => import('@/pages/leave/CalendarPage').then((m) => ({ default: m.CalendarPage })));
const MyLeavePage = lazy(() => import('@/pages/leave/MyLeavePage').then((m) => ({ default: m.MyLeavePage })));
const PoliciesPage = lazy(() => import('@/pages/leave/PoliciesPage').then((m) => ({ default: m.PoliciesPage })));
const MyPayslipsPage = lazy(() => import('@/pages/payroll/SlipPages').then((m) => ({ default: m.MyPayslipsPage })));
const PayslipPage = lazy(() => import('@/pages/payroll/SlipPages').then((m) => ({ default: m.PayslipPage })));
const PreviewPage = lazy(() => import('@/pages/payroll/RunPages').then((m) => ({ default: m.PreviewPage })));
const RunDetailPage = lazy(() => import('@/pages/payroll/RunPages').then((m) => ({ default: m.RunDetailPage })));
const RunListPage = lazy(() => import('@/pages/payroll/RunPages').then((m) => ({ default: m.RunListPage })));
const HolidaysPage = lazy(() => import('@/pages/payroll/SetupPages').then((m) => ({ default: m.HolidaysPage })));
const ProfilesPage = lazy(() => import('@/pages/payroll/SetupPages').then((m) => ({ default: m.ProfilesPage })));
const AttendancePage = lazy(() => import('@/pages/attendance/AttendancePage').then((m) => ({ default: m.AttendancePage })));
const CorrectionQueuePage = lazy(() => import('@/pages/attendance/CorrectionPages').then((m) => ({ default: m.CorrectionQueuePage })));
const CorrectionRequestPage = lazy(() => import('@/pages/attendance/CorrectionPages').then((m) => ({ default: m.CorrectionRequestPage })));
const RecordEditPage = lazy(() => import('@/pages/attendance/CorrectionPages').then((m) => ({ default: m.RecordEditPage })));
const TeamAttendancePage = lazy(() => import('@/pages/attendance/TeamPage').then((m) => ({ default: m.TeamAttendancePage })));
const TimesheetDetailPage = lazy(() => import('@/pages/attendance/TimesheetPages').then((m) => ({ default: m.TimesheetDetailPage })));
const TimesheetPage = lazy(() => import('@/pages/attendance/TimesheetPages').then((m) => ({ default: m.TimesheetPage })));
const Notifications = lazy(() => import('@/pages/Notifications').then((m) => ({ default: m.Notifications })));
const TicketDetailPage = lazy(() => import('@/pages/ticket/TicketDetailPage').then((m) => ({ default: m.TicketDetailPage })));
const TicketFormPage = lazy(() => import('@/pages/ticket/TicketFormPage').then((m) => ({ default: m.TicketFormPage })));
const TicketsPage = lazy(() => import('@/pages/tickets/TicketsPage').then((m) => ({ default: m.TicketsPage })));

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
  { path: '/team/:id/', element: <MemberPage /> },
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
