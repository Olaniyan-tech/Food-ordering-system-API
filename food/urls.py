
from django.urls import path
from .views import(
    AllFoodView, 
    AddToCartView,
    RemoveFromCartView,
    CancelCartView,
    UpdateOrderDetailView, 
    CheckOutView, 
    AllOrdersView, 
    OrderStatusUpdateView,
    OrderDetailView,
    InitializePaymentView,
    VerifyPaymentView,
    PayStackWebhookView
)

app_name = "food"
urlpatterns = [
    path("menu/", AllFoodView.as_view(), name="menu"),
    path("my-orders/", AllOrdersView.as_view(), name="my-orders"),
    path("add_to_cart/", AddToCartView.as_view(), name="add"),
    path("remove/", RemoveFromCartView.as_view(), name="remove"),
    path("cancel/", CancelCartView.as_view(), name="cancel"),
    path("order/details/", UpdateOrderDetailView.as_view(), name="order-details"),
    path("checkout/", CheckOutView.as_view(), name="checkout"),
    path("order/<int:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path("order/<int:order_id>/status/", OrderStatusUpdateView.as_view(), name="order-status"),
    path("order/<int:order_id>/pay/", InitializePaymentView.as_view(), name="initialize-payment"),
    path("order/verify/<str:reference>/", VerifyPaymentView.as_view(), name="verify-payment"),
    path("webhook/paystack/", PayStackWebhookView.as_view(), name="webhook-paystack")
]
