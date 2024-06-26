from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.utils.timezone import make_aware
from djoser.serializers import UserCreateSerializer, UserSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers

from heartstringApp.models import UserAccount, Play, PlayCast, Ticket, Payment, Video, VideoCast, \
    VideoAvailability, OtherOffers, PlayTime, VideoPayments, Seat, ViewHistory

User = get_user_model()


class UserCreateSerializer(UserCreateSerializer):
    user_type = serializers.CharField(default='normal', required=False)  # Add user_type field with default value

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'password', 'user_type')  # Include user_type in fields

    def validate(self, attrs):
        attrs = super().validate(attrs)

        user_type = attrs.get('user_type')
        if user_type not in ['normal', 'admin']:  # Make sure user_type is either 'normal' or 'admin'
            raise serializers.ValidationError("Invalid user type")

        return attrs


class CustomUserSerializer(UserSerializer):
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta(UserSerializer.Meta):
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'user_type', 'added_on', 'last_login')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        last_login = representation.get('last_login')

        if last_login:
            if isinstance(last_login, str):
                # If last_login is a string, try to parse it into a datetime object
                last_login = timezone.make_aware(timezone.datetime.fromisoformat(last_login))

            if not timezone.is_aware(last_login):
                # If it's still not aware, assume it's in the default timezone
                last_login = make_aware(last_login, timezone.get_current_timezone())

            formatted_last_login = timezone.localtime(last_login).strftime('%Y-%m-%d %H:%M:%S')
            representation['last_login'] = formatted_last_login

        return representation


class UserAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'user_type', 'added_on', 'phone')

    def update(self, instance, validated_data):
        # Allow admins to update name and phone without email uniqueness check
        if self.context['request'].user.is_staff:
            instance.first_name = validated_data.get('first_name', instance.first_name)
            instance.last_name = validated_data.get('last_name', instance.last_name)
            instance.phone = validated_data.get('phone', instance.phone)
        else:
            # For regular users, update all fields
            instance.first_name = validated_data.get('first_name', instance.first_name)
            instance.last_name = validated_data.get('last_name', instance.last_name)
            instance.email = validated_data.get('email', instance.email)
            instance.phone = validated_data.get('phone', instance.phone)

        instance.save()
        return instance


class PlaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Play
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation


class MyPlaySerializer(serializers.ModelSerializer):
    # user = UserCreateSerializer(read_only=True)

    class Meta:
        model = Play
        fields = '__all__'

    # def to_representation(self, instance):
    #     response = super().to_representation(instance)
    #     response["user"] = UserCreateSerializer(instance.user).data  # Use 'instance.user' here
    #     return response


class PlayCastSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayCast
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        response = super().to_representation(instance)
        response["play"] = PlaySerializer(instance.play_id).data
        return response, representation


class OtherOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = OtherOffers
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["play"] = PlaySerializer(instance.play_id).data
        return response


class PlayDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayTime
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["play"] = PlaySerializer(instance.play_id).data
        return response


class TicketsSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(read_only=True)
    play = PlaySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = '__all__'
        extra_kwargs = {
            'qr_code': {'required': False}  # Mark qr_code as not required
        }

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(UserAccount.objects.get(id=instance.user_id)).data
        response["play"] = PlaySerializer(instance.play_id).data
        return response


class PaymentSerializer(serializers.ModelSerializer):
    user = UserAccountSerializer(read_only=True)  # Use the UserAccountSerializer for the user field

    class Meta:
        model = Payment
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        # No need to use UserCreateSerializer or UserAccountSerializer here, just use the instance directly
        response["user"] = instance.user_id  # Assuming that user_id is the UserAccount instance
        return response


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation


class ViewHistorySerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(read_only=True)

    class Meta:
        model = ViewHistory
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation


class MyStreamSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(read_only=True)

    class Meta:
        model = Video
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        return representation


class VideoCastSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoCast
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        representation = super().to_representation(instance)
        response["video"] = VideoSerializer(instance.video_id).data
        return response, representation


class VideoAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAvailability
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["video"] = VideoSerializer(instance.video_id).data
        return response


class VideoPaymentSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(read_only=True)

    class Meta:
        model = VideoPayments
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = instance.user_id
        response["video"] = instance.video_id
        return response


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = '__all__'


class BookSeatSerializer(serializers.Serializer):
    seat_id = serializers.IntegerField()

    def validate_seat_id(self, value):
        try:
            seat = Seat.objects.get(id=value, is_booked=False)  # Use is_booked instead of status
        except Seat.DoesNotExist:
            raise serializers.ValidationError("This seat is either booked or does not exist.")
        return value