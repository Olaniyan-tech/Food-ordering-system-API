from rest_framework.exceptions import NotFound
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
import hmac
import hashlib
from food.constants import PAYSTACK_SUCCESS_STATUS
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import status
from food.models import Food, Order
from .serializers import (
    FoodSerializer, 
    OrderSerializer, 
    AddToCartSerializer, 
    OrderDeliveryDetailSerializer, 
    ReviewSerializer
)
from food.services.cart_service import add_item_to_cart, remove_item_from_cart
from food.services.order_service import ( 
    cancel_order, 
    finalize_order,
    mark_preparing, 
    mark_ready, 
    mark_out_for_delivery, 
    mark_delivered,
    update_order_status,
    update_payment_status
)    
from food.services.payment_service import initialize_payment, verify_payment
from food.services.review_service import create_review
from food.selectors import (
    get_available_foods,
    get_available_food_by_id,
    get_user_orders,
    get_pending_order,
    get_order_by_id,
    get_user_order_by_id,
    get_order_by_reference,
    get_order_review, 
    get_food_reviews
)
from food.permissions import IsStaffOrReadOnly, IsOrderOwner, IsStaff
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class AllFoodView(generics.ListAPIView):
    serializer_class = FoodSerializer
    permission_classes = [IsStaffOrReadOnly]

    def get_queryset(self):
        return get_available_foods()
    
    @method_decorator(ratelimit(key="ip", rate="60/m", method="GET", block=True))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
        

class AllOrdersView(generics.ListAPIView):
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        return get_user_orders(self.request.user)

    @method_decorator(ratelimit(key="ip", rate="60/m", method="GET", block=True)) 
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AddToCartView(APIView):

    @method_decorator(ratelimit(key="user", rate="20/m", method="POST", block=True))
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        food_id = serializer.validated_data["food"]
        quantity = serializer.validated_data["quantity"]

        try:
            food = get_available_food_by_id(food_id)
        except Food.DoesNotExist:
            return Response({"error": "Food not found"}, status=status.HTTP_404_NOT_FOUND)       

        try:
            order = add_item_to_cart(request.user, food, quantity)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
        order = get_order_by_id(order.id)
    
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RemoveFromCartView(APIView):

    @method_decorator(ratelimit(key="user", rate="10/m", method="POST", block=True))
    def post(self, request):
        user = request.user
        item_id = request.data.get("item_id")
        action = request.data.get("action")  # 'decrease' or 'delete'

        if not action:
            return Response({"error": "Action is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = remove_item_from_cart(user=user, item_id=item_id, action=action)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)       

        order = get_order_by_id(order.id)
        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
   
class CancelOrderView(APIView):

    @method_decorator(ratelimit(key="user", rate="5/m", method="DELETE", block=True))
    def delete(self, request):
        order = get_pending_order(request.user)
        if not order:
            return Response({"error": "No Order to cancel"}, status=status.HTTP_404_NOT_FOUND)

        try:
            cancel_order(order, user=request.user)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message" : "Order cancelled successfully"}, status=status.HTTP_200_OK)


   
class UpdateOrderDetailView(APIView):

    @method_decorator(ratelimit(key="user", rate="10/m", method="PATCH", block=True))
    def patch(self, request):
        order = get_pending_order(request.user)
        if not order:
            return Response({"error" : "No pending order"}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderDeliveryDetailSerializer(order, data=request.data, partial=True)
        
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"message" : "Order details updated"}, status=status.HTTP_200_OK)


class CheckOutView(APIView):

    @method_decorator(ratelimit(key="user", rate="5/m", method="POST", block=True))
    def post(self, request):
        user = request.user

        order = get_pending_order(user=user)
        if not order:
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

        try:
            order = finalize_order(order, user=user)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)

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

    @method_decorator(ratelimit(key="user", rate="10/m", method="GET", block=True))
    def get(self, request, *args, **kwargs):
            return super().get(request, *args, **kwargs)
        
    def get_object(self):
        try:
            order = get_user_order_by_id(self.kwargs["order_id"], self.request.user)
        except Order.DoesNotExist:
            raise NotFound("Order not found")
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

    @method_decorator(ratelimit(key="user", rate="30/m", method="PATCH", block=True))
    def patch(self, request, order_id):  
        try:
            order = get_order_by_id(order_id)
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
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_409_CONFLICT)
        
        return Response({"id": str(updated_order.id), "status": updated_order.status}, 
            status=status.HTTP_200_OK)
    

