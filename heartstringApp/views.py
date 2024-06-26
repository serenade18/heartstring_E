import hashlib
import hmac
import json
import uuid
import re
from datetime import datetime, timedelta, date
from io import BytesIO
from time import sleep
import time

import qrcode
import requests
from django.core.files.base import ContentFile, File
from django.utils import timezone
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet
from rest_framework import viewsets, status, generics
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from heartstringApp import serializers
from heartstringApp.models import Ticket, Payment, Play, Video, PlayCast, OtherOffers, PlayTime, \
    VideoCast, VideoAvailability, UserAccount, VideoPayments, Seat, ViewHistory
from heartstringApp.serializers import TicketsSerializer, PaymentSerializer, PlaySerializer, \
    PlayCastSerializer, VideoSerializer, VideoCastSerializer, VideoPaymentSerializer, \
    VideoAvailabilitySerializer, OtherOfferSerializer, PlayDateSerializer, UserAccountSerializer, \
    MyPlaySerializer, MyStreamSerializer, SeatSerializer, ViewHistorySerializer

from django.contrib.auth import get_user_model

User = get_user_model()
# Create your views here
# master password: lenu9WcCPuS5tmLpCA7q
# master username: postgres


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
        user_id = self.kwargs.get('user_id')
        user = self.request.user

        if user_id:
            # If a user_id is provided, check if the user is an admin
            if user.is_staff:
                # Admin can edit name and phone of other users
                return get_object_or_404(User, id=user_id)

        # If no user_id or if the user is not an admin, allow users to update their own accounts
        return user

    def perform_update(self, serializer):
        user = self.request.user

        if user.is_staff:
            # Admins can update the name and phone without email uniqueness check
            serializer.save()
        else:
            # Regular users can update all fields, including email, with email uniqueness check
            email = serializer.validated_data.get('email')
            instance = serializer.instance

            if email and User.objects.exclude(pk=instance.pk).filter(email=email).exists():
                raise serializers.ValidationError("User with this email already exists.")

            serializer.save()


class UserAccountDeleteView(generics.DestroyAPIView):
    serializer_class = UserAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    queryset = UserAccount.objects.all()  # Update with the correct queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # You can add additional logic here if needed

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvailableSeatsView(APIView):
    """
    API endpoint that lists available seats for a specific play time.
    """

    def get(self, request, play_time_id, format=None):
        try:
            play_time = PlayTime.objects.get(id=play_time_id)
            available_seats = Seat.objects.filter(play_time=play_time, is_booked=False)
            serializer = SeatSerializer(available_seats, many=True)
            return Response(serializer.data)
        except PlayTime.DoesNotExist:
            return Response({'error': 'PlayTime not found'}, status=status.HTTP_404_NOT_FOUND)


class SeatViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]  # Adjust as needed for your auth requirements

    def list(self, request):
        """
        Filter seats by date and time slot.
        """
        play_date = request.query_params.get('play_date')
        time_slot = request.query_params.get('time_slot')

        try:
            seats = Seat.objects.filter(play_date=play_date, time_slot=time_slot)
            if not seats.exists():
                raise NotFound(detail="No seats found for the provided date and time slot.")
        except ValueError:
            raise ValidationError(detail="Invalid 'date' or 'time_slot' provided.")

        serializer = SeatSerializer(seats, many=True)
        return Response({"error": False, "message": "All Seats List Data", "data": serializer.data})

    @action(detail=False, methods=['post'], url_path='book')
    def book_seats(self, request):
        """
        Book multiple seats by marking them as booked. Expects a list of seat IDs in the request body.
        """
        seat_ids = request.data.get('seat_ids')

        if not seat_ids:
            return Response({'error': True, 'message': 'No seat IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        booked_seats = []
        not_found_seats = []
        already_booked_seats = []

        for seat_id in seat_ids:
            try:
                seat = Seat.objects.get(pk=seat_id)
                if seat.is_booked:
                    already_booked_seats.append(seat_id)
                else:
                    seat.is_booked = True
                    seat.save()
                    booked_seats.append(seat_id)
            except Seat.DoesNotExist:
                not_found_seats.append(seat_id)

        message = "Seats booking status updated."
        if not_found_seats:
            message += f" Not found seats: {not_found_seats}."
        if already_booked_seats:
            message += f" Already booked seats: {already_booked_seats}."

        return Response({
            'error': False,
            'message': message,
            'booked_seats': booked_seats,
            'already_booked_seats': already_booked_seats,
            'not_found_seats': not_found_seats
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='available')
    def available_seats(self, request):
        """
        List all available seats, optionally filtered by date and time slot.
        """
        date = request.query_params.get('date')
        time_slot = request.query_params.get('time_slot')
        queryset = Seat.objects.filter(is_booked=False)

        if date and time_slot:
            try:
                queryset = queryset.filter(play_time__date=date, play_time__time_slot=time_slot)
                if not queryset.exists():
                    raise NotFound(detail="No available seats found for the provided date and time slot.")
            except ValueError:
                raise ValidationError(detail="Invalid 'date' or 'time_slot' provided.")

        if not queryset.exists():
            return Response({'error': True, 'message': 'No available seats.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SeatSerializer(queryset, many=True)
        return Response({"error": False, "message": "All Available Seats", "data": serializer.data})


def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="white", back_color="transparent")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_code_image = buffer.getvalue()

    return qr_code_image


class TicketViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated | IsAdminUser]  # Allow both authenticated users and admin users

    def list(self, request):
        if request.user.is_staff:  # Check if the user is an admin
            tickets = Ticket.objects.all().order_by('-id')  # Retrieve all tickets in the database
        else:
            tickets = Ticket.objects.filter(user=request.user).order_by('-id')  # Filter tickets for regular users

        serializer = TicketsSerializer(tickets, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Tickets List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        try:
            serializer = TicketsSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)

            # Generate a unique ticket number for the current play
            play = serializer.validated_data.get('play')  # Assuming you have a 'play' field in your serializer
            ticket_number = str(uuid.uuid4().hex[:10].upper())  # Generate a unique ticket number

            # Save the ticket with the generated ticket number
            ticket = serializer.save(user=request.user, ticket_number=ticket_number)

            # Include only the ticket ID in the response
            dict_response = {"error": False, "message": "Ticket created Successfully", "ticket_id": ticket.id}
        except Exception as e:
            dict_response = {"error": True, "message": f"Error During Saving Ticket Data: {str(e)}"}

        return Response(dict_response)

        # Custom method to generate and set a default QR code for the ticket

    def generate_default_qr_code(self, ticket):
        qr_code_data = f"Default QR Code Data for Ticket {ticket.ticket_number}"
        qr_code_image = generate_qr_code(qr_code_data)

        # Save the default QR code to the ticket
        ticket.qr_code.save("default_qr_code.png", ContentFile(qr_code_image))
        ticket.save()

    def retrieve(self, request, pk=None):
        queryset = Ticket.objects.filter(user=request.user)
        tickets = get_object_or_404(queryset, pk=pk)
        serializer = TicketsSerializer(tickets, context={"request": request})

        serializer_data = serializer.data
        dict_response = {"error": False, "message": "Single data fetch", "data": serializer_data}

        return Response(dict_response)

    def destroy(self, request, pk=None):
        try:
            queryset = Ticket.objects.all()
            tickets = get_object_or_404(queryset, pk=pk)
            tickets.delete()
            dict_response = {"error": False, "message": "Ticket Deleted Successfully"}
        except:
            dict_response = {"error": True, "message": "Ticket Not Deleted Successfully"}

        return Response(dict_response)


class PaymentViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Check if the user is an admin
        if request.user.user_type == 'admin':
            # Admin users can access all payments
            payments = Payment.objects.all()
        else:
            # Regular users can only access their own payments
            payments = Payment.objects.filter(user=request.user)

        serializer = PaymentSerializer(payments, many=True, context={"request": request})

        response_dict = {"error": False, "message": "Payments List Data", "data": serializer.data}

        return Response(response_dict, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def initiate_payment(self, request):
        # Replace 'ticket_id' with the actual ticket ID you want to associate with the payment
        ticket_id = request.data.get('ticket_id')
        amount = request.data.get('amount')
        user_phone = request.data.get('phone')

        try:
            # Retrieve the Ticket object based on the provided ID
            ticket = Ticket.objects.get(pk=ticket_id)
        except Ticket.DoesNotExist:
            return Response({"error": True, "message": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve user's phone from the authenticated user
        user_email = request.user.email
        # OEgn$6shMB9( :merchant password
        # Define your transaction parameters here
        live = "1"
        oid = str(ticket.ticket_number)  # Use the retrieved Ticket object to get the ID
        inv = ticket.ticket_number  # Use the retrieved Ticket object to get the ticket number
        # amount = str(ticket.price)  # Use the retrieved Ticket object to get the price
        tel = user_phone
        eml = user_email
        vid = "hstring"  # Replace with your Vendor ID
        curr = "KES"
        p1 = ""
        p2 = ""
        p3 = ""
        p4 = ""
        cst = "0"
        crl = "1"
        autopay = "1"
        cbk = "http://heartstringsentertainment.co.ke"  # Replace with your callback URL

        data_string = live + oid + inv + amount + tel + eml + vid + curr + p1 + p2 + p3 + p4 + cst + cbk

        hash_key = "V5BHqdsbRBSc2#9rkky7kC2$NQ%fEEg8"  # Replace with your secret key

        # Convert hashKey and dataString to bytes
        hash_key_bytes = hash_key.encode()
        data_string_bytes = data_string.encode()

        # Create an HMAC-SHA256 hasher
        hasher = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

        # Get the generated hash in hexadecimal format
        generated_hash = hasher.hexdigest()

        # Include the 'hash' parameter in your request data
        request_data = {
            'live': live,
            'oid': oid,
            'inv': inv,
            'amount': amount,
            'tel': tel,
            'eml': eml,
            'vid': vid,
            'curr': curr,
            'p1': p1,
            'p2': p2,
            'p3': p3,
            'p4': p4,
            'cst': cst,
            'crl': crl,
            'hash': generated_hash,  # Include the generated hash
            'autopay': autopay,
            'cbk': cbk
        }

        # Make a POST request to your payment gateway
        response = requests.post('https://apis.ipayafrica.com/payments/v2/transact', data=request_data)

        # Try to extract the SID from the response
        sid = response.json().get('data', {}).get('sid')

        if sid:
            # Now, use the same method to hash the phone, sid, and vid
            data_string_stk = user_phone + vid + sid
            hasher_stk = hmac.new(hash_key_bytes, data_string_stk.encode(), hashlib.sha256)
            generated_hash_stk = hasher_stk.hexdigest()

            # Include the 'hash' parameter in your request data for STK PUSH
            request_data_stk = {
                'phone': user_phone,
                'sid': sid,
                'vid': vid,
                'hash': generated_hash_stk,
            }

            # Make a POST request to your STK PUSH endpoint
            response_stk = requests.post('https://apis.ipayafrica.com/payments/v2/transact/push/mpesa',
                                         json=request_data_stk)

            if response_stk.status_code == 200:
                response_data_stk = response_stk.json()
                header_status_stk = response_data_stk.get('header_status')
                response_status_stk = response_data_stk.get('text')
                if header_status_stk == 200:
                    # STK PUSH request initiated successfully
                    # Proceed to handle the callback action

                    if sid:
                        # 2. Calculate the hash for the callback
                        data_string_callback = vid + sid  # Exclude the phone number

                        # Convert hashKey and dataString to bytes
                        hash_key_bytes = hash_key.encode()
                        data_string_bytes = data_string_callback.encode()

                        # Create an HMAC-SHA256 hasher for the callback
                        hasher_callback = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

                        # Get the generated hash in hexadecimal format for the callback
                        generated_hash_callback = hasher_callback.hexdigest()

                        # 3. Include the 'hash' parameter in your request data for the callback
                        request_data_callback = {
                            'vid': vid,
                            'sid': sid,
                            'hash': generated_hash_callback,
                        }

                        response_callback = requests.post(
                            'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                            json=request_data_callback)

                        if response_callback.status_code == 400:
                            response_data_callback = response_callback.json()

                            # 5. Extract the hash from the callback response using regular expressions
                            callback_text = response_data_callback.get('error', [{}])[0].get('text')
                            callback_hash = re.search(r'hash ([a-fA-F0-9]+)', callback_text).group(1)

                            # 6. Include the extracted hash in your request data for the second callback
                            request_data_second_callback = {
                                'vid': vid,
                                'sid': sid,
                                'hash': callback_hash,  # Use the extracted hash
                            }

                            # Define the maximum number of callback retries
                            max_callback_retries = 8
                            callback_retries = 0

                            while callback_retries < max_callback_retries:
                                # 7. Make a second POST request to the callback endpoint to get callback details
                                response_second_callback = requests.post(
                                    'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                                    json=request_data_second_callback
                                )

                                if response_second_callback.status_code == 200:
                                    response_data_second_callback = response_second_callback.json()
                                    # Check if the status in the second callback response indicates completeness
                                    if response_data_second_callback.get("status") == "aei7p7yrx4ae34":
                                        # Status is complete, process the second callback response

                                        # Construct the ticket details to include in the QR code
                                        ticket_details = f"Ticket Number: {ticket.ticket_number}\n"
                                        ticket_details += f"User Name: {request.user.first_name} {request.user.last_name}\n"
                                        ticket_details += f"User Phone: {user_phone}\n"
                                        ticket_details += f"User Email: {request.user.email}\n"
                                        ticket_details += f"Amount: {response_data_second_callback.get('mc')}\n"  # Assuming 'mc' is the amount
                                        ticket_details += f"Seat Numbers: {ticket.seat_numbers}\n"
                                        ticket_details += f"Mode of Payment: {response_data_second_callback.get('channel')}"

                                        # Store payment information in your database
                                        payment = Payment.objects.create(
                                            ref_number=response_data_second_callback.get('txncd'),
                                            payment_mode=response_data_second_callback.get('channel'),
                                            msisdn=response_data_second_callback.get('msisdn_id'),
                                            msisdn_idnum=response_data_second_callback.get('msisdn_idnum'),
                                            amount=response_data_second_callback.get('mc'),
                                            ticket=ticket,
                                            user=request.user,
                                        )

                                        # Update the ticket details with information you want to include in the QR code
                                        ticket.details = ticket_details
                                        ticket.purchased = True  # Update purchased status to True
                                        ticket.save()

                                        # Generate a new QR code with the updated ticket details
                                        qr = qrcode.QRCode(
                                            version=1,
                                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                                            box_size=10,
                                            border=4,
                                        )

                                        qr.add_data(ticket_details)
                                        qr.make(fit=True)

                                        # Create a QR code image
                                        qr_code_img = qr.make_image(fill_color="black", back_color="white")

                                        # Save the QR code image to a file
                                        qr_code_path = "{}.png".format(
                                            ticket.ticket_number)  # Modify the path as needed
                                        buffer = BytesIO()
                                        qr_code_img.save(buffer, format="PNG")
                                        ticket.qr_code.save(qr_code_path, File(buffer))

                                        # Update the ticket with the file path to the QR code image
                                        ticket.save()

                                        # Return a response indicating successful payment
                                        return Response({"error": False, "message": "Payment completed successfully"})

                                    elif response_data_second_callback.get("status") == "bdi6p2yy76etrs":
                                        # Status is incomplete, increment retry count and wait before retrying
                                        callback_retries += 1
                                        sleep(5)  # Wait for 3 seconds before retrying

                                    else:
                                        # Handle unexpected status, you might want to log this
                                        return Response({"error": True, "message": "Unexpected callback status"},
                                                        status=status.HTTP_400_BAD_REQUEST)

                                else:
                                    # Handle the second callback request error
                                    return Response({"error": True, "message": "Second Callback request failed"},
                                                    status=status.HTTP_400_BAD_REQUEST)

                            # If the loop completes without breaking, it means max_callback_retries was reached
                            return Response({"error": True, "message": "Max retries reached"},
                                            status=status.HTTP_400_BAD_REQUEST)

                        else:
                            # Handle first callback error
                            return Response({"error": True, "message": "First Callback request failed"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response(
                            {"error": True,
                             "message": "STK PUSH request failed with status: " + str(header_status_stk)},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": True, "message": "STK PUSH request failed with status code: " + str(
                        response_stk.status_code)},
                                    status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, pk=None):
        queryset = Payment.objects.filter(user=request.user)
        payments = get_object_or_404(queryset, pk=pk)
        serializer = PaymentSerializer(payments, context={"request": request})
        return Response({"error": False, "message": "Single Data Fetch", "data": serializer.data})


class PlayViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def list(self, request):
        plays = Play.objects.all().order_by('-id')
        serializer = PlaySerializer(plays, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Plays List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},
                            status=status.HTTP_401_UNAUTHORIZED)

        try:
            serializer = PlaySerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                play_instance = serializer.save()
                # Access Play id
                play_id = play_instance.id

                # Access saved serializer and save play cast
                play_cast_list = []
                play_cast_data_list = request.data.get("play_casts", [])
                if not play_cast_data_list:
                    # Handle the indexed format
                    index = 0
                    while f"play_casts[{index}][real_name]" in request.data:
                        play_cast_data = {
                            "play_id": play_id,
                            "image": request.data.get(f"play_casts[{index}][image]"),
                            "real_name": request.data.get(f"play_casts[{index}][real_name]"),
                            "cast_name": request.data.get(f"play_casts[{index}][cast_name]"),
                        }
                        play_cast_list.append(play_cast_data)
                        index += 1
                else:
                    # Handle the non-indexed format
                    for data in play_cast_data_list:
                        play_cast_data = {
                            "play_id": play_id,
                            "image": data.get("image"),
                            "real_name": data.get("real_name"),
                            "cast_name": data.get("cast_name"),
                        }
                        play_cast_list.append(play_cast_data)
                print("play Cast List:", play_cast_list)

                # Save play cast data to table
                serializer1 = PlayCastSerializer(data=play_cast_list, many=True, context={"request": request})
                if serializer1.is_valid():
                    serializer1.save()
                else:
                    print("Play Cast Serializer Validation Errors:", serializer1.errors)

                # Access saved serializer and save other offers
                other_offers_list = []
                other_offers_data_list = request.data.get('other_offers', [])
                if not other_offers_data_list:
                    # Handle the indexed format
                    index = 0
                    while f"other_offers[{index}][offers_name]" in request.data:
                        other_offers_data = {
                            "play_id": play_id,
                            "offers_name": request.data.get(f"other_offers[{index}][offers_name]"),
                            "offer_day": request.data.get(f"other_offers[{index}][offer_day]"),
                            "promo_code": request.data.get(f"other_offers[{index}][promo_code]"),
                            "percentage": request.data.get(f"other_offers[{index}][percentage]"),
                            "number_of_tickets": request.data.get(f"other_offers[{index}][number_of_tickets]"),
                        }
                        other_offers_list.append(other_offers_data)
                        index += 1
                else:
                    for data in other_offers_data_list:
                        other_offers_data = {
                            "play_id": play_id,
                            "offers_name": data.get("offers_name"),
                            "offer_day": data.get("offer_day"),
                            "promo_code": data.get("promo_code"),
                            "percentage": data.get("percentage"),
                            "number_of_tickets": data.get("number_of_tickets"),
                        }
                        other_offers_list.append(other_offers_data)

                print("other offers List:", other_offers_list)

                # Save other offers to table
                serializer3 = OtherOfferSerializer(data=other_offers_list, many=True, context={"request": request})
                if serializer3.is_valid():
                    serializer3.save()
                else:
                    print("Offer Serializer Validation Errors:", serializer3.errors)

                # Access saved serializer and save play date
                play_date_list = []
                play_date_data_list = request.data.get("play_dates", [])
                if not play_date_data_list:
                    # Handle the indexed format
                    index = 0
                    while f"play_dates[{index}][play_date]" in request.data:
                        play_dates_data = {
                            "play_id": play_id,
                            "play_date": request.data.get(f"play_dates[{index}][play_date]"),
                            "time1": request.data.get(f"play_dates[{index}][time1]"),
                            "time2": request.data.get(f"play_dates[{index}][time2]"),
                            "time3": request.data.get(f"play_dates[{index}][time3]"),
                        }
                        play_date_list.append(play_dates_data)
                        index += 1
                else:
                    # Handle the non-indexed format
                    for data in play_date_data_list:
                        play_dates_data = {
                            "play_id": play_id,
                            "play_date": data.get("date"),
                            "time1": data.get("time1"),
                            "time2": data.get("time2"),
                            "time3": data.get("time3"),
                        }
                        play_date_list.append(play_dates_data)
                print("play dates List:", play_date_list)

                # Save play dates to table
                serializer4 = PlayDateSerializer(data=play_date_list, many=True, context={"request": request})
                if serializer4.is_valid():
                    serializer4.save()
                else:
                    print("Play Date Serializer Validation Errors:", serializer4.errors)

                # Dynamic seat creation logic
                seatLayout = [
                    {"wing": "Left",
                     "seats": {"A": 3, "B": 4, "C": 5, "D": 6, "E": 7, "F": 8, "G": 0, "H": 0, "I": 0}},
                    {"wing": "Center",
                     "seats": {"A": 14, "B": 15, "C": 14, "D": 15, "E": 14, "F": 15, "G": 14, "H": 15, "I": 14}},
                    {"wing": "Right",
                     "seats": {"A": 3, "B": 4, "C": 5, "D": 6, "E": 7, "F": 8, "G": 0, "H": 0, "I": 0}},
                ]

                playTimes = PlayTime.objects.filter(play_id=play_instance)

                for playTime in playTimes:
                    for section in seatLayout:
                        wing = section["wing"]
                        for row, seatCount in section["seats"].items():
                            # For each PlayTime, create seats for each time slot
                            time_slots = [playTime.time1, playTime.time2, playTime.time3]
                            play_date = playTime.play_date
                            for time_slot in filter(None, time_slots):  # filter(None, ...) removes empty slots
                                for seatNumber in range(1, seatCount + 1):
                                    seat_id = f"{wing}-{row}{seatNumber}"
                                    Seat.objects.create(
                                        play_time=playTime,
                                        seat_number=seat_id,
                                        wing=wing,
                                        time_slot=time_slot,
                                        is_booked=False,
                                        play_date=play_date
                                    )

                dict_response = {"error": False, "message": "Play added successfully"}
            else:
                dict_response = {"error": True, "message": "Validation Error", "errors": serializer.errors}
        except Exception as e:
            print("Error:", str(e))
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


class MyPlayListView(generics.ListAPIView):
    serializer_class = MyPlaySerializer  # Use your custom serializer
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get_queryset(self):
        # Filter plays that have associated tickets with the 'purchased' status
        # return Play.objects.filter(ticket__purchased=True, ticket__user=self.request.user)
        return Play.objects.filter(ticket__payment__user=self.request.user)


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


class VideoViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]

    def list(self, request):
        videos = Video.objects.all().order_by('-id')
        serializer = VideoSerializer(videos, many=True, context={"request": request})
        response_dict = {"error": False, "message": "All Videos List Data", "data": serializer.data}
        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"}, \
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            serializer = VideoSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                video_instance = serializer.save()

                # Access Video id
                video_id = video_instance.id

                # Process video_casts data (with or without indexes)
                video_cast_list = []
                video_cast_data_list = request.data.get("video_casts", [])
                if not video_cast_data_list:
                    # Handle the indexed format
                    index = 0
                    while f"video_casts[{index}][real_name]" in request.data:
                        video_cast_data = {
                            "video_id": video_id,
                            "image": request.data.get(f"video_casts[{index}][image]"),
                            "real_name": request.data.get(f"video_casts[{index}][real_name]"),
                            "cast_name": request.data.get(f"video_casts[{index}][cast_name]"),
                        }
                        video_cast_list.append(video_cast_data)
                        index += 1
                else:
                    # Handle the non-indexed format
                    for data in video_cast_data_list:
                        video_cast_data = {
                            "video_id": video_id,
                            "image": data.get("image"),
                            "real_name": data.get("real_name"),
                            "cast_name": data.get("cast_name"),
                        }
                        video_cast_list.append(video_cast_data)
                # print("Video Cast List:", video_cast_list)

                # Save video cast data to table
                serializer1 = VideoCastSerializer(data=video_cast_list, many=True, context={"request": request})
                if serializer1.is_valid():
                    serializer1.save()
                else:
                    print("Video Cast Serializer Validation Errors:", serializer1.errors)

                # Process video_available data (with or without indexes)
                video_available_list = []
                video_available_data_list = request.data.get("video_available", [])
                if not video_available_data_list:
                    # Handle the indexed format
                    index = 0
                    while f"video_available[{index}][three_days]" in request.data:
                        video_available_data = {
                            "video_id": video_id,
                            "three_days": request.data.get(f"video_available[{index}][three_days]"),
                            "three_price": request.data.get(f"video_available[{index}][three_price]"),
                            "seven_days": request.data.get(f"video_available[{index}][seven_days]"),
                            "seven_price": request.data.get(f"video_available[{index}][seven_price]"),
                            "fourteen_days": request.data.get(f"video_available[{index}][fourteen_days]"),
                            "fourteen_price": request.data.get(f"video_available[{index}][fourteen_price]"),
                        }
                        video_available_list.append(video_available_data)
                        index += 1
                else:
                    # Handle the non-indexed format
                    for data in video_available_data_list:
                        video_available_data = {
                            "video_id": video_id,
                            "three_days": data.get("three_days"),
                            "three_price": data.get("three_price"),
                            "seven_days": data.get("seven_days"),
                            "seven_price": data.get("seven_price"),
                            "fourteen_days": data.get("fourteen_days"),
                            "fourteen_price": data.get("fourteen_price"),
                        }
                        video_available_list.append(video_available_data)
                # print("Video available List:", video_available_list)

                # Save video availability data to table
                serializer2 = VideoAvailabilitySerializer(data=video_available_list, many=True,
                                                          context={"request": request})
                if serializer2.is_valid():
                    serializer2.save()
                else:
                    print("Video Availability Serializer Validation Errors:", serializer2.errors)

                dict_response = {"error": False, "message": "Video Created Successfully"}
            else:
                dict_response = {"error": True, "message": "Validation Error", "errors": serializer.errors}
        except Exception as e:
            print("Error during video creation:", e)
            dict_response = {"error": True, "message": "Error During Creating Video"}

        return Response(
            dict_response,
            status=status.HTTP_201_CREATED if not dict_response["error"] else status.HTTP_400_BAD_REQUEST
        )

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
        except ValidationError as e:
            dict_response = {"error": True, "message": "Validation Error", "details": str(e)}
        except Exception as e:
            dict_response = {"error": True, "message": "An Error Occurred", "details": str(e)}

        return Response(dict_response,
                        status=status.HTTP_400_BAD_REQUEST if dict_response['error'] else status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)

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


class VideoCastViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # play_cast = PlayCast.objects.filter(user=request.user)
        video_cast = VideoCast.objects.all()
        serializer = VideoCastSerializer(video_cast, many=True, context={"request": request})

        response_dict = {"error": False, "message": "All Play Cast List Data", "data": serializer.data}

        return Response(response_dict)

    def create(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            serializer = VideoCastSerializer(data=request.data, context={"request": request})
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
        queryset = VideoCast.objects.all()
        video_cast = get_object_or_404(queryset, pk=pk)
        serializer = VideoCastSerializer(video_cast, context={"request": request})
        return Response({"error": False, "message": "Single Data Fetch", "data": serializer.data})

    def update(self, request, pk=None):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"},\
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            queryset = VideoCast.objects.all()
            video_cast = get_object_or_404(queryset, pk=pk)
            serializer = VideoCastSerializer(video_cast, data=request.data, context={"request": request})
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


class MyStreamListView(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        video_payments = VideoPayments.objects.filter(user=user)
        active_videos = []

        for video_payment in video_payments:
            video = video_payment.video
            # Ensure video is not None before proceeding
            if video is not None:
                pricing_tiers = VideoAvailability.objects.filter(video_id=video).first()

                # Check if pricing tiers exist for this video
                if pricing_tiers:
                    if video_payment.amount in [int(pricing_tiers.three_price), int(pricing_tiers.seven_price),
                                                int(pricing_tiers.fourteen_price)]:
                        current_datetime = timezone.now()
                        days_difference = (current_datetime - video_payment.added_on).days

                        remaining_access_time = None
                        if video_payment.amount == int(pricing_tiers.three_price):
                            remaining_access_time = 3 - days_difference
                        elif video_payment.amount == int(pricing_tiers.seven_price):
                            remaining_access_time = 7 - days_difference
                        elif video_payment.amount == int(pricing_tiers.fourteen_price):
                            remaining_access_time = 14 - days_difference

                        if remaining_access_time > 0:
                            active_video_data = {
                                'id': video.id,
                                'title': video.title,
                                'synopsis': video.synopsis,
                                'video': video.video,
                                'duration': video.duration,
                                'trailer': video.trailer,
                                'video_poster': video.video_poster,
                                'remaining_access_time': remaining_access_time,
                                'added_on': video.added_on,
                            }
                            active_videos.append(active_video_data)
                else:
                    # Pricing tiers do not exist for this video; you might want to log this or handle it appropriately
                    print(f"No pricing tiers found for video {video.id if video else 'Unknown'}")
            else:
                # Handle the case where video is None
                print(f"VideoPayments instance with ID {video_payment.id} does not have an associated video.")

        # No need to return an error if no active videos are found
        # Serialize the active videos and return the response
        serializer = MyStreamSerializer(active_videos, many=True, context={"request": request})

        # Append the remaining_access_time to each video's data in the serialized response
        data_with_remaining_access_time = serializer.data
        for video_data, remaining_time in zip(data_with_remaining_access_time,
                                              [video['remaining_access_time'] for video in active_videos]):
            video_data['remaining_access_time'] = remaining_time

        response_dict = {"error": False, "message": "Active Videos List Data", "data": serializer.data}
        return Response(response_dict, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        # Ensure that the user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {"error": True, "message": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        queryset = Video.objects.all()
        video = get_object_or_404(queryset, pk=pk)

        # Check if the user has made payments for this video
        video_payments = VideoPayments.objects.filter(user=request.user, video=video).order_by('-added_on')

        if video_payments.exists():
            # Use the latest payment for the video
            video_payment = video_payments.first()
            current_datetime = timezone.now()

            # Query the pricing tiers for the associated video
            pricing_tiers = VideoAvailability.objects.filter(video_id=video).first()

            # Convert the payment amount and pricing tiers to integers for comparison
            payment_amount = int(video_payment.amount)
            three_price = int(pricing_tiers.three_price)
            seven_price = int(pricing_tiers.seven_price)
            fourteen_price = int(pricing_tiers.fourteen_price)

            if (
                    payment_amount != three_price
                    and payment_amount != seven_price
                    and payment_amount != fourteen_price
            ):
                # The payment amount does not match any pricing tier
                return Response(
                    {"error": True, "message": "Invalid payment amount for this video"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate the remaining days based on the payment's added_on date
            days_difference = (current_datetime - video_payment.added_on).days

            remaining_access_time = None
            if payment_amount == three_price:
                remaining_access_time = 3 - days_difference  # Access for 3 days
            elif payment_amount == seven_price:
                remaining_access_time = 7 - days_difference  # Access for 7 days
            elif payment_amount == fourteen_price:
                remaining_access_time = 14 - days_difference  # Access for 14 days

            if remaining_access_time <= 0:
                # Access has expired, return an error response
                return Response(
                    {"error": True, "message": "Access to this video has expired"},
                    status=status.HTTP_403_FORBIDDEN
                )

            serializer = MyStreamSerializer(video, context={"request": request})

            serializer_data = serializer.data

            # Access video_casts associated with the current video
            video_casts = VideoCast.objects.filter(video_id=serializer_data["id"])
            video_casts_serializer = VideoCastSerializer(video_casts, many=True)
            serializer_data["video_casts"] = video_casts_serializer.data

            # Access video_available associated with the current video
            video_available = VideoAvailability.objects.filter(video_id=serializer_data["id"])
            video_available_serializer = VideoAvailabilitySerializer(video_available, many=True)
            serializer_data["video_available"] = video_available_serializer.data

            serializer_data["remaining_access_time"] = remaining_access_time

            return Response({"error": False, "message": "Single Data Fetch", "data": serializer_data})

        else:
            # No payment made, return an error response
            return Response(
                {"error": True, "message": "No payment made for this video"},
                status=status.HTTP_403_FORBIDDEN
            )


class VideoPaymentViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Check if the user is a staff member
        is_staff = request.user.is_staff

        if is_staff:
            # User is a staff member, so they can access all payments
            videopayments = VideoPayments.objects.all()
        else:
            # User is not a staff member, so they can only access their payments
            videopayments = VideoPayments.objects.filter(user=request.user)

        serializer = VideoPaymentSerializer(videopayments, many=True, context={"request": request})
        response_dict = {"error": False, "message": "Payments List Data", "data": serializer.data}
        return Response(response_dict)

    @action(detail=False, methods=["post"])
    def initiate_airtel_payment(self, request):
        video_id = request.data.get('video_id')
        amount = request.data.get('amount')
        user_phone = request.data.get('phone')

        try:
            # Retrieve the Video object based on the provided ID
            video = Video.objects.get(pk=video_id)
        except Video.DoesNotExist:
            return Response({"error": True, "message": "Video not found"}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve user's phone from the authenticated user
        user_email = request.user.email
        # OEgn$6shMB9( :merchant password
        # Define your transaction parameters here
        live = "1"
        oid = f"{int(time.time())}-{uuid.uuid4()}"  # Use the retrieved Video object to get the ID
        inv = str(video.id)  # Use the retrieved Video object to get the ticket number
        tel = user_phone
        eml = user_email
        vid = "hstring"  # Replace with your Vendor ID
        curr = "KES"
        p1 = ""
        p2 = ""
        p3 = ""
        p4 = ""
        cst = "0"
        crl = "0"
        autopay = "1"
        cbk = "http://heartstringsentertainment.co.ke"  # Replace with your callback URL

        data_string = live + oid + inv + amount + tel + eml + vid + curr + p1 + p2 + p3 + p4 + cst + cbk

        hash_key = "V5BHqdsbRBSc2#9rkky7kC2$NQ%fEEg8"  # Replace with your secret key

        # Convert hashKey and dataString to bytes
        hash_key_bytes = hash_key.encode()
        data_string_bytes = data_string.encode()

        # Create an HMAC-SHA256 hasher
        hasher = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

        # Get the generated hash in hexadecimal format
        generated_hash = hasher.hexdigest()

        # Include the 'hash' parameter in your request data
        request_data = {
            'live': live,
            'oid': oid,
            'inv': inv,
            'amount': amount,
            'tel': tel,
            'eml': eml,
            'vid': vid,
            'curr': curr,
            'p1': p1,
            'p2': p2,
            'p3': p3,
            'p4': p4,
            'cst': cst,
            'crl': crl,
            'hash': generated_hash,  # Include the generated hash
            'autopay': autopay,
            'cbk': cbk
        }

        # Make a POST request to your payment gateway
        response = requests.post('https://apis.ipayafrica.com/payments/v2/transact', data=request_data)
        # print(response.text)
        # print(request_data)

        # Try to extract the SID from the response
        sid = response.json().get('data', {}).get('sid')

        if sid:
            # Now, use the same method to hash the phone, sid, and vid
            data_string_stk = user_phone + vid + sid
            hasher_stk = hmac.new(hash_key_bytes, data_string_stk.encode(), hashlib.sha256)
            generated_hash_stk = hasher_stk.hexdigest()

            # Include the 'hash' parameter in your request data for STK PUSH
            request_data_stk = {
                'phone': user_phone,
                'sid': sid,
                'vid': vid,
                'hash': generated_hash_stk,
            }

            # Make a POST request to your STK PUSH endpoint
            response_stk = requests.post('https://apis.ipayafrica.com/payments/v2/transact/push/airtel',
                                         json=request_data_stk)

            if response_stk.status_code == 200:
                response_data_stk = response_stk.json()
                header_status_stk = response_data_stk.get('header_status')
                response_status_stk = response_data_stk.get('text')
                if header_status_stk == 200:
                    # STK PUSH request initiated successfully
                    # Proceed to handle the callback action

                    if sid:
                        # 2. Calculate the hash for the callback
                        data_string_callback = vid + sid  # Exclude the phone number

                        # Convert hashKey and dataString to bytes
                        hash_key_bytes = hash_key.encode()
                        data_string_bytes = data_string_callback.encode()

                        # Create an HMAC-SHA256 hasher for the callback
                        hasher_callback = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

                        # Get the generated hash in hexadecimal format for the callback
                        generated_hash_callback = hasher_callback.hexdigest()

                        # 3. Include the 'hash' parameter in your request data for the callback
                        request_data_callback = {
                            'vid': vid,
                            'sid': sid,
                            'hash': generated_hash_callback,
                        }
                        # print(request_data_callback)

                        response_callback = requests.post(
                            'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                            json=request_data_callback)\

                        if response_callback.status_code == 400:
                            response_data_callback = response_callback.json()

                            # 5. Extract the hash from the callback response using regular expressions
                            callback_text = response_data_callback.get('error', [{}])[0].get('text')
                            callback_hash = re.search(r'hash ([a-fA-F0-9]+)', callback_text).group(1)

                            # 6. Include the extracted hash in your request data for the second callback
                            request_data_second_callback = {
                                'vid': vid,
                                'sid': sid,
                                'hash': callback_hash,  # Use the extracted hash
                            }

                            # Define the maximum number of callback retries
                            max_callback_retries = 8
                            callback_retries = 0

                            while callback_retries < max_callback_retries:
                                # 7. Make a second POST request to the callback endpoint to get callback details
                                response_second_callback = requests.post(
                                    'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                                    json=request_data_second_callback
                                )
                                # print(response_second_callback.text)

                                if response_second_callback.status_code == 200:
                                    response_data_second_callback = response_second_callback.json()
                                    # Check if the status in the second callback response indicates completeness
                                    if response_data_second_callback.get("status") == "aei7p7yrx4ae34":
                                        # Status is complete, process the second callback response

                                        # Store payment information in your database
                                        payment = VideoPayments.objects.create(
                                            ref_number=response_data_second_callback.get('txncd'),
                                            payment_mode=response_data_second_callback.get('channel'),
                                            msisdn=response_data_second_callback.get('msisdn_id'),
                                            msisdn_idnum=response_data_second_callback.get('msisdn_idnum'),
                                            amount=response_data_second_callback.get('mc'),
                                            video=video,
                                            user=request.user,
                                        )

                                        # Return a response indicating successful payment
                                        return Response({"error": False, "message": "Payment completed successfully"})

                                    elif response_data_second_callback.get("status") == "bdi6p2yy76etrs":
                                        # Status is incomplete, increment retry count and wait before retrying
                                        callback_retries += 1
                                        sleep(5)  # Wait for 3 seconds before retrying

                                    else:
                                        # Handle unexpected status, you might want to log this
                                        return Response({"error": True, "message": "Unexpected callback status"},
                                                        status=status.HTTP_400_BAD_REQUEST)

                                else:
                                    # Handle the second callback request error
                                    return Response({"error": True, "message": "Second Callback request failed"},
                                                    status=status.HTTP_400_BAD_REQUEST)

                            # If the loop completes without breaking, it means max_callback_retries was reached
                            return Response({"error": True, "message": "Max retries reached"},
                                            status=status.HTTP_400_BAD_REQUEST)

                        else:
                            # Handle first callback error
                            return Response({"error": True, "message": "First Callback request failed"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response(
                            {"error": True,
                             "message": "STK PUSH request failed with status: " + str(header_status_stk)},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": True, "message": "STK PUSH request failed with status code: " + str(
                        response_stk.status_code)},
                                    status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def initiate_payment(self, request):
        video_id = request.data.get('video_id')
        amount = request.data.get('amount')
        user_phone = request.data.get('phone')

        try:
            # Retrieve the Video object based on the provided ID
            video = Video.objects.get(pk=video_id)
        except Video.DoesNotExist:
            return Response({"error": True, "message": "Video not found"}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve user's phone from the authenticated user
        user_email = request.user.email
        # OEgn$6shMB9( :merchant password
        # Define your transaction parameters here
        live = "1"
        oid = f"{int(time.time())}-{uuid.uuid4()}"  # Use the retrieved Video object to get the ID
        inv = str(video.id)  # Use the retrieved Video object to get the ticket number
        tel = user_phone
        eml = user_email
        vid = "hstring"  # Replace with your Vendor ID
        curr = "KES"
        p1 = ""
        p2 = ""
        p3 = ""
        p4 = ""
        cst = "0"
        crl = "1"
        autopay = "1"
        cbk = "http://heartstringsentertainment.co.ke"  # Replace with your callback URL

        data_string = live + oid + inv + amount + tel + eml + vid + curr + p1 + p2 + p3 + p4 + cst + cbk

        hash_key = "V5BHqdsbRBSc2#9rkky7kC2$NQ%fEEg8"  # Replace with your secret key

        # Convert hashKey and dataString to bytes
        hash_key_bytes = hash_key.encode()
        data_string_bytes = data_string.encode()

        # Create an HMAC-SHA256 hasher
        hasher = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

        # Get the generated hash in hexadecimal format
        generated_hash = hasher.hexdigest()

        # Include the 'hash' parameter in your request data
        request_data = {
            'live': live,
            'oid': oid,
            'inv': inv,
            'amount': amount,
            'tel': tel,
            'eml': eml,
            'vid': vid,
            'curr': curr,
            'p1': p1,
            'p2': p2,
            'p3': p3,
            'p4': p4,
            'cst': cst,
            'crl': crl,
            'hash': generated_hash,  # Include the generated hash
            'autopay': autopay,
            'cbk': cbk
        }

        # Make a POST request to your payment gateway
        response = requests.post('https://apis.ipayafrica.com/payments/v2/transact', data=request_data)

        # Try to extract the SID from the response
        sid = response.json().get('data', {}).get('sid')

        if sid:
            # Now, use the same method to hash the phone, sid, and vid
            data_string_stk = user_phone + vid + sid
            hasher_stk = hmac.new(hash_key_bytes, data_string_stk.encode(), hashlib.sha256)
            generated_hash_stk = hasher_stk.hexdigest()

            # Include the 'hash' parameter in your request data for STK PUSH
            request_data_stk = {
                'phone': user_phone,
                'sid': sid,
                'vid': vid,
                'hash': generated_hash_stk,
            }

            # Make a POST request to your STK PUSH endpoint
            response_stk = requests.post('https://apis.ipayafrica.com/payments/v2/transact/push/mpesa',
                                         json=request_data_stk)

            if response_stk.status_code == 200:
                response_data_stk = response_stk.json()
                header_status_stk = response_data_stk.get('header_status')
                response_status_stk = response_data_stk.get('text')
                if header_status_stk == 200:
                    # STK PUSH request initiated successfully
                    # Proceed to handle the callback action

                    if sid:
                        # 2. Calculate the hash for the callback
                        data_string_callback = vid + sid  # Exclude the phone number

                        # Convert hashKey and dataString to bytes
                        hash_key_bytes = hash_key.encode()
                        data_string_bytes = data_string_callback.encode()

                        # Create an HMAC-SHA256 hasher for the callback
                        hasher_callback = hmac.new(hash_key_bytes, data_string_bytes, hashlib.sha256)

                        # Get the generated hash in hexadecimal format for the callback
                        generated_hash_callback = hasher_callback.hexdigest()

                        # 3. Include the 'hash' parameter in your request data for the callback
                        request_data_callback = {
                            'vid': vid,
                            'sid': sid,
                            'hash': generated_hash_callback,
                        }

                        response_callback = requests.post(
                            'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                            json=request_data_callback)

                        if response_callback.status_code == 400:
                            response_data_callback = response_callback.json()

                            # 5. Extract the hash from the callback response using regular expressions
                            callback_text = response_data_callback.get('error', [{}])[0].get('text')
                            callback_hash = re.search(r'hash ([a-fA-F0-9]+)', callback_text).group(1)

                            # 6. Include the extracted hash in your request data for the second callback
                            request_data_second_callback = {
                                'vid': vid,
                                'sid': sid,
                                'hash': callback_hash,  # Use the extracted hash
                            }

                            # Define the maximum number of callback retries
                            max_callback_retries = 8
                            callback_retries = 0

                            while callback_retries < max_callback_retries:
                                # 7. Make a second POST request to the callback endpoint to get callback details
                                response_second_callback = requests.post(
                                    'https://apis.ipayafrica.com/payments/v2/transact/mobilemoney',
                                    json=request_data_second_callback
                                )

                                if response_second_callback.status_code == 200:
                                    response_data_second_callback = response_second_callback.json()
                                    # Check if the status in the second callback response indicates completeness
                                    if response_data_second_callback.get("status") == "aei7p7yrx4ae34":
                                        # Status is complete, process the second callback response

                                        # Store payment information in your database
                                        payment = VideoPayments.objects.create(
                                            ref_number=response_data_second_callback.get('txncd'),
                                            payment_mode=response_data_second_callback.get('channel'),
                                            msisdn=response_data_second_callback.get('msisdn_id'),
                                            msisdn_idnum=response_data_second_callback.get('msisdn_idnum'),
                                            amount=response_data_second_callback.get('mc'),
                                            video=video,
                                            user=request.user,
                                        )

                                        # Return a response indicating successful payment
                                        return Response({"error": False, "message": "Payment completed successfully"})

                                    elif response_data_second_callback.get("status") == "bdi6p2yy76etrs":
                                        # Status is incomplete, increment retry count and wait before retrying
                                        callback_retries += 1
                                        sleep(5)  # Wait for 3 seconds before retrying

                                    else:
                                        # Handle unexpected status, you might want to log this
                                        return Response({"error": True, "message": "Unexpected callback status"},
                                                        status=status.HTTP_400_BAD_REQUEST)

                                else:
                                    # Handle the second callback request error
                                    return Response({"error": True, "message": "Second Callback request failed"},
                                                    status=status.HTTP_400_BAD_REQUEST)

                            # If the loop completes without breaking, it means max_callback_retries was reached
                            return Response({"error": True, "message": "Max retries reached"},
                                            status=status.HTTP_400_BAD_REQUEST)

                        else:
                            # Handle first callback error
                            return Response({"error": True, "message": "First Callback request failed"},
                                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response(
                            {"error": True,
                             "message": "STK PUSH request failed with status: " + str(header_status_stk)},
                            status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({"error": True, "message": "STK PUSH request failed with status code: " + str(
                        response_stk.status_code)},
                                    status=status.HTTP_400_BAD_REQUEST)


class ViewHistoryViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        watch_history = ViewHistory.objects.filter(user_id=user.id)

        # Create a list to store the serialized data of each watch history entry
        watch_history_data = []

        for entry in watch_history:
            video = entry.video_id
            video_serializer = VideoSerializer(video)

            # Construct the response data for each watch history entry
            entry_data = {
                "id": video.id,
                "title": video.title,
                "duration": video.duration,
                "synopsis": video.synopsis,
                "video": request.build_absolute_uri(video.video.url),
                "trailer": request.build_absolute_uri(video.trailer.url),
                "video_poster": request.build_absolute_uri(video.video_poster.url),
                "added_on": video.added_on,
            }

            watch_history_data.append(entry_data)

        response_dict = {"error": False, "message": "User's Watch History", "data": watch_history_data}
        return Response(response_dict)

    def create(self, request):
        user = request.user
        video_id = request.data.get('video_id')

        # Check if the video is already in the user's watch history
        if ViewHistory.objects.filter(user_id=user.id, video_id=video_id).exists():
            return Response(
                {"error": True, "message": "This video is already in the user's watch history"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ViewHistorySerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user_id=user.id)
            return Response(
                {"error": False, "message": "Video added to watch history successfully"},
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {"error": True, "message": "Validation Error", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

    def retrieve(self, request, pk=None):
        user = request.user
        try:
            watch_history_entry = ViewHistory.objects.select_related('video_id').get(user_id=user.id, pk=pk)
        except ViewHistory.DoesNotExist:
            return Response(
                {"error": True, "message": "Watch history entry does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Fetch the associated video details
        video = watch_history_entry.video_id
        video_serializer = VideoSerializer(video)

        # Construct the response data with video details at the root level
        response_data = {
            "id": video.id,
            "title": video.title,
            "duration": video.duration,
            "synopsis": video.synopsis,
            "video": request.build_absolute_uri(video.video.url),
            "trailer": request.build_absolute_uri(video.trailer.url),
            "video_poster": request.build_absolute_uri(video.video_poster.url),
            "added_on": video.added_on,
            "video_casts": [],
            "video_available": []
        }

        # Add video_casts associated with the current video
        video_casts = VideoCast.objects.filter(video_id=video.id)
        video_casts_serializer = VideoCastSerializer(video_casts, many=True)
        response_data["video_casts"] = video_casts_serializer.data

        # Add video_available associated with the current video
        video_available = VideoAvailability.objects.filter(video_id=video.id)
        video_available_serializer = VideoAvailabilitySerializer(video_available, many=True)
        response_data["video_available"] = video_available_serializer.data

        return Response({"error": False, "message": "Single Data Fetch", "data": response_data})

    def destroy(self, request, pk=None):
        user = request.user
        try:
            watch_history_entry = ViewHistory.objects.get(user_id=user.id, pk=pk)
        except ViewHistory.DoesNotExist:
            return Response(
                {"error": True, "message": "Watch history entry does not exist"},
                status=status.HTTP_404_NOT_FOUND
            )

        watch_history_entry.delete()
        return Response(
            {"error": False, "message": "Watch history entry deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


class HomeApiViewSet(viewsets.ViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Check if the user is an admin
        if not request.user.is_staff:
            return Response({"error": True, "message": "User does not have enough permission to perform this task"}, \
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            # Get the current week and year
            current_date = datetime.today()
            current_week = current_date.isocalendar()[1]
            current_year = current_date.year

            # Calculate weekly ticket totals
            weekly_ticket_data = Ticket.objects.filter(added_on__week=current_week, added_on__year=current_year,
                                                       purchased=True)
            weekly_ticket_total = sum(float(weekly_single_ticket.price) for weekly_single_ticket in weekly_ticket_data)
            ticket_weekly_chart_list = []
            ticket_weekly_chart_list.append({"date": current_date.strftime("%Y-%m-%d"), "amt": weekly_ticket_total})

            # Calculate weekly stream totals
            weekly_stream_data = VideoPayments.objects.filter(added_on__week=current_week, added_on__year=current_year)
            weekly_stream_total = sum(float(weekly_single_stream.amount) for weekly_single_stream in weekly_stream_data)

            # get daily ticket data
            ticket_dates = Ticket.objects.order_by().values("added_on__date").distinct()
            ticket_daily_chart_list = []
            for dates in ticket_dates:
                access_date = dates["added_on__date"]

                ticket_data = Ticket.objects.filter(added_on__date=access_date, purchased=True)
                ticket_amt_inner = 0

                for ticketsingle in ticket_data:
                    ticket_amt_inner += float(ticketsingle.price)

                ticket_daily_chart_list.append({"date": access_date, "amt": ticket_amt_inner})

            # get daily stream data
            stream_dates = VideoPayments.objects.order_by().values("added_on__date").distinct()
            stream_daily_chart_list = []
            for dates in stream_dates:
                access_date = dates["added_on__date"]

                stream_data = VideoPayments.objects.filter(added_on__date=access_date)
                stream_amt_inner = 0

                for streamsingle in stream_data:
                    stream_amt_inner += float(streamsingle.amount)

                stream_daily_chart_list.append({"date": access_date, "amt": stream_amt_inner})

            # get monthly stream data
            stream_month = VideoPayments.objects.order_by().values("added_on__month", "added_on__year").distinct()
            stream_monthly_chart_list = []
            for month in stream_month:
                access_month = month["added_on__month"]
                access_year = month["added_on__year"]

                stream_data = VideoPayments.objects.filter(added_on__month=access_month, added_on__year=access_year)
                stream_month_inner = 0
                access_date = date(year=access_year, month=access_month, day=1)
                for streammonth in stream_data:
                    stream_month_inner += float(streammonth.amount)

                stream_monthly_chart_list.append({"date": access_date, "amt": stream_month_inner})

            # get monthly ticket data
            ticket_month = Ticket.objects.order_by().values("added_on__month", "added_on__year").distinct()
            ticket_monthly_chart_list = []
            for month in ticket_month:
                access_month = month["added_on__month"]
                access_year = month["added_on__year"]

                stream_data = Ticket.objects.filter(added_on__month=access_month, added_on__year=access_year, purchased=True)
                stream_month_inner = 0
                access_date = date(year=access_year, month=access_month, day=1)
                for streammonth in stream_data:
                    stream_month_inner += float(streammonth.price)

                ticket_monthly_chart_list.append({"date": access_date, "amt": stream_month_inner})

            dict_response = {
                "error": False,
                "message": "Dashboard api",
                "users": len(UserAccount.objects.filter(is_staff=0)),
                "active_streams": len(Video.objects.all()),
                "active_plays": len(Play.objects.filter(is_available=1)),
                "tickets_sold": len(Ticket.objects.filter(purchased=1)),
                "weekly_tickets": ticket_weekly_chart_list,
                "weekly_streams": [{"date": current_date.strftime("%Y-%m-%d"), "amt": weekly_stream_total}],
                "daily_tickets": ticket_daily_chart_list,
                "daily_stream": stream_daily_chart_list,
                "monthly_stream": stream_monthly_chart_list,
                "monthly_ticket": ticket_monthly_chart_list,
            }
        except Exception as e:
            dict_response = {"error": True, "message": f"Error performing task: {str(e)}"}

        return Response(dict_response)


play_list = PlayViewSet.as_view({"get": "list"})
play_create = PlayViewSet.as_view({"post": "create"})
play_update = PlayViewSet.as_view({"put": "update"})
play_destroy = PlayViewSet.as_view({"delete": "destroy"})
