from django.db import models
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class UserAccountManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, phone, password=None, user_type=None):
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        email = email.lower()

        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type,
            phone=phone
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, first_name,  last_name, phone, user_type=None, password=None):
        user = self.create_user(email, first_name, last_name, phone, user_type, password)

        user.is_superuser = True
        user.is_staff = True

        user.save(using=self._db)

        return user


class UserAccount(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    user_type = models.CharField(max_length=20, default='normal')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone', 'user_type']

    def __str__(self):
        return self.email


class Play(models.Model):
    class Theater(models.TextChoices):
        ALLIANCE_FRANCAISE = 'Alliance Francaise'
        KENYA_NATIONAL_THEATER = 'Kenya National Theater'
        NAIROBI_CINEMAS = 'Nairobi Cinemas'

    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100)
    synopsis = models.TextField()
    poster = models.ImageField(upload_to='posters/')
    infotrailer = models.FileField(upload_to='info-trailers/')
    theater = models.CharField(choices=Theater.choices, max_length=255)
    is_available = models.BooleanField(default=False)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class PlayCast(models.Model):
    id = models.AutoField(primary_key=True)
    image = models.ImageField(upload_to='play-cast-pictures/', null=True, blank=True)
    real_name = models.CharField(max_length=255, null=True, blank=True)
    cast_name = models.CharField(max_length=255, null=True, blank=True)
    play_id = models.ForeignKey(Play, on_delete=models.CASCADE)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class PlayTime(models.Model):
    id = models.AutoField(primary_key=True)
    play_id = models.ForeignKey(Play, on_delete=models.CASCADE)
    play_date = models.DateField()
    time1 = models.CharField(max_length=255, null=True, blank=True)
    time2 = models.CharField(max_length=255, null=True, blank=True)
    time3 = models.CharField(max_length=255, null=True, blank=True)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class Bogof(models.Model):
    id = models.AutoField(primary_key=True)
    play_id = models.ForeignKey(Play, on_delete=models.CASCADE)
    bogof = models.BooleanField(default=False)
    offer_day = models.DateField(null=True, blank=True)
    number_of_tickets = models.CharField(max_length=100)
    promo_code = models.CharField(max_length=100)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class OtherOffers(models.Model):
    id = models.AutoField(primary_key=True)
    play_id = models.ForeignKey(Play, on_delete=models.CASCADE)
    offers_name = models.CharField(max_length=225)
    offer_day = models.DateField(null=True, blank=True)
    promo_code = models.CharField(max_length=100)
    percentage = models.CharField(max_length=100)
    number_of_tickets = models.CharField(max_length=100)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class PurchasedTicketManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(purchased=True)


class Ticket(models.Model):
    id = models.AutoField(primary_key=True)
    seat_numbers = models.CharField(max_length=100)
    ticket_type = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    email = models.EmailField()
    qr_code = models.ImageField(upload_to='qr_codes/')
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, default=None)
    play_id = models.ForeignKey(Play, on_delete=models.CASCADE, default=None)

    # Additional fields for tracking purchase and payment status
    purchased = models.BooleanField(default=False)

    # Add a ticket_number field
    ticket_number = models.CharField(max_length=10, unique=True, default=uuid.uuid4().hex[:10].upper())

    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()
    purchased_tickets = PurchasedTicketManager()

    def __str__(self):
        return self.seat_numbers


class Payment(models.Model):
    id = models.AutoField(primary_key=True)
    ref_number = models.CharField(max_length=255)
    payment_mode = models.CharField(max_length=255)
    msisdn = models.CharField(max_length=255)
    msisdn_idnum = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE,default=None)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()

    def __str__(self):
        return f'Payment {self.payment_id} for {self.ticket.seat_numbers}'


class Video(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    synopsis = models.TextField()
    video = models.FileField(upload_to='videos/')
    trailer = models.FileField(upload_to='trailers/')
    video_poster = models.ImageField(upload_to='video_poster/')
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class VideoStream(models.Model):
    QUALITY_CHOICES = (
        ('SD', 'Standard Definition'),
        ('HD', 'High Definition'),
        ('FHD', 'Full HD'),
        ('4K', '4K Ultra HD'),
    )

    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    quality = models.CharField(max_length=50, choices=QUALITY_CHOICES)
    is_default = models.BooleanField(default=False)

    def get_cloudfront_url(self):
        # Replace 'CLOUDFRONT_DOMAIN' with CloudFront domain name
        return f'https://CLOUDFRONT_DOMAIN/{self.video.file.name}'


class VideoCast(models.Model):
    id = models.AutoField(primary_key=True)
    image = models.ImageField(upload_to='cast-pictures/', null=True, blank=True)
    real_name = models.CharField(max_length=255, null=True, blank=True)
    cast_name = models.CharField(max_length=255, null=True, blank=True)
    video_id = models.ForeignKey(Video, on_delete=models.CASCADE)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class VideoPayment(models.Model):
    id = models.AutoField(primary_key=True)
    payment_id = models.CharField(max_length=50)
    amount = models.CharField(max_length=100)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE,default=None)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()

    def __str__(self):
        return f'Payment {self.payment_id} for {self.video.title}'


class VideoPayments(models.Model):
    id = models.AutoField(primary_key=True)
    ref_number = models.CharField(max_length=255)
    payment_mode = models.CharField(max_length=255)
    msisdn = models.CharField(max_length=255)
    msisdn_idnum = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE,default=None)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class VideoAvailability(models.Model):
    id = models.AutoField(primary_key=True)
    video_id = models.ForeignKey(Video, on_delete=models.CASCADE)
    three_days = models.CharField(max_length=100)
    three_price = models.CharField(max_length=100)
    seven_days = models.CharField(max_length=100)
    seven_price = models.CharField(max_length=100)
    fourteen_days = models.CharField(max_length=100)
    fourteen_price = models.CharField(max_length=100)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


class ViewHistory(models.Model):
    id = models.AutoField(primary_key=True)
    video_id = models.ForeignKey(Video, on_delete=models.CASCADE)
    user_id = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    added_on = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()


