from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.ProductShellView.as_view(), name="product_list"),
    path("create/", views.ProductAdminShellView.as_view(), name="product_create"),
    path("<int:pk>/", views.ProductPageView.as_view(), name="product_detail"),
    path("<int:pk>/edit/", views.ProductEditView.as_view(), name="product_edit"),
    path("<int:pk>/api/", views.ProductPageView.as_view(), name="product_api"),
    # Product-scoped routes
    path("<int:pk>/errors/", views.ProductErrorShellView.as_view(), name="product_errors"),
    path("<int:pk>/errors/create/", views.ProductErrorShellView.as_view(), name="product_error_create"),
    path("<int:pk>/errors/<int:error_pk>/", views.ProductErrorDetailView.as_view(), name="product_error_detail"),
    path("<int:pk>/tickets/", views.ProductTicketKanbanView.as_view(), name="product_board"),
    path("<int:pk>/tickets/kanban/", views.ProductTicketKanbanView.as_view(), name="product_ticket_kanban"),
    path("<int:pk>/tickets/list/", views.ProductTicketListView.as_view(), name="product_tickets"),
    path("<int:pk>/tickets/create/", views.ProductTicketCreateView.as_view(), name="product_ticket_create"),
    path("<int:pk>/tickets/<int:ticket_pk>/", views.ProductTicketDetailView.as_view(), name="product_ticket_detail"),
    path("<int:pk>/surveys/", views.ProductSurveyListView.as_view(), name="product_surveys"),
    path("<int:pk>/surveys/create/", views.ProductSurveyCreateView.as_view(), name="product_survey_create"),
    path("<int:pk>/rules/", views.ProductRuleListView.as_view(), name="product_rules"),
    path("<int:pk>/rules/create/", views.ProductRuleCreateView.as_view(), name="product_rule_create"),
]
