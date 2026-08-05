from django.urls import path

from . import api_views

app_name = "vendors_api"

urlpatterns = [
    path("register/", api_views.VendorRegisterView.as_view(), name="register"),
    path("store/", api_views.MyStoreView.as_view(), name="my-store"),
    path("stores/<slug:slug>/", api_views.PublicStoreDetailView.as_view(), name="public-store-detail"),
    path("store/resubmit/", api_views.StoreResubmitView.as_view(), name="store-resubmit"),
    path(
        "admin/applications/",
        api_views.VendorApplicationListView.as_view(),
        name="admin-applications",
    ),
    path(
        "admin/applications/<int:pk>/approve/",
        api_views.VendorApproveView.as_view(),
        name="admin-approve",
    ),
    path(
        "admin/applications/<int:pk>/reject/",
        api_views.VendorRejectView.as_view(),
        name="admin-reject",
    ),
]
