from django.contrib.auth.hashers import make_password
from django.utils import timezone
from djoser.serializers import UserCreateSerializer, UserSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers

from heartstringApp.models import UserAccount, Play, PlayCast, Bogof, Ticket, Payment, Video, VideoCast, VideoPayment, \
    VideoAvailability, OtherOffers, PlayTime

User = get_user_model()

# class UserCreateSerializer(UserCreateSerializer):
#     class Meta(UserCreateSerializer.Meta):
#         model = User
#         fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'password')

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
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'last_login')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        last_login = representation.get('last_login')

        if last_login:
            formatted_last_login = timezone.localtime(last_login).strftime('%Y-%m-%d %H:%M:%S')
            representation['last_login'] = formatted_last_login

        return representation


class UserAccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'password')

    def update(self, instance, validated_data):
        # Update password if provided
        password = validated_data.pop('password', None)
        if password:
            instance.password = make_password(password)  # Hash the new password

        # Update other fields
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
    user = UserCreateSerializer(read_only=True)

    class Meta:
        model = Play
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(instance.user_id).data
        return response


class PlayCastSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlayCast
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        response = super().to_representation(instance)
        response["play"] = PlaySerializer(instance.play_id).data
        return response, representation


class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bogof
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["play"] = PlaySerializer(instance.play_id).data
        return response


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

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(instance.user_id).data
        response["play"] = PlaySerializer(instance.play_id).data
        return response


class PaymentSerializer(serializers.ModelSerializer):
    user = UserCreateSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(instance.user_id).data
        return response


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
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
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(instance.user_id).data
        return response


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
        model = VideoPayment
        fields = '__all__'

    def to_representation(self, instance):
        response = super().to_representation(instance)
        response["user"] = UserCreateSerializer(instance.user_id).data
        response["video"] = VideoSerializer(instance.video_id).data
        return response
