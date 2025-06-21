from django.contrib import admin
from .models import Subject, Topic, Question, AnswerOption, TestSession, UserAnswer, Result, UserProfile, Feedback

# AnswerOption uchun Inline admin
class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4  # Har bir savol uchun 4 ta variant avtomatik ko‘rsatiladi
    max_num = 4  # Maksimal 4 ta variantga ruxsat
    fields = ('label', 'text', 'is_correct')
    readonly_fields = ('label',)  # Label o‘zgartirib bo‘lmaydi
    can_delete = False  # Variantlarni o‘chirishni taqiqlash

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('label')  # Variantlarni A, B, C, D tartibida ko‘rsatish

# Question admin
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerOptionInline]
    list_display = ('text', 'topic', 'difficulty', 'is_active')
    list_filter = ('topic__subject', 'difficulty', 'is_active')
    search_fields = ('text', 'topic__name')
    list_per_page = 20

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Variantlarni tekshirish va tartiblash
        options = AnswerOption.objects.filter(question=obj)
        if options.count() != 4:
            self.message_user(request, "Har bir savol uchun roppa-rosa 4 ta variant kiritilishi kerak!", level='ERROR')
        elif options.filter(is_correct=True).count() != 1:
            self.message_user(request, "Faqat bitta variant to‘g‘ri bo‘lishi kerak!", level='ERROR')

# Boshqa modellar uchun admin
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'slug')
    list_filter = ('subject',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'started_at', 'completed', 'score')
    list_filter = ('subject', 'completed')
    search_fields = ('user__username',)

@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('test_session', 'question', 'selected_option', 'is_correct')
    list_filter = ('test_session__subject',)

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('test_session', 'correct_answers', 'total_questions', 'percent')
    list_filter = ('test_session__subject',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_tests', 'total_score')
    search_fields = ('user__username',)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'created_at')
    search_fields = ('user__username', 'subject')