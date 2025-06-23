from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import Subject, Topic, Question, AnswerOption, TestSession, UserAnswer, Result, UserProfile, Feedback

# AnswerOption uchun maxsus form
class AnswerOptionInlineForm(forms.ModelForm):
    class Meta:
        model = AnswerOption
        fields = ['text', 'is_correct']  # 'label' formda ko‘rsatilmaydi


# AnswerOption uchun maxsus formset
class AnswerOptionInlineFormSet(forms.BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        labels = ['A', 'B', 'C', 'D']
        if index is not None and index < len(labels):
            form.initial['label'] = labels[index]
            form.instance.label = labels[index]  # MUHIM!

    def clean(self):
        super().clean()
        labels = set()
        correct_count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                label = form.instance.label  # << cleaned_data emas!
                if not label:
                    raise forms.ValidationError("Har bir variant uchun label (A, B, C, D) kiritilishi kerak.")
                if label in labels:
                    raise forms.ValidationError(f"Takroriy label '{label}' kiritildi.")
                labels.add(label)
                if form.cleaned_data.get('is_correct'):
                    correct_count += 1
        if len(labels) != 4:
            raise forms.ValidationError("Roppa-rosa 4 ta noyob label (A, B, C, D) kiritilishi kerak.")
        if correct_count != 1:
            raise forms.ValidationError("Faqat bitta to‘g‘ri javob bo‘lishi kerak.")

# AnswerOption uchun Inline admin
class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    form = AnswerOptionInlineForm
    formset = AnswerOptionInlineFormSet
    extra = 4
    max_num = 4
    min_num = 4
    fields = ('label', 'text', 'is_correct')
    readonly_fields = ('label',)
    can_delete = False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_deleted=False).order_by('label')

# Question admin
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [AnswerOptionInline]
    list_display = ('text_truncated', 'topic', 'difficulty', 'is_active', 'is_deleted', 'created_at')
    list_filter = ('topic__subject', 'difficulty', 'is_active', 'is_deleted')
    search_fields = ('text', 'topic__name', 'explanation')
    list_per_page = 20
    list_editable = ('is_active',)
    actions = ['restore_deleted', 'mark_as_active', 'mark_as_inactive']

    def text_truncated(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_truncated.short_description = _('Savol matni')

    def save_formset(self, request, form, formset, change):
        if formset.model == AnswerOption:
            labels = set()
            correct_count = 0
            for f in formset.forms:
                if f.cleaned_data and not f.cleaned_data.get('DELETE', False):
                    label = f.instance.label
                    if not label:
                        self.message_user(request, _("Har bir variant uchun label kiritilishi kerak!"), level='ERROR')
                        return
                    labels.add(label)
                    if f.cleaned_data.get('is_correct'):
                        correct_count += 1
            if len(labels) != 4:
                self.message_user(request, _("Roppa-rosa 4 ta noyob label kiritilishi kerak!"), level='ERROR')
                return
            if correct_count != 1:
                self.message_user(request, _("Faqat bitta to‘g‘ri javob bo‘lishi kerak!"), level='ERROR')
                return
        try:
            super().save_formset(request, form, formset, change)
        except Exception as e:
            self.message_user(request, f"Xato yuz berdi: {str(e)}", level='ERROR')
            raise

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        options = AnswerOption.objects.filter(question=obj, is_deleted=False)
        if options.count() != 4:
            self.message_user(request, _("Har bir savol uchun roppa-rosa 4 ta variant kiritilishi kerak!"), level='ERROR')
        elif options.filter(is_correct=True).count() != 1:
            self.message_user(request, _("Faqat bitta variant to‘g‘ri bo‘lishi kerak!"), level='ERROR')

    def restore_deleted(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, _("Tanlangan savollar tiklandi."))
    restore_deleted.short_description = _("O‘chirilgan savollarni tiklash")

    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, _("Tanlangan savollar faol qilindi."))
    mark_as_active.short_description = _("Savollarni faol qilish")

    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, _("Tanlangan savollar faol emas qilindi."))
    mark_as_inactive.short_description = _("Savollarni faol emas qilish")

# Subject admin
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description', 'is_deleted')
    list_filter = ('is_deleted',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    actions = ['restore_deleted']

    def restore_deleted(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, _("Tanlangan fanlar tiklandi."))
    restore_deleted.short_description = _("O‘chirilgan fanlarni tiklash")

# Topic admin
@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'slug', 'is_deleted')
    list_filter = ('subject', 'is_deleted')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    actions = ['restore_deleted']

    def restore_deleted(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, _("Tanlangan mavzular tiklandi."))
    restore_deleted.short_description = _("O‘chirilgan mavzularni tiklash")

# TestSession admin
@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'started_at', 'ended_at', 'completed', 'score', 'is_deleted')
    list_filter = ('subject', 'completed', 'is_deleted')
    search_fields = ('user__username', 'subject__name')
    list_per_page = 20
    actions = ['mark_as_completed', 'restore_deleted']

    def mark_as_completed(self, request, queryset):
        queryset.update(completed=True, ended_at=timezone.now())
        self.message_user(request, _("Tanlangan sessiyalar yakunlandi."))
    mark_as_completed.short_description = _("Sessiyalarni yakunlash")

    def restore_deleted(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, _("Tanlangan sessiyalar tiklandi."))
    restore_deleted.short_description = _("O‘chirilgan sessiyalarni tiklash")

# UserAnswer admin
@admin.register(UserAnswer)
class UserAnswerAdmin(admin.ModelAdmin):
    list_display = ('test_session', 'question', 'selected_option', 'is_correct', 'answered_at')
    list_filter = ('test_session__subject', 'is_correct')
    search_fields = ('test_session__user__username', 'question__text')
    list_per_page = 20

# Result admin
@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('test_session', 'correct_answers', 'total_questions', 'percent')
    list_filter = ('test_session__subject',)
    search_fields = ('test_session__user__username',)

# UserProfile admin
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_tests', 'total_score')
    search_fields = ('user__username', 'bio')
    list_per_page = 20

# Feedback admin
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'created_at', 'status')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'subject', 'message')
    list_editable = ('status',)
    actions = ['mark_as_resolved', 'mark_as_pending']

    def mark_as_resolved(self, request, queryset):
        queryset.update(status='resolved')
        self.message_user(request, _("Tanlangan fikr-mulohazalar hal qilingan deb belgilandi."))
    mark_as_resolved.short_description = _("Fikr-mulohazalarni hal qilingan deb belgilash")

    def mark_as_pending(self, request, queryset):
        queryset.update(status='pending')
        self.message_user(request, _("Tanlangan fikr-mulohazalar kutilmoqda deb belgilandi."))
    mark_as_pending.short_description = _("Fikr-mulohazalarni kutilmoqda deb belgilash")