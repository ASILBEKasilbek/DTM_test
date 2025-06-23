from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

# === Umumiy model (timestamplar) ===
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

# === Foydalanuvchi profili ===
class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    total_tests = models.PositiveIntegerField(default=0)
    total_score = models.FloatField(default=0)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    def __str__(self):
        return self.user.username

    class Meta:
        indexes = [models.Index(fields=['user'])]

# === Fan ===
class Subject(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)

    def generate_unique_slug(self):
        slug = original = slugify(self.name)
        counter = 1
        while Subject.objects.filter(slug=slug, is_deleted=False).exists():
            slug = f"{original}-{counter}"
            counter += 1
        return slug

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['slug'])]

# === Mavzu ===
class Topic(BaseModel):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='topics')
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)

    def generate_unique_slug(self):
        slug = original = slugify(self.name)
        counter = 1
        while Topic.objects.filter(slug=slug, is_deleted=False).exists():
            slug = f"{original}-{counter}"
            counter += 1
        return slug

    def __str__(self):
        return f"{self.subject.name} - {self.name}"

    class Meta:
        unique_together = ('subject', 'name')
        ordering = ['subject', 'name']
        indexes = [models.Index(fields=['slug', 'subject'])]

# === Savol ===
class Question(BaseModel):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Oson'), ('medium', 'O‘rtacha'), ('hard', 'Qiyin')],
        default='medium'
    )
    is_active = models.BooleanField(default=True)
    explanation = models.TextField(blank=True, help_text="To‘g‘ri javob izohi")

    def clean(self):
        if self.pk and not self.options.filter(is_correct=True).exists():
            raise ValidationError("Savolda kamida bitta to‘g‘ri javob bo‘lishi kerak.")
        if self.pk and self.options.count() != 4:
            raise ValidationError("Savolda roppa-rosa 4 ta variant bo‘lishi kerak.")

    def __str__(self):
        return f"{self.topic.name}: {self.text[:50]}..."

    def get_correct_option(self):
        return self.options.filter(is_correct=True).first()

    def get_shuffled_options(self):
        import random
        options = list(self.options.all())
        random.shuffle(options)
        return options

    class Meta:
        indexes = [models.Index(fields=['topic', 'is_active'])]

# === Variantlar ===
class AnswerOption(BaseModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    label = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def clean(self):
        if self.is_correct and self.question_id:
            exists = AnswerOption.objects.filter(
                question_id=self.question_id,
                is_correct=True
            ).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError("Bu savolda allaqachon to‘g‘ri javob belgilangan.")

    def __str__(self):
        return f"{self.label}. {self.text} {'✅' if self.is_correct else '❌'}"

    class Meta:
        unique_together = ('question', 'label')
        ordering = ['label']
        indexes = [models.Index(fields=['question', 'label'])]

# === Test Sessiya ===
class TestSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_sessions')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='test_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    randomized_question_ids = models.JSONField(default=list, blank=True)

    @property
    def duration(self):
        end_time = self.ended_at or timezone.now()
        return end_time - self.started_at

    def calculate_score(self):
        answers = self.answers.all()
        if not answers:
            return 0.0
        correct = answers.filter(selected_option__is_correct=True).count()
        total = answers.count()
        return round((correct / total) * 100, 2) if total else 0.0

    def __str__(self):
        return f"{self.user.username} - {self.subject.name} - {self.started_at.strftime('%Y-%m-%d')}"

    class Meta:
        indexes = [models.Index(fields=['user', 'subject', 'completed'])]

# === Foydalanuvchi javobi ===
class UserAnswer(BaseModel):
    test_session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_answers')
    selected_option = models.ForeignKey(AnswerOption, on_delete=models.CASCADE)
    answered_at = models.DateTimeField(auto_now_add=True)
    is_correct = models.BooleanField(default=False)  # BU KERAK
    
    def clean(self):
        if self.selected_option.question != self.question:
            raise ValidationError("Tanlangan variant ushbu savolga tegishli emas.")

  
    def check_is_correct(self):
        return self.selected_option.is_correct


    def __str__(self):
        return f"{self.test_session.user.username} - {'✅' if self.is_correct() else '❌'}"

    class Meta:
        unique_together = ('test_session', 'question')
        indexes = [models.Index(fields=['test_session', 'question'])]

# === Test natijasi ===
class Result(BaseModel):
    test_session = models.OneToOneField(TestSession, on_delete=models.CASCADE, related_name='result')
    correct_answers = models.PositiveIntegerField()
    total_questions = models.PositiveIntegerField()
    percent = models.FloatField()

    def save(self, *args, **kwargs):
        if self.total_questions:
            self.percent = round((self.correct_answers / self.total_questions) * 100, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.test_session.user.username} - {self.percent}%"

    class Meta:
        indexes = [models.Index(fields=['test_session'])]

# === Fikr-mulohaza ===
class Feedback(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Kutilmoqda'), ('resolved', 'Hal qilingan')],
        default='pending'
    )

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]