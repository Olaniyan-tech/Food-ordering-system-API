import hmac
import hashlib
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import status
from food.models import Food, Order
from .serializers import FoodSerializer, OrderSerializer, AddToCartSerializer, OrderDeliveryDetailSerializer
from food.services.cart_service import add_item_to_cart, remove_item_from_cart
from food.services.order_service import ( 
    cancel_order, 
    finalize_order,
    mark_preparing, 
    mark_ready, 
    mark_out_for_delivery, 
    mark_delivered
)    
from food.services.payment_service import initialize_payment, verify_payment
from food.permissions import IsStaffOrReadOnly, IsOrderOwner, IsStaff
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
import logging

logger = logging.getLogger(__name__)



class AllFoodView(generics.ListAPIView):
        queryset = Food.objects.filter(available=True)
        serializer_class = FoodSerializer
        permission_classes = [IsStaffOrReadOnly]
        

class AllOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        return Order.objects.prefetch_related("items__food").filter(user=self.request.user)


class AddToCartView(APIView):
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        

        food_id = serializer.validated_data["food"]
        quantity = serializer.validated_data["quantity"]

        try:
            food = Food.objects.get(id=food_id, available=True)
        except Food.DoesNotExist:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)

        order = add_item_to_cart(request.user, food, quantity)

        order = Order.objects.prefetch_related("items__food").get(id=order.id)
        
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RemoveFromCartView(APIView):
    def post(self, request):
        user = request.user
        item_id = request.data.get("item_id")
        action = request.data.get("action")  # 'decrease' or 'delete'

        if not action:
            return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = remove_item_from_cart(user=user, item_id=item_id, action=action)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)      

        order = Order.objects.prefetch_related("items__food").get(id=order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CancelCartView(APIView):
    def delete(self, request):
        user = request.user

        try:
            order = Order.objects.get(user=user, status="PENDING")
        except Order.DoesNotExist:
            return Response({"error": "No pending order to cancel"}, status=status.HTTP_404_NOT_FOUND)

        try:
            cancel_order(order, user=user)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message" : "Cart cancelled successfully"}, status=status.HTTP_200_OK)

class UpdateOrderDetailView(APIView):
    def patch(self, request):
        try:
            order = Order.objects.get(user=request.user, status="PENDING")
        except Order.DoesNotExist:
            return Response({"error" : "No pending order"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderDeliveryDetailSerializer(order, data=request.data, partial=True)
        
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message" : "Order details updated"}, status=status.HTTP_200_OK)


class CheckOutView(APIView):
    def post(self, request):
        user = request.user
        try:
            order = Order.objects.get(user=user, status="PENDING")

        except Order.DoesNotExist:
            return Response({"error": "No pending order to checkout"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = OrderDeliveryDetailSerializer(
            instance=order,
            data=request.data,
            context={"request": request},
            partial=True
        )

        if not serializer.is_valid():
            logger.warning(f"Checkout validation failed for user {user.username}: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()

        order = finalize_order(order, user=user)

        logger.info(f"User {user.username} checkedout for order {order.id} successfully.")
        
        return Response(
            {"message": "Order checked out successfully",
            "user" : user.username,
            "address" : order.address,
            "phone" : order.phone,
            "status" : order.status,
            "total" : order.total}, 
            status=status.HTTP_200_OK)

class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsOrderOwner]

    def get_object(self):
        order_id = self.kwargs["order_id"]
        order = get_object_or_404(Order, id=order_id)
        self.check_object_permissions(self.request, order)       
        return order

STATUS_TRANSITION_MAP = {
    "PREPARING": mark_preparing,
    "READY": mark_ready,
    "OUT FOR DELIVERY": mark_out_for_delivery,
    "DELIVERED": mark_delivered
}

class OrderStatusUpdateView(APIView):
    permission_classes = [IsStaff]

    def patch(self, request, order_id):
               
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        requested_status = request.data.get("status", "").strip().upper()
        if not requested_status:
            return Response({"error": "'status' field is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        handler = STATUS_TRANSITION_MAP.get(requested_status)
        if not handler:
            return Response({"error": f"'{requested_status}' is not a valid transition.",
                "valid_status": list(STATUS_TRANSITION_MAP.keys())},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            updated_order = handler(order, user=request.user)
        except ValidationError as e:
            return Response({"error": e.messages[0]}, status=status.HTTP_409_CONFLICT)
        
        return Response({"id": str(updated_order.id), "status": updated_order.status}, 
            status=status.HTTP_200_OK)


class InitializePaymentView(APIView):
    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            authorization_url, reference = initialize_payment(order)
        except ValidationError as e:
            return Response({"error": e.messages[0]}, status=status.HTTP_409_CONFLICT)
        
        return Response({
            "authorization_url": authorization_url,
            "reference": reference
        }, status=status.HTTP_200_OK)

class VerifyPaymentView(APIView):
    def get(self, request, reference):
        try:
            order = Order.objects.get(
                payment_reference=reference, 
                user=request.user
            )
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            payment_data = verify_payment(reference)
        except ValidationError as e:
            return Response({"error": e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        
        if payment_data["status"] == "success":
            order.payment_status = "PAID"
            order.save(update_fields=["payment_status", "updated"])

            logger.info(f"Payment verified for order {order.id} by {request.user.username}")

            return Response({
                "message": "Payment successfull",
                "order_id": order.id,
                "payment_status": order.payment_status,
                "amount_paid": payment_data["amount"] / 100
            }, status=status.HTTP_200_OK)
    
        order.payment_status = "FAILED"
        order.save(update_fields=["payment_status", "updated"])

        return Response({
            "error": "Payment failed",
            "payment_status": order.payment_status
        }, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name="dispatch")
class PayStackWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        paystack_signature = request.headers.get("x-paystack-signature")

        computed = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            request.body,
            hashlib.sha512).hexdigest()
        
        if computed != paystack_signature:
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try: 
            payload = request.data
            event = payload.get("event")
        except Exception:
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        if event == "charge.success":
            reference = payload["data"]["reference"]

            try:
                order = Order.objects.get(payment_reference=reference)
                order.payment_status = "PAID"
                order.save(update_fields=["payment_status", "updated"])
                logger.info(f"Webhook: payment confirmed for order {order.id}")
            except Order.DoesNotExist:
                pass
        
        return Response({"message": "ok"}, status=status.HTTP_200_OK)