class InitializePaymentView(APIView):

    @method_decorator(ratelimit(key="user", rate="5/m", method="POST", block=True))
    def post(self, request, order_id):
        try:
            order = get_user_order_by_id(order_id, request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            authorization_url, reference = initialize_payment(order)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_409_CONFLICT)
        
        return Response({
            "authorization_url": authorization_url,
            "reference": reference
        }, status=status.HTTP_200_OK)
                

class VerifyPaymentView(APIView):
       
    @method_decorator(ratelimit(key="user", rate="10/m", method="GET", block=True))
    def get(self, request, reference):
        try:
            order = get_order_by_reference(reference, request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            payment_data = verify_payment(reference)
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
                
        if payment_data["status"] == PAYSTACK_SUCCESS_STATUS:
            update_payment_status(order, "PAID")
            logger.info(f"Payment verified for order {order.id} by {request.user.username}")

            return Response({
                "message": "Payment successful",
                "order_id": order.id,
                "payment_status": order.payment_status,
                "amount_paid": payment_data["amount"] / 100
            }, status=status.HTTP_200_OK)
    

        update_payment_status(order, 'FAILED')
        logger.info(f"Payment failed for order {order.id} by {request.user.username}")

        return Response({
            "error": "Payment failed",
            "payment_status": order.payment_status
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
        

@method_decorator(csrf_exempt, name="dispatch")
class PayStackWebhookView(APIView):
    permission_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        paystack_signature = request.headers.get("x-paystack-signature")

        if not paystack_signature:
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        computed = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
            request.body,
            hashlib.sha512).hexdigest()
        
        if not hmac.compare_digest(computed, paystack_signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try: 
            payload = request.data
            event = payload.get("event")
            reference = payload.get("data", {}).get("reference")
        except Exception:
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        if not reference:
            logger.warning("Webhook received with no reference")
            return Response({"message": "ok"}, status=status.HTTP_200_OK)
        
        try:
            order = Order.objects.get(payment_reference=reference)
        except Order.DoesNotExist:
            logger.warning(f"No order found with reference {reference}")
            return Response({"message": "ok"}, status=status.HTTP_200_OK)

        if event == "charge.success":
            update_payment_status(order, "PAID")
            logger.info(f"Webhook: Payment confirmed for order {order.id}")
        else:
            update_payment_status(order, "FAILED")
            logger.info(f"Webhook: Payment failed for order {order.id} (event: {event})")          
        
        return Response({"message": "ok"}, status=status.HTTP_200_OK)

        
class CreateReviewView(APIView):

    @method_decorator(ratelimit(key="user", rate="10/m", method="POST", block=True))
    def post(self, request, order_id):
        try:
            order = get_user_order_by_id(order_id, request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
    
        serializer = ReviewSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            review = create_review(
                order=order, 
                user=request.user, 
                validated_data=serializer.validated_data
            )
        except ValidationError as e:
            return Response({"error": e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"User {request.user.username} reviewed Order {order_id}")

        return Response({
            "message": "Review submitted successfully",
            "data": ReviewSerializer(review).data
        }, status=status.HTTP_201_CREATED)


class UpdateReviewView(APIView):

    @method_decorator(ratelimit(key="user", rate="10/m", method="PATCH", block=True))
    def patch(self, request, order_id):
        try:
            order = get_user_order_by_id(order_id, request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        review = get_order_review(order)
        if not review:
            return Response({"error": "No review found"}, status=status.HTTP_404_NOT_FOUND)

        if review.user != request.user:
            return Response({"error": "You can only edit your own review"}, status=status.HTTP_403_FORBIDDEN)

        serializer = ReviewSerializer(review, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        logger.info(f"User {request.user.username} updated review for Order {order_id}")

        return Response({
            "message": "Review updated successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class OrderReviewDetailView(APIView):
    
    @method_decorator(ratelimit(key="user", rate="5/m", method="GET", block=True))
    def get(self, request, order_id):
        try:
            order = get_user_order_by_id(order_id, request.user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        review = get_order_review(order)
        if not review:
            return Response({"error": "No review found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(ReviewSerializer(review).data, status=status.HTTP_200_OK)

        
class FoodReviewsView(generics.ListAPIView):
    serializer_class = ReviewSerializer
    permission_classes = []

    @method_decorator(ratelimit(key="ip", rate="5/m", method="GET", block=True))
    def get(self, request, *args, **kwargs):
            return super().get(request, *args, **kwargs)
   
    def get_queryset(self):
        return get_food_reviews(self.kwargs["food_id"])
        
