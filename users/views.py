from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterSerializer
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from drf_spectacular.utils import extend_schema
import logging
from django.conf import settings


DEBUG = settings.DEBUG
logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: RegisterSerializer})
    def post(self, request):
        logger.info(f"Incoming registration request: {request.data}")

        try:
            serializer = RegisterSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                logger.info(f"New user registered: {user.email if hasattr(user, 'email') else user.username}")
                return Response({
                    "message": "Account created successfully. Please log in to continue",
                    "username": user.username,
                    "email": user.email,
                    "phone": user.profile.phone},
                    status=status.HTTP_201_CREATED)
        
            logger.warning(f"Registration failed: {serializer.errors}")
            return Response({
                "message": "Registration failed. Check input.",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Unexpected error during registration")
            return Response({
                "message": "Server error occurred during registration"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CookieTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try: 
            response_data = super().post(request, *args, **kwargs).data

            response = Response({"message" : "Login successful"}, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=response_data['access'],
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=30*60, #30 minutes
                path='/'
            )

            response.set_cookie(
                key='refresh_token',
                value=response_data['refresh'],
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=7*24*60*60, # 7 days
                path='/'
            )
            return response
        
        except InvalidToken:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({"error": "Login failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({"error" : "Refresh token not provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            serializer = self.get_serializer(data={"refresh": refresh_token})
            serializer.is_valid(raise_exception=True)
            new_access = serializer.validated_data['access']

            response = Response({"message": "Access token refreshed"}, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=new_access,
                httponly=True,
                samesite='Lax' if DEBUG else 'None',
                secure=not DEBUG,
                max_age=30*60,
                path='/'
            )
            
            return response
        
        except TokenError as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            return Response({"error": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f"Refresh token error: {str(e)}")
            return Response({"error": "Could not refresh token"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: None})
    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
                logger.info("Refresh token blacklisted")
            except TokenError:
                logger.warning("Refresh token already invalid")
            except Exception as e:
                logger.error(f"Unexpected error during logout: {str(e)}")
        
        response = Response({"message" : "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie("access_token", path='/')
        response.delete_cookie("refresh_token", path='/')
        response['Cache-Control'] = 'no-store, must-revalidate'

        return response

class UserProfileView(APIView):

    @extend_schema(responses={200: None})
    def get(self, request):
        return Response({
            "username": request.user.username,
            "email": request.user.email
        })