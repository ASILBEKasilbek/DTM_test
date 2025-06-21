from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError

# === Umumiy model (timestamplar) ===
class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# === Foydalanuvchi profili ===
class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    total_tests = models.PositiveIntegerField(default=0)
    total_score = models.FloatField(default=0)

    def __str__(self):
        return self.user.username


# === Fan ===
class Subject(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)

    def generate_unique_slug(self):
        slug = original = slugify(self.name)
        counter = 1
        while Subject.objects.filter(slug=slug).exists():
            slug = f"{original}-{counter}"
            counter += 1
        return slug

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


# === Mavzu ===
class Topic(BaseModel):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
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
        while Topic.objects.filter(slug=slug).exists():
            slug = f"{original}-{counter}"
            counter += 1
        return slug

    def __str__(self):
        return f"{self.subject.name} - {self.name}"

    class Meta:
        unique_together = ('subject', 'name')
        ordering = ['subject', 'name']


# === Savol ===
class Question(BaseModel):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    text = models.TextField()
    image = models.ImageField(upload_to='questions/', blank=True, null=True)
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Oson'), ('medium', 'O‘rtacha'), ('hard', 'Qiyin')],
        default='medium'
    )
    is_active = models.BooleanField(default=True)
    explanation = models.TextField(blank=True, help_text="To‘g‘ri javob izohi")

    def __str__(self):
        return f"{self.topic.name}: {self.text[:50]}..."

    def get_correct_option(self):
        return self.options.filter(is_correct=True).first()


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
        if self.is_correct and self.question and self.question.pk:  # Savol saqlanganligini tekshirish
            exists = AnswerOption.objects.filter(
                question=self.question,
                is_correct=True
            ).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError("Bu savolda allaqachon to‘g‘ri javob belgilangan.")
        def __str__(self):
            return f"{self.label}. {self.text} {'✅' if self.is_correct else '❌'}"

    class Meta:
        unique_together = ('question', 'label')
        ordering = ['label']


# === Test Sessiya ===
class TestSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    questions = models.ManyToManyField(Question, blank=True) 

    @property
    def duration(self):
        end_time = self.ended_at or timezone.now()
        return end_time - self.started_at

    def __str__(self):
        return f"{self.user.username} - {self.subject.name} - {self.started_at.strftime('%Y-%m-%d')}"


# === Foydalanuvchi javobi ===
class UserAnswer(BaseModel):
    test_session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(AnswerOption, on_delete=models.CASCADE)

    def clean(self):
        if self.selected_option.question != self.question:
            raise ValidationError("Tanlangan variant ushbu savolga tegishli emas.")

    def is_correct(self):
        return self.selected_option.is_correct

    def __str__(self):
        return f"{self.test_session.user.username} - {'✅' if self.is_correct() else '❌'}"

    class Meta:
        unique_together = ('test_session', 'question')


# === Test natijasi ===
class Result(BaseModel):
    test_session = models.OneToOneField(TestSession, on_delete=models.CASCADE)
    correct_answers = models.PositiveIntegerField()
    total_questions = models.PositiveIntegerField()
    score = models.FloatField(blank=True, null=True)
    percent = models.FloatField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.total_questions:
            self.percent = round((self.correct_answers / self.total_questions) * 100, 2)
            self.score = round(self.percent, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.test_session.user.username} - {self.score} ball ({self.percent}%)"


# === Fikr-mulohaza ===
class Feedback(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"

    class Meta:
        ordering = ['-created_at']
