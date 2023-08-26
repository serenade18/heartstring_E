import hashlib
import hmac
import json
from datetime import datetime
from io import BytesIO

import qrcode
from django.contrib.sites import requests
from django.core.files.base import ContentFile
from django.shortcuts import render, get_object_or_404
from djoser.views import UserViewSet
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from heartstringApp import serializers
from heartstringApp.models import Ticket, Payment, Play, Video, VideoPayment, PlayCast, Bogof, OtherOffers, PlayTime, \
    VideoCast, VideoAvailability, UserAccount
from heartstringApp.serializers import TicketsSerializer, PaymentSerializer, PlaySerializer, \
    PlayCastSerializer, OfferSerializer, VideoSerializer, VideoCastSerializer, VideoPaymentSerializer, \
    VideoAvailabilitySerializer, OtherOfferSerializer, PlayDateSerializer, UserCreateSerializer, UserAccountSerializer


# Create your views here.


class SuperUserRegistrationView(UserViewSet):
    # Override get_permissions method to allow unauthenticated access only for create_superuser action
    def get_permissions(self):
        if self.action == "create_superuser":
            return [AllowAny()]
        return super().get_permissions()

    @action(["post"], detail=False, url_path="superuser")
    def create_superuser(self, request, *args, **kwargs):
        serializer = serializers.UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create the user object using serializer.save()
        user = serializer.save(user_type='admin')  # Set the user_type to 'admin'

        if user:
            # Set user as a superuser and staff
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()

            return Response({"error": False, "message": "Admin account created and activated successfully"}, status=status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserAccountUpdateView(generics.UpdateAPIView):
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # If the requesting user is an admin and a user_id is provided in the URL, update the specified user's details
        user_id = self.kwargs.get('user_id')
        if user_id and self.request.user.is_staff:
            return get_object_or_404(UserAccount, id=user_id)

        # Otherwise, update the details of the authenticated user
        return self.request.user


class UserAccountDeleteView(generics.DestroyAPIView):
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    queryset = UserAccount.objects.all()  # Update with the correct queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # You can add additional logic here if needed

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code_image = buffer.getvalue()

    return qr_code_image


class TicketViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated | IsAdminUser]  # Allow both authenticated users and admin users

    def list(self, request):
        if request.user.is_staff:  # Check if the user is an admin
            tickets = Ticket.objects.all()  # Retrieve all tickets in the database
        else:
            tickets = Ticket.objects.filter(user=request.user)  # Filter tickets for regular users

        serializer = TicketsSerializer(tickets, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Tickets List Data", "data": serializer.data}

        return Response(response_dict)


    def create(self, request):
        try:
            serializer = TicketsSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            ticket = serializer.save(user=request.user)

            # Generate QR code after successful payment
            if ticket.purchased:
                qr_code_data = f"M-Pesa Shortcode: {ticket.mpesa_shortcode}\n"
                qr_code_data += f"Customer Name: {request.user.username}\n"
                qr_code_data += f"Ticket Number/ID: {ticket.ticket_number}\n"
                qr_code_data += f"Number of Tickets: {ticket.number_of_tickets}\n"

                qr_code_image = generate_qr_code(qr_code_data)

                # Save the QR code to the ticket
                ticket.qr_code.save("qr_code.png", ContentFile(qr_code_image))
                ticket.save()

            dict_response = {"error": False, "message": "Ticket Bought Successfully"}
        except:
            dict_response = {"error": True, "message": "Error During Saving Ticket Data"}

        return Response(dict_response)

    def retrieve(self, request, pk=None):
        queryset = Ticket.objects.filter(user=request.user)
        tickets = get_object_or_404(queryset, pk=pk)
        serializer = TicketsSerializer(tickets, context={"request": request})

        serializer_data = serializer.data
        dict_response = {"error": False, "message": "Single data fetch", "data": serializer_data}

        return Response(dict_response)


class PaymentViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        payments = Payment.objects.filter(user=request.user)
        serializer = PaymentSerializer(payments, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Payments List Data", "data": serializer.data}

        return Response(response_dict)

    @action(detail=False, methods=["post"])
    def initiate_payment(self, request):
        ticket_id = request.data.get("ticket_id")
        ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)

        payment_method = request.data.get("payment_method")
        if payment_method == "mpesa":
            # First call: Get SID
            url_get_sid = "https://apis.ipayafrica.com/payments/v2/transact/token"

            payload_get_sid = {
                "amount": str(ticket.total_amount),
                "oid": str(ticket_id),
                "inv": str(ticket_id),
                "vid": "hstring",  # Replace with your vendor ID
                "curr": "KES",
            }

            # Generate the hash using HMAC-SHA256 algorithm
            hash_data = "".join(f"{key}{value}" for key, value in payload_get_sid.items() if key != "hash")
            secret_key = "YOUR_SECRET_KEY"  # Replace with your secret key
            hash_string = hmac.new(secret_key.encode(), hash_data.encode(), hashlib.sha256).hexdigest()

            payload_get_sid["hash"] = hash_string

            response_get_sid = requests.post(url_get_sid, json=payload_get_sid)
            if response_get_sid.status_code == 200:
                response_data_sid = response_get_sid.json()
                sid = response_data_sid.get("sid")
            else:
                return Response({"success": False, "message": "Error retrieving SID."})

            # Second call: Initiate payment
            url_push_payment = "https://apis.ipayafrica.com/payments/v2/transact/push/mpesa"

            payload_push_payment = {
                "phone": request.user.phone,
                "sid": sid,
                "vid": "hstring",  # Replace with your vendor ID
            }

            # Generate the hash for the second call
            hash_data_push = "".join(f"{key}{value}" for key, value in payload_push_payment.items() if key != "hash")
            hash_string_push = hmac.new(secret_key.encode(), hash_data_push.encode(), hashlib.sha256).hexdigest()

            payload_push_payment["hash"] = hash_string_push

            response_push_payment = requests.post(url_push_payment, json=payload_push_payment)
            if response_push_payment.status_code == 200:
                response_data_push = response_push_payment.json()

                if response_data_push.get("status") == 1:
                    # Payment request successful
                    # Generate a QR code based on the payment details
                    qr_code_data = response_data_push.get("text")
                    qr_code = qrcode.make(qr_code_data)

                    # Save the QR code to a file or return it as a response
                    qr_code.save("payment_qrcode.png")

                    # Associate the payment with the ticket
                    ticket.payment_status = "Pending"
                    ticket.qr_code = qr_code
                    ticket.save()

                    return Response({"success": True, "message": "Payment request sent to MPESA number."})
                else:
                    return Response({"success": False, "message": "Payment request failed."})
            else:
                return Response({"success": False, "message": "Error occurred during payment request."})

        elif payment_method == "card":
            # Retrieve card details from the request data
            # card_number = request.data.get("card_number")
            # card_expiry = request.data.get("card_expiry")
            # card_cvv = request.data.get("card_cvv")
            # card_holder_name = request.data.get("card_holder_name")

            # Implement logic to process the card payment

            # Generate a QR code based on the payment details
            qr_code = qrcode.make("Card Payment")

            # Save the QR code to a file or return it as a response
            qr_code.save("payment_qrcode.png")

            # Associate the payment with the ticket
            ticket.payment_status = "Pending"  # Set the payment status to pending or any appropriate value
            ticket.qr_code = qr_code  # Save the generated QR code to the ticket
            ticket.save()

            return Response({"success": True, "message": "Card payment successful."})
        else:
            # Invalid payment method, return an error response
            return Response({"success": False, "message": "Invalid payment method."})

    def retrieve(self, request, pk=None):
        queryset = Payment.objects.filter(user=request.user)
        payments = get_object_or_404(queryset, pk=pk)
        serializer = PaymentSerializer(payments, context={"request": request})
        return Response({"error": False, "message": "Single Data Fetch", "data": serializer.data})


class PlayViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def list(self, request):
        plays = Play.objects.all()
        serializer = PlaySerializer(plays, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Plays List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)

        try:
            serializer = PlaySerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                play_instance = serializer.save()

                # Access Play id
                play_id = play_instance.id

                # Access saved serializer and save play cast
                play_cast_list = []
                for i in range(len(request.data.getlist("play_casts.image"))):
                    play_cast_data = {
                        "play_id": play_id,
                        "image": request.data.getlist("play_casts.image")[i],
                        "real_name": request.data.getlist("play_casts.real_name")[i],
                        "cast_name": request.data.getlist("play_casts.cast_name")[i],
                    }
                    play_cast_list.append(play_cast_data)
                print("Play Cast List:", play_cast_list)

                # Save play cast data to table
                serializer1 = PlayCastSerializer(data=play_cast_list, many=True, context={"request": request})
                if serializer1.is_valid():
                    serializer1.save()
                else:
                    print("Play Cast Serializer Validation Errors:", serializer1.errors)

                # Access saved serializer and save play offers
                play_offers_list = []
                for i in range(len(request.data.getlist("play_offers.bogof"))):
                    play_offer_data = {
                        "play_id": play_id,
                        "bogof": request.data.getlist("play_offers.bogof")[i],
                        "offer_day": request.data.getlist("play_offers.offer_day")[i],
                        "number_of_tickets": request.data.getlist("play_offers.number_of_tickets")[i],
                        "promo_code": request.data.getlist("play_offers.promo_code")[i],
                    }
                    play_offers_list.append(play_offer_data)
                print("Bogof Offers List:", play_offers_list)

                # Save play offer data to table
                serializer2 = OfferSerializer(data=play_offers_list, many=True, context={"request": request})
                if serializer2.is_valid():
                    serializer2.save()
                else:
                    print("Offer Serializer Validation Errors:", serializer2.errors)

                # Access saved serializer and save other offers
                other_offers_list = []
                for i in range(len(request.data.getlist("other_offers.offers_name"))):
                    other_offer_data = {
                        "play_id": play_id,
                        "offers_name": request.data.getlist("other_offers.offers_name")[i],
                        "offer_day": request.data.getlist("other_offers.offer_day")[i],
                        "promo_code": request.data.getlist("other_offers.promo_code")[i],
                        "percentage": request.data.getlist("other_offers.percentage")[i],
                        "number_of_tickets": request.data.getlist("other_offers.number_of_tickets")[i]
                    }
                    other_offers_list.append(other_offer_data)
                print("Other Offers List:", other_offers_list)

                # Save other offers to table
                serializer3 = OtherOfferSerializer(data=other_offers_list, many=True, context={"request": request})
                if serializer3.is_valid():
                    serializer3.save()
                else:
                    print("Offer Serializer Validation Errors:", serializer3.errors)

                # Access saved serializer and save play date
                play_date_list = []
                for i in range(len(request.data.getlist("play_dates.play_date"))):
                    play_date_data = {
                        "play_id": play_id,
                        "play_date": request.data.getlist("play_dates.play_date")[i],
                        "time1": request.data.getlist("play_dates.time1")[i],
                        "time2": request.data.getlist("play_dates.time2")[i],
                        "time3": request.data.getlist("play_dates.time3")[i]
                    }
                    play_date_list.append(play_date_data)
                print("Play Dates List:", play_date_list)

                # Save other offers to table
                serializer4 = PlayDateSerializer(data=play_date_list, many=True, context={"request": request})
                if serializer4.is_valid():
                    serializer4.save()
                else:
                    print("Offer Serializer Validation Errors:", serializer3.errors)

                dict_response = {"error": False, "message": "Play added successfully"}
            else:
                dict_response = {"error": True, "message": "Validation Error", "errors": serializer.errors}
        except Exception as e:
            dict_response = {"error": True, "message": "Error Adding Play to Database"}

        return Response(dict_response,
                        status=status.HTTP_201_CREATED if not dict_response["error"] else status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "Unauthorized access"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            queryset = Play.objects.all()
            play = get_object_or_404(queryset, pk=pk)
            serializer = PlaySerializer(play, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            dict_response = {"error": False, "message": "Play Updated Successfully"}
        except:
            dict_response = {"error": True, "message": "Play Not Updated Successfully"}

        return Response(dict_response)

    def retrieve(self, request, pk=None):
        queryset = Play.objects.all()
        play = get_object_or_404(queryset, pk=pk)
        serializer = PlaySerializer(play, context={"request": request})

        serializer_data = serializer.data
        # Access play_casts associated with the current play
        play_casts = PlayCast.objects.filter(play_id=serializer_data["id"])
        play_casts_serializer = PlayCastSerializer(play_casts, many=True)
        serializer_data["play_casts"] = play_casts_serializer.data

        # Access play_offers associated with the current play
        play_offers = Bogof.objects.filter(play_id=serializer_data["id"])
        play_offers_serializer = OfferSerializer(play_offers, many=True)
        serializer_data["play_offers"] = play_offers_serializer.data

        # Access other_offers associated with the current play
        other_offers = OtherOffers.objects.filter(play_id=serializer_data["id"])
        other_offers_serializer = OtherOfferSerializer(other_offers, many=True)
        serializer_data["other_offers"] = other_offers_serializer.data

        # Access play_date associated with the current play
        play_dates = PlayTime.objects.filter(play_id=serializer_data["id"])
        play_dates_serializer = PlayDateSerializer(play_dates, many=True)
        serializer_data["play_dates"] = play_dates_serializer.data

        return Response({"error": False, "message": "Single Data Fetch", "data": serializer_data})

    def destroy(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)

        try:
            queryset = Play.objects.all()
            plays = get_object_or_404(queryset, pk=pk)
            plays.delete()
            dict_response = {"error": False, "message": "Play Deleted Successfully"}
        except:
            dict_response = {"error": True, "message": "Play Not Deleted Successfully"}

        return Response(dict_response)


class PlayCastViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # play_cast = PlayCast.objects.filter(user=request.user)
        play_cast = PlayCast.objects.all()
        serializer = PlayCastSerializer(play_cast, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Play Cast List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            serializer = PlayCastSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                dict_response = {"error": False, "message": "Cast Created Successfully"}
            else:
                dict_response = {"error": True, "message": "Validation Error", "errors": serializer.errors}
        except Exception as e:
            print("Error during video creation:", e)
            dict_response = {"error": True, "message": "Error During Creating Video"}

        return Response(dict_response,
                        status=status.HTTP_201_CREATED if not dict_response["error"] else status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        queryset = PlayCast.objects.all()
        play_cast = get_object_or_404(queryset, pk=pk)
        serializer = PlayCastSerializer(play_cast, context={"request": request})
        return Response({"error": False, "message": "Single Data Fetch", "data": serializer.data})

    def update(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            queryset = PlayCast.objects.all()
            play_cast = get_object_or_404(queryset, pk=pk)
            serializer = PlayCastSerializer(play_cast, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            dict_response = {"error": False, "message": "Payment Re-Processed Successfully"}
        except:
            dict_response = {"error": True, "message": "An Error Occurred"}

        return Response(dict_response)

    def destroy(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)

        queryset = PlayCast.objects.all()
        play_cast = get_object_or_404(queryset, pk=pk)
        play_cast.delete()
        return Response({"error": False, "message": "Payment Removed"})


class OffersVIewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # play_cast = PlayCast.objects.filter(user=request.user)
        offers = Bogof.objects.all()
        serializer = OfferSerializer(offers, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Offers List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            serializer = OfferSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            dict_response = {"error": False, "message": "Offer Added Successfully"}
        except:
            dict_response = {"error": True, "message": "Error performing task"}

        return Response(dict_response)

    def retrieve(self, request, pk=None):
        queryset = Bogof.objects.all()
        offers = get_object_or_404(queryset, pk=pk)
        serializer = OfferSerializer(offers, context={"request": request})
        return Response({"error": False, "message": "Single Data Fetch", "data": serializer.data})

    def update(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            queryset = Bogof.objects.all()
            offers = get_object_or_404(queryset, pk=pk)
            serializer = OfferSerializer(offers, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            dict_response = {"error": False, "message": "Payment Re-Processed Successfully"}
        except:
            dict_response = {"error": True, "message": "An Error Occurred"}

        return Response(dict_response)

    def destroy(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)

        queryset = Bogof.objects.all()
        offers = get_object_or_404(queryset, pk=pk)
        offers.delete()
        return Response({"error": False, "message": "Payment Removed"})


class VideoViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def list(self, request):
        videos = Video.objects.all()
        serializer = VideoSerializer(videos, many=True, context={"request": request})
        response_dict = {"error": False, "message": "All Videos List Data", "data": serializer.data}
        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            print(request.data)
            serializer = VideoSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                video_instance = serializer.save()

                # Access Video id
                video_id = video_instance.id

                # Access saved serializer and save video cast
                video_cast_list = []
                for i in range(len(request.data.getlist("video_casts.real_name"))):
                    video_cast_data = {
                        "video_id": video_id,
                        "image": request.data.getlist("video_casts.image")[i],
                        "real_name": request.data.getlist("video_casts.real_name")[i],
                        "cast_name": request.data.getlist("video_casts.cast_name")[i],
                    }
                    video_cast_list.append(video_cast_data)
                print("Video Cast List:", video_cast_list)

                # Save video cast data to table
                serializer1 = VideoCastSerializer(data=video_cast_list, many=True, context={"request": request})
                if serializer1.is_valid():
                    serializer1.save()
                else:
                    print("Video Cast Serializer Validation Errors:", serializer1.errors)

                # Access saved serializer and save video availability
                video_available_list = []
                for i in range(len(request.data.getlist("video_available.three_days"))):
                    video_available_data = {
                        "video_id": video_id,
                        "three_days": request.data.getlist("video_available.three_days")[i],
                        "three_price": request.data.getlist("video_available.three_price")[i],
                        "seven_days": request.data.getlist("video_available.seven_days")[i],
                        "seven_price": request.data.getlist("video_available.seven_price")[i],
                        "fourteen_days": request.data.getlist("video_available.fourteen_days")[i],
                        "fourteen_price": request.data.getlist("video_available.fourteen_price")[i]
                    }
                    video_available_list.append(video_available_data)
                print("Video available List:", video_available_list)

                # Save play cast data to table
                serializer2 = VideoAvailabilitySerializer(data=video_available_list, many=True, context={"request": request})
                if serializer2.is_valid():
                    serializer2.save()
                else:
                    print("Video Availabilty Serializer Validation Errors:", serializer2.errors)

                dict_response = {"error": False, "message": "Video Created Successfully"}
            else:
                dict_response = {"error": True, "message": "Validation Error", "errors": serializer.errors}
        except Exception as e:
            print("Error during video creation:", e)
            dict_response = {"error": True, "message": "Error During Creating Video"}

        return Response(dict_response,
                        status=status.HTTP_201_CREATED if not dict_response["error"] else status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "Unauthorized access"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            queryset = Video.objects.all()
            video = get_object_or_404(queryset, pk=pk)
            serializer = VideoSerializer(video, data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            dict_response = {"error": False, "message": "Video Updated Successfully"}
        except:
            dict_response = {"error": True, "message": "Video Not Updated Successfully"}

        return Response(dict_response)

    def destroy(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_admin:
            return Response({"error": True, "message": "Unauthorized access"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            queryset = Video.objects.all()
            video = get_object_or_404(queryset, pk=pk)
            video.delete()
            dict_response = {"error": False, "message": "Video Deleted Successfully"}
        except:
            dict_response = {"error": True, "message": "Video Not Deleted Successfully"}

        return Response(dict_response)

    def retrieve(self, request, pk=None):
        queryset = Video.objects.all()
        video = get_object_or_404(queryset, pk=pk)
        serializer = VideoSerializer(video, context={"request": request})

        serializer_data = serializer.data
        # Access play_casts associated with the current play
        video_casts = VideoCast.objects.filter(video_id=serializer_data["id"])
        video_casts_serializer = VideoCastSerializer(video_casts, many=True)
        serializer_data["video_casts"] = video_casts_serializer.data

        # Access play_casts associated with the current play
        video_available = VideoAvailability.objects.filter(video_id=serializer_data["id"])
        video_available_serializer = VideoAvailabilitySerializer(video_available, many=True)
        serializer_data["video_available"] = video_available_serializer.data

        return Response({"error": False, "message": "Single Data Fetch", "data": serializer_data})
        # Check if the user has made the payment for the video
        # try:
        #     video_payment = VideoPayment.objects.get(user=request.user, video=video)
        #     current_datetime = datetime.now()
        #     if video_payment.expiration_date >= current_datetime:
        #         return Response({"error": False, "message": "You can watch the video now"})
        #     else:
        #         return Response({"error": True, "message": "Your access to the video has expired"},
        #                         status=status.HTTP_403_FORBIDDEN)
        # except VideoPayment.DoesNotExist:
        #     return Response({"error": True, "message": "You haven't made the payment for this video"},
        #                     status=status.HTTP_403_FORBIDDEN)


class VideoPaymentViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        videopayment = VideoPayment.objects.all()
        serializer = VideoPaymentSerializer(videopayment, many=True, context={"request": request})
        response_dict = {"error": False, "message": "All Payments List Data", "data": serializer.data}
        return Response(response_dict)

    # @action(detail=False, methods=["post"])
    # def initiate_payment(self, request):
    #


class HomeApiViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"}, \
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            customer_count = UserAccount.objects.filter(is_staff=0)
            customer_count_serializer = UserCreateSerializer(customer_count, many=True, context={"request": request})

            video_count = Video.objects.all()
            video_count_serializer = VideoSerializer(video_count, many=True, context={"request": request})

            play_count = Play.objects.filter(is_available=1)
            play_count_serializer = PlaySerializer(play_count, many=True, context={"request": request})

            dict_response = {
                "error": False,
                "message": "Dashboard api",
                "users": len(customer_count_serializer.data),
                "active_streams": len(video_count_serializer.data),
                "active_plays": len(play_count_serializer.data)
            }
        except:
            dict_response = {"error": True, "message": "Error performing task"}

        return Response(dict_response)

play_list = PlayViewSet.as_view({"get": "list"})
play_create = PlayViewSet.as_view({"post": "create"})
play_update = PlayViewSet.as_view({"put": "update"})
play_destroy = PlayViewSet.as_view({"delete": "destroy"})