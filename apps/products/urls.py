from django.urls import path

from apps.errors import views as error_views
from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("create/", views.ProductCreateView.as_view(), name="product_create"),
    path("<int:pk>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("<int:pk>/edit/", views.ProductEditView.as_view(), name="product_edit"),
    path("<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product_delete"),
    path("<int:pk>/api-keys/create/", views.APIKeyCreateView.as_view(), name="api_key_create"),
    path("api-keys/<int:pk>/revoke/", views.APIKeyRevokeView.as_view(), name="api_key_revoke"),
    path("<int:pk>/versions/add/", views.VersionCreateView.as_view(), name="version_create"),
    path("<int:pk>/versions/<int:version_pk>/delete/", views.VersionDeleteView.as_view(), name="version_delete"),
    path("<int:pk>/access/add/", views.ProductAccessAddView.as_view(), name="product_access_add"),
    path("<int:pk>/access/<int:user_pk>/remove/", views.ProductAccessRemoveView.as_view(), name="product_access_remove"),
    # Product-scoped routes
    path("<int:pk>/errors/", views.ProductErrorListView.as_view(), name="product_errors"),
    path("<int:pk>/errors/create/", views.ProductErrorCreateView.as_view(), name="product_error_create"),
    path("<int:pk>/errors/<int:error_pk>/", views.ProductErrorDetailView.as_view(), name="product_error_detail"),
    path("<int:pk>/errors/<int:error_pk>/convert-to-ticket/", error_views.ErrorConvertToTicketView.as_view(), name="product_error_convert_to_ticket"),
    path("<int:pk>/tickets/", views.ProductTicketKanbanView.as_view(), name="product_board"),
    path("<int:pk>/tickets/kanban/", views.ProductTicketKanbanView.as_view(), name="product_ticket_kanban"),
    path("<int:pk>/tickets/list/", views.ProductTicketListView.as_view(), name="product_tickets"),
    path("<int:pk>/tickets/create/", views.ProductTicketCreateView.as_view(), name="product_ticket_create"),
    path("<int:pk>/tickets/bulk-delete/", views.ProductTicketBulkDeleteView.as_view(), name="product_ticket_bulk_delete"),
    path("<int:pk>/tickets/<int:ticket_pk>/", views.ProductTicketDetailView.as_view(), name="product_ticket_detail"),
    path("<int:pk>/surveys/", views.ProductSurveyListView.as_view(), name="product_surveys"),
    path("<int:pk>/surveys/create/", views.ProductSurveyCreateView.as_view(), name="product_survey_create"),
    path("<int:pk>/rules/", views.ProductRuleListView.as_view(), name="product_rules"),
    path("<int:pk>/rules/create/", views.ProductRuleCreateView.as_view(), name="product_rule_create"),
    path("<int:pk>/milestones/add/", views.ProductMilestoneAddView.as_view(), name="milestone_add"),
    path("milestones/<int:pk>/toggle/", views.ProductMilestoneToggleView.as_view(), name="milestone_toggle"),
    path("milestones/<int:pk>/delete/", views.ProductMilestoneDeleteView.as_view(), name="milestone_delete"),
]
